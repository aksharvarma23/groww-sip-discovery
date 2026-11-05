"""Stage 2: label every corpus item against the codebook with Claude.

Resumable: labels are appended to a JSONL cache keyed by item_id, so a
crash or Ctrl-C loses nothing and a rerun only labels what's missing.

    python engine/label.py --estimate                 # size + token estimate, no API calls
    python engine/label.py --pilot 60                 # stratified pilot sample, for review
    python engine/label.py                            # everything (Haiku)
    python engine/label.py --ids eval/golden_ids.txt --model claude-sonnet-5-5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from codebook import FREE_FIELDS, MULTI_FIELDS, SINGLE_FIELDS, codebook_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
DEFAULT_MODEL = "claude-haiku-5-5"
BATCH = 10
MAX_CHARS = 1800  # long Reddit posts are truncated; the opening carries the story

SYSTEM = f"""You label public posts, comments and app reviews about SIP / mutual fund
investing in India for a product research study on why first-time investors stop
their SIPs. Text may be English, Hindi or Hinglish.

Rules:
1. Label ONLY what the text says. Never infer age, income, money source or who
   influenced them from tone or writing style. If it is not stated, use "unstated".
2. If the text is not about someone's own SIP / mutual fund behaviour or question
   (e.g. stock trading, IPOs, UPI payments, app crashes unrelated to SIPs,
   promotions), set voice to "other", every other single-choice field to
   "unstated" and every multi-choice field to ["none"].
3. "advising_others" posts: label the advice-giver's own experience only if they
   describe it; otherwise leave behaviour fields as unstated / none.
4. outcome = "revoked_upi_mandate" ONLY when they say they cancelled or paused
   AutoPay / the mandate in a UPI or bank app (GPay, PhonePe, Paytm, bank app).
   Cancelling inside Groww or another investing app is "cancelled_in_platform".
5. doubt_resolved: "resolved" needs explicit signs they are now settled. Do not
   assume a doubt was resolved because they kept investing.
6. evidence_quote must be copied exactly from the text (<= 25 words), or "" if
   voice is "other".
7. confidence: your probability (0-1) that your labels for this item are right.
   Use < 0.6 when the text is ambiguous, sarcastic, or too short.

