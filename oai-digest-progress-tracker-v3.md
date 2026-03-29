# OAI News Digest — Progress Tracker (Updated March 29, 2026)

## Project Location
- Local: ~/Documents/OAI_News (Antigravity workspace)
- GitHub: github.com/tishir31/oai-digest
- Claude Project: used for strategy/memory/specs
- CLAUDE.md: in project root, bridges context to Claude Code

## Phase 1: Scaffold ✅ DONE
- [x] Folder structure (workspace/, output/, skills/, .agents/workflows/)
- [x] Empty JSON files in workspace/
- [x] agents.md with 4 agent personas
- [x] Skill files created in skills/

## Phase 2: Reporter Agent ✅ DONE
- [x] skills/reporter.md written (including Gmail safety net + retry mode)
- [x] First run with Gemini — fabricated URLs (lesson learned)
- [x] Second run with Claude Code — real web search, real URLs, 22 items
- [x] Gmail safety net pass documented and tested
- [x] Retry mode section added for feedback loop

## Phase 3: Curator Agent ✅ DONE
- [x] skills/curator.md written
- [x] Filtered 22 → 18 items (dedup, categorization, ranking, staleness flagging)

## Phase 4: Fact-Checker Agent ✅ DONE
- [x] skills/fact_checker.md written (URL checks + post-URL checks)
- [x] fact_check_urls.py — Python HTTP verification (403 = bot protection, not broken)
- [x] post_checks.py — date, freshness, specificity, duplicate URL checks
- [x] 18 curated → 17 verified (1 duplicate URL cut)
- [x] Feedback loop implemented via run_pipeline.py (max 2 retries for fixable rejections)

## Phase 5: Editor-in-Chief Agent ✅ DONE
- [x] skills/editor_in_chief.md written
- [x] Produced output/digest_draft.html — 17 items across 6 categories
- [x] Professional tone with specific numbers, names, dates
- [x] Historical log updated (workspace/historical_log.json)
- [x] Gmail draft created via Claude Code MCP

## Phase 6: Gap Checker Agent ✅ DONE
- [x] skills/gap_checker.md written
- [x] Ran via Codex CLI (different model family from Reporter)
- [x] Found 5 missed items (release notes, dev docs, API changes)
- [x] Items processed through Fact-Checker and added to digest
- [x] Updated Gmail draft with gap checker items

## Phase 7: Gmail Integration ✅ DONE
- [x] Gmail MCP connection working (Claude Code ↔ UMich email)
- [x] Gmail draft creation working
- [x] Gmail as Reporter safety net source — documented in skills/reporter.md
- [x] Newsletter handling: extract news facts from analysis sources (Stratechery, The Information, etc.), don't skip them entirely but ignore opinion/commentary sections
- [x] Exclude: marketing emails, promotional content, pure opinion

## Phase 8: Feedback Loop ✅ DONE
- [x] run_pipeline.py — identifies fixable rejections (bad URLs, content mismatch)
- [x] Writes retry_items.json for Reporter retry mode
- [x] Max 2 retry cycles, then drops unresolved items
- [x] Does NOT retry editorial rejections (wrong date, not OpenAI-specific, duplicates)
- [x] Integrated into workflow Step 3

## Phase 9: Orchestration Workflow ✅ DONE
- [x] .agents/workflows/weekly-digest.md — full 7-step pipeline documented
- [x] Model assignments: Claude Code (Reporter), Gemini (Curator + Editor), Python (Fact-Checker), Codex (Gap Checker)
- [x] Includes feedback loop, gap checker, Gmail draft, git push

## Phase 10: Multi-Model Integration ✅ DONE (partially)
- [x] Claude Code for Reporter (real web search + Gmail MCP)
- [x] Gemini 3.1 Pro for Curator + Editor-in-Chief (free, editorial judgment)
- [x] Python scripts for Fact-Checker (no model needed for HTTP)
- [x] Codex CLI for Gap Checker (different model family)
- [ ] Claude Code extension formally configured inside Antigravity settings
- [ ] Cost estimation per weekly run

## Phase 11: Automation ❌ NOT STARTED
- [ ] Schedule Monday 7am runs (cron, GitHub Actions, or Antigravity scheduling)
- [ ] Alerting if pipeline fails
- [ ] End-to-end script that runs all steps without manual intervention

---

## NOT YET IMPLEMENTED
- **Full automation** — pipeline currently requires manual triggering of each step
- **Access control enforcement** — honor-system via skill files only
- **Cross-week stale news search** — Fact-Checker flags but doesn't actively search prior coverage
- **Cost tracking** — no per-run cost estimation yet

## Key Lessons Learned Today
1. **Gemini fabricates URLs** — cannot be used for web search tasks, caught by Fact-Checker
2. **Multi-agent architecture works** — caught URL fabrication that single-agent pipeline would have missed
3. **HTTP 403 ≠ broken link** — bot protection is a real challenge (Bloomberg, OpenAI block scripts)
4. **Memory is a bottleneck** — Antigravity + Claude Code + Codex simultaneously eats 19GB+ RAM
5. **Different agents need different tools** — Reporter needs web search, Fact-Checker needs HTTP requests, Curator just needs JSON
6. **Gap Checker finds real gaps** — Codex caught 5 items Claude missed (mostly release notes and dev docs)
7. **Gmail rules need nuance** — don't exclude newsletters entirely, extract news facts and ignore analysis/opinion
8. **Spec before code** — the architecture design upfront made every implementation step clear
9. **Learn by doing** — went from brain dump to working pipeline in one afternoon

## Architecture Diagram
```
Reporter (Claude) → Curator (Gemini) → Fact-Checker (Python) → Editor-in-Chief (Gemini) → Gap Checker (Codex) → Gmail Draft
     ↑                                        |
     └── retry_items.json (max 2 cycles) ←────┘
```
