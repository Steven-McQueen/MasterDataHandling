# Lessons

- 2026-11-03 (manager): Azure Foundry guardrail sliders read "Lowest blocking" (left) to "Highest
  blocking" (right); "highest blocking" = strictest. I set it to the strictest level by mistake and
  21% of a trial sample was blocked. Rule: after any filter/guardrail change, run 300 texts and
  compare the blocked share with the previous run BEFORE anything else proceeds.

- 2026-11-03 (manager): I approved a ticker rename map entry (EDR -> TKO) from the associate's note
  without verifying it; Endeavor is private, TKO is a different listed company, and the rule then
  auto-assigned 51 rows at a token-set score inflated by generic words. Rules: (1) a map entry is a
  proposal and always goes to review; (2) never approve a company-identity fact without checking it;
  (3) every distinct company-ticker pair gets a recorded review decision, auto-accepted or not.
