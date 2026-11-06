# Plan: Step E trial run on 300 social-media texts

> On approval this file is copied to `tasks/todo.md`.
> Scope now: build the trial, run it, review it, refine the prompt if needed. Aliases (D.2), the full run and the ticker mapping are later gates, started only when you say so.

## Why

Every one of the 22,273 social-media texts must be labelled with the companies it refers to, blind to the trades, so the shifted-date test in the methodology has a label wherever it lands. One LLM call per text does the labelling. The trial checks the prompt on 300 texts before any money is spent on the rest.

**How a call works.** One request = the prompt from `LLM_Prompt.md` + one social-media text. The model has no memory between requests. It never sees another text, the trades, or an earlier answer.

## Files (folder `5) TweetsDB`, created now)

| file | what it is |
|---|---|
| `LLM_SocialMediaScript.py` | the one script |
| `LLM_Prompt.md` | the prompt and the JSON schema, with a version number at the top |
| `SocialMedia.db` | the one database, two tables |

Nothing else: no raw-output folder, no sample-id file, no spreadsheet, no helper module.

## The two tables

**`SocialMedia`**, one row per social-media text (22,273). The columns of `SocialMediaPosts.json` as they are (`ID`, `created_at`, `url`, `text`, `User`, `is_retweet`, `is_quote`, `has_media`, `links`, `platform`) plus:

| column | meaning |
|---|---|
| `trial_sample` | 1 for the 300 trial texts, else 0 |
| `llm_answer` | the model's raw JSON answer, kept for audit |
| `llm_model` | the model version string the API returned, e.g. `gpt-5-mini-2025-08-07` |
| `llm_prompt_version` | the version number from `LLM_Prompt.md` used for this answer |
| `llm_status` | `ok`, or the error |

**`SocialMediaKeywords`**, one row per company reference found:

| column | meaning |
|---|---|
| `ID` | the social-media text it came from |
| `mention_text` | the exact words in the text |
| `entity_type` | `company` / `product_or_brand` / `person` / `sector_or_policy` / `country` |
| `canonical_company` | the model's best legal name for the listed company, or empty for indirect |
| `ticker_guess` | the model's best ticker, or empty |
| `reference_type` | `direct` / `brand` / `executive` / `indirect` |
| `sentiment` | `positive` / `neutral` / `negative`, toward that company |
| `confidence` | `high` / `medium` / `low` |

A text with no company has no row here. The later mapping step adds `ticker` and `match_method` columns to this table. Step F reads only this table.

## What the script does

```
python LLM_SocialMediaScript.py            # trial: the 300 texts, Standard endpoint
python LLM_SocialMediaScript.py --show 30  # print 30 trial texts with their keywords, no calls
```

1. Creates `SocialMedia.db` and loads the JSON into `SocialMedia` if the table is empty. Marks 300 trial texts once (seed 20261102: 200 drawn at random from all texts, 100 drawn at random from texts that contain a company name from `company.db` or a `$TICKER`, so the trial has enough company cases to judge). The marks are never redrawn.
2. Reads `LLM_Prompt.md`.
3. For each trial text without an answer: one call to gpt-5-mini (`reasoning_effort="low"`, strict JSON schema, `max_completion_tokens=3000`, no temperature). Writes `llm_answer`, `llm_model`, `llm_prompt_version`, `llm_status` on the `SocialMedia` row and one `SocialMediaKeywords` row per company found. A rerun after a prompt change clears the 300 trial answers first and redoes them. A rerun after a crash continues where it stopped.
4. Prints: texts done, how many had at least one company, counts per `reference_type` and `sentiment`, average tokens per call, cost of this trial, and the projected cost of all 22,273 at Batch prices.

The full run is the `--all` flag: Global Standard with 24 concurrent workers (Azure has no Global Batch type for gpt-5-mini), back-off on 429/5xx, resumable, progress every 500 texts.

`.env` gains `AZURE_ENDPOINT`, `AZURE_API_VERSION`, `AZURE_DEPLOYMENT_STANDARD`, `AZURE_DEPLOYMENT_BATCH`. Libraries: `openai`, `python-dotenv` (installed).

## Prompt and schema (`LLM_Prompt.md`, version 1)

Call input: `Post:\n<text>` only. No date, account, platform or links.

Schema (strict: every field required, `additionalProperties: false`, null via `anyOf`):

```json
{"name": "company_references", "strict": true, "schema": {
  "type": "object", "additionalProperties": false, "required": ["references"],
  "properties": {"references": {"type": "array", "items": {
    "type": "object", "additionalProperties": false,
    "required": ["mention_text", "entity_type", "canonical_company", "ticker_guess",
                 "reference_type", "sentiment", "confidence"],
    "properties": {
      "mention_text":      {"type": "string"},
      "entity_type":       {"type": "string", "enum": ["company", "product_or_brand", "person", "sector_or_policy", "country"]},
      "canonical_company": {"anyOf": [{"type": "string"}, {"type": "null"}]},
      "ticker_guess":      {"anyOf": [{"type": "string"}, {"type": "null"}]},
      "reference_type":    {"type": "string", "enum": ["direct", "brand", "executive", "indirect"]},
      "sentiment":         {"type": "string", "enum": ["positive", "neutral", "negative"]},
      "confidence":        {"type": "string", "enum": ["high", "medium", "low"]}
    }}}}}}
```

