---
description: Orchestration notes for the OpenAI News pipeline
---

# OpenAI News Digest Orchestration Workflow

This workflow dictates the exact execution sequence for generating the weekly managing director digest. Each agent does ONE job. Model assignments are mandatory, not suggestions.

## Model Assignments (ENFORCED)

| Agent | Model | Why |
|-------|-------|-----|
| Reporter | Claude Code (Anthropic Max) | Best web search + Gmail MCP |
| Curator | Gemini 3.1 Pro (Antigravity) | Editorial judgment, no web needed |
| Coverage Auditor | Python script | No model needed — pure counting |
| Backfill Reporter | GPT / Codex CLI (OpenAI) | Different family from Reporter to catch blind spots |
| Fact-Checker | Python scripts | No model needed — HTTP + keyword checks |
| Editor-in-Chief | Gemini 3.1 Pro (Antigravity) | Strong writer, free |
| Gap Checker | GPT / Codex CLI (OpenAI) | Different family from Reporter |

---

## Phase 1: Reporter (Claude Code)
Cast a wide net for all notable OpenAI stories from the target week.
- Exhaustive web search: OpenAI blog, news wires, major tech press, SEC filings
- **Final sub-step:** Gmail safety net pass (supplementary only, not primary source)
- **Output:** `workspace/raw_items.json`

## Phase 2: Curator (Gemini 3.1 Pro)
Filter, deduplicate, categorize, rank by IB significance.
- **Input:** `workspace/raw_items.json`
- **Output:** `workspace/curated_items.json` (items array only)
- Source diversity report written separately to `workspace/source_diversity_report.json`

## Phase 3: Coverage Auditor (Python script)
Check whether Curator output meets minimum coverage thresholds.
- **Command:** `python3 workspace/coverage_check.py`
- **Input:** `workspace/curated_items.json`
- **Output:** `workspace/coverage_report.json`
- If verdict is `sufficient` → proceed to Phase 5
- If verdict is `needs_backfill` → proceed to Phase 4

## Phase 4: Backfill Reporter (GPT / Codex CLI)
Targeted search for stories in gap areas identified by Coverage Auditor. Only runs if Phase 3 verdict is `needs_backfill`.
- **Engine:** MUST be a different model family than the Phase 1 Reporter
- **Input:** `workspace/coverage_report.json` + `workspace/curated_items.json`
- **Output:** `workspace/backfill_items.json`
- Backfill items are appended to `workspace/raw_items.json` and re-run through Phase 2 (Curator) and Phase 5 (Fact-Checker)
- **Maximum 1 backfill cycle** — no infinite loops

## Phase 5: Fact-Checker + Feedback Loop (Python scripts)
- Run `workspace/fact_check_urls.py` (HTTP verification)
- Run `workspace/post_checks.py` (date, freshness, specificity, duplicate URL)
- **Output:** `workspace/verified_items.json` + `workspace/rejections.json`
- Run `run_pipeline.py` to check for fixable rejections
- If `workspace/retry_items.json` is created:
  - Re-run Reporter (Claude Code) in retry mode per `skills/reporter.md`
  - Re-run Fact-Checker on the new items
  - Maximum 2 retry cycles, then drop unresolved items
- If no fixable rejections, proceed to Phase 6

## Phase 6: Editor-in-Chief (Gemini 3.1 Pro)
Synthesize verified items into professional, hype-free prose formatted for email.
- **Input:** `workspace/verified_items.json` + `workspace/historical_log.json`
- **Output:** `output/digest_draft.html` + updated `workspace/historical_log.json`
- **MUST** diff against last 4 weeks in historical_log.json before including any item
- Category display order: Financials first, then Product, Partnerships, Regulatory, Hires, Research

## Phase 7: Gap Checker (GPT / Codex CLI)
Independent second-opinion search using a different model family.
- **Engine:** MUST be a different model family than the Reporter
- **Input:** `output/digest_draft.html` (for context)
- **Output:** `workspace/gap_check.json`
- If gap_check.json contains items, they go through Phase 5 (Fact-Checker) before inclusion
- Finding zero gaps is a valid outcome

## Phase 8: Final Fact-Check & Draft Update
Any new stories from Gap Checker run through Fact-Checker. Surviving items appended to digest. Historical log committed.
- **Output:** Final `output/digest_draft.html`
- **Commit:** Update `workspace/historical_log.json` with all included items

## Phase 9: Confidence Calibration (Python script)
Post-pipeline calibration to track Reporter accuracy over time.
- **Command:** `python3 workspace/calibrate_confidence.py`
- **Output:** stdout report + appends to `workspace/calibration_log.json`
- Informational only — does not modify the digest

## Phase 10: Pipeline Audit Log
Append a run entry to `workspace/pipeline_audit_log.json` with item counts, engine assignments, rejection reasons, backfill status, and any fixes applied.

## Phase 11: Delivery
- Create a Gmail draft with contents of `output/digest_draft.html`
- Subject: "OpenAI Weekly Digest — [Date Range]"
- Git commit and push all changes