{codebook_text()}
"""


def item_schema() -> dict:
    props: dict = {"id": {"type": "string"}}
    for name, d in SINGLE_FIELDS.items():
        props[name] = {"type": "string", "enum": list(d)}
    for name, d in MULTI_FIELDS.items():
        props[name] = {"type": "array", "items": {"type": "string", "enum": list(d)}}
    for name in FREE_FIELDS:
        props[name] = {"type": "string"}
    props["confidence"] = {"type": "number", "minimum": 0, "maximum": 1}
    return {"type": "object", "properties": props, "required": list(props)}


TOOL = {
    "name": "record_labels",
    "description": "Record codebook labels for every item in the batch.",
    "input_schema": {
        "type": "object",
        "properties": {"items": {"type": "array", "items": item_schema()}},
        "required": ["items"],
    },
}


def validate(lab: dict, text: str) -> dict:
    """Coerce anything outside the codebook rather than trusting it."""
    issues = []
    for name, d in SINGLE_FIELDS.items():
        if lab.get(name) not in d:
            issues.append(f"{name}={lab.get(name)!r}")
            lab[name] = "unstated" if "unstated" in d else list(d)[-1]
    for name, d in MULTI_FIELDS.items():
        vals = [v for v in (lab.get(name) or []) if v in d]
        if len(vals) != len(lab.get(name) or []):
            issues.append(f"{name} had invalid values")
        if len(vals) > 1 and "none" in vals:
            vals.remove("none")
        lab[name] = vals or ["none"]
    q = (lab.get("evidence_quote") or "").strip().strip('"')
    lab["quote_verified"] = bool(q) and q.lower() in text.lower()
    if q and not lab["quote_verified"]:
        issues.append("quote not found in text")
    try:
        lab["confidence"] = float(lab.get("confidence", 0))
    except (TypeError, ValueError):
        lab["confidence"] = 0.0
    lab["validation_issues"] = issues
    return lab


def label_batch(client, model: str, batch: pd.DataFrame) -> list[dict]:
    payload = [
        {"id": r.item_id, "source": r.source, "context": r.context_title[:120],
         "text": r.text[:MAX_CHARS]}
        for r in batch.itertuples()
    ]
    msg = client.messages.create(
        model=model,
        max_tokens=8000,
        system=SYSTEM,
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "record_labels"},
        messages=[{"role": "user", "content":
                   "Label each item. Return one entry per id.\n\n"
                   + json.dumps(payload, ensure_ascii=False)}],
    )
    out = next(b.input for b in msg.content if b.type == "tool_use")["items"]
    # The model occasionally returns the array, or its entries, as JSON strings
    if isinstance(out, str):
        out = json.loads(out)
    out = [json.loads(x) if isinstance(x, str) else x for x in out]
    if not all(isinstance(x, dict) for x in out):
        raise ValueError(f"unexpected tool output (stop_reason={msg.stop_reason})")
    texts = dict(zip(batch.item_id, batch.text))
    labelled = []
    for lab in out:
        if lab.get("id") in texts:
            lab = validate(lab, texts[lab["id"]][:MAX_CHARS])
            lab["model"] = model
            labelled.append(lab)
    usage = {"in": msg.usage.input_tokens, "out": msg.usage.output_tokens}
    return labelled, usage


def load_done(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {json.loads(l)["id"] for l in path.open(encoding="utf-8") if l.strip()}


def pick(df: pd.DataFrame, args) -> pd.DataFrame:
    if args.ids:
        ids = {l.strip() for l in Path(args.ids).read_text(encoding="utf-8").splitlines() if l.strip()}
        return df[df.item_id.isin(ids)]
    if args.pilot:
        per = max(1, args.pilot // df.source.nunique())
        return pd.concat([g.sample(min(len(g), per), random_state=7)
                          for _, g in df.groupby("source")])
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--pilot", type=int, default=0, help="stratified sample size")
    ap.add_argument("--ids", help="file of item_ids to label (e.g. golden set)")
    ap.add_argument("--estimate", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    df = pd.read_csv(PROC / "corpus.csv", dtype=str, encoding="utf-8").fillna("")
    df = pick(df, args)
    tag = args.model.replace("claude-", "").replace("/", "_")
    out_path = PROC / f"labels_{tag}.jsonl"
    todo = df[~df.item_id.isin(load_done(out_path))]

    chars = todo.text.str.slice(0, MAX_CHARS).str.len().sum()
    n_batches = -(-len(todo) // BATCH)
    est_in = int(chars / 3.2) + n_batches * (len(SYSTEM) // 3.5 + 600)
    est_out = len(todo) * 230
    print(f"items to label: {len(todo)} (of {len(df)} selected) in {n_batches} calls")
    print(f"by source: {todo.source.value_counts().to_dict()}")
    print(f"estimated tokens: ~{est_in:,.0f} in, ~{est_out:,.0f} out on {args.model}")
    print("multiply by the current per-token prices at https://docs.claude.com/en/docs/about-claude/pricing")
    if args.estimate or todo.empty:
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set.")
    import anthropic
    client = anthropic.Anthropic(max_retries=5)

    lock = threading.Lock()
    tot = {"in": 0, "out": 0, "done": 0, "failed_batches": 0}
    batches = [todo.iloc[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    with out_path.open("a", encoding="utf-8") as f, ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(label_batch, client, args.model, b): b for b in batches}
        for fut in as_completed(futs):
            try:
                labs, usage = fut.result()
            except Exception as e:  # keep going; the rerun picks it up
                with lock:
                    tot["failed_batches"] += 1
                print(f"\n  batch failed ({e.__class__.__name__}: {str(e)[:120]})")
                continue
            with lock:
                for lab in labs:
                    f.write(json.dumps(lab, ensure_ascii=False) + "\n")
                f.flush()
                tot["in"] += usage["in"]
                tot["out"] += usage["out"]
                tot["done"] += len(labs)
                print(f"  labelled {tot['done']}/{len(todo)}  tokens in {tot['in']:,} out {tot['out']:,}",
                      end="\r")
    print(f"\ndone: {tot}")
    print(f"labels -> {out_path.relative_to(ROOT)}")
    if tot["failed_batches"]:
        print("some batches failed; rerun the same command to retry only those items")


if __name__ == "__main__":
    main()
