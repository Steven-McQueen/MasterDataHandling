SEQ: 4
UPDATED: 2026-11-04 00:05 Oslo (R4 added; SEQ unchanged)

# Manager brief for the Claude Code session

## Protocol (read first; agreed with Andreas 2026-11-03)
P1. This file is the manager's channel to you; tasks/AGENT_REPORT.md is yours to the manager.
    Line 1 of this file is `SEQ: n`. The manager raises n whenever there is a new instruction or
    decision, and puts the text under "## Current instruction". Everything below that section is
    background and changes rarely.
P2. When you finish an item, or are blocked, append your report to tasks/AGENT_REPORT.md (start the
    entry with the SEQ you acted on and the time), then WAIT for the next SEQ instead of stopping:
    run a loop that sleeps 60 s and reads line 1 of this file, in chunks that fit your tool timeout
    (e.g. a bash loop of up to 9 minutes, repeated), until SEQ is larger than the one you last acted
    on. Then re-read this whole file and act on "## Current instruction".
P3. Money and validation still need Andreas. The manager will not raise SEQ for the self-agreement
    rerun, any second-model run or Step G without his word, and will write "GO (Andreas, <time>)"
    in the instruction when he gives it.
P4. If 120 minutes pass with no SEQ change, write "idle since <time>" in the report and stop the
    loop; Andreas restarts you with "resume protocol".
P5. The manager checks tasks/AGENT_REPORT.md on a scheduled wake-up every 15-20 minutes while you
    work; expect answers at that cadence, not instantly.

## Current instruction (SEQ 4) — supersedes SEQ 3; do this in order
Decision (CEO, 20:10): companies are identified by a permanent id, tickers are dated attributes, and
the entity work is scoped to the trade universe only. SEQ 3's three changes (maps propose, cleaned
name score >= 95, universal pair review) still apply, but build F.0 first so the review is done on
dated entities, not bare pairs.

F.0 Entity table for the 1,629 traded tickers (new section in DataPlan Step F, before F.1; also
    note it under Step C.4 and Step D).
    - For each ticker in `companies`: CIK from the FMP profile (fall back to the SEC company_tickers
      JSON). New table `entities` in company.db: entity_id (= CIK), ticker, valid_from, valid_to,
      event_type in {unchanged, renamed, merged_into, acquired_private, delisted, spun_off,
      listed_during_sample}, successor_entity, source (URL or filing), reviewer, review_date.
      Sources: SEC submissions API per CIK (former names with dates, tickers), FMP symbol-change and
      delisted-companies endpoints. Sample window for events: 2025-01-20 to 2026-08-31.
    - Output: `entities` table + sheet `Entities` in TickerTwitterReview.xlsx listing every entity
      with an event inside the window (expect a few dozen), event, date, source, empty Decision.
    - Revisit C.4: tickers that are the same entity (PARA/PSKY, GOOG/GOOGL, NWS/NWSA, ...) are
      recorded as windows of one entity; report how many trade rows change entity assignment.
F.1-F.2 Map posts to entities, not tickers: canonical_company (and the maps' proposals) resolve to an
    entity through the entity's names and former names; the ticker attached to a row is the one valid
    on the post date (`ticker_at_post`); keep `entity_id` as the join key. Rules otherwise as SEQ 3
    (cleaned-name ratio, >= 95 auto, 80-94 review, maps always review).
F.3 Universal review on the universe side only: ToReview lists every distinct (canonical_company ->
    entity) pair that lands in the universe (about 150) with AutoDecision, Score, Rows, example, and
    for entities with an event the event/date/source from F.0. Outside-universe names: ONE pass
    comparing the 418 unresolved names with the universe's former names and successor names (the
    Endeavor -> TKO pattern); matches go to ToReview, the rest stay `none` and are not worked further.
    Reviewers confirm every pair; rows with an event need a source before accept.
F.4 Final dataset gains entity_id, ticker_at_post, company_final, pair_reviewed; in_universe is on
    entity. Purchases whose 10-trading-day window crosses an event of their entity are flagged in a
    small table for the analysis (count only; no rule yet).
