"""Core logic for the "Before you stop" MVP. No Streamlit here, so it can be tested.

Flow: the investor says in their own words why they want to stop their SIP ->
an LLM sorts the reason into one of a few categories and writes two short,
neutral lines -> a quality gate checks those lines -> the app shows options
that fit the reason (skip, lower, move date, stop, withdraw) with plain facts,
plus an optional restart reminder.

Safety design:
  * Numbers on screen are computed by code from the investor's own data, never
    by the model. Any number the model writes must be one we gave it.
  * The gate blocks fund/stock names, advice, predictions and fear/urgency words.
  * If the gate fails, or the model is unavailable, the app falls back to
    pre-written text for the category (keyword classifier when no model).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

CATEGORIES = {
    "temporary_money_need": "Needs the money for something else for a while",
    "disappointing_returns": "Returns look too small or negative",
    "outside_doubt": "Doubt from news, a video, friends or family",
    "payment_or_app_problem": "Payment failed, mandate or app issue",
    "goal_changed": "Goal reached or no longer relevant",
    "switching_funds": "Wants to move to a different fund",
    "unclear": "Reason not clear",
}

# Options shown per category, in order. Keys map to OPTION_TEXT.
OPTIONS_BY_CATEGORY = {
    "temporary_money_need": ["skip", "lower", "move_date", "stop", "withdraw"],
    "disappointing_returns": ["understand", "lower", "skip", "stop", "withdraw"],
    "outside_doubt": ["understand", "skip", "lower", "stop", "withdraw"],
    "payment_or_app_problem": ["move_date", "fix_payment", "skip", "stop"],
    "goal_changed": ["stop", "lower", "withdraw"],
    "switching_funds": ["stop", "lower", "understand"],
    "unclear": ["skip", "lower", "move_date", "stop", "withdraw"],
}

OPTION_TEXT = {
    "skip": ("Skip the next 1-3 instalments",
             "No money is taken for the months you choose. Your SIP restarts on its own afterwards, "
             "and the money already invested stays invested."),
    "lower": ("Lower the monthly amount",
              "Keep the SIP running at a smaller amount you are comfortable with. You can raise it again later."),
    "move_date": ("Move the debit date",
                  "Pick a date that falls after your income or allowance arrives, so the balance is there."),
    "fix_payment": ("Check the payment set-up",
                    "See the status of your AutoPay or mandate and the bank account it uses before deciding anything."),
    "understand": ("See what your numbers mean",
                   "A plain explanation of invested amount, current value and why early months can look flat or negative."),
    "stop": ("Stop the SIP",
             "No future instalments. The money already invested stays invested and keeps its current value; "
             "nothing is sold. You can start a new SIP any time."),
    "withdraw": ("Withdraw money",
                 "Sells units and sends money to your bank. Exit loads or tax may apply depending on the fund and how "
                 "long you held it: check the fund's scheme document or the app's help page before you do this."),
}

# Pre-written, reviewed fallback lines per category (used when the model is
# unavailable or its output fails the gate). They contain no numbers.
FALLBACK = {
    "temporary_money_need": (
        "You need the money for something else right now.",
        "Stopping is not the only choice: you can pause a few instalments or lower the amount, and the money you "
        "have already invested stays where it is either way."),
    "disappointing_returns": (
        "The returns so far look smaller than you expected.",
        "Market-linked funds move up and down, and in the first months most of the value is simply what you put in. "
        "The current value compared with your invested amount shows where you stand today."),
    "outside_doubt": (
        "Something you heard or read made you doubt the SIP.",
        "It can help to compare what you heard with your own numbers below, and with official investor education "
        "material, before deciding."),
    "payment_or_app_problem": (
        "A payment or app issue is getting in the way.",
        "This may be fixable without stopping: check the mandate status and debit date first."),
    "goal_changed": (
        "Your goal for this money has changed.",
        "You can stop new instalments without selling what you already hold, or adjust the amount to fit a new goal."),
    "switching_funds": (
        "You are thinking about moving to a different fund.",
        "Stopping this SIP does not sell what you hold here. Choosing a fund is your decision; official investor "
        "education material can help you compare."),
    "unclear": (
        "Thanks for sharing.",
        "Here are your options, with what each one does. Nothing changes until you confirm."),
}

OFFICIAL_SOURCES = [
    ("SEBI investor education", "https://investor.sebi.gov.in/"),
    ("AMFI: Mutual Funds Sahi Hai", "https://www.mutualfundssahihai.com/"),
]

# ---------------------------------------------------------------- the quality gate
FUND_WORDS = r"\b(nippon|quant|parag|parikh|ppfas|hdfc|sbi|icici|axis|mirae|motilal|kotak|tata|uti|aditya|birla|dsp|franklin|edelweiss|bandhan|canara|pgim|invesco|navi|hsbc|baroda|sundaram|whiteoak|mahindra|nifty|sensex|small ?cap|mid ?cap|large ?cap|flexi ?cap|elss|index fund|gold|stock|share|crypto|fd|fixed deposit)\b"
ADVICE_WORDS = r"\b(you should|you must|i recommend|we recommend|i suggest|we suggest|best (fund|option|choice)|better to|don'?t stop|do not stop|keep investing|stay invested|switch to|invest in|buy (now|more|this|the dip)|sell (now|everything|it all|before)|guarantee[ds]?|will (go up|recover|rise|grow|fall|crash)|sure to)\b"
URGENCY_WORDS = r"\b(hurry|last chance|miss out|don'?t miss|before it'?s too late|now or never|limited time|regret|lose everything|panic|crash(es|ing)?|urgent|immediately|act now)\b"
MAX_WORDS = 70


@dataclass
class GateResult:
    passed: bool
    reasons: list = field(default_factory=list)


def allowed_numbers(ctx: dict) -> set[str]:
    nums = set()
    for v in ctx.values():
        if isinstance(v, (int, float)):
            for s in (f"{v}", f"{abs(v)}", f"{v:,.0f}", f"{abs(v):,.0f}", f"{v:.0f}", f"{abs(v):.0f}",
                      f"{abs(v):.1f}"):
                nums.add(s.replace(",", ""))
    return nums


def gate(text: str, ctx: dict) -> GateResult:
    reasons = []
    low = text.lower()
    if re.search(FUND_WORDS, low):
        reasons.append("mentions a fund, index or product")
    if re.search(ADVICE_WORDS, low):
        reasons.append("reads as advice or a prediction")
    if re.search(URGENCY_WORDS, low):
        reasons.append("uses fear or urgency wording")
    nums = {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}
    stray = nums - allowed_numbers(ctx)
    if stray:
        reasons.append("uses numbers not in the investor's data: " + ", ".join(sorted(stray)))
    if len(text.split()) > MAX_WORDS:
        reasons.append(f"longer than {MAX_WORDS} words")
    return GateResult(not reasons, reasons)


# ---------------------------------------------------------------- non-AI classifier (fallback)
KEYWORDS = [
    ("payment_or_app_problem", r"auto ?pay|mandate|debit(ed)?|failed|bounce|otp|ecs|bank (account|issue)|app (issue|problem|not)|charged twice|insufficient"),
    ("temporary_money_need", r"need (the )?money|fees?|rent|emergency|hospital|medical|operation|loan|emi|wedding|trip|laptop|bike|job|salary (late|delayed|cut)|tight|paisa nahi|paise nahi|de nahi|afford|expenses?|stipend|pocket money"),
    ("disappointing_returns", r"returns?|loss|negative|red|minus|profit (is )?(only|so) |not growing|no growth|gained nothing|ghata|nuksan|kam (ho|hai)|less than (i|what) (invested|put)"),
    ("outside_doubt", r"news|crash|war|recession|youtube|video|friend|papa|mummy|parents|uncle|someone said|told me|instagram|influencer|tariff|election"),
    ("switching_funds", r"switch|another fund|different fund|better fund|other fund|overlap|move (my|to)"),
    ("goal_changed", r"goal|reached|bought|done saving|no longer need|don'?t need"),
]


def keyword_category(text: str) -> str:
    low = text.lower()
    for cat, pat in KEYWORDS:
        if re.search(pat, low):
            return cat
    return "unclear"


# ---------------------------------------------------------------- the model call
SYSTEM = f"""You are a calm, neutral helper inside an Indian investing app. A first-time investor
wants to stop their monthly SIP and has said why in their own words (English, Hindi or Hinglish).

