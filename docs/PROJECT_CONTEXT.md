# OAI News Digest — Project Context

> **Purpose of this file**: A self-contained context dump that any AI tool (Claude Code, Antigravity, Claude.ai web app) can read to immediately understand the project. Update after material changes — this is the canonical source of truth.

## TL;DR
A multi-agent pipeline producing a weekly OpenAI news digest for senior investment banking professionals (managing directors). Runs Monday morning, covers the prior Mon–Sun. Goal: zero hype, zero broken links, zero stale news. Long-term goal: generalize to any topic.

**Repo**: github.com/tishir31/oai-digest
**Local**: ~/Documents/OAI_News
**Owner**: Tishir (IB analyst, treats AI as contractor and self as architect)

---

## Architecture

```
Reporter (Claude Code)
    ↓ raw_items.json
Curator (Gemini 3.1 Pro / Antigravity)
    ↓ curated_items.json + source_diversity_report.json
Coverage Auditor (Python script)
    ↓ coverage_report.json
    ├─ if needs_backfill ─→ Backfill Reporter (Codex CLI) ─→ loop back to Curator (max 1 cycle)
    └─ if sufficient ─→
Fact-Checker (Python: fact_check_urls.py)
    ↓ verified_items.json + rejections.json
    └─ if fixable rejections ─→ run_pipeline.py → retry loop (max 2 cycles)
Editor-in-Chief (Gemini 3.1 Pro / Antigravity)
    ↓ digest_draft.html + historical_log.json (appended)
Gap Checker (Codex CLI — different model family)
    ↓ gap_check.json
    └─ if items found ─→ Fact-Checker → Editor-in-Chief
Confidence Calibration (Python: calibrate_confidence.py)
    ↓ calibration_log.json
Pipeline Audit Log (Python: log_pipeline_run.py)
    ↓ pipeline_audit_log.json
Delivery: Gmail draft + git push
```

### Model Assignments (ENFORCED via skill files; not yet via code)

| Agent | Model | Why |
|-------|-------|-----|
| Reporter | Claude Code (Anthropic Max) | Best web search + Gmail MCP |
| Curator | Gemini 3.1 Pro (Antigravity) | Editorial judgment, no web needed, free |
| Coverage Auditor | Python | No model needed |
| Backfill Reporter | Codex CLI (OpenAI sub) | DIFFERENT family from Reporter — catches blind spots |
| Fact-Checker | Python | HTTP requests + keyword matching |
| Editor-in-Chief | Gemini 3.1 Pro (Antigravity) | Strong writer, free |
| Gap Checker | Codex CLI (OpenAI sub) | DIFFERENT family from Reporter |

**Why multi-model**: Same model has correlated blind spots — using different families (Claude + Codex) catches stories one model alone would miss.

---

## Key Design Rules

1. **One agent, one job.** Each agent has exactly one responsibility. No agent does work outside its defined role.
2. **Editor-in-Chief is the only writer to `output/`.** All other agents propose; only the Chief commits.
3. **Reporter and Backfill/Gap Checkers MUST use different model families.** Reduces correlated hallucinations.
4. **Gmail is a SAFETY NET only.** Reporter searches the web first; checks email last; excludes analysis newsletters; always links to the original source, not the email.
5. **Historical log dedup is the most important quality gate.** Editor-in-Chief diffs every item against the last 4 weeks of `historical_log.json`. Genuinely new info on previously covered topics gets a "Follow-up" annotation; pure duplicates are rejected.
6. **HTTP 403 ≠ broken URL.** Sites like Bloomberg and OpenAI block bot requests. Treat 403 as likely-valid, recommend manual verification.
7. **Coverage floor: 7 items minimum, no more than 1 empty category.** Coverage Auditor enforces; if violated, Backfill Reporter runs (max 1 cycle).
8. **Confidence scoring must discriminate.** Reporter rates `high` only for official sources or 2+ corroborating outlets. >70% `high` triggers calibration warning.
9. **Display order favors IB audience: Financials FIRST**, then Product, Partnerships, Regulatory, Hires, Research.

