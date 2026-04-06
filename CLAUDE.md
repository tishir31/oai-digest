# OAI Weekly News Digest

## What This Project Is
An automated multi-agent pipeline that produces a weekly email digest of notable OpenAI news for an investment banking team. Delivered as a Gmail draft every Monday morning covering the prior week (Mon-Sun).

## Architecture: Multi-Agent Newsroom
Seven agents with distinct roles, each doing ONE job, running across multiple models:

1. **Reporter** (Claude Code — needs real web search)
   - Skill file: skills/reporter.md
   - Searches web for all OpenAI news from target week
   - Writes to: workspace/raw_items.json
   - Gmail access as supplementary source only (safety net, not primary)
   - Exclude analysis newsletters (Stratechery, Ben Thompson, etc.)

2. **Curator** (Gemini via Antigravity — editorial judgment, no web needed)
   - Skill file: skills/curator.md
   - Filters, deduplicates, categorizes, ranks
   - Reads: workspace/raw_items.json
   - Writes to: workspace/curated_items.json
   - Source diversity report written to: workspace/source_diversity_report.json

3. **Coverage Auditor** (Python script — no model needed)
   - Skill file: skills/coverage_auditor.md
   - Script: workspace/coverage_check.py
   - Checks if Curator output meets coverage floor (default 7 items, no more than 1 empty category)
   - Reads: workspace/curated_items.json
   - Writes to: workspace/coverage_report.json
   - If verdict is "needs_backfill", triggers Backfill Reporter

4. **Backfill Reporter** (GPT / Codex CLI — MUST be different model family from Reporter)
   - Skill file: skills/backfill_reporter.md
   - Only runs if Coverage Auditor says "needs_backfill"
   - Targeted search for stories in gap categories (not a full re-search)
   - Reads: workspace/coverage_report.json + workspace/curated_items.json
   - Writes to: workspace/backfill_items.json
   - Output goes back through Curator → Fact-Checker (max 1 backfill cycle)

5. **Fact-Checker** (Python scripts — no model needed for URL checks)
   - Skill file: skills/fact_checker.md
   - URL verification via Python requests (fact_check_urls.py)
   - Date, freshness, specificity, dedup checks via model (post_checks.py)
   - Reads: workspace/curated_items.json + workspace/historical_log.json
   - Writes to: workspace/verified_items.json + workspace/rejections.json
   - HTTP 403 = likely bot protection, not a rejection (Bloomberg, OpenAI block scripts)

6. **Editor-in-Chief** (Gemini via Antigravity — only one with write access to final output)
   - Skill file: skills/editor_in_chief.md
   - Writes summaries, formats email, updates historical log
   - Reads: workspace/verified_items.json
   - Writes to: output/digest_draft.html + workspace/historical_log.json

7. **Gap Checker** (GPT / Codex CLI — MUST be different model family from Reporter)
   - Skill file: skills/gap_checker.md
   - Reviews completed draft, searches for missed stories
   - Reads: output/digest_draft.html
   - Writes to: workspace/gap_check.json
   - Items found go through Fact-Checker before inclusion

## Key Rules
- Editor-in-Chief is sole committer to output/ — all others propose, only Chief commits
- Multi-model reduces correlated hallucinations (Reporter, Backfill Reporter, and Gap Checker must use different model families)
- Gmail is a SAFETY NET source for Reporter — search web first, check email last, exclude analysis newsletters, always link to original source
- Historical log (workspace/historical_log.json) tracks past digests — Editor-in-Chief MUST diff against last 4 weeks before including any item
- Coverage floor: minimum 7 curated items, no more than 1 empty category — enforced by Coverage Auditor
- One agent, one job — no agent should do work outside its defined role
- Model enforcement is currently honor-system via skill files and workflow — future: enforce in pipeline_automated.py

## Pipeline Enhancements (April 2026)

### Source Diversity Scoring
- Reporter tags each item with source_type (official_blog, press_release, wire_service, tech_press, regulatory_filing, research_preprint, developer_docs, social_media, other)
- Curator checks source_type distribution and flags if >60% from one type or no official sources found

### Temporal Clustering
- Curator groups items covering the same event, keeps best source as primary
- Adds corroboration_count and corroborating_urls to each primary item
- Items with 3+ independent sources get a rank boost

### Historical Dedup (Active)
- Editor-in-Chief reads historical_log.json and rejects items that were already covered in prior 4 weeks
- Genuinely new info about a previously covered topic gets historical_context annotation
- This is the most important quality gate

### Confidence Calibration
- Run workspace/calibrate_confidence.py after each pipeline run
- Tracks whether Reporter's confidence scores actually predict survival through the pipeline
- Saves calibration data to workspace/calibration_log.json for trend tracking

## Categories (in display order — Financials first for IB audience)
1. Earnings / Financials / Fundraising
2. Product Launches & Updates
3. Partnerships & Deals
4. Regulatory & Policy
5. Key Hires / Departures
6. Technical Research / Model Releases

## Current Status
- Reporter: DONE — Claude Code with web search + source_type tagging
- Curator: DONE — source diversity scoring + temporal clustering
- Coverage Auditor: DONE — workspace/coverage_check.py (coverage floor + category gaps)
- Backfill Reporter: DONE — skill file ready, triggered by Coverage Auditor
- Fact-Checker: DONE — Python scripts for URL + post checks
- Editor-in-Chief: DONE — with active historical dedup
- Gap Checker: DONE — skill file ready, needs GPT/Codex CLI configured
- Confidence calibration: DONE — workspace/calibrate_confidence.py
- Pipeline audit log: DONE — workspace/pipeline_audit_log.json
- Orchestration workflow: DONE — .agents/workflows/weekly-digest.md (11 phases)
- Gmail integration: DONE — via Gmail MCP, draft created manually for now
- Automation/scheduling: DEFERRED — reviewing token costs

## Not Yet Implemented
- Model enforcement in code (currently honor-system via skill files)
- GPT/Codex CLI integration for Backfill Reporter and Gap Checker
- Automated Gmail draft creation (currently manual via MCP)
- Scheduled automation (cron/on-demand)
- Generalization to arbitrary topics (OpenAI is currently hardcoded)

## Output Format
Email subject: "OpenAI Weekly Digest — [Date Range]"
Each item: **Headline** (Date) — 1-2 sentence summary. [Source](link)
Grouped by category, ranked by significance within category.
Tone: professional, concise, suitable for senior IB audience.
