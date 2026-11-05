"""Stage 1: raw CSVs -> one clean, de-duplicated, relevance-filtered corpus.

App-store reviews of Groww are mostly about stocks, F&O, IPOs and UPI, so they
must mention SIPs / mutual funds to survive. Forum and YouTube items were
already found with SIP queries, so they only need to be long enough to say
something. The LLM later makes the final relevance call; this step only
removes what is obviously off-topic, to save cost.

    python engine/prepare.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

MF_TERMS = re.compile(
    r"\b(?:sip|sips|mutual\s*funds?|\bmf\b|mfs|nav|xirr|elss|index\s*fund|"
    r"autopay|auto\s*pay|mandate|instal+ment|step[\s-]?up|redeem|redemption|"
    r"exit\s*load|expense\s*ratio|folio|lumpsum|lump\s*sum|kisht|kist)\b",
    re.I,
)
MIN_CHARS = {"play_store": 25, "app_store": 25, "upi_app_reviews": 25, "reddit": 40, "tradingqna": 40, "youtube": 30}


MIN_DATE = "2021-01-01"  # older items describe a different market and app; drop for every source
# @handles of other users inside the text; the lookbehind leaves emails alone
MENTION = re.compile(r"(?<![\w.@])@[A-Za-z0-9_][A-Za-z0-9_.\-]*")
# TradingQ&A quoted replies start with the quoted user's name, e.g. "Bhuvan: ..."
QUOTED_NAME = re.compile(r"^[A-Z][A-Za-z_.]{1,30}:\s")


def load_raw() -> pd.DataFrame:
    frames = [pd.read_csv(f, dtype=str, encoding="utf-8").fillna("")
              for f in sorted(RAW.glob("*.csv"))]
    if not frames:
        raise SystemExit(f"No CSVs in {RAW}. Run collect/run_all.py first.")
    return pd.concat(frames, ignore_index=True)


def prepare() -> dict:
    df = load_raw()
    stats = {"raw": df.groupby("source").size().to_dict()}

    # ISO dates compare as strings; undated items are dropped too
    df = df[df["created_at"] >= MIN_DATE]
    stats["after_date_filter"] = df.groupby("source").size().to_dict()

    df["text"] = df["text"].str.strip()
    df = df[df["text"].str.len() >= df["source"].map(MIN_CHARS).fillna(30)]
    df = df.drop_duplicates("item_id")
    # Same text posted many times (copy-paste reviews, spam) -> keep one
    df["_norm"] = df["text"].str.lower().str.replace(r"\W+", " ", regex=True).str.strip()
    df = df.drop_duplicates("_norm")
    stats["after_length_and_dedupe"] = df.groupby("source").size().to_dict()

    is_store = df["source"].isin(["play_store", "app_store"])
    mentions_mf = df["text"].str.contains(MF_TERMS)
    df = df[~is_store | mentions_mf].drop(columns="_norm")
    stats["after_relevance_prefilter"] = df.groupby("source").size().to_dict()

    df["text"] = df["text"].str.replace(MENTION, "@user", regex=True)
    is_tqna = df["source"] == "tradingqna"
    df.loc[is_tqna, "text"] = df.loc[is_tqna, "text"].str.replace(QUOTED_NAME, "[user]: ", regex=True)
    df["n_chars"] = df["text"].str.len()
    df.to_csv(OUT / "corpus.csv", index=False, encoding="utf-8")
    (OUT / "prepare_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats


if __name__ == "__main__":
    print(json.dumps(prepare(), indent=2))
