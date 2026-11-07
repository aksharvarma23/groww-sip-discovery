"""MVP: "Before you stop", a calm check-in when a first-time investor goes to stop their SIP.

Concept prototype for a product case study. Not affiliated with Groww; nothing
here changes any real investment. Not investment advice.

    streamlit run apps/mvp_app.py
Secrets (optional): GEMINI_API_KEY, GEMINI_MODEL (default gemini-3.8-flash-lite)
"""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

import pandas as pd
import streamlit as st

import mvp_core as core

HERE = Path(__file__).resolve().parent
st.set_page_config(page_title="Before you stop: SIP check-in", page_icon="🌱", layout="centered")


# ---------------------------------------------------------------- model client
def get_client():
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
        model = st.secrets.get("GEMINI_MODEL", "gemini-3.8-flash-lite")
    except Exception:
        key, model = "", "gemini-3.8-flash-lite"
    if not key:
        return None, model
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key, http_options=types.HttpOptions(
        timeout=30_000, retry_options=types.HttpRetryOptions(attempts=1)))
    return client, model


CLIENT, MODEL = get_client()


def log(event: str, **props):
    st.session_state.setdefault("events", []).append(
        {"time": dt.datetime.now().strftime("%H:%M:%S"), "event": event, **props})


# ---------------------------------------------------------------- header
st.title("Before you stop")
st.caption("A calm check-in when someone goes to stop their SIP. Concept prototype for a product case study; "
           "not affiliated with Groww, and nothing here changes a real investment.")
st.warning("**Not investment advice.** This tool never recommends funds, predicts markets or tells you what to do. "
           "It explains your options so you can decide.", icon="ℹ️")

tab_flow, tab_eval, tab_about = st.tabs(["Try the flow", "Quality check", "How it works"])

# ---------------------------------------------------------------- sidebar: the investor's SIP
with st.sidebar:
    st.subheader("Your SIP (sample data)")
    st.caption("Change these to try different situations.")
    amount = st.number_input("Monthly amount (₹)", 100, 100000, 2000, step=100)
    months = st.number_input("Months invested", 1, 60, 7)
    invested = amount * months
    current = st.number_input("Current value (₹)", 0, 10_000_000, int(invested * 0.95), step=100)
    ctx = core.context_from(invested, current, months, amount)

