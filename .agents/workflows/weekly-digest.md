---
description: Orchestration notes for the OpenAI News pipeline
---

# OpenAI News Digest Orchestration Workflow

This workflow dictates the exact execution sequence for generating the weekly managing director digest.

## Phase 1: Reporter
The Reporter agent casts a wide net to find all notable OpenAI stories from the past week.
- Perform exhaustive web searches (OpenAI blog, news wires, major tech press, SEC filings).
- **Final Sub-step:** **Gmail Safety Net Pass**. (Check Gmail to verify nothing major was missed. Important: This is explicitly the final sub-step of the Reporter phase, not a standalone phase).
- **Output:** `workspace/raw_items.json`

## Phase 2: Curator
The assignment editor filters fluff, scores signal-to-noise, and ranks items by significance for an investment banking audience.
- **Input:** `workspace/raw_items.json`
- **Output:** `workspace/curated_items.json` (items array only — source_diversity written to `workspace/source_diversity_report.json`)

### Phase 3: Fact-Checker + Feedback Loop (Python scripts + Claude Code)
- Run workspace/fact_check_urls.py (HTTP verification)
- Run workspace/post_checks.py (date, freshness, specificity, duplicate URL)
- Output: workspace/verified_items.json + workspace/rejections.json
- Run run_pipeline.py to check for fixable rejections
- If workspace/retry_items.json is created:
  - Re-run Reporter (Claude Code) in retry mode per skills/reporter.md
  - Re-run Fact-Checker on the new items
  - Maximum 2 retry cycles, then drop unresolved items
- If no fixable rejections, proceed to Phase 4

## Phase 4: Editor-in-Chief (Initial Draft)
The master agent synthesizes the verified components into precise, professional, hype-free prose formatted for email delivery.
- **Input:** `workspace/verified_items.json` + `workspace/historical_log.json`
- **Output:** `output/digest_draft.html` + updated `workspace/historical_log.json`
- **MUST** diff against last 4 weeks in historical_log.json before including any item

## Phase 5: Gap Checker
A secondary, independent model (e.g. GPT/Codex instead of Claude) reviews the draft to catch blind spots like developer docs, regulatory filings, or GitHub PRs.
- **Engine:** Must use a DIFFERENT model family than the Reporter (e.g., if Reporter is Claude, Gap Checker should be GPT/Codex)
- **Input:** `output/digest_draft.html` (for context)
- **Output:** `workspace/gap_check.json`
- If gap_check.json contains items, they must go through Phase 3 (Fact-Checker) before inclusion

## Phase 6: Final Fact-Check & Draft Update
Any new stories found by the Gap Checker run through the Fact-Checker again. All surviving items are appended to the digest, and the historical record is officially committed.
- **Output:** Final `output/digest_draft.html`
- **Commit:** Update `workspace/historical_log.json` with all included items

## Phase 7: Confidence Calibration
Run the post-pipeline calibration script to track Reporter accuracy over time.
- **Command:** `python3 workspace/calibrate_confidence.py`
- **Output:** stdout report + appends to `workspace/calibration_log.json`
- This phase is informational — it does not modify the digest

## Phase 8: Pipeline Audit Log
Append a run entry to `workspace/pipeline_audit_log.json` with item counts, engine assignments, rejection reasons, and any fixes applied.

## Phase 9: Delivery
- Create a Gmail draft with the contents of `output/digest_draft.html`
- Subject: "OpenAI Weekly Digest — [Date Range]"
- Git commit and push all changes
