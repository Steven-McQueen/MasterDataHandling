# Step 10, checks: decisions

Fixed on 2026-11-09, before any check was computed. The five checks are the kokebok's (step 10); everything else is as in Part 3 (`9) Part3Returns/0) Decisions.md`). Each check reruns the Part 3 test with one thing changed and reports the Posted group's return per dollar against its shifted worlds, beside the main result. A check does not pass or fail the result; it decides which sentence we may write.

## Common to every check
- Main amount only (midpoint), all accounts, direct mentions, labels as in Part 3 (first post in the window decides).
- The same 499 worlds and the same p-values as Part 3: p_upper, p_lower, and p_two = 2 × the smaller, capped at 1.
- Groups reported: Posted (the reading), All, Praised and Roasted (for reference).

## The checks
1. **Horizons.** Market-adjusted equity return over trading days 1–2, 1–5, 1–10 and 1–20 after day 0. The Part 3 sample already holds every purchase's 20-day window in every world.
2. **Before the purchase.** Trading days −5 to −1 before day 0. A purchase whose day 0 falls in the first five trading days of the returns table (from 2025-01-21) has fewer than five days before it; it uses the days available. The report counts these purchases in the real world.
3. **Short shifts only.** Only the worlds with a shift of 30 to 90 days forward or backward (shift_days 30–90 and 467–527: 122 worlds plus the real one). Read from the Part 2 and Part 3 world tables; nothing is recomputed. Part 2's main count (Praised hits) is reported beside it.
4. **Return models.** Raw, market-adjusted, CAPM, FF3 + momentum and FF5 + momentum (`ar_raw`, `ar_mkt`, `ar_capm`, `ar_ff3m`, `ar_ff5m`). Tickers without betas have no model returns, so this check uses the purchases with a full series under all five columns; the market-adjusted result is reported on the same purchases.
5. **Big purchases.** Without the five largest purchases by midpoint amount (ties broken by date, then ticker), removed in every world. The five are listed by name.

## Output
One robustness table (`robustness.csv`, `ChecksReport.txt`) with the Posted group's return per dollar, the mean of its shifted worlds, Δr and the p-values under each check, beside the main result, and the horizon profile (`horizons.png`).
