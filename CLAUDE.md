# OAI Weekly News Digest

## What This Project Is
An automated multi-agent pipeline that produces a weekly email digest of notable OpenAI news for an investment banking team. Delivered as a Gmail draft every Monday morning covering the prior week (Mon-Sun).

## Architecture: Multi-Agent Newsroom
Four agents with distinct roles, running across multiple models:

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

3. **Fact-Checker** (Python script + model for editorial checks)
   - Skill file: skills/fact_checker.md
   - URL verification via Python requests (fact_check_urls.py)
   - Date, freshness, specificity, dedup checks via model (post_checks.py)
   - Reads: workspace/curated_items.json + workspace/historical_log.json
   - Writes to: workspace/verified_items.json + workspace/rejections.json
   - HTTP 403 = likely bot protection, not a rejection (Bloomberg, OpenAI block scripts)

4. **Editor-in-Chief** (master agent — only one with write access to final output)
   - Skill file: skills/editor_in_chief.md
   - Writes summaries, formats email, updates historical log
   - Reads: workspace/verified_items.json
   - Writes to: output/digest_draft.html + workspace/historical_log.json

## Key Rules
- Editor-in-Chief is sole committer to output/ — all others propose, only Chief commits
- Multi-model reduces correlated hallucinations (Reporter and Fact-Checker must use different model families)
- Gmail is a SAFETY NET source for Reporter — search web first, check email last, exclude analysis newsletters, always link to original source
- Historical log (workspace/historical_log.json) tracks past digests — Editor-in-Chief MUST diff against last 4 weeks before including any item
- Target: all notable items (no forced minimum, but exhaustive search)

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

## Categories (in display order)
1. Product Launches & Updates
2. Partnerships & Deals
3. Earnings / Financials / Fundraising
4. Regulatory & Policy
5. Key Hires / Departures
6. Technical Research / Model Releases

## Current Status
- Phase 1 (Scaffold): DONE
- Phase 2 (Reporter): DONE — Claude Code with web search + source_type tagging
- Phase 3 (Curator): DONE — source diversity scoring + temporal clustering
- Phase 4 (Fact-Checker): DONE — Python scripts for URL + post checks
- Phase 5 (Editor-in-Chief): DONE — with active historical dedup
- Confidence calibration: DONE — workspace/calibrate_confidence.py
- Phase 6 (Orchestration workflow): NOT STARTED
- Phase 7 (Gmail integration): NOT STARTED
- Phase 8 (Automation/scheduling): DEFERRED — reviewing token costs

## Not Yet Implemented
- Access control enforcement (currently honor-system via skill files)
- Feedback loop (Fact-Checker → Reporter rejections, max 2 iterations)
- Gmail MCP integration in pipeline
- Scheduled automation
- Claude Code + Codex CLI integration inside Antigravity

## Output Format
Email subject: "OpenAI Weekly Digest — [Date Range]"
Each item: **Headline** (Date) — 1-2 sentence summary. [Source](link)
Grouped by category, ranked by significance within category.
Tone: professional, concise, suitable for senior IB audience.