---

## File Structure

```
~/Documents/OAI_News/
├── CLAUDE.md                           # Instructions for Claude Code sessions
├── docs/
│   └── PROJECT_CONTEXT.md              # THIS FILE — canonical context
├── skills/                             # Agent skill files (instructions)
│   ├── reporter.md
│   ├── curator.md
│   ├── coverage_auditor.md
│   ├── backfill_reporter.md
│   ├── fact_checker.md
│   ├── editor_in_chief.md
│   └── gap_checker.md
├── .agents/workflows/weekly-digest.md  # Original workflow (Markdown)
├── .antigravity/                       # Antigravity-specific configs
│   ├── agents/                         # YAML wrapper agent definitions
│   │   ├── reporter.yaml               # → wraps `claude` CLI
│   │   ├── curator.yaml                # → uses Antigravity native Gemini
│   │   ├── coverage_auditor.yaml       # → wraps python script
│   │   ├── backfill_reporter.yaml      # → wraps `codex` CLI
│   │   ├── fact_checker.yaml           # → wraps python scripts
│   │   ├── editor_in_chief.yaml        # → uses Antigravity native Gemini
│   │   └── gap_checker.yaml            # → wraps `codex` CLI
│   └── workflows/weekly-digest.yaml    # Antigravity workflow definition
├── workspace/                          # Pipeline data (machine-readable)
│   ├── raw_items.json                  # Reporter output
│   ├── curated_items.json              # Curator output (items only)
│   ├── source_diversity_report.json    # Curator metadata (separate file)
│   ├── coverage_report.json            # Coverage Auditor verdict
│   ├── verified_items.json             # Fact-Checker passed items
│   ├── rejections.json                 # Fact-Checker rejected items
│   ├── gap_check.json                  # Gap Checker output
│   ├── historical_log.json             # Cumulative record (all past digests)
│   ├── calibration_log.json            # Confidence calibration history
│   ├── pipeline_audit_log.json         # Per-run step summaries
│   ├── fact_check_urls.py              # URL verification script
│   ├── coverage_check.py               # Coverage Auditor script
│   ├── calibrate_confidence.py         # Calibration script
│   └── log_pipeline_run.py             # Audit log writer
├── output/
│   └── digest_draft.html               # Final email body
├── run_pipeline.py                     # Feedback loop handler
└── pipeline_automated.py               # Future: full automation entry point
```

---

## Agent Skill File Structure

Each `skills/*.md` file follows this template:

```markdown
# {Name} Agent Skill

## Role
{Single-sentence description of the agent's one job}

## Engine
{Which model/script must run this agent}

## Input
- {Input file paths}

## Output
- {Output file paths}

## Tasks
{Numbered list of what the agent does, in order}

## Output Schema
{JSON shape of the output}

## Quality Rules
{What the agent must never do}

## What This Agent Does NOT Do
{Explicit non-responsibilities — prevents scope creep}
```

---

## Pipeline Enhancements (April 2026)

### Source Diversity Scoring
- Reporter tags each item with `source_type` (one of 9: official_blog, press_release, wire_service, tech_press, regulatory_filing, research_preprint, developer_docs, social_media, other)
- Curator computes distribution and writes to `source_diversity_report.json` (separate file, NOT inside the items array)
- Warning fires if any single type exceeds 60% or no official sources are present

### Temporal Clustering
- Curator groups items covering the same event, picks the best source as primary
- Adds `corroboration_count` and `corroborating_urls` to each primary
- Items with 3+ independent sources get a rank boost
- **Never include the primary's own URL in `corroborating_urls` (self-reference bug)**

### Historical Dedup
- Editor-in-Chief reads `historical_log.json` and rejects items already in the prior 4 weeks
- Genuinely new info on previously covered topics gets a "Follow-up" annotation
- This is the single most important quality gate