Your job: understand the reason and write two short, plain lines. You are NOT an advisor.

Hard rules:
- Never recommend, rank or name any fund, stock, index, product or asset class.
- Never say what they should do, never predict markets, never promise outcomes.
- No fear, urgency or guilt (no "crash", "regret", "miss out", "hurry").
- Use only the numbers given in the investor's data, exactly as given. Prefer no numbers.
- If they ask which fund to pick or what to do, set asks_for_advice to true and say you can't advise.
- reflection: one sentence (<= 20 words) restating their reason neutrally, in English.
- explanation: <= 55 words, plain English, explaining what their situation means using their data;
  mention that options other than stopping exist only if relevant. No advice.

Categories: {json.dumps(CATEGORIES)}

Return JSON only: {{"category": one of the category keys, "confidence": 0-1,
"reflection": str, "explanation": str, "asks_for_advice": bool}}"""


@dataclass
class Assessment:
    category: str
    reflection: str
    explanation: str
    source: str            # "ai", "ai_failed_gate", "no_model"
    model: str = ""
    gate_reasons: list = field(default_factory=list)
    asks_for_advice: bool = False
    confidence: float = 0.0
    errors: list = field(default_factory=list)


def _models(client, preferred: str) -> list[str]:
    names = []
    try:
        for m in client.models.list():
            n = (m.name or "").removeprefix("models/")
            acts = getattr(m, "supported_actions", None) or []
            if "generateContent" in acts and n.startswith("gemini") and "flash" in n and not any(
                    k in n for k in ("image", "tts", "audio", "live", "embedding", "vision", "computer")):
                names.append(n)
    except Exception:
        pass

    def key(n):
        v = re.findall(r"gemini-(\d+(?:\.\d+)?)", n)
        return (0 if "lite" in n else 1, "preview" in n or "exp" in n, -float(v[0]) if v else 0, n)
    return list(dict.fromkeys([preferred] + sorted(set(names), key=key)[:3]))


def ask_model(text: str, ctx: dict, client, preferred: str = "gemini-3.8-flash-lite") -> tuple[dict, str, list]:
    from google.genai import types
    user = json.dumps({"investor_data": ctx, "reason_in_their_words": text[:800]}, ensure_ascii=False)
    errors = []
    for m in _models(client, preferred):
        for thinking in (True, False):
            try:
                cfg = dict(system_instruction=SYSTEM, temperature=0, response_mime_type="application/json",
                           max_output_tokens=600)
                if thinking:
                    cfg["thinking_config"] = (types.ThinkingConfig(thinking_budget=0) if m.startswith("gemini-2.")
                                              else types.ThinkingConfig(thinking_level="low"))
                resp = client.models.generate_content(model=m, contents=user,
                                                      config=types.GenerateContentConfig(**cfg))
                out = json.loads(resp.text)
                if isinstance(out, list):
                    out = out[0]
                return out, m, errors
            except Exception as e:
                errors.append(f"{m}: {e.__class__.__name__}: {str(e)[:120]}")
    raise RuntimeError("; ".join(errors))


def assess(text: str, ctx: dict, client=None, preferred: str = "gemini-3.8-flash-lite") -> Assessment:
    """The eval-gated pipeline. client=None means no model (non-AI fallback)."""
    if client is None:
        cat = keyword_category(text)
        r, e = FALLBACK[cat]
        return Assessment(cat, r, e, source="no_model")
    try:
        out, model, errs = ask_model(text, ctx, client, preferred)
    except Exception as e:
        cat = keyword_category(text)
        r, ex = FALLBACK[cat]
        return Assessment(cat, r, ex, source="no_model", errors=[str(e)[:400]])
    cat = out.get("category") if out.get("category") in CATEGORIES else "unclear"
    conf = float(out.get("confidence") or 0)
    refl, expl = str(out.get("reflection", "")).strip(), str(out.get("explanation", "")).strip()
    advice_q = bool(out.get("asks_for_advice"))
    g = gate(refl + " " + expl, ctx)
    reasons = list(g.reasons)
    if conf < 0.5:
        reasons.append(f"low confidence ({conf:.2f})")
    if not refl or not expl:
        reasons.append("empty output")
    if reasons:
        fr, fe = FALLBACK[cat]
        return Assessment(cat, fr, fe, source="ai_failed_gate", model=model, gate_reasons=reasons,
                          asks_for_advice=advice_q, confidence=conf, errors=errs)
    return Assessment(cat, refl, expl, source="ai", model=model, asks_for_advice=advice_q,
                      confidence=conf, errors=errs)


def context_from(invested: float, current: float, months: int, amount: float) -> dict:
    """Numbers the screen shows, computed here, never by the model."""
    change = current - invested
    pct = round(100 * change / invested, 1) if invested else 0.0
    return {"monthly_amount": int(amount), "months_invested": int(months), "invested": int(invested),
            "current_value": int(current), "change": int(change), "change_pct": pct}
