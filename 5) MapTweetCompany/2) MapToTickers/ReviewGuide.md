# Step 5.2 review guide: what it is for, and what to do

Written for the authors. The technical description is in `README.md`, Step 5.2; this file explains the purpose, the review and the output. The review was completed on 2026-11-08; sections 3 and 4 remain the instructions for any later change.

## 1. What Part 1b needs from this step

Part 1b asks: *of the publicly listed companies Trump posted about, what share did he also buy?*

- **Denominator:** every listed company he posted about. A company counts if it had a public listing anywhere (NYSE, Nasdaq, Tokyo, an ADR, OTC) at any time in the sample window, traded by him or not: Fox, Tesla, The New York Times, Toyota, Trump Media.
- **Numerator:** those whose ticker is in the final purchase table, `3) Prices/RawData/purchases.csv` (1,594 tickers).

So every company the LLM named needs one of two verdicts: *its ticker*, or *not listed* (`NONE`). That is the whole review. Two further things ride on the same decision:

- A ticker in the **trade universe** (`4) CompanyDB/company.db`, the 1,620 tickers he bought or sold) links the company's posts to the trades. Parts 2 and 3 use only these, so the ticker of a traded company must be exactly right.
- 26 universe tickers were only sold (HOG among them). They are in the universe but not purchased, so `in_universe = 1` does not mean `purchased = 1`; Part 1b uses `purchased`.

Result (2026-11-08): 178 listed companies posted about, 141 purchased, **79.2 %** (`TwitterDescriptiveAnalysis.xlsx`, `7_Part1Share`).

## 2. How a post becomes a ticker (the chain)

1. **Step 5.1, the LLM.** Reads one post at a time, blind to the trades, and writes down every company it refers to: the words (`mention_text`), the legal name (`canonical_company`), a ticker guess, and whether it is a direct mention, a brand, an executive or an indirect reference (an industry, a country). 22,273 posts → 6,468 references, of which 2,819 name a company.
2. **Notebook section 1, standardizing.** LLM names and universe names get the same cleaning (upper case, `Corporation` → `CORP`, …); ticker guesses get the share-class and rename maps (`GOOGL` → `GOOG`, `PARA` → `PSKY` → `SKYD`). Spellings that clean to the same name are one company. A symbol is a label with a date, not a company: `PARA` belongs to Parabolic Technologies since 2026-08-07, so the notebook stops if a guess under a retired symbol is dated after the symbol was reassigned (none today).
3. **Notebook section 2, one suggestion per company.** The 2,819 references fall into 559 companies. For each, rules look for a universe ticker: guess and name agree → `ticker+name`; exact name → `name`; a named executive → `executive`; guess in the universe but names differ → `ticker only`; closest name → `similarity`; nothing → `none`. A suggestion is never a decision. 157 companies got one; 402 got none (most of those are not in the universe, which is exactly what the review then records).
4. **The review (`1_CompanyReview`, you).** One decision per company: the suggestion is right (`v`), or the ticker / `NONE` goes in `TickerOverride` with a `Reason`.
5. **`2_MentionExceptions` (you).** Where one company's decision is wrong for some of its mentions: Tylenol under Johnson & Johnson is Kenvue; MSNBC under Comcast is Versant from 2026.
6. **Notebook sections 3–4, applying.** Decisions and exceptions are applied by code; a reference dated when its company had no price (SpaceX before 2026-06-12, WK Kellogg after 2025-09-25) loses the ticker for that reference only; checks run; the final file is written.

Why a review when the rules already agree? Both signals in `ticker+name` come from the same LLM, so they can agree on the wrong company (Tylenol → JNJ: name and ticker agree, both wrong, Kenvue since 2023). Only a person reading the mentions catches that. It is the same reason Step 2 reviewed the trade tickers by hand.

## 3. The rules of the review

### 3.1 Which ticker

| the company is … | write | example |
|---|---|---|
| in the trade universe and the suggestion is right | `v` | Tesla, TSLA |
| in the trade universe, but the suggestion is wrong or missing | the universe ticker + `Reason` | UFC under "Endeavor" → `TKO` |
| listed somewhere, not traded by him | its ticker on that exchange + `Reason` | New York Times → `NYT`; Toyota → `TM` |
| not listed at any time in the window | `NONE` + `Reason` | Trump Organization, ByteDance, INDYCAR |

`v` together with an override is allowed and means the override (you looked, and this is the decision). The notebook follows the rename chain, so an old symbol (`PSKY`) lands on the latest (`SKYD`).

### 3.2 Delisted, newly listed, merged

