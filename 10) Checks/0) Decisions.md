# Step 10, checks: decisions

Fixed on 2026-11-09, before any check was computed. The five checks are the kokebok's (step 10); everything else is as in Part 3 (`9) Part3Returns/0) Decisions.md`). Each check reruns the Part 3 test with one thing changed and reports the Posted group's return per dollar against its shifted worlds, beside the main result. A check does not pass or fail the result; it decides which sentence we may write.

## Common to every check
- Main amount only (midpoint), all accounts, direct mentions, labels as in Part 3 (first post in the window decides).
- The same worlds and the same p-values as Part 3 (499 worlds when fixed; 500 since L = 558 on 2026-11-10): p_upper, p_lower, and p_two = 2 × the smaller, capped at 1.
- Groups reported: Posted (the reading), All, Praised and Roasted (for reference).

## The checks
1. **Horizons.** Market-adjusted equity return over trading days 1–2, 1–5, 1–10 and 1–20 after day 0. The Part 3 sample already holds every purchase's 20-day window in every world.
2. **Before the purchase.** Trading days −5 to −1 before day 0. A purchase whose day 0 falls in the first five trading days of the returns table (from 2025-01-21) has fewer than five days before it; it uses the days available. The report counts these purchases in the real world.
3. **Short shifts only.** Only the worlds with a shift of 30 to 90 days forward or backward (shift_days 30–90 and L − 90 to L − 30: 122 worlds plus the real one; 468–528 since L = 558). Read from the Part 2 and Part 3 world tables; nothing is recomputed. Part 2's main count (Praised hits) is reported beside it.
4. **Return models.** Raw, market-adjusted, CAPM, FF3 + momentum and FF5 + momentum (`ar_raw`, `ar_mkt`, `ar_capm`, `ar_ff3m`, `ar_ff5m`). Tickers without betas have no model returns, so this check uses the purchases with a full series under all five columns; the market-adjusted result is reported on the same purchases.
5. **Big purchases.** Without the five largest purchases by midpoint amount (ties broken by date, then ticker), removed in every world. The five are listed by name.

## Added on 2026-11-10, after the main results
Both were added after the Part 3 and check results of 2026-11-09 were seen; they are reported as checks, not as the main test.
- **Check 1, every horizon.** Trading days 1–1, 1–2, …, 1–10 (and 1–20 as before), so the profile is shown in full rather than at four points. Day 0 stays out: its return runs from the previous close and includes moves before the trade.
- **Check 1, search p-value.** Because one of ten horizons can look significant by chance, the smallest two-sided p of the Posted group over 1–1 … 1–10 is compared with the same smallest p in every world (as Part 1's window search). Written to `horizon_search.csv` and the report.
- **Check 6, relevance floor.** Labels from direct references with relevance ≥ 0.3 only (the main test has no floor; README open decision 8). The Part 3 test is rerun with these labels, and Part 2's Praised, any-mention and Roasted purchase hits are counted with the same floor in every world. A check that the count without the floor reproduces Part 2 is in the report.

## Added on 2026-11-11, after the main results
Added after the results on the v6 labels were seen; reported as a check, not as the main test.
- **Check 7, without media companies.** 62 percent of the real Roasted purchase hits are purchases of media companies, which the accounts attack almost daily. Check 7 removes the purchases of the seven owners of a national US news network or newspaper, by their latest symbol: FOXA (Fox News), NWSA (The Wall Street Journal, New York Post), WBD (CNN), CMCSA (NBC; MSNBC and CNBC until the 2026 spin-off), DIS (ABC), SKYD (CBS) and VSNT (MSNBC and CNBC since). The list is fixed by ownership of a news outlet, not by how often a company is mentioned. The Part 3 test is rerun without these purchases in every world, and Part 2's Praised, any-mention and Roasted purchase hits are counted without them in every world.
- **Check 8, specification curve for Part 2** (`SpecCurve.py`). The grid was fixed on 2026-11-11 before the script was run, and every combination is reported: outcome (Praised, any post, Roasted) × reference types (direct; + brand; + brand and executive) × accounts (all; @realDonaldTrump; @WhiteHouse) × sentiment cut-off (0.3, 0.5, 0.7; not for any post) × relevance floor (none, 0.3, 0.5, 0.7) × window (trading days 1–5, 1–10, 1–20) × media companies (in, out): 1,512 specifications, each counted in all 500 worlds. The three outcomes are read one by one. Because the specifications share posts and purchases, the reading is a joint test per outcome that treats every world in turn as the real one (Simonsohn, Simmons and Nelson 2020): the median ratio of real to expected, and the number of specifications above and below chance at 5 percent, against the same statistic in every world. Some options are stricter or narrower than we would choose as a main test (a relevance floor of 0.7, @WhiteHouse only); they are in the grid so that it is complete, not because they are equally good tests.

## Output
One robustness table (`robustness.csv`, `ChecksReport.txt`) with the Posted group's return per dollar, the mean of its shifted worlds, Δr and the p-values under each check, beside the main result, and the horizon profile (`horizons.png`).
