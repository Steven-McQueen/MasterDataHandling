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

## Added on 2026-11-13, after the main results
Fixed before the script below was written or run, after every result of 2026-11-12 had been seen (data due diligence of 2026-11-12); reported as checks, not as the main test. Script: `ChecksExtra.py`; outputs `extra_checks.csv`, `extra_world_counts.csv`, `ExtraChecksReport.txt`.
- **Check 9, posts on day 0 included.** Part 2's purchase hits counted with posts on day 0 itself (window: day 0 to trading day 10), as promised in `8) Part2Timing/0) Decisions.md` (`INCLUDE_DAY0`): Praised, any post and Roasted, direct mentions, all accounts. Part 3 is rerun with labels from the same window (the first post on or after day 0 decides); the return window stays trading days 1–10, because a return on day 0 runs from the previous close and includes moves before the trade.
- **Check 10, every shift.** The worlds of every shift from 1 to 557 days (557 shifted worlds and the real one), the design before the smallest shift of 30 days was set on 2026-11-09. Part 2's three counts and Part 3's Posted return are recomputed in these worlds; nothing else changes.
- **Check 11, the reverse direction.** Do posts about a company come before its purchases more often than chance? Part 2's count with the window moved before the purchase: purchases with at least one qualifying post on the calendar days from trading day −10 to trading day −1 before day 0 (day 0 excluded), for Praised, any post and Roasted, in the same 500 worlds. A purchase whose day 0 lies fewer than ten trading days after the first day of the trading calendar uses the days available; the report counts them. No return test: the question is about the order of posts and purchases, not about returns.

## Added on 2026-11-13: the two optional analyses of the kokebok
Fixed before the script was written or run, after every main result and checks 1–11 had been seen; reported as optional analyses, not as the main test. The kokebok lists them under "Optional, if time allows" (step 10). Script: `OptionalAnalyses.py`; outputs `optional_sales.csv`, `optional_postwindows.csv`, `optional_world_stats.csv`, `OptionalReport.txt`.

**Check 12, sales.** A sale is treated as a purchase with the sign reversed: amount times minus the market-adjusted equity return, so money not lost counts as money earned (kokebok).
- Sales: the `Trades` rows with `Transaction` = sale, lots merged to one row per company and trade date, amounts summed at low, midpoint and high; the midpoint is used.
- Sample: the tickers of the Part 3 sample (a market-adjusted return on every trading day of the returns table); the other sales are left out and counted in the report.
- Window and labels as in Part 3: day 0 is the sale date or the next trading day; the first direct post about the company (all accounts) in trading days 1–10 after day 0 decides the label: Posted, Praised (sentiment ≥ 0.5), Roasted (≤ −0.5), No post.
- Returns: return per dollar sold over trading days 1–10, r = Σ amount × (−MAR) / Σ amount, per group (All, Posted, Praised, Roasted, No post), and the dollar total.
- Timing: sales followed by at least one Praised, any, or Roasted direct post within trading days 1–10 (Part 2's count, for sales).
- Worlds: the 500 worlds of Step 6; every sale moves by the same number of days as the purchases. p_upper, p_lower and the two-sided p as in Parts 2 and 3.
- Reading: the mirror of the research question for sales is a sale followed by criticism. Roasted counts and the Roasted return are read beside Posted; no group is the main test.

**Check 13, post windows.** Keep the purchases fixed and move the posts: do the stocks he has bought move on the day of a post about them and the day after? (kokebok).
- Events: direct mentions (all accounts) of the companies in the Part 3 sample, one event per company and event day (several posts about one company on one event day are one event; it is Praised if any of them is Praised and Roasted if any is Roasted).
- Event day 0: the first trading day whose close comes after the post: a post on a trading day before 16:00 US Eastern time has that day, any later post the next trading day.
- Held: at least one purchase of the company with a trade date before day 0 (holdings before 2025 are not observed).
- Return: market-adjusted return on day 0 plus day 1.
- Statistics per group (Praised, any, Roasted): the mean return over held events (equal-weighted; the reading), and a dollar version that weights each event by the summed midpoint amount of the company bought before day 0 (a proxy for the position: sales and price changes are ignored). The mean over all events, held or not, is reported for comparison with Ge, Kurov and Wolfe (2018).
- Worlds: the purchases stay; every post's US Eastern timestamp moves by the same number of calendar days, circularly over the post calendar from 2025-01-20 to 2026-08-26 (the last day whose day 1 is in the returns table; later posts are left out and counted). Every shift from 30 days to the calendar length minus 30, plus the real world. p_upper, p_lower and the two-sided p (Praised is predicted to be positive).

## Added on 2026-11-13: robustness of checks 12 and 13
Fixed before the script was written or run, after the results of checks 12 and 13 had been seen; every variant is reported. Script: `OptionalRobustness.py`; outputs `optional_robustness.csv`, `OptionalRobustnessReport.txt`. Each variant changes one thing in check 13 and keeps the rest (Praised held events, equal-weighted mean, the real world and every shift of the posts, p_upper, p_lower, p_two). Praised is the reading; Roasted is reported beside it.
- **13.1 Windows.** Market-adjusted return on day 0 only, days 0–1 (main), 0–2 and 0–5, and days 2–10 (does the move reverse?). A window that runs past the returns table uses the days available; the report counts these events in the real world.
- **13.2 Before the post.** Day −1, and days −5 to −1 (does he praise stocks that are already rising?). A window that starts before the returns table uses the days available.
- **13.3 Return models.** Raw, CAPM and FF5 + momentum (`ar_raw`, `ar_capm`, `ar_ff5m`), on the events whose company has a full series under all four columns; the market-adjusted result is reported on the same events.
- **13.4 Without the five largest events.** In every world, the five Praised held events with the largest return are dropped before the mean is taken (and the five most negative Roasted events for Roasted).
- **13.5 Relevance ≥ 0.3.** Only direct references with relevance of at least 0.3 make events.
- **13.6 Without the media companies.** The seven tickers of check 7 (FOXA, NWSA, WBD, CMCSA, DIS, SKYD, VSNT) are removed.
- **13.7 Accounts.** @realDonaldTrump only.
- **13.8 Sentiment cut-offs.** Praised at 0.3 and at 0.7 (Roasted at −0.3 and −0.7).
- **13.9 Short shifts.** Only the shifts of 30 to 90 days forward or backward (30–90 and Lp − 90 to Lp − 30).
- **Check 12, without the five largest sales.** The five largest sales by midpoint amount (ties broken by date, then ticker) are removed in every world, as check 5 does for purchases; the sale returns per group and the three timing counts are reported.

## Output
One robustness table (`robustness.csv`, `ChecksReport.txt`) with the Posted group's return per dollar, the mean of its shifted worlds, Δr and the p-values under each check, beside the main result, and the horizon profile (`horizons.png`).
