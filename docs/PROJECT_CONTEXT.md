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
Coverage Check₁ (Python: coverage_check.py)
    ↓ coverage_report.json
    ├─ if needs_backfill ─→ Backfill Reporter (Codex CLI) ─→ loop back to Curator (max 1 cycle)
    └─ if sufficient ─→
Fact-Checker (Python: fact_check_urls.py)
    ↓ verified_items.json + rejections.json
    └─ if fixable rejections ─→ run_pipeline.py → retry loop (max 2 cycles)
Post-Checks (Python: post_checks.py)
    ↓ filters stale/continuation items + duplicate URLs from verified_items.json
Coverage Check₂ (Python: coverage_check.py — RE-RUN after post_checks)
    ├─ if post_checks hollowed out categories ─→ Backfill Reporter (max 1 cycle)
    └─ if still sufficient ─→
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

### Model Assignments

Two execution modes exist. The cloud routine handles all steps autonomously:

**Cloud (Remote Routine — current production mode):**

| Agent | Model | Notes |
|-------|-------|-------|
| Reporter | Claude Opus 4.6 | Web search via cloud session |
| Curator | Claude Opus 4.6 | Same session, different prompt |
| Coverage Auditor | Python | Runs in cloud environment |
| Fact-Checker | Python | Runs in cloud environment |
| Post-Checks | Python | Runs in cloud environment |
| Editor-in-Chief | Claude Opus 4.6 | Same session |
| Gap Checker | Claude Opus 4.6 | Uses different analytical approach, not different model |
| Gmail Draft | Claude + Gmail MCP | Connected via MCP connector |

**Local (Antigravity — for max quality with multi-model diversity):**

| Agent | Model | Notes |
|-------|-------|-------|
| Reporter | Claude Code CLI | Your Anthropic Max subscription |
| Curator | Gemini 3.1 Pro | Free via Antigravity |
| Backfill Reporter | Codex CLI | Different model family |
| Editor-in-Chief | Gemini 3.1 Pro | Free via Antigravity |
| Gap Checker | Codex CLI | Different model family |

**Why multi-model matters**: Same model has correlated blind spots. Multi-model diversity is most valuable for Gap Checker and Backfill Reporter (the "second opinion" steps). The cloud routine handles this by using a different analytical approach instead of a different model — acceptable trade-off for automation convenience.

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
└── pipeline_automated.py               # Full pipeline via API (post_checks + coverage checks included)
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

### Post-Checks (Staleness Detection)
- `post_checks.py` runs AFTER URL fact-checking, catches items that passed URL checks but have editorial problems
- **Staleness detection**: catches items where the event date falls within the window but the underlying story is much older (e.g., "affirms" an old court order, "completes" a phased retirement begun months ago)
- **Duplicate URL detection**: catches two items pointing to the same source
- **Date verification gap** (known): the Reporter can claim a date that doesn't match the actual article publication date. Partial fix: extract dates from URLs that encode them (e.g., `/2026/03/21/`). Full fix requires HTML parsing.
- False positives possible (e.g., "since January" in a growth metric). Script flags; human/Editor decides.

### Coverage Auditor + Backfill Reporter
- Coverage Auditor runs **TWICE**: once after Curator (pre-filter), once after post_checks (post-filter)
- The second run catches cases where staleness removals hollow out categories
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

### Lesson 11: "Within the date window" ≠ "new this week"
The most important pipeline bug found during QA. Items like "GPT-4o retirement completes" (April 3) or "Judge affirms 20M logs order" (April 1) have dates within the target week — but the underlying stories began months earlier. These are milestones in old stories, not new events. An MD who read last month's news already knows. Fix: `post_checks.py` scans for staleness keywords ("affirms", "completes", "phased sunset", "closing out") and origin-date references ("began February 13"). This is the freshness gate that `fact_check_urls.py` (which only checks URL liveness) cannot provide.

### Lesson 12: Reporter dates can't be trusted
The Reporter assigned "March 22" to an article whose URL literally contained `/2026/03/21/`. The fact-checker verified the URL was live but never checked whether the claimed date matched the source. Partial fix: extract dates from URL paths. Full fix: parse article HTML for publication metadata. Until then, human QA on dates near window boundaries is essential.

### Lesson 13: Coverage check must run after every filter step
The coverage check originally ran only once (after Curator). When `post_checks.py` later removed 3 items and emptied 2 categories, nobody noticed until human review. Fix: coverage_check.py now runs twice — after Curator and after post_checks — with the second run able to trigger Backfill Reporter if categories were hollowed out.

### Lesson 14: Local vs. cloud is not either/or
Antigravity (local) gives full multi-model orchestration with Claude + Gemini + Codex, but requires your laptop to be on. Cloud routines (Claude Code remote triggers) run autonomously from anywhere but only have Claude. The right answer is both: cloud handles the weekly Monday run automatically; local is for when you want max quality or are debugging. The two paths coexist.

### Lesson 15: Cloud routines can't push to git without explicit setup
The first cloud routine run completed all pipeline steps but the git push failed silently — the cloud environment didn't have write access to the GitHub repo. Git push permissions need explicit configuration (deploy key or PAT) in the cloud environment.

### Lesson 16: Per-routine API tokens are scoped and safe
Claude Code routines generate a bearer token (`sk-ant-oat01-...`) that is scoped to a single routine. It can only fire that one routine — no access to account data, other routines, or Claude Code settings. Safe to store in Vercel env vars. Don't confuse with OpenAI API keys (`sk-proj-...`) — mixing these up causes 401 errors.

