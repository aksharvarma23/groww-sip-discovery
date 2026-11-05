"""AI Discovery Engine: why first-time investors' SIPs stop.

Streamlit dashboard over the engine's outputs (outputs/*.json, *.csv.gz).
No AI key is needed to browse. The "Try it" tab labels new text live with
Gemini when GEMINI_API_KEY is set in Streamlit secrets.

    streamlit run apps/engine_app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
sys.path.insert(0, str(ROOT / "engine"))

st.set_page_config(page_title="SIP Discovery Engine", page_icon="🔎", layout="wide")


@st.cache_data
def load():
    summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    survey = json.loads((OUT / "survey.json").read_text(encoding="utf-8"))
    items = pd.read_csv(OUT / "items.csv.gz", dtype=str).fillna("")
    golden = pd.read_csv(OUT / "golden.csv", dtype=str).fillna("")
    return summary, survey, items, golden


S, SV, ITEMS, GOLD = load()
G = S["golden"]
NICE = {"play_store": "Play Store", "app_store": "App Store", "upi_app_reviews": "GPay / PhonePe reviews",
        "reddit": "Reddit", "tradingqna": "TradingQ&A", "youtube": "YouTube comments"}


def counts_df(d: dict, label: str, value: str = "Count") -> pd.DataFrame:
    return pd.DataFrame({label: list(d.keys()), value: list(d.values())})


READABLE = {"cash_crunch": "Money got tight", "competing_expense": "Money needed elsewhere",
            "negative_returns": "Saw a loss", "someone_comment": "Someone's comment",
            "market_news": "Market-fall news", "fund_comparison": "Other funds did better",
            "small_early_returns": "Returns too small", "debit_alert": "Debit reminder",
            "tax_confusion": "Tax confusion", "platform_distrust": "Distrust of the platform",
            "charges_concern": "Worry about charges", "mandate_setup_problem": "Mandate set-up problem",
            "insufficient_balance": "Low balance on debit date", "app_ux_problem": "Couldn't do it in the app"}


def hbar(d: dict, label: str) -> None:
    """Horizontal bars, largest first, full labels."""
    import altair as alt
    df = pd.DataFrame({label: [READABLE.get(k, k) for k in d], "Count": list(d.values())})
    chart = (alt.Chart(df).mark_bar().encode(
        x=alt.X("Count:Q"),
        y=alt.Y(f"{label}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=320)),
        tooltip=[label, "Count"]).properties(height=34 * max(len(df), 2)))
    st.altair_chart(chart, width="stretch")


st.title("AI Discovery Engine: why first-time investors' SIPs stop")
st.caption("Research prototype for a product case study on Groww. Public posts only; no usernames stored. "
           "Nothing here is investment advice.")

tabs = st.tabs(["How it works", "Sources", "Findings", "Explore evidence", "Validation", "Try it"])

# --------------------------------------------------------------------------- how it works
with tabs[0]:
    st.subheader("From public posts to ranked opportunities")
    st.graphviz_chart("""
    digraph {
      rankdir=LR; node [shape=box, style=rounded, fontname=Helvetica, fontsize=11];
      A [label="Collect\\n6 public sources\\n~196k items"];
      B [label="Clean\\ndate >= 2021, dedupe,\\nSIP keyword filter,\\nmask handles"];
      C [label="Label with an LLM\\nfixed codebook, schema-forced,\\nverbatim quote check"];
      D [label="Map to metric tree\\nsignals -> branch of\\n12-month continuation"];
      E [label="Validate\\n20-item hand-labelled\\ngolden set"];
      F [label="Triangulate\\nsurvey (n=18 with a SIP)\\n+ async interviews"];
      A -> B -> C -> D -> F; C -> E -> D;
    }""")
    st.markdown("""
**Question it answers:** where does 12-month SIP continuation break for first-time investors, and why?

