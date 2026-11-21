# 12) AddedChecks

Checks and analyses added on 20 Nov 2026, after the main results (Steps 6-11) had been seen.
Each script states in its header what was decided before it was run and what was added after.
Nothing here changes the main pipeline: the scripts read the repo's stored outputs or call the
settings modules of Steps 7-9 (`7) Part1b_Talk/TalkSettings.py`, `8) Part1_Timing/TimingSettings.py`,
`9) Part2_Returns/ReturnsSettings.py`) and `10) Checks`.

Numbers in the thesis that come from these checks cite the output files listed below.

## Helpers

- `_common.py`, `loop_common.py`: shared loaders (Part 1 and Part 2 inputs, shifted dates,
  share-based p-values). Both wrap the repo's settings modules. The A scripts and `review_A/`
  import `loop_common.py`; B4, B4a, B4c, B4e, B4g, B5, B5b, B6 and the `rv_b5*` scripts import `_common.py`.

## Scripts (outputs in `out/`)

- `A1_praised_in_checks.py`: Part 2 return per dollar of the Praised group beside Posted, in the main test and in every check that reruns Part 2. `A1_praised_in_checks.csv/.txt`
- `A2_calendar_adjusted.py`: calendar neutrality of the real purchase windows (posts about any company) and the calendar-adjusted hit rate. `A2_calendar_adjusted.csv/.txt`, `A2_world_rates.csv`
- `A3_post_side_counts.py`: Part 1 post-side counts beside the purchase-hit counts, p-values recomputed from `world_counts.csv`. `A3_post_side_counts.csv/.txt`
- `A4_dependent_worlds.py`: autocorrelation across shifted worlds, effective number of worlds, p-value floor. `A4_dependent_worlds.csv/.txt`, `A4_acf.csv`
- `A5_no_wrap.py`: Part 1 and Part 2 without the wrap of the circular shift (two versions). `A5_no_wrap.csv/.txt`, `A5_no_wrap_worlds.csv`, `A5_quarterly_profile.csv`
- `A6_power.py`: effects detectable at 50 and 80 percent power under the repo's critical-value rule. `A6_power.csv/.txt`
- `A7_multiple_testing.py`: test families as run, p-value floors, adjusted p-values for Check 13.10. `A7_families.csv`, `A7_check13_adjusted.csv`, `A7_check13_worlds.csv`, `A7_multiple_testing.txt`
- `A8_leave_out_amazon.py`: Part 2 without the Amazon purchase of 2026-04-17. `A8_leave_out_amazon.csv/.txt`
- `A9_equal_weighted.py`: Part 2 with equal weights instead of midpoint amounts. `A9_equal_weighted.csv/.txt`
- `B1_poisson.py`: Poisson model of Part 1b beside the LPM rows, and against the shifted worlds. `B1_poisson.csv/.txt`, `B1_poisson_worlds.csv`
- `B2_cumulative_treatments.py`: exposure and owned treatments of Part 1b under the wrap. `B2_cumulative_treatments.csv/.txt`
- `B3_check2_check13.py`: Check 2 and Check 13 rows as stored, with line numbers. `B3_check2_check13.csv/.txt`
- `B4_extract.py`: two-sided Part 2 p-values, survivorship counts, factor-model rows, read from stored outputs. `B4_extract.txt`
- `B4a_lowhigh_amounts.py`: Part 2 with the low and high ends of the disclosed ranges, final data. `B4a_lowhigh_amounts.csv/.txt`
- `B4c_v5_row.py`: label version v5 beside v6, as stored and rerun on the final data (extracts the v5 label file from commit 7ab940f). `B4c_v5_row.csv/.txt`, `_v5_Twitter_tickers_7ab940f.xlsx`
- `B4d_text_only.py`: posts dropped by the text-only rule, by account. `B4d_text_only.csv/.txt`
- `B4e_filtered_posts.py`: the posts blocked by the content filter and how far they could move the Part 1 counts. `B4e_filtered_posts.csv/.txt`
- `B4g_praised_part1_rule.py`: Part 2 Praised and Roasted groups under the Part 1 rule (any post instead of first post). `B4g_praised_part1_rule.csv/.txt`
- `B5_roasted_taxloss.py`: test of the tax-loss reading of the Roasted excess (prior 20-day return). `B5_roasted_taxloss.csv/.txt`, `B5_roasted_taxloss_real.csv`
- `B5b_addendum_full_prior.py`: B5 statistics with complete prior windows only (imports B5). `B5b_addendum_full_prior.txt`
- `B6_palantir_figure.py`: Palantir figure for Chapter 4 (window, hit, shift). `fig_palantir.pdf/.png/.tex`, `B6_palantir_figure.txt`
- `B7_decision_timeline.py`: when each analysis choice was recorded against the first result it affects (reads `git log`; rows first recorded in the kokebok version of 6 Nov 2026 carry "doc.", corrected 2026-11-21). `B7_decision_timeline.csv/.tex/.txt`

