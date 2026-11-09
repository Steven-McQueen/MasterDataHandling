Step N = kokebok step N = folder N; inside a step, N.k = section k of its notebook, or its k-th sub-folder or script.

```
master/                                          # one folder per stage, read in order; each holds RawData, one notebook or script, one review workbook, one output
├── 1) SocialMedia/                              # Step 1 = kokebok step 1: posts
│   ├── Fetch/
│   │   └── Fetch_TruthSocial.py
│   │   └── Fetch_Twitter.py
│   ├── RawData/
│   │   ├── Original/                            # untouched API / dataset output
│   │   └── *.json                               # cleaned per-account files (CleanRawData.py)
│   └── CleanRawData.py
│   └── Merge.py                                 # merges the cleaned files
│   └── SocialMediaPosts.json                    # OUTPUT: one row per post (22,273)
├── 2) Trades/                                   # Step 2 = kokebok step 2: raw disclosures -> final trades and purchase table
│   └── RawData/
│   │   └── Trump_trades_2025_RAW.csv
│   │   └── Trump_trades_2026_RAW (quiver).csv
│   │   └── TickersDB.xlsx
│   │   └── FMP_company_names.xlsx               # FMP names per ticker (cache, Step 2.4.3 and 2.5.5)
│   │   └── FMP_symbol_changes.json              # FMP symbol-change list (cache, section 5.3)
│   │   └── FMP_ticker_checks.json               # FMP profile + first price date per symbol (cache, section 5.3)
│   │   └── FirstPriceFetch/                     # co-author's notes from the first price fetch; provenance of section 5, not read by code
│   └── TradesCleaning.ipynb                     # sections 1–4 cleaning (Steps 2.1–2.4), 5 ticker corrections after prices (Step 2.5), 6 purchase table (Step 2.6)
│   └── TickerReview.xlsx                        # every manual decision, one sheet per review, in section order (… TickerCompanyMismatchReviewed, WrongCompanyAfterPrices, TickerRenames, NonEquity, Unpriceable); each ticker change with its reason (Reason / Why / ReviewNote)
│   └── Trump_trades_2025_2026.xlsx              # OUTPUT: Trades (final, 27,628 rows, 1,620 tickers) · TradesBeforePriceReview (state after Step 2.4) · TickerCompanyLookup · CompanyTickerGroups · Purchases · PurchasesMerged · PurchasesLeftOut · ChangeLog
├── 3) Prices/                                   # Step 3 = kokebok step 3: purchases -> daily prices -> abnormal returns -> review (co-author's scripts), one sub-folder per step
│   ├── RawData/
│   │   └── purchases.csv                        # written by 2) Trades section 6 (18,797 rows, 1,594 tickers)
│   │   └── french/                              # Kenneth French daily factors: 3-factor, 5-factor, momentum (to 2026-09-30)
│   ├── 1) FetchPrices/
│   │   └── FetchPrices.py                       # FMP dividend-adjusted closes per ticker in purchases.csv (key pasted at run time, not stored)
│   │   └── prices.csv                           # OUTPUT: date, ticker, adj_close (1,639 tickers, 2025-01-10 .. 2026-08-31)
│   │   └── FetchPrices2024.py                   # same fetch for the pre-sample window (key from env FMP_API_KEY), own resume file
│   │   └── prices_2024.csv                      # OUTPUT: date, ticker, adj_close (1,577 tickers, 2023-12-15 .. 2025-01-17)
│   │   └── prices_2024_missing.csv              # tickers with no or partial 2024 data (17 none, 22 start late)
│   │   └── prices_2024_partial.csv              # resume file of FetchPrices2024.py
│   ├── 2) ComputeReturns/
│   │   └── ComputeReturns.py                    # factors, returns, wrong days blanked, betas (BETA_ESTIMATION = "presample" or "insample"), abnormal returns
│   │   └── returns_table_presample.csv          # OUTPUT used by the analysis: ret, ar_raw, ar_mkt, ar_capm, ar_ff3m, ar_ff5m per ticker and day (630,470 rows)
│   │   └── betas_presample.csv                  # OUTPUT: the one beta table for every world; method, nobs, window, alpha, R2, betas, note per ticker and model
│   │   └── factors_daily_presample.csv          # daily factors as decimals plus the market return
│   │   └── ReturnsReport_presample.txt          # run report (methods, forced fallbacks, review days removed)
│   │   └── returns_table.csv                    # setting "insample", run of 2026-11-05 (630,473 rows; kept for comparison)
│   │   └── model_estimates.csv                  # setting "insample": betas, alpha, R2, nobs per ticker and model
│   │   └── factors_daily.csv                    # setting "insample": daily factors
│   │   └── ReturnsReport.txt                    # setting "insample": run report
│   ├── 3) ReviewPrices/
│   │   └── PricesReview.ipynb                   # final trades vs price symbols, integrity, spans vs entity events, extreme moves, ELME payouts
│   │   └── PricesReview.xlsx                    # ExtremeMoves + ExtremeMovesNotes (hand review, Decision = genuine / wrong, read back by step 2) · Summary · Universe · SupersededSymbols · … · Unreviewed20to50 · ELME · Review20to50InWindow
│   │   └── PricesReview2024.xlsx                # ExtremeMoves2024: pre-sample days above ±50% (Decision read back by step 2, pre-sample only) · Notes
│   │   └── PricesReview_backup_2026-11-06.xlsx  # untouched copy of PricesReview.xlsx before the rows of 2026-11-06 were added
│   └── RunPrices.py                             # runs step 1, then step 2, with the same Python on Windows or macOS; writes RunLog.txt
│   └── RunLog.txt                               # output of the last RunPrices.py runs
├── 4) CompanyDB/                                # Step 4 = kokebok step 4 — the ticker universe for the join (input: 2) Trades, sheet Trades)
│   └── BuildCompanyDB.py                        # Step 4.1: companies + executives from FMP
│   └── BuildEntities.py                         # Step 4.2: entities table (CIK, dated tickers, events) + Entities review sheet
│   └── company.db                               # companies + executives + entities + entity_sources (raw SEC/FMP answers)
│   └── CompanyDB_long.xlsx                      # QA export
│   └── PromptKeywords.md                        # empty; keyword generation dropped 2026-11-03
├── 5) MapTweetCompany/                           # Step 5 = kokebok step 5, label posts: which company a post mentions, in what tone
│   ├── 1) LabelTweets/                          # Step 5.1 — LLM labelling, text only, blind to trades
│   │   └── LLM_Prompt.md                        # frozen prompt + schema, version history at the bottom
│   │   └── LLM_SocialMediaScript.py             # one call per post, concurrent, resumable
│   │   └── SocialMedia.db                       # OUTPUT: SocialMedia + SocialMediaKeywords
│   │   └── blocked_texts.csv                    # the posts Azure's content filter refused (ID, date, account, text)
│   │   └── blocked_trial_texts.csv              # same for the two 300-post development samples, with filter category
│   ├── 2) MapToTickers/                         # Step 5.2 — map LLM companies to trade tickers
│   │   └── ReviewGuide.md                       # for the authors: what Part 1 needs from this step, the post -> ticker chain, the review rules, and how to read the output
│   │   └── TwitterTickerCleaning.ipynb          # same structure and tone as TradesCleaning.ipynb
│   │   └── TickerTwitterReview.xlsx             # review (complete 2026-11-08), sheets in order: ReadMe · 1_CompanyReview (one row per company: suggestion + v / override = its ticker on any exchange, or NONE) · 2_MentionExceptions · 3_NotListedOnPostDate · Entities (Step 4.2)
│   │   └── Twitter_tickers_2025_2026.xlsx       # OUTPUT: one row per post × company (6,468): post · LLM label · decision (public_ticker, ticker = universe join key, listed / in_universe / purchased, status); ReadMe sheet defines the columns
│   │   └── TwitterDescriptiveAnalysis.xlsx      # descriptive tables for the data chapter; 7_Part1Share = purchased share of the listed companies posted about
│   └── 3) LabelAccuracy/                        # Step 5.3 — hand-coded check of the LLM labels; planned: precision sample, recall sample, results
├── 6) CalendarShifts/                          # Step 6 = kokebok step 6: the shifted worlds
│   └── CalendarShifts.py                        # settings (start 2025-01-20, L = 557, MIN_SHIFT = 30), shift formula, checks
│   └── worlds.csv                               # OUTPUT: world, shift_days, shift_start, L (499 worlds, world 0 = real)
│   └── ShiftsReport.txt                         # inputs read, purchases outside the calendar, checks
├── 7) Part1Talk/                                # Step 7 = kokebok step 7, Part 1: does he mention what he has bought?
│   └── 0) Decisions.md                          # every Part 1 choice, fixed before results
│   └── Part1Settings.py                         # all paths, dates, windows, mention definitions; shared functions
│   └── RunPart1.py                              # runs 1) to 3) in order; writes RunLog.txt
│   ├── 1) BuildPanel/
│   │   └── BuildPanel.py                        # ticker x calendar-day panel from Step 5.2 and Step 2
│   │   └── panel.csv.gz                         # OUTPUT: 954,180 rows; mentions per definition, purchases, treatments
│   │   └── tickers.csv                          # per ticker: first purchase, purchase days, mention days
│   │   └── BuildPanelChecks.txt                 # counts against the sources, spot checks
│   ├── 2) Estimate/
│   │   └── EstimatePart1.py                     # LPM and Poisson with ticker + day effects, lead/lag bins, descriptives
│   │   └── results.csv · leadlag.csv · leadlag.png · descriptives.txt · EstimateReport.txt
│   └── 3) Inference/
│       └── ShiftedWorlds.py                     # the same slope in all 499 worlds; p-values, hits, window search
│       └── inference.csv · world_estimates.csv · worlds_main.png · InferenceReport.txt
├── 8) Part2Timing/                              # Step 8 = kokebok step 8, Part 2: do purchases precede (positive) posts?
│   └── 0) Decisions.md                          # every Part 2 choice, fixed before results
│   └── Part2Settings.py                         # paths, window, thresholds, outcomes; shared functions
│   └── RunPart2.py                              # runs 1) and 2) in order; writes RunLog.txt
│   ├── 1) Hits/
│   │   └── Hits.py                              # posts inside each purchase's 10-trading-day window
│   │   └── purchase_hits.csv · hit_posts.csv · hits_summary.csv · HitsChecks.txt
│   └── 2) Inference/
│       └── ShiftedWorlds.py                     # the same counts in all 499 worlds; p-values, ratios
│       └── inference.csv · world_counts.csv · worlds_main.png · InferenceReport.txt
├── 9) Part3Returns/                             # Step 9 = kokebok step 9, Part 3: did the purchases, above all the Posted ones, earn more than on shifted dates?
│   └── 0) Decisions.md                          # every Part 3 choice, fixed 2026-11-09 before any result; scripts (Part3Settings.py, RunPart3.py) not yet written
├── 10) Checks/ … 11) Exhibits/                  # Steps 10–11 = kokebok steps 10–11; each folder is created when its work starts
├── .env                                         # API keys (FMP, Twitter, Azure OpenAI); never shared
├── .gitattributes                               # Git LFS: the large raw and output files (SocialMedia.db, company.db, returns tables, WhiteHouse_Twitter.json)
├── .gitignore                                   # keeps .env and Python caches out of version control
├── README.md                                    # the master file (data plan): every step as actually run, its logic and files, decisions and limitations
└── FolderOverview.md
```