# ---------------------------------------------------------------- the flow
with tab_flow:
    stage = st.session_state.get("stage", "card")

    def card():
        c1, c2, c3 = st.columns(3)
        c1.metric("Invested", f"₹{ctx['invested']:,}")
        c2.metric("Current value", f"₹{ctx['current_value']:,}", f"{ctx['change_pct']:+.1f}%")
        c3.metric("Monthly", f"₹{ctx['monthly_amount']:,}")

    if stage == "card":
        st.subheader("Your monthly SIP")
        card()
        st.caption(f"{ctx['months_invested']} instalments so far.")
        if st.button("Stop SIP", type="secondary"):
            st.session_state.stage = "ask"
            log("stop_tapped", months=ctx["months_invested"], change_pct=ctx["change_pct"])
            st.rerun()

    elif stage == "ask":
        st.subheader("Before you stop, what's making you want to?")
        st.caption("Optional. Say it in your own words, in English or Hindi. This helps us show the options that fit.")
        examples = ["I need money for my course fee next month",
                    "7 months and profit is only 300 rupees",
                    "News says the market will crash",
                    "Paise 2 mahine nahi de paunga, baad me start karunga"]
        pick = st.radio("Examples", ["(write my own)"] + examples, index=0, label_visibility="collapsed")
        text = st.text_area("Your reason", value="" if pick == "(write my own)" else pick, height=90,
                            placeholder="e.g. need the money for something else for a couple of months")
        c1, c2 = st.columns([1, 1])
        if c1.button("Show my options", type="primary", disabled=not text.strip()):
            with st.spinner("Understanding your reason..."):
                a = core.assess(text, ctx, CLIENT, MODEL)
            st.session_state.assessment = a
            st.session_state.stage = "options"
            log("reason_submitted", category=a.category, source=a.source, gate_failed=bool(a.gate_reasons))
            st.rerun()
        if c2.button("Skip this and stop"):
            st.session_state.assessment = core.Assessment("unclear", *core.FALLBACK["unclear"], source="skipped")
            st.session_state.stage = "options"
            st.session_state.preselect = "stop"
            log("checkin_skipped")
            st.rerun()

    elif stage == "options":
        a: core.Assessment = st.session_state.assessment
        st.subheader(a.reflection)
        st.write(a.explanation)
        badge = {"ai": f"AI-written · passed all quality checks · {a.model}",
                 "ai_failed_gate": "Standard text shown · the AI's answer failed a quality check",
                 "no_model": "Standard text shown · AI unavailable, reason matched by keywords",
                 "skipped": "No reason given"}[a.source]
        st.caption(badge)
        if a.gate_reasons:
            with st.expander("Why the AI text was replaced"):
                st.write("; ".join(a.gate_reasons))
        if a.asks_for_advice:
            st.info("We can't recommend funds or predict markets. For independent information: "
                    + " · ".join(f"[{n}]({u})" for n, u in core.OFFICIAL_SOURCES))
        card()

        opts = core.OPTIONS_BY_CATEGORY[a.category]
        pre = st.session_state.pop("preselect", None)
        idx = opts.index(pre) if pre in opts else 0
        choice = st.radio("Your options", opts, index=idx, format_func=lambda k: core.OPTION_TEXT[k][0])
        st.write(core.OPTION_TEXT[choice][1])

        detail = {}
        if choice == "skip":
            detail["months"] = st.select_slider("Skip how many instalments?", [1, 2, 3], 2)
            restart = dt.date.today() + dt.timedelta(days=30 * (detail["months"] + 1))
            st.caption(f"Your SIP would restart automatically around {restart:%d %b %Y}.")
        elif choice == "lower":
            detail["new_amount"] = st.slider("New monthly amount (₹)", 100, int(ctx["monthly_amount"]),
                                             max(100, int(ctx["monthly_amount"]) // 2), step=100)
        elif choice == "move_date":
            detail["day"] = st.slider("Debit on day of the month", 1, 28, 10)
        elif choice == "understand":
            st.markdown(f"""
- **Invested:** ₹{ctx['invested']:,} over {ctx['months_invested']} months.
- **Current value:** ₹{ctx['current_value']:,}, which is {ctx['change_pct']:+.1f}% compared with what you put in.
- In the first months most of the value is simply the money you added, so gains or losses look small or flat.
- Values of market-linked funds go up and down; today's number is a snapshot, not a final result.
""")
        elif choice == "stop":
            if st.checkbox("Remind me to think about restarting"):
                detail["remind_on"] = str(st.date_input("Remind me on",
                                                        dt.date.today() + dt.timedelta(days=60)))
        elif choice == "withdraw":
            st.caption("Official information: " + " · ".join(f"[{n}]({u})" for n, u in core.OFFICIAL_SOURCES))

        if st.button("Confirm", type="primary"):
            log("option_confirmed", option=choice, category=a.category, **detail)
            st.session_state.stage = "done"
            st.session_state.done = (choice, detail)
            st.rerun()
        if st.button("Back"):
            st.session_state.stage = "card"
            st.rerun()

    elif stage == "done":
        choice, detail = st.session_state.done
        st.success(f"Done: {core.OPTION_TEXT[choice][0].lower()}. (Prototype: nothing real was changed.)")
        if detail.get("remind_on"):
            st.write(f"We'll remind you on {detail['remind_on']}. You can turn this off any time.")
        if st.button("Start again"):
            for k in ("stage", "assessment", "done"):
                st.session_state.pop(k, None)
            st.rerun()

    with st.expander("Analytics events from this session"):
        ev = st.session_state.get("events", [])
        st.dataframe(pd.DataFrame(ev) if ev else pd.DataFrame(columns=["time", "event"]), hide_index=True)

# ---------------------------------------------------------------- eval
with tab_eval:
    st.subheader("Quality check against the test set")
    cases = json.loads((HERE / "mvp_eval_cases.json").read_text(encoding="utf-8"))
    st.markdown(f"""
{len(cases)} situations written from real public posts and survey answers (paraphrased), each with the
category a careful human would choose. Three of them try to make the tool give advice or predictions.
For each case we record: did the AI pick the right category, did its text pass the quality gate, and did it
flag requests for advice. The non-AI version (keyword matching) is scored on the same set for comparison.
""")
    base = sum(core.keyword_category(c["text"]) == c["expected"] for c in cases)
    st.metric("Non-AI keyword version: correct category", f"{base}/{len(cases)}")
    if CLIENT is None:
        st.info("The AI isn't configured in this deployment, so only the non-AI score is shown.")
    elif st.button(f"Run the {len(cases)} test cases with the AI (about 1-2 minutes)"):
        rows, bar = [], st.progress(0.0)
        for i, c in enumerate(cases):
            a = core.assess(c["text"], ctx, CLIENT, MODEL)
            rows.append({"id": c["id"], "text": c["text"], "expected": c["expected"], "AI category": a.category,
                         "correct": a.category == c["expected"], "text source": a.source,
                         "gate issues": "; ".join(a.gate_reasons),
                         "advice request flagged": (a.asks_for_advice if c.get("must_flag_advice") else None)})
            bar.progress((i + 1) / len(cases))
            time.sleep(1.5)  # stay inside free-tier rate limits
        st.session_state.eval_rows = rows
    rows = st.session_state.get("eval_rows")
    if rows:
        df = pd.DataFrame(rows)
        ai_ran = df["text source"].isin(["ai", "ai_failed_gate"])
        c1, c2, c3 = st.columns(3)
        c1.metric("AI: correct category", f"{int(df.correct.sum())}/{len(df)}")
        c2.metric("AI text passed the gate", f"{int((df['text source'] == 'ai').sum())}/{int(ai_ran.sum())}")
        adv = df[df["advice request flagged"].notna()]
        c3.metric("Advice requests flagged", f"{int(adv['advice request flagged'].sum())}/{len(adv)}")
        if (~ai_ran).any():
            st.warning(f"{int((~ai_ran).sum())} case(s) fell back to the non-AI version because the model "
                       "was unavailable; their category came from keywords.")
        st.dataframe(df, hide_index=True)
        st.download_button("Download results (CSV)", df.to_csv(index=False), "mvp_eval_results.csv")

# ---------------------------------------------------------------- about
with tab_about:
    st.subheader("Why this exists")
    st.markdown("""
**The problem.** In our research, young first-time investors (students and people in their first job) mostly
stop a SIP for a reason they see as *temporary*: money needed for something else, or a disappointing early
number. They stop it completely, intending to come back, and most don't (5 of the 7 survey respondents who stopped
planned to restart and hadn't). Some in-between options, like skipping an instalment or changing the amount,
already exist, but they aren't put in front of people at the moment they decide to stop, and doubts get resolved on YouTube or Google rather than with the investor's own numbers.

**What this does.** When someone taps *Stop SIP*, it asks why in their own words, then shows the options that
fit that reason (skip a few months, lower the amount, move the date, stop, withdraw) with plain facts about
each, and offers a restart reminder. Stopping always stays one tap away.

**Where AI earns its place.** People describe the reason in their own words, often in Hinglish and with mixed
reasons ("paise 2 mahine nahi de paunga, baad me start karunga"). A drop-down or keyword rules miss many of
these (the keyword version gets 14 of 20 test cases right). AI reads the reason and writes a short explanation
grounded in the investor's own numbers.

**Safety.**
1. Numbers on screen are computed by code, never by the model; any number the model writes must be one it was given.
2. A quality gate blocks fund or product names, advice, predictions, and fear or urgency wording, and checks length.
3. If the AI's answer fails the gate, or the AI is unavailable, pre-written text for that reason is shown instead,
   and the screen says so.
4. Requests for fund tips or market predictions are declined, with links to official investor education.
5. No fear, FOMO or urgency, and no extra steps to stop: "Skip this and stop" is always there.

AI: Google Gemini API (free tier). Please don't type personal details.
""")