### Added on 21 Nov 2026 (after the audit of 21 Nov; all after the main results)

- `C01_kokebok_hit_definition.py`: Part 1 under the hit definition of the kokebok of 6 Nov (any post, calendar days 1-10) beside the main test (Praised, trading days 1-10). `C01_kokebok_hit_definition.csv/.txt`
- `C02_power_adjusted.py`: critical value and detectable effects of the calendar-adjusted statistic (observed/expected hits, code of `review_A/R2`), and the clustering diagnostic behind its mean of 0.76. `C02_power_adjusted.csv/.txt`, `C02_world_oe.csv` (run after C16)
- `C03_disclosure_lag.py`: days from trade to filing for the 2026 purchases, by report. `C03_disclosure_lag.csv/.txt`
- `C15_insample_betas.py`: Part 2 purchases whose factor betas are estimated in the sample or on 60-249 pre-sample days. `C15_insample_betas.txt`
- `C16_detectable_exact.py`: Table B.7 under the thesis's own p-value rule (counts must reach the smallest integer with p <= 0.05; returns must exceed the 12th largest shifted value), plus the Praised count at the 0.7 cut-off. `C16_detectable_exact.csv/.txt`
- `C22_part1b_search_lower.py`: the Part 1b window search in the lower direction beside the repo's upper search. `C22_part1b_search_lower.txt`
- `C24_untraced_counts.py`: Chapter 5 counts that had no output file (score distribution, label shares, names to companies, v5/v6 agreement, Table 5.2 lots and purchases per day). `C24_untraced_counts.txt`
- `C30_roasted_p_history.py`: Praised and Roasted counts in every committed Part 1 run, read from the git history. `C30_roasted_p_history.txt`
- `B5_roasted_taxloss_as_run.py`: the as-run original of B5 (from the loop worktree, folder `12) LoopChecks/`), unchanged. Its SHA-256 (21a1008a...) is the one recorded in `out/B5_design_sha256_before_run.txt`. `B5_roasted_taxloss.py` is the same design with the folder name in its output title and one word of its header changed (see the diff of the two files). The as-run file was never committed before it was run, so its hash dates the design only by the file's own record, seconds before the output was written.

`out/B5_design_sha256_before_run.txt` records the SHA-256 of the B5 script as run on 2026-11-20,
which is `B5_roasted_taxloss_as_run.py` (added 2026-11-21). The committed `B5_roasted_taxloss.py`
differs from it only in the folder name in its output title and the word "round-2" removed from
its header, so its own hash does not match the recorded one.

## Reviewer cross-checks

Independent checks of the scripts above, written by a second reviewer.

- `review_A/` (outputs in `review_A/out/`): `R2_calendar_adjustment_alternatives.py` (A2 with
  covariance-adjusted and indirectly standardized statistics), `R5_wrap_decomposition.py` (A5 split
  into forward and backward moves), `R6_power_exact.py` (A4/A6 with the exact rejection threshold),
  `R8_symmetric_trim.py` (A8 with the same trim in every world).
- `review_B/` (printed output saved beside each script as `<script>.out.txt`): `rv_b1.py` (B1,
  LPM and Poisson on the same sample), `rv_b2.py` (B2 slopes against world-level exposure and
  small-shift subsets, reads `out/B2_cumulative_treatments.csv`), `rv_b5.py`, `rv_b5_pre.py`, `rv_b5_sales.py` (B5 split by
  prior return, prior Roasted posts and sales; `rv_b5.py` also writes `rv_b5_worlds.csv`).

## Rerun

From the repo root, with the packages in `requirements.txt` and the Git LFS files pulled:

    python "12) AddedChecks/<script>.py"
    python "12) AddedChecks/review_A/<script>.py"
    python "12) AddedChecks/review_B/<script>.py" > "12) AddedChecks/review_B/<script>.out.txt"

Run B2 before `review_B/rv_b2.py`, and C16 before C02. C30 needs the full git history. The other scripts read only the repo's stored outputs and can
run in any order. A full run takes about ten minutes (A7, B1 and B2 take the longest).
