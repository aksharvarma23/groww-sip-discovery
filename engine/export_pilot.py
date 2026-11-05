"""Join pilot labels back to their text so a human can read them side by side.

    python engine/export_pilot.py                    # Haiku labels
    python engine/export_pilot.py --model claude-sonnet-5-5
Writes data/processed/pilot_review.csv
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="claude-haiku-5-5")
args = ap.parse_args()

tag = args.model.replace("claude-", "")
labs = pd.DataFrame([json.loads(l) for l in (PROC / f"labels_{tag}.jsonl").open(encoding="utf-8")
                     if l.strip()])
corpus = pd.read_csv(PROC / "corpus.csv", dtype=str, encoding="utf-8").fillna("")
df = corpus.merge(labs, left_on="item_id", right_on="id", how="inner")
for c in ["what_checked", "doubt_triggers", "resolution_sources", "other_branch_signals", "validation_issues"]:
    df[c] = df[c].apply(lambda v: "; ".join(v) if isinstance(v, list) else v)
cols = ["item_id", "source", "text", "voice", "started_by", "understanding", "return_horizon",
        "expectation_type", "check_frequency", "what_checked", "doubt_triggers", "doubt_resolved",
        "resolution_sources", "outcome", "stage", "life_stage", "money_source",
        "other_branch_signals", "evidence_quote", "quote_verified", "unmet_need",
        "confidence", "validation_issues", "url"]
out = PROC / "pilot_review.csv"
df[cols].to_csv(out, index=False, encoding="utf-8")
print(f"{len(df)} rows -> {out.relative_to(ROOT)}")
print("relevant (voice != other):", int((df.voice != "other").sum()))
print("low confidence (< 0.6):", int((df.confidence < 0.6).sum()))
print("quote not verified:", int((~df.quote_verified.astype(bool) & (df.voice != "other")).sum()))