### Coverage Auditor + Backfill Reporter
- Coverage Auditor runs after Curator: counts items, checks category distribution
- If verdict is `needs_backfill`, Backfill Reporter (different model family) does a targeted gap search
- Maximum 1 backfill cycle to prevent infinite loops

### Confidence Calibration
- `calibrate_confidence.py` runs after the digest is drafted
- Tracks whether Reporter's `confidence` ratings predict actual survival through the pipeline
- Flags overconfidence: if >85% of items rated `high`, or if `medium` survives better than `high`

### Pipeline Audit Log
- `log_pipeline_run.py` reads all output files and writes a structured per-run summary to `pipeline_audit_log.json`
- Lets you answer "what did the pipeline do this week" without re-reading every file

---

## Lessons Learned

### Lesson 1: Multi-model orchestration is about correlated blind spots
A second pass with the same model finds the same things it found the first time, missing the same things it missed. The whole point of using Codex for the Gap Checker isn't quality — it's *uncorrelation*. Different training data, different search patterns, different blind spots.

### Lesson 2: Schema bugs hide in plain sight
The Curator generated by Gemini put a `source_diversity` object as the last element of the items array — structurally invalid, would have broken any downstream code that loops `for item in items`. Lesson: define output schemas explicitly in skill files, and have a Python validator (not the model) check the structure.

### Lesson 3: Self-references in corroboration data
Twice now, the Curator has listed an item's own URL inside its `corroborating_urls`. This isn't corroboration. Fix is in the skill file (explicit "never include the primary's own URL"), but a Python validator catching this at the boundary would be more reliable.

### Lesson 4: Reporter overconfidence is a real failure mode
First run: 16/17 items rated "high" confidence. The field provided zero discrimination. Fix: explicit rubric in `skills/reporter.md` (`high` only for official sources or 2+ outlets, `medium` for single source, `low` for unconfirmed) plus a self-check trigger at >70% high. Calibration script now flags overconfidence.

### Lesson 5: Stale workspace files pollute audit logs
The Gap Checker wrote `gap_check.json` last week. The next week's audit log script picked it up and reported "5 gaps found" — but those gaps were from last week's digest. Each agent should clear its output file at the start of a run. Until that's enforced, archive stale files manually.

### Lesson 6: HTTP 403 is not a failure
Bloomberg, OpenAI, and several other quality sources block automated requests. The Fact-Checker treats 403 as likely-valid and flags for manual review. Don't reject items based on 403 alone.

### Lesson 7: Curator's clustering decisions are subjective
The Curator decides whether two related items get clustered (e.g., the four executive-reshuffle stories on April 3 became one clustered item). This is a judgment call — there's no algorithm. Document the clustering rationale in `curator_notes` so future runs are auditable.

### Lesson 8: Antigravity does NOT use local CLIs natively
Antigravity routes its agents through Google's brokered model fleet (free Gemini, free Claude Opus 4.6 Thinking, GPT-OSS 120B). It does NOT call your local `claude`/`codex`/`gemini` CLIs.

To use your existing subscriptions inside Antigravity, the workaround is the **wrapper pattern**: create an Antigravity agent with a cheap coordinator model (Gemini Flash) whose only job is to execute a terminal command (`claude -p ...` or `codex -p ...`) via the Terminal surface. The actual reasoning happens inside the CLI subprocess. Antigravity manages orchestration; your subscription pays for the inference.

This requires the **Terminal Command Auto Execution** allow-list to include `claude`, `codex`, and `python3 workspace/`.

### Lesson 9: One-agent-one-job prevents scope creep
The temptation is to bolt new logic onto an existing agent ("the Curator should also check coverage"). Resist it. Adding the Coverage Auditor as a separate agent — with its own skill file, its own output, and its own pass/fail verdict — keeps each piece testable in isolation.