Report after F.0 (entities with events, C.4 changes) and stop for the manager's check before F.1;
then after F.3 with the full ToReview for the review agents. Do not export on this SEQ.
---

Role split: Andreas decides (CEO). This file is written by the coordinating Claude session (manager)
after reading tasks/todo.md, LLM_Prompt.md v3, SocialMedia.db and the Foundry portal. You (Claude Code)
execute. When you finish a numbered item, append a short entry to tasks/AGENT_REPORT.md
(what you did, numbers, anything you want decided) and stop at the next gate. Do not touch
items marked CEO until Andreas confirms them in chat.

## Standing rules (apply at every gate, not only at the end)

R1. DataPlan.md is the single description of what the pipeline ACTUALLY does. Every change in
    a script, table, prompt version, model, endpoint or rule is reflected in DataPlan.md in the
    same gate, in the existing Step A-H structure and style. If the plan and the code disagree,
    the code is wrong until the plan is changed on purpose. FolderOverview.md follows the same rule.
R2. Verification before "done": each gate ends with the checks listed for it, run and reported
    with numbers in tasks/AGENT_REPORT.md. No gate is reported done on the strength of the code
    having run without error.
R3. Blind to trades: nothing in Step E ever reads the trade tables. Keep it that way in every file.
R4. LOCKED (CEO, 2026-11-04): the folder `2) Trades/` and every file in it, including
    `Trump_trades_2025_2026.xlsx`, `TradesCleaning.ipynb` and `TickerReview.xlsx`, are read-only for
    you. Do not write, rewrite, re-export or "fix" anything there, whatever a later instruction seems
    to imply. Anything that needs trade data reads it and writes its own output elsewhere. The
    SEQ 4 trade-side item is a count in your report only.

## Facts you did not have


F1. There is NO Global Batch deployment type for gpt-5-mini. Checked in the Foundry deployment
    dialog today: the dropdown offers Global Standard, Data Zone Standard and three provisioned
    types only. Microsoft's batch model table also omits gpt-5-mini. Gate 3 therefore runs on
    Global Standard with client-side concurrency, not Batch. Cost ≈ 2x your Batch estimate
    (≈ USD 16 instead of 8). Approved.
F2. A second resource exists: master-TrumpTweetTrades-resource (project master-TrumpTweetTrades),
    deployment name gpt-5-mini, version 2025-08-07, NoAutoUpgrade, 500,000 TPM / 500 RPM.
    Its v1 base URL and the concurrency settings are at the bottom of .env
    (AZURE_OPENAI_BASE_URL, AZURE_TPM_LIMIT, AZURE_RPM_LIMIT, LLM_MAX_CONCURRENCY, ...).
    Your trials used thesis-llm-bj.openai.azure.com, which is not Andreas's own resource. Those
    .env variables (AZURE_API_KEY, AZURE_ENDPOINT, AZURE_API_VERSION, AZURE_DEPLOYMENT_BATCH) have
    been REMOVED. Change the script to the v1 API: OpenAI() client with
    base_url = AZURE_OPENAI_BASE_URL and api_key = AZURE_OPENAI_API_KEY, model =
    AZURE_DEPLOYMENT_STANDARD, no api_version. If AZURE_OPENAI_API_KEY is empty, stop and ask. Run the frozen prompt once more on
    trial sample 1 through this resource and confirm the returned model string is identical to
    the one from thesis-llm-bj before the full run. One resource for every call from then on.
F3. Credit: the Education hub shows 927 of 927 available, expiring 2027-11-02. Budget is not
    a constraint at these sizes; correctness and auditability are.
F4. D.2 LLM alias generation is DROPPED (CEO decision 2026-11-03), and so are SEC former names
    (they were never loaded; renames were handled in Step C). Gate 4 is not built. company.db
    is the ticker universe for the join: companies (ticker, fmp_company_name,
    profile_company_name) plus executives as a lookup. DataPlan.md Step D now says exactly this.