- **Listed for part of the window** (listed during it: SpaceX 2026-06-12, Newsmax 2025-03-31; delisted during it: WK Kellogg 2025-10, U.S. Steel 2025-06-18): keep the ticker. The company was one he could have bought. For universe tickers the notebook drops the ticker from references dated outside the price series (`3_NotListedOnPostDate`); for tickers outside the universe there is no price series, so the dates stand in your `Reason` only. The company stays in the Part 1b denominator either way.
- **Never listed in the window** (X Corp / Twitter, private since 2022, if treated as itself): `NONE`.
- **Merger successor** (Paramount Global → Paramount Skydance → `SKYD`): the chain handles it; all Paramount references carry `SKYD`, the ticker the trades carry.
- **Taken private** (Endeavor, March 2025): its own ticker stays with it; it is not the acquirer's. UFC and WWE references are `TKO`, a separate listed company.
- **A brand that changed hands** (Tylenol, CNBC): the listed parent *on the post date*, via `2_MentionExceptions` with `FromDate` / `ToDate`.

### 3.3 What is not a company reference

- A naming-rights venue or sponsored event (MetLife Stadium, Coca-Cola 600, Wells Fargo Center, Cadillac Championship) → `NONE` (or an exception when the company has other real mentions).
- A person quoted in a public office (Lutnick as Commerce Secretary, Pulte at FHFA, Bisignano at SSA) → not a reference to the firm he left.
- A film or TV title named in passing → not the studio.
- "DJT" as his signature, TrumpRx, @TrumpAccounts → not Trump Media.

## 4. Running it

Save the workbook, close Excel, run `TwitterTickerCleaning.ipynb` top to bottom (it takes a few minutes). The notebook reports how many companies are decided and pending and stops with a plain message on any invalid entry (a `Review` other than `v`, an override that is not a ticker or `NONE`, an override without a reason, an exception that matches nothing). It rewrites `Twitter_tickers_2025_2026.xlsx` and `TwitterDescriptiveAnalysis.xlsx`; Part 1b (`7) Part1b_Talk/RunTalk.py`) then reads the new file.

## 5. Reading the output: `Twitter_tickers_2025_2026.xlsx`

One row per post × company reference (6,468 rows). Sheet `ReadMe` defines every column; the short version, in three groups:

| group | columns | meaning |
|---|---|---|
| the post (Step 1) | `ID`, `created_at`, `User`, `platform`, `text` | which post; a post with three companies has three rows |
| what the LLM read (Step 5.1) | `mention_text`, `reference_type`, `canonical_company`, `sentiment`, `relevance`, `confidence` | the words, the type (direct / brand / executive / indirect), the name the LLM gave, and its scores |
| the decision (Step 5.2) | `company`, `public_ticker`, `ticker`, `listed`, `in_universe`, `purchased`, `status`, `decided_by`, `reason` | see below |

- `public_ticker`: the stock, any exchange, from the review. Empty when not listed, indirect, or not listed on the post date.
- `ticker`: the same symbol **if it is in the trade universe**; empty otherwise. This is the join key with `Trump_trades_2025_2026.xlsx` and what Parts 2 and 3 read.
- `listed` / `in_universe` / `purchased`: 1/0 flags, each implied by the previous (`purchased` ⇒ `in_universe` ⇒ `listed`).
- `status`, one word per row:

| `status` | meaning | rows |
|---|---|---|
| `universe` | carries a trade-universe ticker | 1,691 |
| `listed_not_traded` | a listed company he never traded (NYT, DJT, TM, …) | 258 |
| `not_listed` | no public listing in the window (`NONE` in the review) | 841 |
| `not_listed_on_post_date` | the company has a ticker, but no price that day (SpaceX before listing, KLG after delisting) | 29 |
| `indirect` | an industry, country or group of companies; no company | 3,649 |
| `pending` | a company not yet reviewed | 0 |

- `decided_by`: where the decision came from: `company review` (`1_CompanyReview`), `mention exception` (`2_MentionExceptions`), `listing check (prices.csv)`, or `no company (indirect reference)`.
- `reason`: your `Reason` text, where you wrote one, or the listing check's.

The suggestion, the rule that found it and its score are **not** in this file; they are the audit trail in `TickerTwitterReview.xlsx`.

## 6. How to account for it in the thesis

The data chapter needs four things, all in `TwitterDescriptiveAnalysis.xlsx`:

1. **The chain** (section 2 above, in two or three sentences) and that labels were produced blind to the trades.
2. **How the suggestions were found and what the review did with them**: `6_SuggestionVsReview`. For example: "Of 559 companies named, the rules linked 157 to a traded company; the authors confirmed 141 and rejected 16 as namesakes, venues or office-holders (`NONE`); of the 402 without a suggestion, 6 were traded companies under another name, 40 were listed companies outside the trade universe and 356 were not listed."
3. **What the final file contains**: `5_Status` and `4_ReferenceTypes`, and the rules of section 3, stated as rules.
4. **The Part 1b share**: `7_Part1Share`: of the listed companies he posted about, the share purchased, over distinct companies, references and posts.

Everything is reproducible from `SocialMedia.db`, `company.db`, `purchases.csv`, `TickerTwitterReview.xlsx` and the notebook; the review workbook is the audit trail, as `2) Trades/TickerReview.xlsx` is for the trades.