### Lesson 10: The non-determinism of Reporter runs
Two runs of the same Reporter on the same week produce overlapping but not identical sets of items. This week: one run found CFO Friar/Model Spec/Visual Product Discovery; another found Secondary Market $765B/Standard Voice Mode/Dresser elevation as standalone. The fix is to **union** the results across runs and let the Curator dedup, not to treat any single Reporter output as canonical.

---

## Open Issues / Not Yet Implemented

| Issue | Impact | Priority |
|-------|--------|----------|
| Model enforcement is honor-system | Wrong model could run an agent without anyone noticing | Medium — fix in `pipeline_automated.py` |
| `post_checks.py` is missing | Date/freshness/specificity checks aren't running, only URL checks | Medium — write the script |
| Gap Checker hasn't been wired into a real run | Have skill file + agent YAML, no actual GPT/Codex execution yet | High — needs Antigravity Terminal allow-list configured |
| Stale workspace files | Each agent should clear its output file at start of run | Low — manual archiving works for now |
| Reporter overconfidence | 75% high this week, just at threshold; calibration script flags >85% | Low — fixed for next run via skill file update |
| Antigravity YAML schema | Best-guess structure based on tutorials; may need adjustment | Medium — test on first real run |
| Two workflow files | Old `.agents/workflows/weekly-digest.md` + new `.antigravity/workflows/weekly-digest.yaml` | Low — delete old after new is verified |

---

## Run History Snapshot

| Week | Run Date | Reporter | Curator Kept | Verified | In Digest | Notes |
|------|----------|----------|--------------|----------|-----------|-------|
| 2026-03-22 to 03-28 | 2026-03-29 | 17 | 17 | 17 | 17 | First run, no historical dedup possible |
| 2026-03-31 to 04-05 (v1) | 2026-04-06 | 17 | 11 | 11 | 11 | First run with enhancements; structural bugs found and fixed in audit |
| 2026-03-31 to 04-05 (v2) | 2026-04-08 | 20 | 13 | 13 | 13 | Fresh re-run after Antigravity test; supplemented missing items |

---

## Quick Reference: How to Run

### Manual (current state)
```bash
cd ~/Documents/OAI_News
# Step 1: Reporter — run Claude Code with skills/reporter.md as the prompt
# Step 2: Curator — run Gemini in Antigravity with skills/curator.md
# Step 3: Coverage check
python3 workspace/coverage_check.py
# Step 4: Fact check
python3 workspace/fact_check_urls.py
# Step 5: Editor-in-Chief — run Gemini in Antigravity with skills/editor_in_chief.md
# Step 6: Gap check (when enabled) — run Codex CLI with skills/gap_checker.md
# Step 7: Calibration
python3 workspace/calibrate_confidence.py
# Step 8: Audit log
python3 workspace/log_pipeline_run.py
# Step 9: Manually create Gmail draft from output/digest_draft.html
# Step 10: git add, commit, push
```

### Automated (Path B — Antigravity wrapper, planned)
1. Open Antigravity → Cmd+Shift+M (Agent Manager)
2. Run `weekly-digest.yaml` workflow with target_week_start and target_week_end inputs
3. Antigravity orchestrates each agent step in sequence
4. Each wrapper agent calls the appropriate CLI (`claude` for Reporter, `codex` for Backfill/Gap, etc.)
5. Final digest appears in `output/digest_draft.html`; manual review then send

---

## Future Direction

1. **Generalize beyond OpenAI** — abstract "OpenAI" to a configurable target topic so the same pipeline can produce digests for other companies/themes
2. **Full automation** — `pipeline_automated.py` becomes the orchestration entry point with hardcoded model assignments (true model enforcement)
3. **Scheduling** — cron job or on-demand trigger from phone
4. **Feedback loop** — capture which items the human reader actually engaged with, feed back into Curator ranking
5. **Multi-week trend analysis** — read across `historical_log.json` to surface multi-week storylines