1. **Collect.** Play Store, App Store, GPay/PhonePe reviews, Reddit (via the Arctic Shift archive), TradingQ&A and YouTube comments, all in one schema, authors never stored.
2. **Clean.** Drop pre-2021 items, duplicates and very short text; keep app reviews only if they mention SIPs or mutual funds; mask @handles and quoted names.
3. **Label.** Claude Haiku labels each item against one codebook (who started them, what they understood, what they expected, what triggered doubt, whether it was resolved, what happened to the SIP, segment signals). Output is forced into fixed options, and every evidence quote must appear word for word in the text.
4. **Map to the metric.** Each signal maps to a branch of the metric tree (drift, doubt resolution, progress vs expectation, mechanical failure, affordability, trust, competing needs).
5. **Validate.** A blind, hand-labelled golden set measures where the AI can be trusted. Fields that fail are not used for numbers.
6. **Triangulate.** Survey and interviews test the links public text can't show.
""")

# --------------------------------------------------------------------------- sources
with tabs[1]:
    st.subheader("What was analysed")
    f = S["funnel"]
    srcs = [s for s in NICE if s in f["raw"]]
    tbl = pd.DataFrame({
        "Source": [NICE[s] for s in srcs],
        "Collected": [f["raw"].get(s, 0) for s in srcs],
        "After date filter (2021+)": [f.get("after_date_filter", {}).get(s, 0) for s in srcs],
        "After cleaning": [f["after_length_and_dedupe"].get(s, 0) for s in srcs],
        "Sent to the LLM": [f["after_relevance_prefilter"].get(s, 0) for s in srcs],
        "About someone's own SIP": [f["relevant"].get(s, 0) for s in srcs],
    })
    tot = tbl.drop(columns="Source").sum()
    tbl.loc[len(tbl)] = ["Total", *tot.tolist()]
    st.dataframe(tbl, hide_index=True, width="stretch")
    st.markdown(f"""
