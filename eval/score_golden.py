"""Score the engine against the hand-labelled golden set.

Reads eval/golden_set.xlsx (human labels, 'Label here' tab) and the engine's
labels, writes eval/golden_scored.csv (one row per item, <field>_ai and
<field>_human) and prints agreement per field.

    python eval/score_golden.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["voice", "started_by", "understanding", "return_horizon", "t1", "t2", "doubt_resolved", "outcome", "note"]


def blank(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == ""


def main() -> None:
    ws = load_workbook(ROOT / "eval" / "golden_set.xlsx")["Label here"]
    rows = []
    for r in range(6, 26):
        rows.append({"gid": ws.cell(r, 1).value, "source": ws.cell(r, 2).value, "text": ws.cell(r, 4).value,
                     **{f: ws.cell(r, 5 + i).value for i, f in enumerate(FIELDS)}})
    h = pd.DataFrame(rows)
    ids = (ROOT / "eval" / "golden_ids.txt").read_text(encoding="utf-8").split()
    # golden_ids.txt is in the same order the items were drawn; the sheet order maps via golden_key
    key = pd.read_csv(ROOT / "eval" / "golden_key.csv", dtype=str)
    h = h.merge(key[["gid", "item_id"]], on="gid")
    assert set(h.item_id) <= set(ids)

    labs = {}
    for line in (ROOT / "data" / "processed" / "labels_haiku-5-5.jsonl").open(encoding="utf-8"):
        if line.strip():
            lab = json.loads(line)
            labs[lab["id"]] = lab

    out = []
    for _, r in h.iterrows():
        a = labs[r.item_id]
        row = {"gid": r.gid, "item_id": r.item_id, "source": r.source, "text": r.text, "human_note": r.note or ""}
        voice_h = "other" if blank(r.voice) else r.voice
        row["voice_ai"], row["voice_human"] = a["voice"], voice_h
        for f in ["started_by", "understanding", "return_horizon", "doubt_resolved", "outcome"]:
            row[f + "_ai"] = a[f]
            row[f + "_human"] = "unstated" if blank(r[f]) else r[f]
        row["doubt_triggers_ai"] = ";".join(t for t in a["doubt_triggers"] if t != "none")
        row["doubt_triggers_human"] = ";".join(sorted(t for t in [r.t1, r.t2] if not blank(t) and t != "none"))
        row["confidence_ai"] = a["confidence"]
        out.append(row)
    g = pd.DataFrame(out)
    g.to_csv(ROOT / "eval" / "golden_scored.csv", index=False)

    for f in ["voice", "started_by", "understanding", "return_horizon", "doubt_triggers", "doubt_resolved", "outcome"]:
        a, hh = g[f + "_ai"], g[f + "_human"]
        if f == "doubt_triggers":
            a = a.map(lambda s: ";".join(sorted(s.split(";"))) if s else "")
        print(f"{f:16} {int((a == hh).sum()):2}/{len(g)}")


if __name__ == "__main__":
    main()