### Lesson 17: Vercel env vars require redeployment
Adding a new environment variable in Vercel doesn't take effect until the project redeploys. Either push a new commit (triggers auto-deploy) or manually redeploy from the Deployments tab.

---

## Open Issues / Not Yet Implemented

| Issue | Impact | Priority |
|-------|--------|----------|
| Cloud git push not working | Routine completes but can't push results to GitHub | High — add deploy key or PAT to cloud environment |
| OpenAI API key not in cloud env | Gap Checker can't call GPT in cloud; uses Claude second-pass instead | Medium — add OPENAI_API_KEY to routine environment when UI supports it |
| Reporter date verification | Reporter claims dates that don't match article publication dates | High — add URL date extraction to `post_checks.py` |
| QC summary email | Want a separate email with rejection reasons, coverage stats, calibration | Medium — add as Step 11b in routine |
| `post_checks.py` false positives | Growth metrics like "since January" get flagged as staleness | Low — needs negation/context awareness |
| Stale workspace files | Each agent should clear its output file at start of run | Low — manual archiving works for now |
| Antigravity YAML schema not tested | Best-guess structure based on tutorials; may need adjustment | Medium — test on first real Antigravity run |
| Two workflow files | Old `.agents/workflows/weekly-digest.md` + new `.antigravity/workflows/weekly-digest.yaml` | Low — delete old after new is verified |

---

## Run History Snapshot

| Week | Run Date | Reporter | Curator Kept | Verified | In Digest | Notes |
|------|----------|----------|--------------|----------|-----------|-------|
| 2026-03-22 to 03-28 | 2026-03-29 | 17 | 17 | 17 | 17 | First run, no historical dedup possible |
| 2026-03-31 to 04-05 (v1) | 2026-04-06 | 17 | 11 | 11 | 11 | First run with enhancements; structural bugs found |
| 2026-03-31 to 04-05 (v2) | 2026-04-08 | 20 | 13 | 13 | 13 | Fresh re-run; supplemented missing items |
| 2026-03-31 to 04-05 (v3) | 2026-04-09 | 20 | 13 | 10 | 10 | post_checks.py built; 3 stale items rejected |
| Combined: 03-22 to 04-05 | 2026-04-09 | 27 (merged) | 22 | 20 | 20 | Two-week catch-up; 2 cross-week merges, 5 rejected |
| 04-28 to 05-04 (cloud) | 2026-05-04 | ? | ? | ? | ? | First cloud routine run; Gmail draft produced; git push failed |

---

## Quick Reference: How to Run

### Manual (current state)
```bash
cd ~/Documents/OAI_News
# Step 1: Reporter — run Claude Code with skills/reporter.md as the prompt
# Step 2: Curator — run Gemini in Antigravity with skills/curator.md
# Step 3: Coverage check (first pass)
python3 workspace/coverage_check.py
# Step 4: Fact check URLs
python3 workspace/fact_check_urls.py
# Step 5: Post-checks (staleness, date verification, duplicate URLs)
python3 workspace/post_checks.py
# Step 6: Coverage check (second pass — after post_checks may have removed items)
python3 workspace/coverage_check.py
# Step 7: Editor-in-Chief — run Gemini in Antigravity with skills/editor_in_chief.md
# Step 8: Gap check (when enabled) — run Codex CLI with skills/gap_checker.md
# Step 9: Calibration
python3 workspace/calibrate_confidence.py
# Step 8: Audit log
python3 workspace/log_pipeline_run.py
# Step 9: Manually create Gmail draft from output/digest_draft.html
# Step 10: git add, commit, push
```

### Automated — Cloud Routine (current production mode)
- **Trigger ID**: `trig_01QPM9inh86qSpEvrj8spwoT`
- **Schedule**: Every Monday 9am PT (4pm UTC)
- **On-demand**: "Run OAI Digest" button on AI Maps website (ai-map-cyan.vercel.app)
- **Environment**: "Mobile Agent" (`env_01DnXAizYUh9ePV5dWsXuFdc`)
- **Repo**: `tishir31/oai-digest` (cloned fresh each run)
- **Model**: Claude Opus 4.6 (1M context)
- **Connectors**: Gmail MCP
- **View/manage**: https://claude.ai/code/routines

**How the button works:**
AI Maps site → `api/run-digest.js` (Vercel serverless) → POST to Anthropic `/fire` endpoint with `ROUTINE_TOKEN` → spawns Claude Code cloud session → runs full 12-step pipeline → Gmail draft created

**Vercel env vars needed:**
- `ROUTINE_TOKEN` = per-routine bearer token (`sk-ant-oat01-...`)
- `GEMINI_API_KEY` = already configured (for other AI Maps features)

### Local — Antigravity (for multi-model quality runs)
1. Open Antigravity → Cmd+Shift+M (Agent Manager)
2. Run `weekly-digest.yaml` workflow with target_week_start and target_week_end inputs
3. Each wrapper agent calls the appropriate CLI (`claude` for Reporter, `codex` for Backfill/Gap, etc.)
4. Requires Terminal Command Auto Execution allow-list: `claude`, `codex`, `python3 workspace/`
5. **Not yet tested** — YAML schema may need adjustment on first run

---

## Future Direction

1. **Fix cloud git push** — add deploy key or PAT so routine can push results back to repo
2. **QC summary email** — separate Gmail with rejection reasons, coverage stats, calibration data
3. **Add OpenAI key to cloud environment** — enables true multi-model Gap Checker in cloud
4. **Generalize beyond OpenAI** — abstract "OpenAI" to a configurable target topic
5. **Feedback loop** — capture which items the human reader actually engaged with, feed back into Curator ranking
6. **Multi-week trend analysis** — read across `historical_log.json` to surface multi-week storylines
