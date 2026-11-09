# AI Evidence Log: SIP continuation for first-time investors

Case study: Growth PM, Groww. Metric: share of first-time mutual fund investors with an active SIP
(a successful instalment in the last 30 days) 12 months after their first SIP.

- Discovery engine (live): https://akshargroww-sip-discovery.streamlit.app/
- Code and data summaries: this repository
- If an app shows "This app has gone to sleep", click the wake-up button; it takes about 30 seconds.

---

## 1. Sources and volume analysed

Collected 20 Oct to 29 Oct 2026. Items before 1 Jan 2021 dropped. No usernames stored; @handles and quoted
names masked before any AI call.

| Source | How collected | Collected | After date filter | After cleaning | Sent to the LLM | About someone's own SIP |
|---|---|---|---|---|---|---|
| Play Store reviews (Groww) | google-play-scraper | 182,949 | 182,949 | 58,593 | 3,899 | 1,835 |
| App Store reviews (Groww) | Apple public RSS feed | 100 | 100 | 73 | 8 | 2 |
| GPay and PhonePe reviews mentioning SIPs | google-play-scraper + keyword filter | 56 | 56 | 51 | 51 | 21 |
| Reddit (4 Indian investing subreddits) | Arctic Shift archive, capped 25 posts + 25 comments per subreddit-month | 8,393 | 8,393 | 8,253 | 8,253 | 6,784 |
| TradingQ&A | Discourse JSON API | 4,653 | 2,758 | 2,607 | 2,607 | 998 |
| YouTube comments on SIP videos | yt-dlp | 4,160 | 3,978 | 2,321 | 2,321 | 1,155 |
| **Total** | | **200,311** | **198,234** | **71,898** | **17,139** | **10,795** |

"Sent to the LLM": app reviews kept only if they mention SIP or mutual fund terms; other sources were found
with SIP search terms. "About someone's own SIP": the LLM's relevance label (`voice` not `other`).
Reddit fetched about 220,000 posts and comments in total; the per-month cap keeps it from swamping the other
sources, preferring posts that mention stopping, pausing, losses or AutoPay.

**Primary research.** Survey (Google Form), 23 respondents, 18 of whom had started a SIP. Convenience sample
from the author's network; the author's own response is included. Counts are reported, not percentages.

## 2. How the engine works

1. **Collect** six sources into one schema (`collect/`).
2. **Clean**: date filter, de-duplication, minimum length, SIP relevance filter, masking (`engine/prepare.py`).
3. **Label** with Claude Haiku against one codebook (`engine/codebook.py`, `engine/label.py`): relevance,
   who got them started, understanding, expected return horizon, doubt triggers, whether doubt was resolved,
   what happened to the SIP, life stage, money source. Output is forced into fixed options through a JSON schema;
   anything outside the codebook is reset; every evidence quote is checked to appear word for word in the text
   (94% did). Cost for the full run: about USD 3.
4. **Map** each signal to a branch of the metric tree and rank branches by frequency x how much the product
   can change it (`engine/build_outputs.py`).
5. **Validate** against a hand-labelled golden set (below). Fields under 75% agreement are not used for numbers.
6. **Triangulate** with the survey and a close reading of first-person accounts.

## 3. Golden set: 20 items labelled by hand

Drawn at random within groups so that every source, every outcome type, Hinglish items, students, and two items
the model called off-topic appear. Labelled blind by the author (model labels hidden). Pass mark 75%.

| Field | Agreed | Used for numbers? |
|---|---|---|
| Relevance (about their own SIP or not) | 17/20 | Yes |
| Expected return horizon | 15/20 | Yes |
| Who got them started | 14/20 | Borderline: directional only |
| Voice (own experience, question, advice) | 14/20 | Borderline: directional only |
| Doubt triggers | 11/20 | No: qualitative only |
| What happened to the SIP | 9/20 | No: qualitative only |
| Understood what they hold | 9/20 | No: qualitative only |
| Doubt resolved | 8/20 | No: qualitative only |

**Where it failed.** The model over-calls stops: it labelled 13 of 20 items as a SIP being stopped, skipped,
cancelled, failing or redeemed; the human labelled 4. It caught all 4 real ones, so about 1 in 3 of its
"stop" labels is genuine. It also labels doubt "unresolved" far more often (11 vs 5).
Consequence: engine stop counts are reported as upper bounds, about 3x too high, and used only to compare
branches and segments.

**Limitations of the golden set.** One labeller, who rates confidence in their own labels at about 70%.
Twenty items gives a rough guide, not a precise error rate. Item-level comparison: `eval/golden_scored.csv`.

## 4. Where AI output was rejected or corrected

1. **A payment-gateway complaint labelled "revoked UPI mandate" (G20, Reddit).** The post is about a gateway
   charge on a new SIP, not about stopping. The model's label would have inflated the one signal our hypothesis
   most needed. Rejected; the human label (no outcome, no doubt) is used, and the revoked-mandate signal in the
   engine (15 items) is treated as unreliable.
2. **App-crash complaints labelled "cancelled" or "redeemed" (G05, G03, Play Store).** One review blames the
   app for losses and threatens to leave; another is one garbled line. The model read intent to leave as an
   actual stop. This is the main source of the 3x over-count above; Play Store stop counts are not used.
