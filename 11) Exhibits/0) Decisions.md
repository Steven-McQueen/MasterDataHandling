# Step 11, exhibits: decisions

Fixed on 2026-11-09. The exhibit list is the kokebok's (step 12, Exhibits), with the sample table and the Part 1 table from the build plan's list of results. Exhibits are drawn from the outputs of Steps 2 to 10; nothing is estimated again here, except the Part 2 gap between Praised and Roasted hits, which the kokebok asks for (step 8, item 5) and which is computed from Part 2's world table.

## Exhibits
| File | Chapter | Content | Source |
|---|---|---|---|
| `tab_sample` | 4 Data | purchases, companies, amounts; posts by account | `2) Trades`, `1) SocialMedia`, `9) Part3Returns/1) Returns` |
| `tab_part1` | 6 Results | Part 1: slope, shifted mean, p-values and mention-days per window | `7) Part1Talk` |
| `fig_part2_worlds` | 6 Results | Part 2: luck counts with the real count marked, any / Praised / Roasted | `8) Part2Timing` |
| `tab_part2` | 6 Results | Part 2: hits, luck mean, excess, p-values, and the Praised − Roasted gap | `8) Part2Timing` |
| `fig_part3_groups` | 6 Results | Part 3: luck return per dollar per group with the real one marked | `9) Part3Returns` |
| `tab_part3` | 6 Results | Part 3: return per dollar, excess and p per group; gap tests and Posted dollar total | `9) Part3Returns` |
| `tab_contributors` | 6 Results | the ten largest contributions to the Posted dollar excess | `9) Part3Returns` |
| `tab_robustness` | 7 Robustness | Posted group under each check beside the main result | `10) Checks` |
| `fig_horizons` | 7 Robustness | Posted return per dollar by horizon, real against the shifted worlds | `10) Checks` |
| `tab_models` | 7 Robustness | Posted group under the five return models | `10) Checks` |

## Format
- Tables: LaTeX with `booktabs` (one `table` environment per file, with caption, label and a note) and the same numbers as CSV.
- Figures: vector PDF, one style for all (grey for the shifted worlds, orange for the real value), 6.3 inches wide to fit the text width.
- Numbers: British style with "we"; p-values to three decimals; dollar amounts with thousands separators. Returns per dollar and excess returns are given to two decimals, because the differences are a few hundredths of a percentage point.
- Labels: `tab:` and `fig:` followed by the file name without its prefix (for example `tab:part3`).
