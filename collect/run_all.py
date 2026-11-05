"""Run every collector, survive individual failures, write a manifest.

    python collect/run_all.py            # everything
    python collect/run_all.py reddit     # one source
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import date

import pandas as pd

from app_reviews import app_store, play_store, upi_apps
from common import RAW_DIR, write_rows
from forums import tradingqna
from reddit_arctic import collect as reddit  # Arctic Shift archive; forums.reddit (PRAW) needs Reddit API approval
from youtube import youtube

COLLECTORS = {
    "play_store": play_store,
    "app_store": app_store,
    "upi_app_reviews": upi_apps,
    "reddit": reddit,
    "tradingqna": tradingqna,
    "youtube": youtube,
}

if __name__ == "__main__":
    wanted = sys.argv[1:] or list(COLLECTORS)
    for name in wanted:
        print(f"== {name}")
        try:
            write_rows(name, COLLECTORS[name]())
        except Exception:
            print(f"!! {name} failed — continuing with the others")
            traceback.print_exc()

    manifest = {"collected_on": date.today().isoformat(), "sources": {}}
    for f in sorted(RAW_DIR.glob("*.csv")):
        df = pd.read_csv(f, dtype=str)
        manifest["sources"][f.stem] = {
            "rows": len(df),
            "date_min": df["created_at"].min() if len(df) else None,
            "date_max": df["created_at"].max() if len(df) else None,
        }
    (RAW_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
