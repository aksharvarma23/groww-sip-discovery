"""The codebook: every label the engine can assign, and what it means.

Single source of truth. The LLM prompt, the JSON schema the LLM fills, the
rules baseline, the golden-set scorer and the dashboard all read from here.

Built around the working hypothesis (Step 1, agreed 20-Oct-2026):
  borrowed intent -> little understanding of what they hold -> expected early
  returns -> doubt with nowhere to resolve it -> skip/pause -> forget ->
  lapse, most likely by revoking the UPI AutoPay mandate outside Groww.
Cash flow, mandate set-up, UX and trust are kept as checks on other branches.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Single-choice fields (exactly one value)
# ---------------------------------------------------------------------------
VOICE = {
    "own_experience": "Describes their own SIP / mutual fund experience",
    "asking_question": "Asks a question about their own situation",
    "advising_others": "Advises or answers someone else",
    "other": "Anything else (generic opinion, promo, off-topic)",
}

STARTED_BY = {
    "family": "Parents / relatives told or helped them start",
    "friends_peers": "Friends, batchmates, colleagues",
    "finfluencer": "YouTube / Instagram / finfluencer content",
    "employer": "Employer, HR, office",
    "app_prompt": "The app itself (banner, notification, onboarding)",
    "self": "Their own research / decision",
    "unstated": "Not stated",
}

UNDERSTANDING = {
    "specific": "Can say what they hold (fund type, what it invests in, why)",
    "vague": "Only vague ('some mutual fund', 'whatever papa chose')",
    "confused": "Visibly misunderstands how SIPs / funds work",
    "unstated": "Cannot tell",
}

RETURN_HORIZON = {
    "months": "Expected to see meaningful returns within months",
    "one_two_years": "Expected results in 1-2 years",
    "long_term": "Expects to hold 5+ years / accepts slow start",
    "unstated": "Not stated",
}

EXPECTATION_TYPE = {
    "quick_gains": "Expected noticeable gains quickly",
    "steady_fd_like": "Expected steady, FD-like growth with no down months",
    "long_term_compounding": "Expected long-term compounding, accepts volatility",
    "goal": "Saving for a named goal",
    "tax_saving": "Started for tax saving (ELSS)",
    "habit": "Started to build a saving habit",
    "unstated": "Not stated",
}

CHECK_FREQUENCY = {
    "daily_or_more": "Checks daily or more",
    "weekly": "Checks about weekly",
    "monthly": "Checks around debit / statement time",
    "rarely": "Rarely or never checks",
    "unstated": "Not mentioned",
}

DOUBT_RESOLVED = {
    "resolved": "Had doubt and it was settled (now confident)",
    "partly": "Had doubt, somewhat reassured, still uneasy",
    "unresolved": "Had doubt and it was not settled",
    "no_doubt": "No doubt expressed",
    "unstated": "Cannot tell",
}

OUTCOME = {
    "continued": "Kept the SIP going",
    "increased": "Increased / stepped up / added a SIP",
    "considering_stop": "Thinking about stopping or pausing, has not yet",
    "skipped": "Skipped / paused instalments",
    "cancelled_in_platform": "Cancelled / stopped the SIP inside the investing app",
    "revoked_upi_mandate": "Cancelled or paused the AutoPay / UPI mandate in a UPI or bank app",
    "debit_failed": "Instalment failed without them deciding (balance, bank, mandate)",
    "redeemed": "Withdrew / redeemed the money",
    "unstated": "No outcome described",
}

STAGE = {
    "pre_start": "Has not started yet",
    "setup": "Starting / setting up the first SIP or mandate",
    "early_0_3m": "Roughly the first 3 months",
    "mid_3_12m": "Roughly 3-12 months in",
    "late_12m_plus": "More than a year in",
    "unstated": "Cannot tell",
}

LIFE_STAGE = {
    "student": "Student",
    "early_career": "First job / 0-3 years working",
    "established": "Older / more years working / family responsibilities",
    "unstated": "Not stated",
}

MONEY_SOURCE = {
    "family_money": "Parents / pocket money / family support",
    "stipend_freelance": "Stipend, internship, freelance",
    "own_salary": "Own salary",
    "savings": "Existing savings",
    "unstated": "Not stated",
}

# ---------------------------------------------------------------------------
# Multi-choice fields (all that apply; ["none"] if nothing)
# ---------------------------------------------------------------------------
WHAT_CHECKED = {
    "total_value": "Current value / total amount",
    "absolute_return": "Absolute gain or loss in rupees or %",
    "xirr": "XIRR / annualised return",
    "daily_change": "1-day change / today's movement",
    "nav_units": "NAV / units",
    "fund_vs_others": "How their fund compares with other funds",
    "none": "Nothing described",
}

DOUBT_TRIGGERS = {
    "small_early_returns": "Returns too small to notice after months of investing",
    "negative_returns": "Saw red / loss",
    "market_news": "Market fall news, crash talk",
    "someone_comment": "A friend / relative / influencer comment raised doubt",
    "debit_alert": "A debit notification / reminder made them question it",
    "fund_comparison": "Saw other funds doing better",
    "none": "No doubt trigger described",
}

RESOLUTION_SOURCES = {
    "family": "Asked family",
    "friends": "Asked friends / peers",
    "youtube_finfluencer": "YouTube / finfluencers",
    "reddit_forum": "Reddit / forums",
    "google": "Google / articles",
    "advisor": "Advisor / distributor / bank RM",
    "app_content": "Something inside the investing app",
    "nowhere": "Says they did not look anywhere / did not know whom to ask",
    "none": "Nothing described",
}

OTHER_BRANCH_SIGNALS = {
    "cash_crunch": "Money got tight / income stopped",
    "competing_expense": "Money needed for something else",
    "insufficient_balance": "Balance not there on debit date",
    "mandate_setup_problem": "Could not set up / approve the mandate or AutoPay",
    "app_ux_problem": "Could not find or do something in the app",
    "charges_concern": "Worried about charges, exit load, hidden fees",
    "platform_distrust": "Does not trust the platform",
    "tax_confusion": "Confused about tax / lock-in",
    "none": "None of these",
}

SINGLE_FIELDS = {
    "voice": VOICE,
    "started_by": STARTED_BY,
    "understanding": UNDERSTANDING,
    "return_horizon": RETURN_HORIZON,
    "expectation_type": EXPECTATION_TYPE,
    "check_frequency": CHECK_FREQUENCY,
    "doubt_resolved": DOUBT_RESOLVED,
    "outcome": OUTCOME,
    "stage": STAGE,
    "life_stage": LIFE_STAGE,
    "money_source": MONEY_SOURCE,
}
MULTI_FIELDS = {
    "what_checked": WHAT_CHECKED,
    "doubt_triggers": DOUBT_TRIGGERS,
    "resolution_sources": RESOLUTION_SOURCES,
    "other_branch_signals": OTHER_BRANCH_SIGNALS,
}
FREE_FIELDS = {
    "evidence_quote": "Shortest exact span from the text that supports the labels (<= 25 words)",
    "unmet_need": "One line, in your words, on what this person needed and did not get; '' if none",
}

# Outcomes that count as a continuation break, and the lapse routes among them
BREAK_OUTCOMES = {"considering_stop", "skipped", "cancelled_in_platform",
                  "revoked_upi_mandate", "debit_failed", "redeemed"}
LAPSE_ROUTES = ["skipped", "cancelled_in_platform", "revoked_upi_mandate", "debit_failed", "redeemed"]
CONTINUE_OUTCOMES = {"continued", "increased"}

# ---------------------------------------------------------------------------
# Metric tree (Step 1). Signals map onto the branch they erode so findings land
# directly on the decomposition. Drift is the primary branch.
# ---------------------------------------------------------------------------
METRIC_NODES = {
    "C_drift": "PRIMARY. A skipped or forgotten SIP comes back instead of lapsing",
    "B3_doubt_resolution": "When doubt hits, the investor can resolve it",
    "B1_progress_fit": "What the investor sees matches what they expected",
    "A_mechanical": "Instalments keep succeeding without anyone deciding",
    "B2_affordability": "Amount and date fit the investor's cash flow",
    "B4_trust": "The investor trusts the platform",
    "D_competing_needs": "Money is not pulled for another need",
}

SIGNAL_TO_NODE = {
    # doubt triggers
    "small_early_returns": "B1_progress_fit",
    "negative_returns": "B1_progress_fit",
    "fund_comparison": "B1_progress_fit",
    "market_news": "B3_doubt_resolution",
    "someone_comment": "B3_doubt_resolution",
    "debit_alert": "C_drift",
    # other branch signals
    "cash_crunch": "B2_affordability",
    "insufficient_balance": "B2_affordability",
    "competing_expense": "D_competing_needs",
    "mandate_setup_problem": "A_mechanical",
    "app_ux_problem": "B3_doubt_resolution",
    "tax_confusion": "B3_doubt_resolution",
    "charges_concern": "B4_trust",
    "platform_distrust": "B4_trust",
}

# How much a product team can change each node (0-1). A PM judgement call:
# edit it and the opportunity ranking re-computes.
ADDRESSABILITY = {
    "C_drift": 0.8,
    "B3_doubt_resolution": 0.8,
    "B1_progress_fit": 0.7,
    "A_mechanical": 0.9,
    "B2_affordability": 0.6,
    "B4_trust": 0.4,
    "D_competing_needs": 0.3,
}


def describe(d: dict) -> str:
    return "\n".join(f"  - {k}: {v}" for k, v in d.items())


def codebook_text() -> str:
    parts = ["SINGLE-CHOICE FIELDS (exactly one value each):"]
    for name, d in SINGLE_FIELDS.items():
        parts.append(f"\n{name}:\n{describe(d)}")
    parts.append("\n\nMULTI-CHOICE FIELDS (all that apply; [\"none\"] alone if nothing applies):")
    for name, d in MULTI_FIELDS.items():
        parts.append(f"\n{name}:\n{describe(d)}")
    parts.append("\n\nFREE-TEXT FIELDS:")
    for name, desc in FREE_FIELDS.items():
        parts.append(f"  - {name}: {desc}")
    return "\n".join(parts)