System prompt:

```
You label social-media posts for a study of which publicly listed companies a post refers to.
You read ONE post and return every reference to a company. You have no list of companies;
use your own knowledge. Return an empty list when the post refers to no company.

A reference is one of:
- direct:    the company's name or stock ticker appears (incl. "$TSLA", "Nvidia", "Fox News",
             an account handle that belongs to the company such as "@nvidia").
- brand:     a product, brand, service, or subsidiary that belongs to exactly one listed company
             ("iPhone" -> Apple, "Instagram" -> Meta Platforms, "Truth Social" -> Trump Media &
             Technology Group).
- executive: a named person, mentioned in connection with the company or their role in it
             ("Elon Musk said Tesla will..."). A person mentioned in another capacity
             (Musk as DOGE head, a CEO quoted on politics unrelated to the firm) is NOT a reference.
- indirect:  a sector, industry, policy or country statement that affects a set of companies
             without naming one ("tariffs on steel", "Big Pharma", "the chip industry").
             For indirect: canonical_company = null, ticker_guess = null; mention_text
             carries the theme.

Rules:
1. mention_text is the exact span copied from the post.
2. canonical_company is the current legal name of the LISTED PARENT in English
   ("Alphabet Inc." for Google/YouTube, "Meta Platforms, Inc." for Instagram,
   "Warner Bros. Discovery, Inc." for CNN, "Comcast Corporation" for NBC/MSNBC until the
   2025 spin-off, then "Versant"). Private, state-owned or unlisted entities keep their own
   name with ticker_guess = null (SpaceX, Cargill, X Corp, Washington Post).
3. ticker_guess is the primary U.S. listing ticker, upper case, no "$" (TSLA, BRK-B, GOOG).
   null if unlisted or unsure.
4. Governments, agencies, parties, universities, sports teams, NGOs and people acting as
   politicians are not companies. Countries count only as indirect references, and only
   when the statement is about trade, investment or industry, not diplomacy or war.
5. One row per distinct company per post, even if named several times. If the same
   company appears as a name and as a brand, return one row with the strongest type
   (direct > brand > executive).
6. sentiment is the stance of the post toward THAT company, not the mood of the post:
   praise, endorsement, good news, deals announced with pride -> positive;
   attacks, blame, threats, "fake news", bad news -> negative;
   factual mention, list of attendees, neutral citation -> neutral.
7. "RT @user:" and "QT @user:" prefixes mark reposts; label the full text as it stands.
   The handle itself is a reference only if it is a company account.
8. confidence: high = name or ticker explicit and unambiguous; medium = brand or executive
   mapping you are sure of; low = guess, ambiguous nickname, or unclear which company.
```

(The word "post" inside the prompt is for the model and means a social-media post; it does not appear in any table or column name.)

## Trial and refinement

1. Run the trial (about USD 0.30).
2. I read all 300 results and report: counts, 20–30 examples, what went wrong and how often, and whether it is good enough.
3. If not: I change the prompt, bump the version number in `LLM_Prompt.md`, rerun the 300. The trial rows are overwritten. Expected 2–4 passes, each announced before it runs.
4. You accept. The prompt is frozen at that version. The 300 trial texts stay marked and are excluded from the Step G validation samples.

## Cost

Third-party price trackers (no first-party Azure rate card found): gpt-5-mini Standard USD 0.25 / 1M input, 2.00 / 1M output; Batch half. With ≈ 1,500 prompt tokens per call, ≈ 1.8M tokens of text in total, ≈ 50 answer and ≈ 300 reasoning tokens per call:

| run | calls | cost |
|---|---|---|
| trial, per pass (Standard) | 300 | ≈ 0.3 |
| all texts (Batch) | 22,273 | ≈ 12 (≈ 28 if reasoning averages 1,000 tokens) |
| aliases (Batch) | 1,629 | ≈ 1.2 |
| self-agreement rerun, Step G (Batch) | 500 | ≈ 0.3 |

The trial prints the measured averages and the projected total. Nothing larger runs without your go-ahead.

## Gates

