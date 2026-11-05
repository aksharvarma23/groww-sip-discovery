"""Stage 3: turn the labelled corpus, golden set and survey into the small files
the dashboard reads (outputs/). Run after label.py and after scoring the golden set.

    python engine/build_outputs.py

Writes:
  outputs/items.csv.gz     relevant items with their labels (text trimmed, no authors)
  outputs/summary.json     funnel, per-source counts, metric-tree counts, segment view
  outputs/golden.csv       golden set: human vs AI labels per field
  outputs/survey.json      survey aggregates (counts only; responses never published)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from codebook import (BREAK_OUTCOMES, METRIC_NODES, SIGNAL_TO_NODE,  # noqa: E402
                      ADDRESSABILITY)

ROOT = Path(__file__).resolve().parents[1]
PROC, RAW, OUT = ROOT / "data" / "processed", ROOT / "data" / "raw", ROOT / "outputs"
OUT.mkdir(exist_ok=True)

GOLDEN_FIELDS = ["voice", "started_by", "understanding", "return_horizon",
                 "doubt_triggers", "doubt_resolved", "outcome"]
PASS_MARK = 0.75


def load_labelled() -> pd.DataFrame:
    c = pd.read_csv(PROC / "corpus.csv", dtype=str, encoding="utf-8").fillna("")
    labs = [json.loads(l) for l in (PROC / "labels_haiku-5-5.jsonl").open(encoding="utf-8") if l.strip()]
    L = pd.DataFrame(labs).drop_duplicates("id", keep="last")
    d = c.merge(L, left_on="item_id", right_on="id", how="inner")
    d["segment"] = d["life_stage"].map({"student": "Student / first job",
                                        "early_career": "Student / first job",
                                        "established": "Working longer"}).fillna("Not stated")
    d["is_break"] = d["outcome"].isin(BREAK_OUTCOMES)
    return d


def golden_table() -> tuple[pd.DataFrame, dict]:
    """eval/golden_scored.csv has one row per item: gid, item_id, source, text,
    <field>_ai and <field>_human for each golden field (triggers as ';'-joined)."""
    g = pd.read_csv(ROOT / "eval" / "golden_scored.csv", dtype=str).fillna("")
    stats = {}
    for f in GOLDEN_FIELDS:
        a, h = g[f + "_ai"], g[f + "_human"]
        if f == "doubt_triggers":
            norm = lambda s: ";".join(sorted(x for x in s.split(";") if x and x != "none"))
            a, h = a.map(norm), h.map(norm)
        agree = int((a == h).sum())
        stats[f] = {"agree": agree, "n": len(g), "share": round(agree / len(g), 2),
                    "passes": agree / len(g) >= PASS_MARK,
                    "disagree_ids": list(g.gid[a != h])}
    ab = g.outcome_ai.isin(BREAK_OUTCOMES)
    hb = g.outcome_human.isin(BREAK_OUTCOMES)
    stats["_break_precision"] = {"ai_breaks": int(ab.sum()), "human_breaks": int(hb.sum()),
                                 "both": int((ab & hb).sum())}
    return g, stats


def survey_summary() -> dict:
    p = ROOT / "survey" / "responses.csv"
    if not p.exists():
        return {}
    df = pd.read_csv(p, dtype=str).fillna("")
    df.columns = ['ts', 'consent', 'ever', 'first_mf', 'when', 'app', 'age', 'doing', 'money', 'regular',
                  'who', 'explain', 'expect', 'check', 'look', 'thought', 'why_doubt', 'did_next',
                  'cleared', 'status', 'how_stop', 'restart', 'why_fail', 'fix', 'how_skip', 'unsure']
    s = df[df.ever == "Yes"].copy()
    seg = {"Studying": "Student / first job",
           "Studying, with a stipend or part-time income": "Student / first job",
           "In my first job (0-2 years)": "Student / first job",
           "Working for more than 2 years": "Working 2+ years"}
    s["segment"] = s.doing.map(seg).fillna("Other")
    s["stopped"] = s.status.ne("Still running: money goes in every month")

    def multi(col, opts):
        out = {}
        for o in opts:
            out[o] = int(s[col].str.contains(re.escape(o), regex=True).sum())
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    return {
        "respondents": len(df), "with_sip": len(s),
        "segment": s.segment.value_counts().to_dict(),
        "stopped_by_segment": s.groupby("segment").stopped.sum().astype(int).to_dict(),
        "status": s.status.value_counts().to_dict(),
        "who": s.who.value_counts().to_dict(),
        "explain": s.explain.value_counts().to_dict(),
        "thought_of_stopping": s.thought.value_counts().to_dict(),
        "never_doubted_and_stopped": int(((s.thought == "Never") & s.stopped).sum()),
        "doubt_triggers": multi("why_doubt", ["I needed the money for something else", "The profit looked too small",
                                              "News about the market falling", "It was showing a loss",
                                              "The 'money will be debited' message", "Something someone said to me"]),
        "what_next": multi("did_next", ["Searched on Google", "Nothing, I didn't look into it",
                                        "Watched YouTube videos", "Asked friends", "Read Reddit or forums",
                                        "Asked family", "Used the app's help section"]),
        "how_stopped": multi("how_stop", ["Cancelled the SIP in the investing app", "Withdrew the money",
                                          "Turned off AutoPay or the mandate in GPay, PhonePe or my bank app",
                                          "Don't remember"]),
        "restart_plan": s.restart[s.restart != ""].value_counts().to_dict(),
    }


def main() -> None:
    d = load_labelled()
    rel = d[d.voice != "other"].copy()

    # ---- items for the explorer ----
    keep = ["item_id", "source", "created_at", "url", "context_title", "text", "voice", "started_by",
            "understanding", "return_horizon", "expectation_type", "check_frequency", "doubt_triggers",
            "doubt_resolved", "resolution_sources", "outcome", "stage", "life_stage", "money_source",
            "other_branch_signals", "evidence_quote", "quote_verified", "unmet_need", "confidence",
            "segment", "is_break"]
    items = rel[keep].copy()
    items["text"] = items.text.str.slice(0, 700)
    for col in ["doubt_triggers", "resolution_sources", "other_branch_signals"]:
        items[col] = items[col].map(lambda v: ";".join(v) if isinstance(v, list) else v)
    items.to_csv(OUT / "items.csv.gz", index=False, compression="gzip")

    # ---- metric tree: signals per node, among break posts ----
    brk = rel[rel.is_break]
    node_counts = {k: 0 for k in METRIC_NODES}
    for _, r in brk.iterrows():
        hit = set()
        for sig in list(r.doubt_triggers) + list(r.other_branch_signals):
            if sig in SIGNAL_TO_NODE:
                hit.add(SIGNAL_TO_NODE[sig])
        if r.outcome in ("skipped",):
            hit.add("C_drift")
        if r.outcome == "debit_failed":
            hit.add("A_mechanical")
        for n in hit:
            node_counts[n] += 1

    def multi_counts(df, col):
        return pd.Series([x for v in df[col] for x in v if x != "none"]).value_counts().to_dict()

    seg_view = {}
    for seg, g in rel[rel.segment != "Not stated"].groupby("segment"):
        b = g[g.is_break]
        seg_view[seg] = {"items": len(g), "breaks": len(b),
                         "outcomes": b.outcome.value_counts().to_dict(),
                         "doubt_triggers": multi_counts(b, "doubt_triggers"),
                         "other_signals": multi_counts(b, "other_branch_signals"),
                         "started_by": g.started_by[g.started_by != "unstated"].value_counts().to_dict()}

    g, gstats = golden_table()
    g.to_csv(OUT / "golden.csv", index=False)

    stats = json.loads((PROC / "prepare_stats.json").read_text(encoding="utf-8"))
    manifest = json.loads((RAW / "manifest.json").read_text(encoding="utf-8"))
    rlog = json.loads((RAW / "reddit_collection_log.json").read_text(encoding="utf-8"))
    summary = {
        "funnel": {**stats,
                   "labelled": d.groupby("source").size().to_dict(),
                   "relevant": rel.groupby("source").size().to_dict()},
        "manifest": manifest, "reddit_log": rlog,
        "outcomes_by_source": pd.crosstab(rel.source, rel.outcome).to_dict(orient="index"),
        "started_by": rel.started_by.value_counts().to_dict(),
        "metric_nodes": {k: {"desc": METRIC_NODES[k], "break_posts": node_counts[k],
                             "addressability": ADDRESSABILITY[k]} for k in METRIC_NODES},
        "segments": seg_view,
        "golden": gstats,
        "quote_verified_share": round(float(rel.quote_verified.astype(bool).mean()), 3),
        "median_confidence": float(rel.confidence.astype(float).median()),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=int), encoding="utf-8")
    (OUT / "survey.json").write_text(json.dumps(survey_summary(), indent=2), encoding="utf-8")
    print(f"items: {len(items)} | golden: {len(g)} | outputs -> {OUT}")


if __name__ == "__main__":
    main()
