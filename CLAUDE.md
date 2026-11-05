# Groww SIP continuation — discovery engine

PM fellowship assignment. Goal metric: % of first-time mutual fund investors on
Groww with an active SIP (a successful instalment in the last 30 days) 12 months
after their first SIP. This repo is Part 1, the AI discovery engine: it collects
public feedback, labels it against a codebook with Claude, and quantifies where
continuation breaks.

## How we work: the user decides, step by step

The user wants to be involved in every decision. **Stop at each checkpoint below,
report, and wait for the user before continuing.** Never change
`engine/codebook.py` (labels, metric tree, addressability weights) without the
user's explicit agreement; it encodes decisions they made.

Working hypothesis (agreed, to be tested, not assumed): students and young grads
start a SIP because family told them to, don't understand what they hold, expect
visible returns early, hit doubt they can't resolve, skip, forget, and the SIP
lapses, most likely by revoking the UPI AutoPay mandate in GPay/PhonePe outside
Groww. Cash flow, mandate set-up, UX and trust are tracked as checks.

## Layout

- `collect/` one collector per source -> `data/raw/<source>.csv` (one shared schema, no author names)
- `engine/codebook.py` labels, metric tree, addressability — single source of truth
- `engine/prepare.py` raw -> `data/processed/corpus.csv` (dedupe, length, SIP/MF relevance prefilter)
- `engine/label.py` Claude labelling, resumable JSONL cache in `data/processed/labels_<model>.jsonl`
- `engine/export_pilot.py` pilot labels joined to text for human review

## Step 3 runbook

1. Setup
   ```
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Collect. Run sources one at a time so one failure doesn't hide the others:
   ```
   cd collect
   python run_all.py play_store
   python run_all.py app_store
   python run_all.py upi_app_reviews
   python run_all.py reddit
   python run_all.py tradingqna
   python run_all.py youtube
   cd ..
   ```
   Reddit and YouTube are slow on purpose (rate limits); expect 20-60 minutes
   each. If Reddit returns 403/429 repeatedly, stop and report — don't add
   logins or workarounds without asking. If a source fails, report the error
   and continue with the others.
3. `python engine/prepare.py`
4. `python engine/label.py --estimate`

**CHECKPOINT A.** Report to the user: rows per source at each stage (from
`data/raw/manifest.json` and `data/processed/prepare_stats.json`), date ranges,
the token estimate, and the cost at current prices from
https://docs.claude.com/en/docs/about-claude/pricing. Wait.

5. After the user approves: `export ANTHROPIC_API_KEY=...` (the user supplies
   it; never write it to a file or commit it), then
   ```
   python engine/label.py --pilot 60
   python engine/export_pilot.py
   ```

**CHECKPOINT B.** Tell the user the pilot is ready. They will upload
`data/processed/pilot_review.csv`, `corpus.csv`, `prepare_stats.json` and
`data/raw/manifest.json` to their Claude chat to review the labels before the
full run. Do not run the full labelling until they say so.

## Rules

- Never store or print author names, handles, account numbers or PAN.
- Don't commit `.env`, `.streamlit/secrets.toml` or any API key.
- Don't "fix" a low count by widening filters on your own; report it.