3. **"I stopped my SIP" on Reddit mostly means switching funds.** Reading 186 posts where people say they
   stopped their own SIP showed that a large share stop one SIP and start another in the same breath
   (overlap, "better" fund, direct vs regular). The engine labels these as stops. Corrected in the analysis:
   fund switches are a separate category (`switching_funds` in the MVP), and only clear exits are quoted as
   stop stories.

A fourth, smaller correction: the engine found almost no "family told me to start" (6 items before Reddit,
120 after). The survey then showed only 3 of 18 started because of family, so that link of the original
hypothesis was challenged, not confirmed.

## 5. First-person accounts read in full (secondary evidence)

Interviews could not be run in the time available. These public accounts were read in full and quoted
(paraphrased in the deck). They are public posts, not interviews.

| Source | Date | What it shows |
|---|---|---|
| YouTube comment (yt_UgyZz6PkiIk_Ym1IprJ4AaABAg) | Oct 2024 | Can't pay for 2 months, wants to restart; asks whether to choose "skip" or "cancel" |
| Play Store review (play_e10390c4) | Aug 2026 | After knee surgery, needed one month off; skipping only allowed 2+ days before the date |
| [Reddit r/personalfinanceindia](https://www.reddit.com/r/personalfinanceindia/comments/1rf1z7d/) | Feb 2026 | 28M stopped all SIPs: wanted an emergency fund; returns "not that great"; SIPs "suggested by my relative"; "I don't understand much in market" |
| [Reddit r/personalfinanceindia](https://www.reddit.com/r/personalfinanceindia/comments/1rjlzuc/) | Mar 2026 | 26M redeemed everything: family hospital bills and debts, poor market, war news |
| [Reddit r/personalfinanceindia](https://www.reddit.com/r/personalfinanceindia/comments/1co4iq3/) | May 2024 | Stopped all MFs to save for college fees |
| [Reddit r/personalfinanceindia](https://www.reddit.com/r/personalfinanceindia/comments/16l624y/) | Sep 2023 | 28M stopped SIPs to decide between investing and repaying a student loan |
| [Reddit r/mutualfunds](https://www.reddit.com/r/mutualfunds/comments/1fyxkrg/) | Oct 2024 | Paused for a personal need that then fell through |
| [Reddit r/mutualfunds](https://www.reddit.com/r/mutualfunds/comments/1haf851/) | Dec 2024 | AutoPay failed on low balance; a workaround created a duplicate SIP; cancelled in frustration |
| [Reddit r/mutualfunds](https://www.reddit.com/r/mutualfunds/comments/1gkt2g6/) | Nov 2024 | Cancelled on the app, bank still attempted the debit and charged a bounce fee |
| [Reddit r/mutualfunds](https://www.reddit.com/r/mutualfunds/comments/1ijpkvp/) | Feb 2025 | Started June, switched August, "gained nothing", "felt sad" |
| [Reddit r/mutualfunds](https://www.reddit.com/r/mutualfunds/comments/1cbup6s/very_slow_growth_in_tata_digital_fund/l1212tk/) | Apr 2024 | Stopped after "minuscule growth"; the fund later rose about 30% |
| YouTube comment (yt_UgxxPCXF38G1sSwtYe14AaABAg) | Oct 2023 | Stopped; value below amount invested after a year; asks whether to withdraw at a loss |
| YouTube comment (yt_UgwuabgjWac2Zw1wbGl4AaABAg) | Jan 2026 | ₹2,000 SIP, 6 months, still -5%: asks what to do |
| YouTube comment (yt_UgzMNmyW0mc4wXrY1fl4AaABAg) | Apr 2026 | Was about to stop; a video changed their mind (doubt resolved outside the app) |
| Play Store review (play_782d0d5a) | Feb 2024 | Changed phone number, OTP still went to the old one, so stopped the SIP |
| GPay/PhonePe review (play_e3df356d) | Sep 2026 | Withdrew SIP money for hospital expenses |
| [Reddit r/mutualfunds](https://www.reddit.com/r/mutualfunds/comments/1dslzio/) | Jul 2024 | 24, unsure about savings, often changes the SIP amount |

## 6. MVP quality evaluation

**Test set:** 20 situations (`apps/mvp_eval_cases.json`), paraphrased from the posts above and the survey, each
with the expected reason category; three are adversarial (asks for a fund tip; asks for a market prediction;
no reason given).

| Check | Result |
|---|---|
| Non-AI version (keyword rules) picks the right category | 14/20 (misses Hinglish and mixed reasons) |
| Quality gate blocks seeded bad outputs (advice, fund name, urgency, invented number) | 4/4 blocked |
| Pre-written fallback text passes its own gate | 7/7 categories |
| AI version on the 20 cases | Not completed: the Gemini free tier returned "high demand" (503) and retired-model (404) errors during the build window. The harness runs in the app's "Quality check" tab whenever a key is set. |

**Safe fallback.** When the AI is unavailable or its answer fails the gate, the app shows reviewed,
pre-written text for the reason category and says so on screen. Numbers are always computed by code.

## 7. Known limitations

- No Reddit official API (closed to self-service since Nov 2025); Reddit came from a third-party archive and is a capped sample.
- App Store data is limited to Apple's public feed (100 recent reviews).
- TradingQ&A users skew experienced; findings are reported per source.
- LLM labels are reliable only for relevance and return horizon (see section 3).
- Survey: 23 respondents, convenience sample, includes the author.
- No interviews and no MVP user tests were completed in the time available.
- The MVP's AI provider (Gemini free tier) was unavailable at submission; the app runs on its fallback.

Nothing in this project is investment advice.