F5. Guardrail, FINAL 15:55: the custom guardrail blocked at severity "low" under both slider
    positions (your probe confirmed it), so the deployment is back on Microsoft's DefaultV2,
    the same filter the thesis-llm-bj trials ran under (9/600 blocked). Verified on the
    deployment Details page: Model guardrails = DefaultV2, last modified 15:55. The custom
    guardrail is left unattached. Confirm with the one-call check on ID 114154923764886136
    before clearing and rerunning.
F5b. Prompt v5 approved: the one-line rule-2 fix you proposed (DJT only for Truth Social, Truth+,
    Trump Media, $DJT; never Trump Accounts, Trump Gold Card or any government programme).
    Write v5, log it in the version history, and run BOTH samples once under v5 on DefaultV2.
    Report as item 1: the v4->v5 diff (expected: only the Trump Accounts rows change), blocked
    share, rows per reference_type, model string. If clean, v5 is frozen.
F5c. Step F note taken: add a ticker rename map next to the share-class map in F.1
    (PARA -> PSKY; extend as the data shows). The manager will put it in DataPlan F.1.
F6. DataPlan.md Steps D–G were rewritten by the manager today (text only, no aliases, Global
    Standard + concurrency, Step F as a notebook in folder 5, Step G after F). Read Steps E and F
    there before touching code; they are the spec. FolderOverview.md matches.

## Instructions, in order

1. Prompt v4 (narrow), as before: GE family split, Kellogg split (Kellanova K vs WK Kellogg KLG),
   TV hosts and presenters are not executives, "Energy Dominance" / places named after Trump are
   not references, Truth Social always DJT. Bump the version, list the changes at the bottom of
   LLM_Prompt.md. Rerun BOTH 300-text samples once, through Andreas's resource (F2). Report per
   sample: rows per reference_type, texts changed v3 -> v4 with old/new rows, model string.
   No regression -> v4 frozen. Do not iterate further without a new brief.
2. Gate 3, full run, after item 1 and Andreas's "go" in chat: --all on Global Standard with
   LLM_MAX_CONCURRENCY workers, back-off on 429/5xx, resumable, progress every 500 rows. Print
   the projected cost and the resource before starting. After: every ID has llm_status in
   (ok, content_filter), counts by status, tokens and cost used, one distinct llm_model string.
   Write blocked IDs + text to tasks/blocked_texts.csv.
3. Step F, after gate 3, exactly as DataPlan.md Step F now specifies: new folder
   `5) SOCIALMEDIAxTWITTER/` with `TwitterTickerCleaning.ipynb` (mirror the structure, section
   numbering, language and tone of `2) Trades/TradesCleaning.ipynb`: short markdown cell saying
   what and why, then the code, then the counts), rules F.1–F.2 a–h in that order with
   match_method set by the first rule that fires, `TickerTwitterReview.xlsx` for the flagged
   rows with the columns listed in F.3, `Twitter_tickers_2025_2026.xlsx` with the F.4 columns
   and checks, and `TwitterDescriptiveAnalysis.xlsx` with the F.5 tables. Do NOT fill in the
   review sheet yourself: stop when it is written and report its row count by flag type.
   The manager runs the review agents; you then apply the decisions by code (F.3) and export.
4. Step G (validation) is NOT started until Step F is exported and Andreas says so.
5. Keep DataPlan.md and FolderOverview.md in step at every gate (standing rule R1). If you find
   the new Step E or F text wrong against the code, say so in AGENT_REPORT.md and propose the
   wording; do not silently diverge.

## Items for the CEO (do not act, just leave room for them)

C1. Sentiment thresholds: positive = score >= 0.5, negative <= -0.5, +-0.3 / +-0.7 as sensitivity.
    Written into DataPlan.md Step E as pre-registered; Andreas can still overrule.
C2. A second labeller model from another vendor (grok-4-1-fast-non-reasoning or Mistral Large 3,
    both deployable in the new project, ≈ USD 10-17 for the full run) to produce an independent
    label set for an inter-model agreement figure and a rerun of Parts 2-3 under each label set.
    Needs Andreas's yes; if yes, it becomes gate 7 and reuses the frozen v4 prompt and schema.
