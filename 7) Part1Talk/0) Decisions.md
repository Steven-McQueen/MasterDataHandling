# Part 1, talk: decisions

Fixed on 2026-11-06, before any Part 1 result was estimated. Every setting named here lives in `Part1Settings.py`; change it there, not in the scripts.

## Question
Does Trump (his own accounts and the White House accounts in the sample) mention a company more often after he has bought it?

## Why the design uses purchases, not ownership
The first plan was "probability of a post rises once he owns the company" (Max). Phase 0 showed that this barely varies over time: of the 145 companies in the trade universe that are ever mentioned, 111 were first bought by 2025-02-02, so only 56 company-days with a mention lie before a first purchase (1,127 after). Holdings before 2025 are not observed either. Purchases, by contrast, repeat (median 28 purchase days per mentioned company). So:

- **Main result: recent purchase.** `recent_k = 1` if the company was bought on any of the k calendar days before day t (days t-k .. t-1). Windows k = 1, 3, 5, 10, 20, 30; main window 10 (`MAIN_WINDOW`).
- **Robustness: exposure.** log(1 + cumulative purchased amount in USD up to day t-1), amounts at the midpoint of the disclosed range.
- **Description: ownership.** `owned = 1` after the first purchase; reported with the weakness above, not as a test.

## Panel
- One row per ticker and calendar day, 2025-01-20 to 2026-08-31 (`PANEL_START`, `PANEL_END`). Balanced.
- Universe: every ticker in `2) Trades/Trump_trades_2025_2026.xlsx`, sheet `Trades` (purchases and sales). Companies mentioned but outside the trade universe have no ticker in Step 5.2 and cannot be bought, so they are left out.
- All purchases count, including the 21 left out of pricing: Part 1 needs no prices.
- Sales are ignored: amounts are ranges, so a full exit cannot be seen.
- Post dates are taken in US Eastern time (`POST_TZ`), the time zone of the trade dates.
- Purchase dates are used as disclosed, also the four dated on a weekend (calendar-day design).

## Outcome
- **Main:** at least one post that day with a **direct** mention of the company (`MAIN_MENTION`). Counted per post, not per row (a post naming a company twice counts once).
- **Robustness:** direct + brand; direct + brand + executive; direct mentions by @realDonaldTrump only (the White House accounts are run by staff).
- Indirect references carry no ticker and never count.
- The 331 posts blocked by Azure's content filter carry no labels and count as no mention (limitation; biases towards zero).

## Model
- Linear probability model, y = β · treatment + company effect + day effect. Estimated on the balanced panel; standard errors clustered by ticker and by day (two-way).
- Effect reported in percentage points, next to the baseline probability and as a ratio.
- Poisson with the same fixed effects (count of posts) as robustness.
- Lead/lag bins: purchases 21-30, 11-20, 1-10 days AFTER the post day (posting before buying), on the same day, and 1-10, 11-20, 21-30 days BEFORE, in one regression.
- Robustness: window including the purchase day (days t-k .. t).

## Inference
- Shifted worlds from `6) CalendarShifts/worlds.csv`: the real world and 498 shifts of all purchase dates (every shift from 30 to 527 days). In each world the same estimate is computed; p-value = share of all 499 worlds with an estimate at least as large as the real one (one-sided: more talk after buying).
- Window search: the minimum p-value over the six windows is compared with the minimum p-value of every shifted world, so picking the best window is accounted for.
- Amended 2026-11-09: the first run used every shift from 1 day (557 worlds). Shifts under 30 days are now left out, as the kokebok sets, because a purchase moved by a few days stays inside its own window (Step 6).
- Effect size from the worlds: real mention-days inside windows versus the average of the shifted worlds.

## Limitations to state
Holdings before 2025 unobserved; sales ignored; text-only labels; 331 filtered posts; the White House accounts are not Trump himself (robustness above); the shift calendar has L = 557, so the 44 purchases of 2026-07-31 wrap to the calendar start in every world (see `6) CalendarShifts/ShiftsReport.txt`).
