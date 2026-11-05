"""Play Store + App Store reviews for Groww.

Play Store: google-play-scraper, newest first, paged until the date cutoff.
App Store: Apple's public RSS feed (10 pages x 50 = max ~500 most recent).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import requests
from google_play_scraper import Sort, reviews

from common import UA, clean_text, iso, polite_sleep, write_rows

PLAY_ID = "com.nextbillion.groww"
APPLE_ID = "1404871703"


# UPI apps: where an AutoPay mandate is most likely revoked. Only reviews that
# mention SIPs / mutual funds / Groww are kept; the rest is about payments.
UPI_APPS = {
    "com.google.android.apps.nbu.paisa.user": "Google Pay",
    "com.phonepe.app": "PhonePe",
}
UPI_KEEP = re.compile(r"\b(?:sip|sips|mutual\s*funds?|groww|\bmf\b|nav|amc|"
                      r"investment|invest)\b", re.I)


def _play(app_id: str, source: str, title: str, since: str, max_items: int,
          keep=None) -> list[dict]:
    cutoff = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
    rows: list[dict] = []
    for lang in ("en", "hi"):
        token, fetched = None, 0
        while fetched < max_items:
            batch, token = reviews(
                app_id, lang=lang, country="in", sort=Sort.NEWEST,
                count=200, continuation_token=token,
            )
            if not batch:
                break
            fetched += len(batch)
            stop = False
            for r in batch:
                at = r["at"].replace(tzinfo=timezone.utc)
                if at < cutoff:
                    stop = True
                    continue
                text = clean_text(r["content"])
                if keep is not None and not keep.search(text):
                    continue
                rows.append({
                    "source": source,
                    "item_id": f"play_{r['reviewId']}",
                    "parent_id": "",
                    "created_at": iso(at),
                    "text": text,
                    "rating": r["score"],
                    "likes": r.get("thumbsUpCount", 0),
                    "url": f"https://play.google.com/store/apps/details?id={app_id}",
                    "context_title": title,
                    "query": f"lang={lang}",
                })
            print(f"  {title}[{lang}] fetched {fetched}, kept {len(rows)}", end="\r")
            if stop or token is None:
                break
            polite_sleep(0.5)
        print()
    # en and hi feeds overlap; dedupe on id
    seen, out = set(), []
    for r in rows:
        if r["item_id"] not in seen:
            seen.add(r["item_id"])
            out.append(r)
    return out


def play_store(since: str = "2024-01-01", max_items: int = 60000) -> list[dict]:
    return _play(PLAY_ID, "play_store", "Groww (Play Store)", since, max_items)


def upi_apps(since: str = "2024-06-01", max_items: int = 40000) -> list[dict]:
    """GPay + PhonePe reviews that mention SIPs / mutual funds. Low yield by
    design: most of their reviews are about payments."""
    rows: list[dict] = []
    for app_id, name in UPI_APPS.items():
        rows += _play(app_id, "upi_app_reviews", f"{name} (Play Store)",
                      since, max_items, keep=UPI_KEEP)
    return rows


def app_store() -> list[dict]:
    rows: list[dict] = []
    for page in range(1, 11):
        url = (f"https://itunes.apple.com/in/rss/customerreviews/page={page}"
               f"/id={APPLE_ID}/sortby=mostrecent/json")
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        if resp.status_code != 200:
            break
        entries = resp.json().get("feed", {}).get("entry", [])
        if isinstance(entries, dict):
            entries = [entries]
        got = 0
        for e in entries:
            if "im:rating" not in e:  # first entry on page 1 is the app itself
                continue
            got += 1
            rows.append({
                "source": "app_store",
                "item_id": f"ios_{e['id']['label']}",
                "parent_id": "",
                "created_at": iso(e.get("updated", {}).get("label")),
                "text": clean_text(f"{e['title']['label']}. {e['content']['label']}"),
                "rating": e["im:rating"]["label"],
                "likes": e.get("im:voteSum", {}).get("label", ""),
                "url": f"https://apps.apple.com/in/app/id{APPLE_ID}",
                "context_title": "Groww (App Store)",
                "query": "",
            })
        if got == 0:
            break
        polite_sleep(1)
    return rows


if __name__ == "__main__":
    print("Play Store ...")
    write_rows("play_store", play_store())
    print("App Store ...")
    write_rows("app_store", app_store())
    print("GPay + PhonePe ...")
    write_rows("upi_app_reviews", upi_apps())
