"""Reddit posts and comments via the Arctic Shift archive (no login).

Why this source: Reddit closed self-service API access in Nov 2025, and its
public .json endpoints return 403. Arctic Shift is a community-run Reddit
archive with a public API: https://arctic-shift.photon-reddit.com
Name it as the source in the Evidence Log; it is not run by Reddit.

How it works (behaviour checked against the live API on 24-Oct-2026):
  * Keyword search on POSTS times out on their side, so posts are listed by
    subreddit + date window and filtered here for SIP / mutual fund terms.
  * Keyword search on COMMENTS (body=SIP) needs a numeric limit (<=100,
    "auto" is refused) and often times out on a month window, so comments are
    fetched week by week with retries. It is the slow, flaky part: run posts
    first (--no-comments), then comments.
  * Both endpoints return newest first; paging walks `before` backwards.
  * "Timeout. Maybe slow down a bit" (HTTP 422) -> back off and retry.

To keep labelling balanced with the other sources, each subreddit-month keeps
at most CAP posts and CAP comments: items that mention stopping, pausing,
losses, AutoPay etc. first, then a random sample of the remaining SIP items.
Everything fetched is cached per subreddit-month and kind, so a rerun resumes
and only retries windows that failed.

    python reddit_arctic.py                  # all subreddits, 2021-01 to now
    python reddit_arctic.py --no-comments    # posts only (fast, reliable)
    python reddit_arctic.py --cap 40         # keep more per month (default 25)
Authors are never stored. Deleted / removed items are dropped.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from common import RAW_DIR, UA, clean_text, write_rows

BASE = "https://arctic-shift.photon-reddit.com/api"
SUBREDDITS = ["personalfinanceindia", "IndiaInvestments", "mutualfunds", "FIREIndia"]
START = "2021-01"
CACHE = RAW_DIR / "reddit_cache"
CACHE.mkdir(parents=True, exist_ok=True)

SIP_TERMS = re.compile(
    r"\b(?:sip|sips|mutual\s*funds?|xirr|elss|index\s*funds?|autopay|auto\s*pay|"
    r"mandate|step[\s-]?up)\b", re.I)
# Continuation signals: kept first when a month has more than CAP items.
CONT_TERMS = re.compile(
    r"\b(?:stop\w*|paus\w*|skip\w*|cancel\w*|discontinu\w*|redeem\w*|redemption|"
    r"withdr\w*|exit\w*|loss\w*|negative|in (?:the )?red|continue|worth it|"
    r"regret\w*|forg[eo]t\w*|autopay|auto\s*pay|mandate|band kar\w*|"
    r"bandh?\s*kar\w*|nuksan|ghata)\b", re.I)
GONE = {"[deleted]", "[removed]", ""}

S = requests.Session()
S.headers["User-Agent"] = UA


def _get(path: str, **params) -> list[dict] | None:
    """One API call with back-off. Returns rows, or None if it kept failing."""
    for attempt in range(6):
        try:
            r = S.get(f"{BASE}/{path}", params=params, timeout=60)
            j = r.json()
        except (requests.RequestException, ValueError):
            j, r = {"error": "network"}, None
        if j.get("data") is not None:
            time.sleep(1.5)  # be polite even on success
            return j["data"]
        time.sleep(5 * (attempt + 1))
    return None


def _months(start: str, end: date):
    y, m = map(int, start.split("-"))
    while (y, m) <= (end.year, end.month):
        nxt = (y + (m == 12), 1 if m == 12 else m + 1)
        yield f"{y:04d}-{m:02d}", f"{y:04d}-{m:02d}-01", f"{nxt[0]:04d}-{nxt[1]:02d}-01"
        y, m = nxt


def _walk(path: str, after: str, before: str, **params) -> tuple[list[dict], bool]:
    """Page backwards through a window. Returns (rows, complete?)."""
    rows, seen = [], set()
    cur_before = before
    while True:
        batch = _get(path, after=after, before=cur_before, **params)
        if batch is None:
            return rows, False
        new = [x for x in batch if x["id"] not in seen]
        if not new:
            return rows, True
        for x in new:
            seen.add(x["id"])
        rows += new
        oldest = min(int(x["created_utc"]) for x in new)
        cur_before = str(oldest)  # unix seconds are accepted for before/after
        lim = params.get("limit", 100)
        if lim != "auto" and len(batch) < int(lim):
            return rows, True


def _iso(ts) -> str:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()


def _post_row(p: dict, sub: str) -> dict | None:
    title, body = p.get("title") or "", p.get("selftext") or ""
    if body.strip() in ("[deleted]", "[removed]"):
        body = ""
    if p.get("removed_by_category") or not title:
        return None
    text = clean_text(f"{title}. {body}")
    if not SIP_TERMS.search(text):
        return None
    return {
        "source": "reddit", "item_id": f"rd_{p['id']}", "parent_id": "",
        "created_at": _iso(p["created_utc"]), "text": text, "rating": "",
        "likes": p.get("score", ""), "url": "https://www.reddit.com" + p.get("permalink", ""),
        "context_title": f"r/{sub}: {title}"[:200], "query": "arctic_shift:posts",
    }


def _comment_row(c: dict, sub: str) -> dict | None:
    body = (c.get("body") or "").strip()
    if body in GONE:
        return None
    text = clean_text(body)
    if not SIP_TERMS.search(text):
        return None
    link = (c.get("link_id") or "").replace("t3_", "")
    return {
        "source": "reddit", "item_id": f"rd_{c['id']}", "parent_id": f"rd_{link}" if link else "",
        "created_at": _iso(c["created_utc"]), "text": text, "rating": "",
        "likes": c.get("score", ""), "url": "https://www.reddit.com" + c.get("permalink", ""),
        "context_title": f"r/{sub}", "query": "arctic_shift:comments body=SIP",
    }


def _cap(rows: list[dict], cap: int, rng: random.Random) -> list[dict]:
    if len(rows) <= cap:
        return rows
    cont = [r for r in rows if CONT_TERMS.search(r["text"])]
    rest = [r for r in rows if not CONT_TERMS.search(r["text"])]
    rng.shuffle(cont)
    rng.shuffle(rest)
    return (cont + rest)[:cap]


def _weeks(after: str, before: str):
    """Split a month into four windows: 1-8, 8-15, 15-22, 22-next month."""
    y = after[:7]
    edges = [after, f"{y}-08", f"{y}-15", f"{y}-22", before]
    return list(zip(edges[:-1], edges[1:]))


def _month(kind: str, sub: str, label: str, after: str, before: str) -> dict:
    """Fetch (or load from cache) one subreddit-month of posts or comments."""
    cache = CACHE / f"{sub}_{kind}_{label}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    if kind == "posts":
        raw, ok = _walk("posts/search", after, before, subreddit=sub, limit="auto")
        rows = [r for r in (_post_row(p, sub) for p in raw) if r]
    else:
        raw, ok = [], True
        for a, b in _weeks(after, before):
            part, ok_w = _walk("comments/search", a, b, subreddit=sub, body="SIP", limit=100)
            raw += part
            ok = ok and ok_w
        rows = [r for r in (_comment_row(c, sub) for c in raw) if r]
    month = {"fetched": len(raw), "rows": rows, "complete": ok}
    if ok and label != date.today().strftime("%Y-%m"):  # never cache a half-finished month
        cache.write_text(json.dumps(month, ensure_ascii=False), encoding="utf-8")
    return month


def _add_parent_titles(rows: list[dict]) -> int:
    """Append the parent post's title to each comment's context_title, so the
    labeller sees what the comment replies to. Titles are fetched 100 ids per
    call (500 is refused) and cached; ids that fail are retried on a rerun."""
    cache = CACHE / "parent_titles.json"
    titles = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    need = sorted({r["parent_id"][3:] for r in rows if r["parent_id"]} - set(titles))
    for i in range(0, len(need), 100):
        chunk = need[i:i + 100]
        got = _get("posts/ids", ids=",".join(chunk), fields="id,title")
        if got is None:
            continue
        found = {p["id"]: (p.get("title") or "").strip() for p in got}
        titles.update({pid: found.get(pid, "") for pid in chunk})  # "" = not in the archive
    cache.write_text(json.dumps(titles, ensure_ascii=False), encoding="utf-8")
    n = 0
    for r in rows:
        title = titles.get(r["parent_id"][3:], "") if r["parent_id"] else ""
        if title and title not in GONE and title != "[deleted by user]":
            r["context_title"] = f"{r['context_title']}: {title}"[:200]
            n += 1
    return n


def collect(cap: int = 25, start: str = START, comments: bool = True) -> list[dict]:
    rng = random.Random(7)
    today = date.today()
    kinds = ["posts", "comments"] if comments else ["posts"]
    kept = []
    log = {"source": "Arctic Shift archive (https://arctic-shift.photon-reddit.com)",
           "cap_per_sub_month_per_kind": cap, "start": start, "kinds": kinds,
           "incomplete_windows": [], "per_sub": {}}
    for sub in SUBREDDITS:
        stats = {"posts_fetched": 0, "posts_sip": 0, "comments_fetched": 0, "comments_sip": 0, "kept": 0}
        for label, after, before in _months(start, today):
            line = []
            for kind in kinds:
                month = _month(kind, sub, label, after, before)
                if not month["complete"]:
                    log["incomplete_windows"].append(f"{sub} {kind} {label}")
                stats[f"{kind}_fetched"] += month["fetched"]
                stats[f"{kind}_sip"] += len(month["rows"])
                keep = _cap(month["rows"], cap, rng)
                stats["kept"] += len(keep)
                kept += keep
                line.append(f"{len(month['rows'])} SIP {kind}")
            print(f"  r/{sub} {label}: {', '.join(line)}  (kept so far {len(kept)})      ", end="\r")
        print()
        log["per_sub"][sub] = stats
    if comments:
        log["comments_with_parent_title"] = _add_parent_titles(kept)
        print(f"parent titles on {log['comments_with_parent_title']} of "
              f"{sum(1 for r in kept if r['parent_id'])} kept comments")
    (RAW_DIR / "reddit_collection_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(json.dumps(log["per_sub"], indent=2))
    if log["incomplete_windows"]:
        print(f"{len(log['incomplete_windows'])} windows incomplete; rerun the same command to retry only those")
    return kept


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=25, help="max posts and max comments per subreddit-month")
    ap.add_argument("--start", default=START, help="first month, YYYY-MM")
    ap.add_argument("--no-comments", action="store_true", help="posts only")
    a = ap.parse_args()
    write_rows("reddit", collect(a.cap, a.start, comments=not a.no_comments))
