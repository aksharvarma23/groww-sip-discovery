"""Shared helpers for the collectors.

Every collector writes rows in ONE schema so the pipeline never has to care
where an item came from. Author names / handles are never stored.
"""
from __future__ import annotations

import csv
import hashlib
import html
import re
import time
from datetime import datetime, timezone
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

FIELDS = [
    "source",        # play_store | app_store | reddit | tradingqna | youtube
    "item_id",       # stable id, prefixed with source
    "parent_id",     # thread/post/video the item belongs to ("" for top level)
    "created_at",    # ISO date (UTC)
    "text",          # the content, HTML stripped
    "rating",        # 1-5 for app reviews, "" otherwise
    "likes",         # thumbs-up / upvotes / likes where available
    "url",
    "context_title", # post title / video title / app name
    "query",         # search query that surfaced it ("" for app reviews)
]

UA = "Mozilla/5.0 (research script; SIP continuation study; contact via GitHub)"

_tag = re.compile(r"<[^>]+>")
_ws = re.compile(r"\s+")


def clean_text(s: str | None) -> str:
    if not s:
        return ""
    s = html.unescape(_tag.sub(" ", s))
    return _ws.sub(" ", s).strip()


def iso(ts) -> str:
    """Accept datetime, epoch seconds or ISO string; return YYYY-MM-DD."""
    if ts in (None, ""):
        return ""
    if isinstance(ts, datetime):
        dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    elif isinstance(ts, (int, float)):
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    else:
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            return str(ts)[:10]
    return dt.date().isoformat()


def short_hash(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:12]


def write_rows(name: str, rows: list[dict]) -> Path:
    path = RAW_DIR / f"{name}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            if r.get("text"):
                w.writerow({k: r.get(k, "") for k in FIELDS})
    print(f"  wrote {len(rows):>6} rows -> {path.relative_to(RAW_DIR.parents[1])}")
    return path


def polite_sleep(sec: float = 1.5) -> None:
    time.sleep(sec)


# Search queries shared by Reddit, TradingQ&A and YouTube. English + Hinglish,
# deliberately biased toward the *continuation* problem, not toward starting.
SEARCH_QUERIES = [
    "stopped SIP",
    "pause SIP",
    "should I stop my SIP",
    "SIP negative returns",
    "first SIP",
    "started SIP last year",
    "SIP not giving returns",
    "SIP autopay failed",
    "SIP mandate",
    "continue SIP or stop",
    "SIP beginner regret",
    "Groww SIP",
    "SIP band kar du",
    "SIP loss me hai",
]
