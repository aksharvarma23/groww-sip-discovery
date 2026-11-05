"""Reddit (official API via PRAW, script-app OAuth) and TradingQ&A (Discourse JSON API).

Reddit credentials come from session environment variables only, never files:
REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD.
"""
from __future__ import annotations

import os

import requests

from common import SEARCH_QUERIES, UA, clean_text, iso, polite_sleep, write_rows

SUBREDDITS = [
    "IndiaInvestments",
    "mutualfunds",
    "personalfinanceindia",
    "IndianStreetBets",
    "FIREIndia",
    "Indian_Academia",   # students talking about money
]

S = requests.Session()
S.headers["User-Agent"] = UA


def _get(url: str, **params):
    for attempt in range(4):
        r = S.get(url, params=params, timeout=30)
        if r.status_code == 429:
            polite_sleep(10 * (attempt + 1))
            continue
        if r.status_code != 200:
            return None
        return r.json()
    return None


def _walk_comments(comments, post_id, title, url, query, out, depth=0):
    # Author is never read: only body, id, time and score.
    for c in comments:
        body = clean_text(c.body)
        if body and body not in ("[deleted]", "[removed]"):
            out.append({
                "source": "reddit",
                "item_id": f"rd_{c.id}",
                "parent_id": f"rd_{post_id}",
                "created_at": iso(c.created_utc),
                "text": body,
                "rating": "",
                "likes": c.score,
                "url": url,
                "context_title": title,
                "query": query,
            })
        if depth < 2:
            _walk_comments(c.replies, post_id, title, url, query, out, depth + 1)


def _reddit_client():
    import praw

    missing = [k for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
                           "REDDIT_USERNAME", "REDDIT_PASSWORD") if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"Set these session env vars first: {', '.join(missing)}")
    r = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        username=os.environ["REDDIT_USERNAME"],
        password=os.environ["REDDIT_PASSWORD"],
        user_agent="script:groww-sip-discovery:v1.0 (SIP continuation research)",
        check_for_async=False,
    )
    r.user.me()  # fail fast on bad credentials instead of 84 silent failures
    return r


def reddit(posts_per_query: int = 25, comments_per_post: int = 60) -> list[dict]:
    from prawcore.exceptions import PrawcoreException

    api = _reddit_client()  # PRAW paces requests to Reddit's OAuth rate limit
    rows: list[dict] = []
    seen_posts: set[str] = set()
    failures = 0
    for sub in SUBREDDITS:
        for q in SEARCH_QUERIES:
            try:
                posts = list(api.subreddit(sub).search(
                    q, sort="relevance", time_filter="all", limit=posts_per_query))
            except PrawcoreException as ex:
                failures += 1
                print(f"\n  !! r/{sub} '{q}': {ex.__class__.__name__}: {ex}")
                continue
            for p in posts:
                if p.id in seen_posts:
                    continue
                seen_posts.add(p.id)
                url = "https://www.reddit.com" + p.permalink
                title = f"r/{sub}: {p.title}"
                rows.append({
                    "source": "reddit",
                    "item_id": f"rd_{p.id}",
                    "parent_id": "",
                    "created_at": iso(p.created_utc),
                    "text": clean_text(f"{p.title}. {p.selftext or ''}"),
                    "rating": "",
                    "likes": p.score,
                    "url": url,
                    "context_title": title,
                    "query": q,
                })
                if p.num_comments == 0:
                    continue
                try:
                    p.comment_sort = "top"
                    p.comment_limit = comments_per_post
                    p.comments.replace_more(limit=0)
                    _walk_comments(p.comments, p.id, title, url, q, rows)
                except PrawcoreException as ex:
                    failures += 1
                    print(f"\n  !! comments for rd_{p.id}: {ex.__class__.__name__}")
            print(f"  reddit r/{sub} '{q}': total {len(rows)}", end="\r")
    print(f"\n  reddit request failures: {failures}")
    return rows


TQ = "https://tradingqna.com"


def tradingqna(pages: int = 3, posts_per_topic: int = 20) -> list[dict]:
    rows: list[dict] = []
    seen_topics: set[int] = set()
    for q in SEARCH_QUERIES:
        for page in range(1, pages + 1):
            data = _get(f"{TQ}/search.json", q=q, page=page)
            polite_sleep(1.5)
            if not data or not data.get("topics"):
                break
            for t in data["topics"]:
                if t["id"] in seen_topics:
                    continue
                seen_topics.add(t["id"])
                topic = _get(f"{TQ}/t/{t['id']}.json")
                polite_sleep(1.5)
                if not topic:
                    continue
                url = f"{TQ}/t/{t.get('slug', '')}/{t['id']}"
                for i, p in enumerate(topic["post_stream"]["posts"][:posts_per_topic]):
                    rows.append({
                        "source": "tradingqna",
                        "item_id": f"tq_{p['id']}",
                        "parent_id": "" if i == 0 else f"tq_t{t['id']}",
                        "created_at": iso(p.get("created_at")),
                        "text": clean_text(p.get("cooked")),
                        "rating": "",
                        "likes": p.get("reads", ""),
                        "url": url,
                        "context_title": t.get("title", ""),
                        "query": q,
                    })
        print(f"  tradingqna '{q}': total {len(rows)}", end="\r")
    print()
    return rows


if __name__ == "__main__":
    print("Reddit ...")
    write_rows("reddit", reddit())
    print("TradingQ&A ...")
    write_rows("tradingqna", tradingqna())
