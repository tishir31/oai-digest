# Cloud Routine Prompt — Canonical version

This is the prompt to paste into the Anthropic routine UI (claude.ai/code/routines → OAI Digest routine → Edit → replace prompt body).

**Before pasting**: replace `PASTE_TOKEN_HERE` with the value of `~/.gap_check_token` (run `cat ~/.gap_check_token` to retrieve it).

---

```
Read docs/PROJECT_CONTEXT.md and skills/ for full context.

Run the OAI News Digest pipeline for the prior week (Monday-Sunday). Calculate the date range from today and store as WEEK_START and WEEK_END (YYYY-MM-DD format).

============================================================
STEP 0 — Configure git identity (required for any commit)
============================================================
Run:
  git config user.name "OAI Digest Routine"
  git config user.email "noreply+routine@anthropic.com"

============================================================
STEP 1 — REPORTER (three independent passes)
============================================================

Pass 1 (web broad): Read skills/reporter.md "Source Priority (Pass 1)". Search the web exhaustively for OpenAI news from WEEK_START to WEEK_END, leading with openai.com and major tech press. Apply the external-coverage rule for openai.com primaries. Write workspace/raw_items_pass1.json.

Pass 2 (web independent): Read skills/reporter.md "Source Priority (Pass 2)". DO NOT read raw_items_pass1.json. Search starting from court filings, regulatory actions, government deals, industry-specific press, international outlets. Frame as "what is the world saying about OpenAI this week." Write workspace/raw_items_pass2.json.

Pass 3 (Gmail active source): Read skills/reporter.md "Source Priority (Pass 3)". Use Gmail connector. Include The Information, Axios Pro Rata, Bloomberg, Semafor Tech, direct emails from OpenAI/Microsoft. EXCLUDE Stratechery, Ben Thompson, Platformer. Always link to original source. Write workspace/raw_items_pass3.json.

============================================================
STEP 2 — UNION (deterministic merge of the three passes)
============================================================
Run:
  python3 workspace/union_reporter_passes.py

This produces workspace/raw_items.json (deduped on canonical URL) and workspace/union_report.json (audit of pass overlap).

============================================================
STEP 3 — CURATOR
============================================================
Read skills/curator.md and workspace/raw_items.json. Filter, dedupe, categorize, rank, cluster temporally. Write workspace/curated_items.json and workspace/source_diversity_report.json.

============================================================
STEP 4 — Coverage Audit (shape — count + categories)
============================================================
Run:
  python3 workspace/coverage_check.py

If verdict is "needs_backfill", read skills/backfill_reporter.md and run a targeted gap search (max 1 cycle). Re-run Curator on the augmented set, then re-run coverage_check.py.

============================================================
STEP 5 — Coverage Audit 2.0 (content — calls Vercel proxy / GPT)
============================================================
Run:
  GAP_CHECK_TOKEN='PASTE_TOKEN_HERE' python3 workspace/coverage_check_content.py WEEK_START WEEK_END

If workspace/content_gap_items.json is non-empty, those items are MANDATORY backfill. Append them to workspace/curated_items.json (set curated=true on each), then re-run python3 workspace/coverage_check.py to refresh the shape audit.

============================================================
STEP 6 — Fact-Checker
============================================================
Run:
  python3 workspace/fact_check_urls.py

If there are fixable rejections, invoke Reporter Retry Mode (skills/reporter.md → Retry Mode section) up to 2 cycles.

============================================================
STEP 7 — Post-Checks (staleness + duplicate URLs)
============================================================
Run:
  python3 workspace/post_checks.py

============================================================
STEP 7b — Event-level dedup within draft
============================================================
Run:
  python3 workspace/dedup_within_draft.py

This catches cases where two outlets covered the same event with
different URLs (Reuters and Bloomberg both filed Musk-settlement
stories, etc). Loser items get merged into the winner's
corroborating_urls.

============================================================
STEP 8 — Coverage Audit (re-run after post_checks)
============================================================
Run:
  python3 workspace/coverage_check.py

If post_checks hollowed out a category, run Backfill Reporter once.

============================================================
STEP 9 — Editor-in-Chief
============================================================
Read skills/editor_in_chief.md and workspace/verified_items.json. Diff every item against the last 4 weeks of workspace/historical_log.json. Generate output/digest_draft.html and append the new entries to workspace/historical_log.json.

============================================================
STEP 10 — Gap Checker (post-Editor, GPT via Vercel proxy)
============================================================
Run this command. It calls the Vercel proxy with the final draft AND the verified items array so the proxy can dedup gap suggestions against existing items:

python3 -c "
import json, urllib.request
draft = open('output/digest_draft.html').read()
items = json.load(open('workspace/verified_items.json'))
body = json.dumps({
    'draft_html': draft,
    'week_start': 'WEEK_START',
    'week_end': 'WEEK_END',
    'current_items': items,
}).encode()
req = urllib.request.Request('https://ai-map-cyan.vercel.app/api/gap-check', data=body, headers={'Authorization': 'Bearer PASTE_TOKEN_HERE', 'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req, timeout=180)
data = json.loads(resp.read())
with open('workspace/gap_check.json', 'w') as f:
    json.dump(data.get('gaps', []), f, indent=2)
print(f'Gap Checker found {len(data.get(\"gaps\", []))} potential gaps; web_search_call_count={data.get(\"web_search_call_count\", 0)}')
"

If workspace/gap_check.json has items, run them through Fact-Checker (python3 workspace/fact_check_urls.py against a temporary curated_items.json containing just gap items) and re-invoke Editor-in-Chief to incorporate verified gaps.

============================================================
STEP 11 — Confidence calibration + audit log
============================================================
Run:
  python3 workspace/calibrate_confidence.py
  python3 workspace/log_pipeline_run.py

============================================================
STEP 12 — GIT COMMIT AND PUSH (MANDATORY — do not skip)
============================================================
This step is CRITICAL. Audit logs are written in this cloud sandbox and discarded unless pushed to GitHub. Without push, future debugging is impossible.

Run these commands sequentially, capturing all output to workspace/git_push_log.txt:

  echo "=== git status ===" > workspace/git_push_log.txt
  git status >> workspace/git_push_log.txt 2>&1
  echo "=== git remote -v ===" >> workspace/git_push_log.txt
  git remote -v >> workspace/git_push_log.txt 2>&1
  git add workspace/ output/ >> workspace/git_push_log.txt 2>&1
  git commit -m "Weekly digest WEEK_START to WEEK_END (cloud routine run)" >> workspace/git_push_log.txt 2>&1
  echo "=== git push attempt ===" >> workspace/git_push_log.txt
  git push origin HEAD:main --verbose >> workspace/git_push_log.txt 2>&1
  GIT_PUSH_EXIT=$?
  echo "=== git push exit code: $GIT_PUSH_EXIT ===" >> workspace/git_push_log.txt

Read workspace/git_push_log.txt and remember its contents — you will append a summary to the Gmail draft in the next step.

If git push failed (non-zero exit), DO NOT FAIL THE ENTIRE RUN. Continue to Step 13. The user needs the digest in Gmail even if push fails.

============================================================
STEP 13 — Gmail draft (with diagnostics footer)
============================================================
Use the Gmail connector to create a draft email.

Subject: "OpenAI Weekly Digest — WEEK_START to WEEK_END"
To: tishir.chhaparia@citi.com

Body: contents of output/digest_draft.html PLUS a "Pipeline Diagnostics" section appended at the bottom in <details><summary> tags so MDs can collapse it. The diagnostics block must include:

  <hr><details><summary>Pipeline Diagnostics (collapsible)</summary>
  <pre>
  Week: WEEK_START to WEEK_END
  Reporter passes: [counts from workspace/union_report.json]
  After dedup: [total_after_dedup from union_report.json]
  Curated items: [count from curated_items.json]
  Verified items: [count from verified_items.json]
  Content coverage check verdict: [verdict from content_coverage_report.json]
  Content gap items found: [filtered_gap_count from content_coverage_report.json]
  Final digest items: [count in digest_draft.html]
  Gap Checker (post-editor): [count from gap_check.json]
  Git push: [SUCCESS or FAILURE based on GIT_PUSH_EXIT]
  Git push log:
  [Last 20 lines of workspace/git_push_log.txt]
  </pre></details>

This makes pipeline state visible in the email even when git push fails.

============================================================
STEP 14 — Final report to caller
============================================================
Print a structured summary:
- Item counts at each stage
- Whether content coverage check or gap checker added items
- Whether git push succeeded
- Gmail draft ID

If git push failed, the failure is captured in the email diagnostics — that is the recovery path.
```

---

## What changed vs the previous prompt

- **STEP 0** — explicit git identity config (in case cloud env lacks it)
- **STEP 2** — replaces "manually merge into raw_items.json" with `union_reporter_passes.py` (deterministic)
- **STEP 5** — new Coverage Audit 2.0 via Vercel proxy (catches gaps before Editor)
- **STEP 10** — Gap Checker now sends `current_items` so the proxy can dedup server-side
- **STEP 12** — git push is now MANDATORY with full diagnostic capture; non-zero exit doesn't fail the run
- **STEP 13** — Gmail draft now includes a collapsible diagnostics footer showing all pipeline stages and git push status
- **Step ordering**: git push moved BEFORE Gmail so the email can report the push status

## How to verify the next run

After triggering, check:
1. New commit on `tishir31/oai-digest` main branch (push worked) — OR
2. Open Gmail draft, scroll to the bottom, click "Pipeline Diagnostics" → see why push failed (push didn't work)

Either way, you have visibility now.
