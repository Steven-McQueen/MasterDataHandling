# Part 3, returns: decisions

Fixed on 2026-11-09, before any Part 3 result was computed. Every setting named here will live in `Part3Settings.py`; change it there, not in the scripts. Most choices come from the kokebok (step 9) and the data plan (README.md); the step each one comes from is in brackets.

## Question
Did the purchases earn more, after adjusting for the market, than the same purchases with the same amounts would have earned on shifted dates? Above all: did the purchases followed by a post about the same company (Posted) earn more per dollar than the Posted purchases of the shifted worlds? (Research question, kokebok step 9.)

## Unit and sample
- One purchase = one company bought on one day: `2) Trades/Trump_trades_2025_2026.xlsx`, sheet `PurchasesMerged` (17,724 company-days). The 21 unpriceable purchases in `PurchasesLeftOut` stay in Part 2 and are left out of Part 3. [Step 2.6, open decision 2]
- **Same purchases in every world.** Part 3 keeps only tickers with a market-adjusted return on every trading day from 2025-01-21 to 2026-08-28, the 20th trading day after the last purchase (the longest horizon, check 1). A shifted purchase can land anywhere in the sample, so a ticker with a shorter series would drop out of some worlds and not others, and the worlds would no longer hold the same purchases and amounts. We report how many purchases and what share of the amount the rule excludes, and the real-world return of the excluded purchases.
- **Days marked wrong in the price review** (`3) Prices/3) ReviewPrices/PricesReview.xlsx`, sheet `ExtremeMoves`, Decision = wrong; 10 days, of which Step 3 removed 5 and 5 were blank already) count as a market-adjusted return of zero on that day, in the real world and in every shifted world. The full-series rule is applied after this.
- Amounts: the midpoint of the disclosed range (`amount_mid`). Amended 2026-11-09: the first run also reported the low and high ends; the authors decided to use the midpoint only, as the kokebok's "midpoint for value ranges". The highest range in the table ends at USD 25 million, so every range has a midpoint.

## Return of one purchase
- Day 0 is the trade date, or the next trading day if the trade date was not one; the same rule as Part 2. Trading days are the dates of `3) Prices/2) ComputeReturns/factors_daily_presample.csv`. [Step 8.1]
- **Market-adjusted equity return (MAR):** the sum of the stock's market-adjusted daily returns (`ar_mkt` in `returns_table_presample.csv`) over trading days 1 to 10 after day 0. Day 0 itself is not included. [Step 3.2.4]
- The window is the same as the Part 2 hit window, so a Posted purchase's return window covers every post that made it Posted.
- Horizons 1–2, 1–5 and 1–20, days −5 to −1 and the other return models (`ar_raw`, `ar_capm`, `ar_ff3m`, `ar_ff5m`) are checks (step 10), computed from the same table.

## Groups
- Labels from Part 2 (`8) Part2Timing/`): direct mentions, all accounts, trading days 1 to 10. [Step 8]
  - **Posted:** at least one post about the company in the window (outcome `direct_any`).
  - **No post:** none.
  - **Praised:** the first post in the window has sentiment ≥ 0.5 (`direct_pos50`).
  - **Roasted:** the first post in the window has sentiment ≤ −0.5 (`direct_neg50`).
  - If a purchase is followed by both a positive and a negative post, the first one decides; we report how many such cases there are. [Kokebok step 8]
- The labels are set again in every shifted world from that world's dates.

## Statistics per group
- **Market-adjusted total return:** T = sum over the group of amount × MAR, in USD.
- **Return per dollar:** r = T ÷ the total amount of the group.
- For all purchases, T and r give the same answer, because the sample rule keeps the same purchases and amounts in every world. For the other groups, membership and amount change between worlds; the main statistic is r.
- **Main comparison:** r of the real Posted group against r of the Posted group in every shifted world.

## Inference
- The same statistics in every world of `6) CalendarShifts/worlds.csv` (world 0 real). Shifted day 0 moves to the next trading day as in the real world.
- p_upper = share of all worlds, the real one included, with a value at least as large as the real one; p_lower the other direction. The main p-value for returns is two-sided: 2 × the smaller of p_upper and p_lower, capped at 1.
- **Excess return per dollar:** Δr = real r minus the mean r of the shifted worlds.
- **Dollar excess:** Δr × the real amount of the group.
- **Contributors:** a Posted purchase's contribution is its amount × (its MAR minus the mean r of the shifted Posted groups). The contributions add up to the Posted group's dollar excess. The ten largest are reported by name.

## Added after the first results (2026-11-09)
These were open when the decisions above were fixed and were settled after the first Part 3 run; the main statistic and comparison above are unchanged.
- **Direct tests of the group gaps:** r(Praised) − r(Roasted) and r(Posted) − r(No post), each against the same gap in every world (`GAPS`), with the same two-sided p-value.
- **The Posted group's dollar total T** is tested beside its return per dollar, because more dollars ahead of posts would not show in r.
- **Neutral posts** stay inside Posted: a purchase whose first post in the window is neither Praised nor Roasted is Posted and in neither sub-group.
- **Smallest shift:** 30 days (Step 6).

## Limitations to state
Holding period assumed at ten trading days (which sale closes which purchase is unknown); amounts known only as ranges; the 21 unpriceable purchases and the tickers without a full series are left out; daily data cannot separate a post from the news that prompted it; the accounts are discretionary, so the tests compare the account's trading calendar with the posts.
