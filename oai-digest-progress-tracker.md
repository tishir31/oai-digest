# OAI News Digest — Progress Tracker

## Project Location
~/Documents/OAI_News (Antigravity workspace)

## Phase 1: Scaffold ✅ DONE
- [x] Folder structure created (workspace/, output/, skills/, .agents/workflows/)
- [x] Empty JSON files in workspace/ (raw_items, curated_items, verified_items, rejections, historical_log)
- [x] agents.md with 4 agent personas (Reporter, Curator, Fact-Checker, Editor-in-Chief)
- [x] Skill files created in skills/

## Phase 2: Reporter Agent ✅ DONE
- [x] skills/reporter.md written with full instructions
- [x] Tested Reporter — produced structured JSON output
- [x] Iterated to increase coverage (9 → 20+ items)
- [x] JSON schema validated (headline, date, url, source_name, category, raw_snippet, confidence, gmail_sourced)
- [ ] Gmail safety net pass — NOT YET TESTED (MCP connection exists via Claude Code but not wired into this pipeline)

## Phase 3: Curator Agent 🔄 IN PROGRESS
- [x] skills/curator.md written with full instructions
- [ ] Test Curator on Reporter output
- [ ] Validate filtering, dedup, categorization, ranking, staleness flagging

## Phase 4: Fact-Checker Agent ❌ NOT STARTED
- [ ] skills/fact_checker.md — needs detailed instructions
- [ ] URL verification (actual HTTP requests)
- [ ] Content matching (does page content match headline?)
- [ ] Date verification
- [ ] Freshness/stale news detection
- [ ] Historical log cross-reference
- [ ] Rejection → Reporter feedback loop

## Phase 5: Editor-in-Chief Agent ❌ NOT STARTED
- [ ] skills/editor_in_chief.md — needs detailed instructions
- [ ] Summary writing
- [ ] Final ranking and formatting
- [ ] Email HTML output
- [ ] Historical log update after each run

## Phase 6: Orchestration Workflow ❌ NOT STARTED
- [ ] .agents/workflows/weekly-digest.md — the slash command
- [ ] Wire all agents in sequence
- [ ] Implement feedback loop (Fact-Checker → Reporter rejections, max 2 iterations)
- [ ] Error handling and run logging

## Phase 7: Gmail Integration ❌ NOT STARTED
- [ ] Connect Gmail MCP (UMich email) to pipeline
- [ ] Test with Reporter as supplementary source
- [ ] Newsletter exclusion filter (Stratechery, etc.)
- [ ] Verify it only triggers after web search pass

## Phase 8: Multi-Model Integration ❌ NOT STARTED
- [ ] Set up Claude (Anthropic API) for Reporter or Editor-in-Chief
- [ ] Set up GPT/Codex (OpenAI API) for Fact-Checker
- [ ] Test cross-model verification (different model families catch different hallucinations)
- [ ] Configure model selection in agents.md or workflow

## Phase 9: Email Delivery ❌ NOT STARTED
- [ ] Gmail API OAuth setup for draft creation
- [ ] Format final output as email-ready HTML
- [ ] Create draft in Tishir's inbox

## Phase 10: Automation ❌ NOT STARTED
- [ ] Schedule to run every Monday morning
- [ ] Alerting if pipeline fails
- [ ] Historical log persistence across runs

---

## NOT YET IMPLEMENTED (designed but not built)
- **Access control enforcement** — currently honor-system via skill file instructions. No technical enforcement preventing agents from writing to wrong files. Real enforcement would come with a Python orchestrator that only passes relevant files to each agent.
- **Feedback loop** — designed (Fact-Checker rejects → Reporter retries, max 2 iterations) but not wired up yet
- **Historical log dedup** — the file exists but is empty and no agent reads it yet
- **Stale news detection** — Curator can flag suspicious items, but the Fact-Checker's cross-week search isn't built
- **Multi-model pipeline** — all agents currently run on Gemini 3.1 Pro in Antigravity. No cross-model verification yet.

---

## Key Decisions Made
- Antigravity as orchestration platform
- 4-agent newsroom: Reporter → Curator → Fact-Checker → Editor-in-Chief
- Editor-in-Chief is sole committer to final output
- Gmail is supplementary source only (safety net, not primary)
- Exclude analysis newsletters (Stratechery, etc.) from Gmail source
- Multi-model: different model families for Reporter vs Fact-Checker to reduce correlated hallucinations
- Target: all notable items (no forced minimum, but exhaustive search)
