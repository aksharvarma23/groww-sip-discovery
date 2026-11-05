# AI Discovery Engine: why first-time investors' SIPs stop

Product case study (Groww, Growth team). Goal metric: the share of first-time
mutual fund investors who still have an active SIP 12 months after starting.

**Live dashboard:** _link added after deployment_

## What the engine does

1. **Collects** public feedback from six sources into one schema, with no usernames:
   Play Store, App Store, GPay and PhonePe reviews, Reddit (via the Arctic Shift
   archive), TradingQ&A and YouTube comments. (`collect/`)
2. **Cleans** it: 2021 onwards, de-duplicated, SIP and mutual fund relevance filter,
   @handles and quoted names masked. (`engine/prepare.py`)
3. **Labels** every item against one codebook with an LLM, forcing fixed label
   options and checking that each evidence quote appears word for word.
   (`engine/codebook.py`, `engine/label.py`)
4. **Maps** each signal to a branch of the continuation metric tree and ranks
   branches by how often they appear and how much the product can change them.
   (`engine/build_outputs.py`)
5. **Validates** the labels against a blind, hand-labelled golden set of 20 items.
   Fields below 75% agreement are not used for numbers. (`eval/`)

## Run the dashboard locally

```
pip install -r apps/requirements.txt
streamlit run apps/engine_app.py
```

The "Try it" tab labels new text live if `GEMINI_API_KEY` is set in
`.streamlit/secrets.toml`; every other tab works without a key.

## Rebuild from scratch

```
pip install -r requirements.txt
cd collect && python run_all.py && cd ..
python engine/prepare.py
python engine/label.py            # needs ANTHROPIC_API_KEY
python eval/score_golden.py
python engine/build_outputs.py
```

Raw scrapes, the full labelled corpus and survey responses are not in this
repository (size and privacy). The dashboard reads the summaries in `outputs/`.

Nothing in this project is investment advice.
