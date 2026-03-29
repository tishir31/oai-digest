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
- **Output:** `workspace/curated_items.json`

### Step 3: Fact-Checker + Feedback Loop (Python scripts + Claude Code)
- Run workspace/fact_check_urls.py (HTTP verification)
- Run workspace/post_checks.py (date, freshness, specificity, duplicate URL)
- Output: workspace/verified_items.json + workspace/rejections.json
- Run run_pipeline.py to check for fixable rejections
- If workspace/retry_items.json is created:
  - Re-run Reporter (Claude Code) in retry mode per skills/reporter.md
  - Re-run Fact-Checker on the new items
  - Maximum 2 retry cycles, then drop unresolved items
- If no fixable rejections, proceed to Step 4

## Phase 4: Editor-in-Chief (Initial Draft)
The master agent synthesizes the verified components into precise, professional, hype-free prose formatted for email delivery.
- **Input:** `workspace/verified_items.json`
- **Output:** `output/digest_draft.html`

## Phase 5: Gap Checker
A secondary, independent model (e.g. GPT/Codex instead of Claude) reviews the draft to catch blind spots like developer docs, regulatory filings, or GitHub PRs.
- **Input:** `output/digest_draft.html` (for context)
- **Output:** `workspace/gap_check.json`

## Phase 6: Final Fact-Check & Log Commit
Any new stories found by the Gap Checker run through the Fact-Checker again. All surviving items are appended to the digest, and the historical record is officially committed.
- **Output:** Final HTML sent to managing directors.
- **Commit:** Update `workspace/historical_log.json` with all included items to ensure deduplication on future runs.