- **Reddit** came from the [Arctic Shift](https://arctic-shift.photon-reddit.com) archive (Reddit closed self-service API access in Nov 2025). It is capped at 25 posts and 25 comments per subreddit per month, preferring posts that mention stopping, pausing or losses, so its share is a sample, not a census.
- **App Store** is limited by Apple's public feed (the most recent ~100 reviews).
- **Quality checks:** {S['quote_verified_share']:.0%} of evidence quotes appear verbatim in the source text; median model confidence {S['median_confidence']:.2f}.
""")

# --------------------------------------------------------------------------- findings
with tabs[2]:
    st.subheader("Where continuation breaks")
    st.info("Read with the Validation tab: on the golden set, the AI flagged 13 of 20 items as a SIP stopping; "
            f"the human labeller flagged {G['_break_precision']['human_breaks']}. Counts below are upper bounds, "
            "roughly 3x too high, and are useful for comparing branches and segments, not as rates.")
    mn = S["metric_nodes"]
    nodes = pd.DataFrame({"Branch": [v["desc"] for v in mn.values()],
                          "Break posts with this signal": [v["break_posts"] for v in mn.values()],
                          "How much the product can change it (0-1)": [v["addressability"] for v in mn.values()]})
    nodes["Opportunity score"] = (nodes["Break posts with this signal"] * nodes["How much the product can change it (0-1)"]).round(0)
    st.dataframe(nodes.sort_values("Opportunity score", ascending=False), hide_index=True, width="stretch")
    st.caption("Addressability is a product judgement set in engine/codebook.py, not a model output.")

    st.subheader("Young investors vs those working longer (public posts)")
    seg = S["segments"]
    c1, c2 = st.columns(2)
    for col, name in zip((c1, c2), ("Student / first job", "Working longer")):
        v = seg.get(name, {})
        with col:
            st.markdown(f"**{name}**: {v.get('items', 0)} posts that state the life stage, {v.get('breaks', 0)} describe a break")
            sig = {**v.get("doubt_triggers", {}), **v.get("other_signals", {})}
            top = dict(sorted(sig.items(), key=lambda kv: -kv[1])[:8])
            hbar(top, "Signal in break posts")

    st.subheader("What the survey adds (n = 18 with a SIP; counts, not percentages)")
    a, b, c = st.columns(3)
    stop_seg = SV.get("stopped_by_segment", {})
    seg_n = SV.get("segment", {})
    a.metric("Students and first-jobbers who stopped or skipped",
             f"{stop_seg.get('Student / first job', 0)} of {seg_n.get('Student / first job', 0)}")
    b.metric("Working 2+ years who stopped", f"{stop_seg.get('Working 2+ years', 0)} of {seg_n.get('Working 2+ years', 0)}")
    rp = SV.get("restart_plan", {})
    b_planned = rp.get("Yes, but I haven't got to it yet", 0)
    c.metric("Stoppers who planned to restart but haven't", f"{b_planned} of {sum(rp.values())}")
    x, y = st.columns(2)
    with x:
        st.markdown("**What made them think about stopping**")
        hbar(SV.get("doubt_triggers", {}), "Trigger")
    with y:
        st.markdown("**How the stoppers stopped**")
        hbar(SV.get("how_stopped", {}), "Route")
    st.markdown(f"""
**Reading across sources**
- Everyone who stopped had thought about stopping first; none of the {SV.get('thought_of_stopping', {}).get('Never', 0)} who never had doubts stopped.
- "Needed the money for something else" is the most common trigger in the survey, and cash crunch / competing expense are the top non-market signals in young investors' break posts.
- Most stops happen **inside the investing app** (cancel or withdraw), not by revoking AutoPay elsewhere, so the product can act at that moment.
- Nobody who doubted used the app's help section; they used Google, YouTube or did nothing.
""")

# --------------------------------------------------------------------------- explore
with tabs[3]:
    st.subheader("Browse the labelled posts")
    c1, c2, c3, c4 = st.columns(4)
    src = c1.multiselect("Source", sorted(ITEMS.source.unique()), format_func=lambda s: NICE.get(s, s))
    segf = c2.multiselect("Segment", sorted(ITEMS.segment.unique()))
    outc = c3.multiselect("Outcome", sorted(ITEMS.outcome.unique()))
    q = c4.text_input("Search text")
    df = ITEMS
    if src:
        df = df[df.source.isin(src)]
    if segf:
        df = df[df.segment.isin(segf)]
    if outc:
        df = df[df.outcome.isin(outc)]
    if q:
        df = df[df.text.str.contains(q, case=False, regex=False)]
    st.caption(f"{len(df):,} posts match. Showing up to 200.")
    show = df[["source", "created_at", "outcome", "doubt_triggers", "started_by", "segment",
               "evidence_quote", "unmet_need", "confidence", "url"]].head(200)
    st.dataframe(show, hide_index=True, width="stretch",
                 column_config={"url": st.column_config.LinkColumn("Link"),
                                "source": st.column_config.TextColumn("Source")})

# --------------------------------------------------------------------------- validation
with tabs[4]:
    st.subheader("How far to trust the AI labels")
    st.markdown("20 items, drawn at random within groups (every source, every outcome type, Hinglish, two items "
                "the model called off-topic), labelled blind by a human. Pass mark: 75% agreement.")
    rows = []
    names = {"voice": "Relevance / voice", "started_by": "Who got them started", "understanding": "Understood the fund",
             "return_horizon": "Expected return horizon", "doubt_triggers": "Doubt triggers",
             "doubt_resolved": "Doubt resolved", "outcome": "What happened to the SIP"}
    for k, label in names.items():
        v = G[k]
        rows.append({"Field": label, "Agreed": f"{v['agree']}/{v['n']}", "Share": v["share"],
                     "Used for numbers?": "Yes" if v["passes"] else "No: qualitative only",
                     "Disagreed on": ", ".join(v["disagree_ids"])})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    bp = G["_break_precision"]
    st.markdown(f"""
**Main failure: over-calling stops.** The AI said {bp['ai_breaks']} of 20 items describe a SIP being stopped, skipped,
cancelled or failing; the human said {bp['human_breaks']}. It caught all {bp['both']} real ones, but only about
1 in 3 of its "breaks" is genuine. It also marks doubt as "unresolved" far more often than the human did.

**Limitations.** One labeller, who rates their own confidence in the labels at about 70%. Twenty items gives a rough
guide, not a precise error rate.
""")
    gid = st.selectbox("Inspect an item", GOLD.gid.tolist())
    r = GOLD[GOLD.gid == gid].iloc[0]
    st.write(r.text)
    comp = pd.DataFrame({"Field": list(names.values()),
                         "AI": [r[k + "_ai"] for k in names], "Human": [r[k + "_human"] for k in names]})
    st.dataframe(comp, hide_index=True, width="stretch")
    if r.human_note:
        st.caption(f"Labeller's note: {r.human_note}")

# --------------------------------------------------------------------------- try it
with tabs[5]:
    st.subheader("Label a new comment with the engine")
    st.markdown("Paste a review, comment or post about a SIP. The engine labels it with the same codebook and runs "
                "the same checks as the batch pipeline. Please don't enter personal details: this demo uses Google's "
                "Gemini API free tier, whose inputs may be used by Google.")
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
        model = st.secrets.get("GEMINI_MODEL", "gemini-2.5-flash")
    except Exception:  # no secrets file in this deployment
        key, model = "", "gemini-2.5-flash"
    examples = ["Started a SIP in first job because a friend said so. 7 months in, profit is only 300 rupees. "
                "Need money for a course fee next month so I cancelled it, will restart later.",
                "Papa ne SIP start karwaya tha, abhi loss me hai, band kar du kya?"]
    pick = st.selectbox("Or start from an example", ["(type your own)"] + examples)
    text = st.text_area("Text", value="" if pick == "(type your own)" else pick, height=120)
    if st.button("Label it", disabled=not text.strip()):
        if not key:
            st.warning("The live demo isn't configured (no GEMINI_API_KEY in this deployment). "
                       "Browse the other tabs to see the engine's results.")
        else:
            try:
                from gemini_label import label_text
                with st.spinner("Labelling..."):
                    lab = label_text(text, key, model)
            except Exception as e:  # rate limit, timeout, network, malformed output
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    st.error("The free AI quota is used up for the moment. Try again in a minute; the other tabs still work.")
                elif "timed out" in msg.lower() or "timeout" in msg.lower():
                    st.error("The model took too long to answer. Try again; the other tabs still work.")
                else:
                    st.error(f"The model call failed ({e.__class__.__name__}). Try again in a minute.")
            else:
                checks = []
                if lab["validation_issues"]:
                    checks.append("Some labels were outside the codebook and were reset: " + "; ".join(lab["validation_issues"]))
                if not lab.get("quote_verified") and lab.get("voice") != "other":
                    checks.append("The evidence quote was not found word for word in the text.")
                if lab["confidence"] < 0.6:
                    checks.append(f"Low confidence ({lab['confidence']:.2f}): treat these labels as a guess.")
                if lab.get("outcome") in {"considering_stop", "skipped", "cancelled_in_platform",
                                          "revoked_upi_mandate", "debit_failed", "redeemed"}:
                    checks.append("On the golden set, about 1 in 3 'stop' labels was confirmed by a human. Check the text.")
                if checks:
                    st.warning("Quality checks:\n\n- " + "\n- ".join(checks))
                else:
                    st.success("Passed the quality checks.")
                show = {k: lab.get(k) for k in ["voice", "started_by", "understanding", "return_horizon",
                                                  "doubt_triggers", "doubt_resolved", "outcome", "life_stage",
                                                  "other_branch_signals", "evidence_quote", "unmet_need", "confidence"]}
                st.json(show)
