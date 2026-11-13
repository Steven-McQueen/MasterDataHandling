# Part 2, timing: decisions

Fixed on 2026-11-07, before any Part 2 result was computed. Every setting named here lives in `Part2Settings.py`; change it there, not in the scripts. Most choices come from the data plan (README.md); the step each one comes from is in brackets.

## Question
Does a disclosed purchase of a company precede a post about that company more often than chance would predict, and in particular a positive post? (Research question.)

## Unit: a purchase
- One purchase = one company bought on one day: `2) Trades/Trump_trades_2025_2026.xlsx`, sheet `PurchasesMerged` (17,724 company-days), plus the 21 lots in `PurchasesLeftOut` merged the same way. The plan names `PurchasesMerged` as the table the hit count reads, and keeps the unpriceable purchases in Part 2 (Part 2 needs no prices). [Step 2.5, open decision 2]

## Window
- Day 0 is the trade date, or the next trading day if the trade date was not one; the window is trading days 1 to 10 after day 0, the same window as the return test. [Step 3.2.3]
- A post counts if its US Eastern date lies after day 0 and on or before trading day 10, weekends inside the window included (`WINDOW_TRADING_DAYS`).
- Posts on day 0 itself do not count, because the order of trade and post within the day is unknown; including them is a robustness check (`INCLUDE_DAY0`).
- Trading days are the dates of `3) Prices/2) ComputeReturns/factors_daily_presample.csv`, the calendar Step 3 uses.

## Hit
- A purchase is a hit if at least one post with a qualifying mention of the same ticker falls inside its window. A post naming the company twice counts once.
- Second count (post side, the wording of the research question): qualifying post-company pairs that fall inside the window of at least one purchase of that company.

## Outcomes
- Mention type: **direct** (main); direct + brand; direct + brand + executive. Indirect references carry no ticker.
- Tone (sentiment score of the reference, −1 to 1, pre-registered thresholds) [Step 5.1]:
  - any mention (the "talk" analysis),
  - **Praised:** sentiment ≥ 0.5 (main), with ≥ 0.3 and ≥ 0.7 as sensitivity,
  - **Roasted:** sentiment ≤ −0.5, with ≤ −0.3 and ≤ −0.7.
- Accounts: all three (main); @realDonaldTrump only as robustness.
- Tone given talk: the share of hits (any mention) that are Praised hits, real versus shifted.

## Inference
- The same counts in every world of `6) CalendarShifts/worlds.csv` (world 0 real, 498 shifts from 30 to 527 days). Shifted purchase dates are calendar days; day 0 moves to the next trading day as in the real world.
- p_upper = share of all 499 worlds with a count at least as large as the real one; p_lower the other direction. Effect size: real hits divided by the mean of the shifted worlds.
- Amended 2026-11-09: the first run used every shift from 1 day (557 worlds). Shifts under 30 days are now left out, as the kokebok sets, because a purchase moved by a few days stays inside its own window (Step 6).
- Amended 2026-11-10: the shift calendar is L = 558 (2025-01-20 to 2026-07-31, both end dates included), so every purchase day lies inside it: 499 shifts from 30 to 528 days, 500 worlds with the real one (Step 6).
- Main test: Praised hits (direct, all accounts, sentiment ≥ 0.5). The other outcomes are reported in the same table and labelled as secondary.

## Limitations to state
Text-only labels and the 331 filtered posts (more likely hostile, so they lower the Roasted count); the White House accounts are run by staff; the shift calendar has L = 558 (Step 6; amended 2026-11-10, was 557).