| gate | what |
|---|---|
| **1, done 2026-11-03** | `.env` entries; `LLM_Prompt.md` v1; the script; `SocialMedia.db` built (22,273 texts, 300 trial); model string confirmed `gpt-5-mini-2025-08-07`; trial run three times (v1, v2, v3), each reviewed. v3 (numeric sentiment, relevance, confidence; Elon = Tesla): 293/300 labelled, 7 blocked by Azure's content filter; 67 texts with a reference; 117 rows (47 direct, 11 brand, 6 executive, 53 indirect). Cost USD 0.21 per pass; projected full run USD 7.9 at Batch prices. Script renamed to `LLM_SocialMediaScript.py`. Hold-out check 2026-11-03: a second, disjoint 300-text sample (`trial_sample = 2`, seed 20261103, `--sample 2`) run once with v3 unchanged: 298/300 labelled, 2 blocked; 74 texts with a reference; 107 rows (40 direct, 11 brand, 5 executive, 51 indirect); 44 ticker rows in 32 texts. Faults found: two "not a reference" items still labelled (Energy Dominance, an airport named after Trump), Truth Social once without the DJT ticker, @KelloggsUS -> K (should be KLG), TV hosts labelled as executives. No missed company among the 224 texts without a reference Prompt v4 (GE/Kellogg splits, hosts not executives, Trump places/slogans excluded, DJT ticker) and v5 (DJT never for Trump Accounts) run on both samples 2026-11-03 through `master-TrumpTweetTrades-resource` (Azure v1 API, DefaultV2 content filter): v5 294/300 and 293/300 labelled, 13 of 600 blocked, model `gpt-5-mini-2025-08-07`. Details in `tasks/AGENT_REPORT.md` |
| 2 | prompt passes until you accept; freeze |
| **3, done 2026-11-03** | `--all` flag on Global Standard, 24 workers: 21,638 texts in 84 minutes, 0 failed calls, USD 16.6. Every `ID` has a status: 21,942 ok, 331 content_filter (1.5%); one model string `gpt-5-mini-2025-08-07`, prompt v5 on every row. 6,468 keyword rows in 4,376 texts; 1,962 ticker rows (190 distinct tickers) in 1,633 texts. Blocked posts in `tasks/blocked_texts.csv`. Details in `tasks/AGENT_REPORT.md` |
| 4 | D.2 aliases in folder 3: `LLM_CreateCompanyKeywords.py`, prompt in the existing `PromptKeywords.md`, new `aliases` table in `company.db`; 20-ticker trial on Standard first |
| **5, done 2026-11-03** | Step F as a notebook, `6) SOCIALMEDIAxTWITTER/TwitterTickerCleaning.ipynb` (spec in DataPlan Step F): rules a–h, review of 14 pairs applied by code (6 accept, 8 not in universe), `Twitter_tickers_2025_2026.xlsx` 6,468 rows / 4,376 posts, 1,708 rows with a universe ticker (144 tickers), `TwitterDescriptiveAnalysis.xlsx` 11 sheets. Part 1: 144 of 559 distinct mentioned companies in the universe (25.8%). Details in `tasks/AGENT_REPORT.md` Revised 2026-11-04 (SEQ 4): companies become permanent entities (SEC CIK) with dated tickers; `4) CompanyDB/BuildEntities.py` builds `entities` (1,620 entities, 161 with an event in the window, sheet `Entities` for review); F.1–F.4 to be rebuilt on entity_id after the manager's check CEO task 2026-11-04 (R4 lifted for it): Step C.8 `2) Trades/TradesCleaning.ipynb` section 5 (until 2026-11-05 a separate notebook) + `.xlsx` correct 385 trade rows (184 wrong company, 201 latest ticker) and drop 21 note purchases (BlackRock Funding, BP Capital Markets, Société Générale, CAST), 27,628 rows, universe 1,629 → 1,620; INDV and HLX kept after the co-author's return check; company.db, entities and Step F rerun (Part 1 26.3%, 1 pair pending review) Folders renumbered 2026-11-04: new `3) Prices` (C.8 review, Step H), CompanyDB 4), TweetsDB 5), SOCIALMEDIAxTWITTER 6); chain re-run through the new paths Step H review 2026-11-04: Filip's returns moved to `3) Prices`, `ReturnsReview.ipynb` rebuilds purchases (18,818), fetches 7 changed tickers, 18,784 purchases with full windows, 27 outlier days all genuine, 21 purchases unpriceable at FMP (decision pending) |
| 6 | DataPlan.md and FolderOverview.md updated at each gate |

## Verification of gate 1

- `SocialMedia`: 22,273 rows, `ID` unique, exactly 300 with `trial_sample = 1`.
- All 300 have `llm_status = ok`, the same `llm_model` string, `llm_prompt_version = 1`.
- Review report delivered.

## Settled decisions (2026-11-02)

| decision | outcome |
|---|---|
| model / endpoints | gpt-5-mini; Standard for the trial, Global Batch for full runs |
| trial sample | 200 random + 100 drawn from texts that contain a company name or `$TICKER` |
| fields | exactly the DataPlan E.1 list, no extras |
| MMC/MRSH, TWO/TWOD | mapping flags them for manual review |
| naming | no table or column named `post`; database `SocialMedia.db`, tables `SocialMedia` and `SocialMediaKeywords` |
| files | three per folder; raw answers kept as a column, not as files |
| LLM input | text only; company handles count as direct mentions |
| where it runs | trial runs locally from this session on the Standard endpoint (about 5 minutes, USD 0.30 per pass); the full run goes through Azure Batch, so the laptop is needed only to submit and download |
| clean-up | any helper or one-off script is deleted after it has run; only the three files per folder remain |
