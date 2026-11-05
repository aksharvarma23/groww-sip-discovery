"""YouTube comments on Indian personal-finance videos about SIPs, via yt-dlp.

No API key. Searches each query, takes the top N videos, pulls top comments.
Comment authors are never stored.
"""
from __future__ import annotations

import yt_dlp

from common import iso, clean_text, write_rows

VIDEO_QUERIES = [
    "should I stop my SIP",
    "SIP negative returns what to do",
    "SIP for beginners India",
    "SIP stop karu ya continue",
    "SIP loss me hai kya kare",
    "mutual fund SIP mistakes beginners",
    "Groww SIP tutorial",
    "SIP pause or stop",
]


def youtube(videos_per_query: int = 6, comments_per_video: int = 300) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    search_opts = {"quiet": True, "extract_flat": True, "skip_download": True}
    comment_opts = {
        "quiet": True,
        "skip_download": True,
        "getcomments": True,
        "extractor_args": {"youtube": {
            "max_comments": [str(comments_per_video), str(comments_per_video), "30", "5"],
            "comment_sort": ["top"],
        }},
    }
    with yt_dlp.YoutubeDL(search_opts) as ydl:
        hits = []
        for q in VIDEO_QUERIES:
            res = ydl.extract_info(f"ytsearch{videos_per_query}:{q}", download=False)
            hits += [(q, e["id"]) for e in res.get("entries", []) if e and e.get("id")]
    with yt_dlp.YoutubeDL(comment_opts) as ydl:
        for q, vid in hits:
            if vid in seen:
                continue
            seen.add(vid)
            try:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
            except Exception as ex:  # members-only, age-gated, removed ...
                print(f"  skip {vid}: {ex.__class__.__name__}")
                continue
            for c in info.get("comments") or []:
                rows.append({
                    "source": "youtube",
                    "item_id": f"yt_{c['id']}",
                    "parent_id": f"yt_{vid}",
                    "created_at": iso(c.get("timestamp")),
                    "text": clean_text(c.get("text")),
                    "rating": "",
                    "likes": c.get("like_count", 0),
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "context_title": info.get("title", ""),
                    "query": q,
                })
            print(f"  youtube {len(seen)} videos, {len(rows)} comments", end="\r")
    print()
    return rows


if __name__ == "__main__":
    print("YouTube ...")
    write_rows("youtube", youtube())
