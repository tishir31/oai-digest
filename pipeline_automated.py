#!/usr/bin/env python3
"""
pipeline_automated.py — Full OAI News Digest pipeline via API calls.

Runs the entire multi-agent pipeline end-to-end:
  Reporter (Claude + web search) → Curator (Claude) → Fact-Checker (Python) →
  Feedback Loop (max 2 retries) → Editor-in-Chief (Claude) → Gap Checker (OpenAI) →
  Confidence Calibration → Gmail Draft → Git commit

Usage:
    python pipeline_automated.py

Environment variables:
    ANTHROPIC_API_KEY  — Required for Reporter, Curator, Editor-in-Chief
    OPENAI_API_KEY     — Required for Gap Checker (different model family)

Optional flags:
    --skip-gap-checker    Skip the Gap Checker step
    --skip-gmail          Skip Gmail draft creation
    --skip-git            Skip git commit/push
    --dry-run             Print what would happen without executing API calls
"""

import json
import os
import sys
import subprocess
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SKILLS_DIR = Path("skills")
WORKSPACE = Path("workspace")
OUTPUT = Path("output")

RAW_ITEMS = WORKSPACE / "raw_items.json"
CURATED_ITEMS = WORKSPACE / "curated_items.json"
VERIFIED_ITEMS = WORKSPACE / "verified_items.json"
REJECTIONS = WORKSPACE / "rejections.json"
RETRY_ITEMS = WORKSPACE / "retry_items.json"
HISTORICAL_LOG = WORKSPACE / "historical_log.json"
GAP_CHECK = WORKSPACE / "gap_check.json"
DIGEST_DRAFT = OUTPUT / "digest_draft.html"
CALIBRATION_SCRIPT = WORKSPACE / "calibrate_confidence.py"
FACT_CHECK_SCRIPT = WORKSPACE / "fact_check_urls.py"
POST_CHECK_SCRIPT = WORKSPACE / "post_checks.py"
COVERAGE_CHECK_SCRIPT = WORKSPACE / "coverage_check.py"
COVERAGE_REPORT = WORKSPACE / "coverage_report.json"
AUDIT_LOG_SCRIPT = WORKSPACE / "log_pipeline_run.py"

MAX_RETRIES = 2

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_target_week():
    """Calculate the prior Monday–Sunday date range."""
    today = datetime.now()
    # Last Sunday
    days_since_sunday = (today.weekday() + 1) % 7
    last_sunday = today - timedelta(days=days_since_sunday)
    last_monday = last_sunday - timedelta(days=6)
    return last_monday.strftime("%Y-%m-%d"), last_sunday.strftime("%Y-%m-%d")


def read_skill(name):
    """Read a skill file from the skills directory."""
    path = SKILLS_DIR / f"{name}.md"
    if not path.exists():
        log.error(f"Skill file not found: {path}")
        sys.exit(1)
    return path.read_text()


def load_json(path):
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def extract_json_from_response(text):
    """Extract JSON array or object from model response text.
    
    Handles cases where the model wraps JSON in markdown code fences.
    """
    import re
    # Try to find JSON in code fences first
    fence_match = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n```', text)
    if fence_match:
        text = fence_match.group(1)
    
    # Try parsing as-is
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to find the first [ or { and parse from there
    for i, ch in enumerate(text):
        if ch in '[{':
            # Find the matching bracket
            try:
                return json.loads(text[i:])
            except json.JSONDecodeError:
                continue
    
    log.error(f"Could not extract JSON from response. First 500 chars:\n{text[:500]}")
    return None


# ---------------------------------------------------------------------------
# API Clients
# ---------------------------------------------------------------------------

def call_anthropic(system_prompt, user_message, use_web_search=False, model="claude-sonnet-4-20250514"):
    """Call the Anthropic Messages API. Returns the text response."""
    import anthropic
    
    client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var
    
    kwargs = {
        "model": model,
        "max_tokens": 16000,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }
    
    if use_web_search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]
    
    log.info(f"Calling Anthropic ({model}, web_search={use_web_search})...")
    
    response = client.messages.create(**kwargs)
    
    # Extract text from response content blocks
    text_parts = []
    for block in response.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)
    
    full_text = "\n".join(text_parts)
    log.info(f"Anthropic response: {len(full_text)} chars, stop_reason={response.stop_reason}")
    
    # If stop_reason is "end_turn" we're good.
    # If it's "tool_use", we need to handle the tool loop for web search.
    if response.stop_reason == "tool_use" and use_web_search:
        full_text = _handle_web_search_loop(client, kwargs, response)
    
    return full_text


def _handle_web_search_loop(client, base_kwargs, initial_response):
    """Handle the multi-turn web search tool use loop."""
    messages = base_kwargs["messages"].copy()
    response = initial_response
    max_loops = 20  # Safety valve
    
    for i in range(max_loops):
        # Collect all content from the assistant response
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})
        
        # Find all tool_use blocks and create tool results
        tool_results = []
        for block in assistant_content:
            if block.type == "tool_use":
                # For web_search, the API handles it server-side.
                # We just need to continue the conversation.
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Search completed. Continue with your analysis.",
                })
        
        if not tool_results:
            break
            
        messages.append({"role": "user", "content": tool_results})
        
        # Make the next API call
        response = client.messages.create(
            model=base_kwargs["model"],
            max_tokens=base_kwargs["max_tokens"],
            system=base_kwargs["system"],
            messages=messages,
            tools=base_kwargs.get("tools", []),
        )
        
        if response.stop_reason != "tool_use":
            break
    
    # Extract final text
    text_parts = []
    for block in response.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)
    
    return "\n".join(text_parts)


def call_openai(system_prompt, user_message, model="gpt-4o"):
    """Call the OpenAI Chat Completions API. Returns the text response."""
    from openai import OpenAI
    
    client = OpenAI()  # Uses OPENAI_API_KEY env var
    
    log.info(f"Calling OpenAI ({model})...")
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=8000,
    )
    
    text = response.choices[0].message.content
    log.info(f"OpenAI response: {len(text)} chars")
    return text


# ---------------------------------------------------------------------------
# Pipeline Steps
# ---------------------------------------------------------------------------

def step_reporter(week_start, week_end):
    """Step 1: Reporter — gather raw news items via Claude + web search."""
    log.info("=" * 60)
    log.info("STEP 1: REPORTER")
    log.info(f"Target week: {week_start} to {week_end}")
    log.info("=" * 60)
    
    skill = read_skill("reporter")
    
    user_msg = f"""Search for ALL notable OpenAI news from the week of {week_start} to {week_end}.

Follow your skill instructions exactly. Use web search to find every story. 
Tag each item with the correct source_type.
Output ONLY a valid JSON array — no commentary before or after the JSON.
The date range is {week_start} (Monday) through {week_end} (Sunday).
Today's date is {datetime.now().strftime('%Y-%m-%d')}.
Target at least 15-20 items. Be thorough."""

    response = call_anthropic(skill, user_msg, use_web_search=True)
    
    data = extract_json_from_response(response)
    if data is None:
        log.error("Reporter failed to produce valid JSON. Saving raw response.")
        (WORKSPACE / "reporter_raw_response.txt").write_text(response)
        sys.exit(1)
    
    save_json(RAW_ITEMS, data)
    log.info(f"Reporter produced {len(data)} items → {RAW_ITEMS}")
    return data


def step_curator():
    """Step 2: Curator — filter, deduplicate, rank, cluster."""
    log.info("=" * 60)
    log.info("STEP 2: CURATOR")
    log.info("=" * 60)
    
    raw = load_json(RAW_ITEMS)
    if not raw:
        log.error("No raw items found. Cannot curate.")
        sys.exit(1)
    
    skill = read_skill("curator")
    
    user_msg = f"""Here are the raw items from the Reporter:

{json.dumps(raw, indent=2)}

Follow your skill instructions exactly. Apply all 7 steps: Filter, Deduplicate, Categorize, Rank, Flag Staleness, Source Diversity Check, Temporal Clustering.

Output ONLY a valid JSON array with all items (both curated:true and curated:false). 
Include the source_diversity object as the last element of the array.
No commentary before or after the JSON."""

    response = call_anthropic(skill, user_msg, use_web_search=False)
    
    data = extract_json_from_response(response)
    if data is None:
        log.error("Curator failed to produce valid JSON. Saving raw response.")
        (WORKSPACE / "curator_raw_response.txt").write_text(response)
        sys.exit(1)
    
    save_json(CURATED_ITEMS, data)
    curated_count = sum(1 for item in data if isinstance(item, dict) and item.get("curated"))
    log.info(f"Curator kept {curated_count}/{len(raw)} items → {CURATED_ITEMS}")
    return data


def step_fact_checker():
    """Step 3: Fact-Checker — URL verification via Python script."""
    log.info("=" * 60)
    log.info("STEP 3: FACT-CHECKER")
    log.info("=" * 60)
    
    if not FACT_CHECK_SCRIPT.exists():
        log.error(f"Fact-check script not found: {FACT_CHECK_SCRIPT}")
        sys.exit(1)
    
    result = subprocess.run(
        [sys.executable, str(FACT_CHECK_SCRIPT)],
        capture_output=True,
        text=True,
    )
    
    log.info(result.stdout.strip() if result.stdout else "No output")
    if result.returncode != 0:
        log.warning(f"Fact-checker stderr: {result.stderr}")
    
    verified = load_json(VERIFIED_ITEMS)
    rejected = load_json(REJECTIONS)
    log.info(f"Verified: {len(verified)}, Rejected: {len(rejected)}")
    return verified, rejected


def step_post_checks():
    """Step 3b: Post-Checks — staleness, date verification, duplicate URLs."""
    log.info("=" * 60)
    log.info("STEP 3b: POST-CHECKS (staleness/dates)")
    log.info("=" * 60)

    if not POST_CHECK_SCRIPT.exists():
        log.warning(f"Post-check script not found: {POST_CHECK_SCRIPT}. Skipping.")
        return

    result = subprocess.run(
        [sys.executable, str(POST_CHECK_SCRIPT)],
        capture_output=True,
        text=True,
    )

    log.info(result.stdout.strip() if result.stdout else "No output")
    if result.returncode != 0:
        log.warning(f"Post-checks stderr: {result.stderr}")

    verified = load_json(VERIFIED_ITEMS)
    rejected = load_json(REJECTIONS)
    log.info(f"After post-checks: {len(verified)} verified, {len(rejected)} rejected")


def step_coverage_check(label=""):
    """Run coverage check and return verdict."""
    suffix = f" ({label})" if label else ""
    log.info(f"COVERAGE CHECK{suffix}")

    if not COVERAGE_CHECK_SCRIPT.exists():
        log.warning(f"Coverage check script not found: {COVERAGE_CHECK_SCRIPT}. Skipping.")
        return "sufficient"

    result = subprocess.run(
        [sys.executable, str(COVERAGE_CHECK_SCRIPT)],
        capture_output=True,
        text=True,
    )

    log.info(result.stdout.strip() if result.stdout else "No output")

    report = load_json(COVERAGE_REPORT) if COVERAGE_REPORT.exists() else {}
    verdict = report.get("verdict", "sufficient") if isinstance(report, dict) else "sufficient"
    log.info(f"Coverage verdict: {verdict}")
    return verdict


def step_audit_log():
    """Run pipeline audit log."""
    log.info("AUDIT LOG")

    if not AUDIT_LOG_SCRIPT.exists():
        log.warning(f"Audit log script not found: {AUDIT_LOG_SCRIPT}. Skipping.")
        return

    result = subprocess.run(
        [sys.executable, str(AUDIT_LOG_SCRIPT)],
        capture_output=True,
        text=True,
    )

    log.info(result.stdout.strip() if result.stdout else "No output")


def step_feedback_loop(week_start, week_end):
    """Step 4: Feedback loop — retry fixable rejections via Reporter."""
    log.info("=" * 60)
    log.info("STEP 4: FEEDBACK LOOP")
    log.info("=" * 60)
    
    FIXABLE_REASONS = ["URL returned HTTP 404", "Content does not match headline"]
    
    for iteration in range(1, MAX_RETRIES + 1):
        rejected = load_json(REJECTIONS)
        
        fixable = [
            item for item in rejected
            if any(reason in item.get("rejection_reason", "") for reason in FIXABLE_REASONS)
            and item.get("retry_count", 0) < MAX_RETRIES
        ]
        
        if not fixable:
            log.info(f"No fixable rejections. Feedback loop complete.")
            break
        
        log.info(f"Retry iteration {iteration}: {len(fixable)} fixable items")
        
        # Increment retry count
        for item in fixable:
            item["retry_count"] = item.get("retry_count", 0) + 1
        
        save_json(RETRY_ITEMS, fixable)
        
        # Call Reporter in retry mode
        skill = read_skill("reporter")
        retry_section = skill.split("## Retry Mode")[-1] if "## Retry Mode" in skill else skill
        
        user_msg = f"""You are in RETRY MODE. Read these items that failed fact-checking and find working replacement URLs.

{json.dumps(fixable, indent=2)}

Target week: {week_start} to {week_end}.

For each item, search for the same story from a different authoritative source with a working URL.
Return ONLY a valid JSON array with the corrected items. Keep all original fields but update url, source_name, and source_type as needed.
If you cannot find a working source, set "unrecoverable": true on that item."""

        response = call_anthropic(skill, user_msg, use_web_search=True)
        
        fixed = extract_json_from_response(response)
        if fixed is None:
            log.warning("Retry produced no valid JSON. Skipping this retry cycle.")
            break
        
        # Merge fixed items back into raw_items
        raw = load_json(RAW_ITEMS)
        fixed_headlines = {item["headline"] for item in fixed if not item.get("unrecoverable")}
        
        # Replace matching items in raw
        for i, raw_item in enumerate(raw):
            for fixed_item in fixed:
                if raw_item["headline"] == fixed_item["headline"] and not fixed_item.get("unrecoverable"):
                    raw[i] = fixed_item
                    break
        
        save_json(RAW_ITEMS, raw)
        log.info(f"Fixed {len(fixed_headlines)} items. Re-running Curator and Fact-Checker...")
        
        # Re-run Curator and Fact-Checker
        step_curator()
        step_fact_checker()
    
    # Clean up retry file
    if RETRY_ITEMS.exists():
        RETRY_ITEMS.unlink()


def step_editor_in_chief(week_start, week_end):
    """Step 5: Editor-in-Chief — write final digest."""
    log.info("=" * 60)
    log.info("STEP 5: EDITOR-IN-CHIEF")
    log.info("=" * 60)
    
    verified = load_json(VERIFIED_ITEMS)
    if not verified:
        log.warning("No verified items. Producing empty digest.")
    
    historical = load_json(HISTORICAL_LOG)
    skill = read_skill("editor_in_chief")
    
    user_msg = f"""Here are the verified items for this week's digest:

{json.dumps(verified, indent=2)}

Here are the last 4 weeks of historical items for dedup checking:

{json.dumps(historical[-80:], indent=2)}

Target week: {week_start} to {week_end}.

Follow your skill instructions exactly:
1. Historical dedup check against the last 4 weeks
2. Final review
3. Write summaries
4. Group and rank by category
5. Format the email as HTML

Output the complete HTML email. Start with the HTML — no commentary before or after.
Use the subject line: "OpenAI Weekly Digest — {week_start} to {week_end}"
Opening line should state the number of notable items."""

    response = call_anthropic(skill, user_msg, use_web_search=False)
    
    # For the editor, the response IS the HTML (not JSON)
    # Strip any code fences if present
    html = response.strip()
    if html.startswith("```html"):
        html = html[7:]
    if html.startswith("```"):
        html = html[3:]
    if html.endswith("```"):
        html = html[:-3]
    html = html.strip()
    
    OUTPUT.mkdir(parents=True, exist_ok=True)
    DIGEST_DRAFT.write_text(html)
    log.info(f"Digest draft written → {DIGEST_DRAFT} ({len(html)} chars)")
    
    # Update historical log
    for item in verified:
        item["digest_date"] = datetime.now().strftime("%Y-%m-%d")
    historical.extend(verified)
    save_json(HISTORICAL_LOG, historical)
    log.info(f"Historical log updated with {len(verified)} items")
    
    return html


def step_gap_checker(week_start, week_end):
    """Step 6: Gap Checker — second opinion from a different model family."""
    log.info("=" * 60)
    log.info("STEP 6: GAP CHECKER (OpenAI)")
    log.info("=" * 60)
    
    if not os.environ.get("OPENAI_API_KEY"):
        log.warning("OPENAI_API_KEY not set. Skipping Gap Checker.")
        return []
    
    draft_html = DIGEST_DRAFT.read_text() if DIGEST_DRAFT.exists() else ""
    skill = read_skill("gap_checker")
    
    user_msg = f"""Here is the current digest draft for the week of {week_start} to {week_end}:

{draft_html[:8000]}

Search for any notable OpenAI news from {week_start} to {week_end} that is NOT covered in this digest.
Follow your skill instructions exactly.
Output ONLY a valid JSON array of missed items, or an empty array [] if no gaps found."""

    response = call_openai(skill, user_msg, model="gpt-4o")
    
    data = extract_json_from_response(response)
    if data is None or not data:
        log.info("Gap Checker found no gaps (or failed to parse). Moving on.")
        save_json(GAP_CHECK, [])
        return []
    
    save_json(GAP_CHECK, data)
    log.info(f"Gap Checker found {len(data)} potential gaps")
    
    # If gaps found, they still need fact-checking
    if data:
        log.info("Running fact-check on gap items...")
        # Merge gap items into curated_items format and re-run fact checker
        for item in data:
            item["curated"] = True
            item["rank_within_category"] = 99
            item["staleness_flag"] = False
            item["corroboration_count"] = 1
            item["corroborating_urls"] = []
            item["curator_notes"] = "Added by Gap Checker"
            item["gap_check_sourced"] = True
        
        # Append to curated items and re-run fact checker
        curated = load_json(CURATED_ITEMS)
        curated.extend(data)
        save_json(CURATED_ITEMS, curated)
        
        step_fact_checker()
        
        # Check if any gap items survived
        verified = load_json(VERIFIED_ITEMS)
        gap_survived = [v for v in verified if v.get("gap_check_sourced")]
        if gap_survived:
            log.info(f"{len(gap_survived)} gap items verified. Regenerating digest...")
            step_editor_in_chief(week_start, week_end)
        else:
            log.info("No gap items survived fact-checking.")
    
    return data


def step_calibration():
    """Step 7: Run confidence calibration."""
    log.info("=" * 60)
    log.info("STEP 7: CONFIDENCE CALIBRATION")
    log.info("=" * 60)
    
    if not CALIBRATION_SCRIPT.exists():
        log.warning(f"Calibration script not found: {CALIBRATION_SCRIPT}")
        return
    
    result = subprocess.run(
        [sys.executable, str(CALIBRATION_SCRIPT)],
        capture_output=True,
        text=True,
    )
    
    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            log.info(f"  {line}")
    if result.returncode != 0:
        log.warning(f"Calibration stderr: {result.stderr}")


def step_gmail_draft(week_start, week_end):
    """Step 8: Create Gmail draft (requires Gmail API setup)."""
    log.info("=" * 60)
    log.info("STEP 8: GMAIL DRAFT")
    log.info("=" * 60)
    
    if not DIGEST_DRAFT.exists():
        log.error("No digest draft found. Cannot create Gmail draft.")
        return
    
    # Gmail draft creation via API requires OAuth credentials.
    # For now, log instructions for manual creation or Claude Code.
    log.info("Gmail draft creation requires OAuth setup.")
    log.info("To create the draft manually, use Claude Code with Gmail MCP:")
    log.info(f"  'Create a Gmail draft with the contents of {DIGEST_DRAFT}'")
    log.info(f"  Subject: 'OpenAI Weekly Digest — {week_start} to {week_end}'")
    
    # TODO: Implement Gmail API integration
    # from google.oauth2.credentials import Credentials
    # from googleapiclient.discovery import build
    # ...


def step_git_commit(week_start, week_end):
    """Step 9: Git commit and push."""
    log.info("=" * 60)
    log.info("STEP 9: GIT COMMIT")
    log.info("=" * 60)
    
    msg = f"Weekly digest {week_start} to {week_end}"
    
    try:
        subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", msg], check=True, capture_output=True)
        subprocess.run(["git", "push"], check=True, capture_output=True)
        log.info(f"Committed and pushed: '{msg}'")
    except subprocess.CalledProcessError as e:
        log.warning(f"Git operation failed: {e}")
        log.info("You may need to commit/push manually.")


def print_summary(week_start, week_end):
    """Print a summary of the pipeline run."""
    raw = load_json(RAW_ITEMS)
    curated = [i for i in load_json(CURATED_ITEMS) if isinstance(i, dict) and i.get("curated")]
    verified = load_json(VERIFIED_ITEMS)
    rejected = load_json(REJECTIONS)
    gaps = load_json(GAP_CHECK)
    
    log.info("")
    log.info("=" * 60)
    log.info("PIPELINE SUMMARY")
    log.info("=" * 60)
    log.info(f"  Week:              {week_start} to {week_end}")
    log.info(f"  Reporter found:    {len(raw)} items")
    log.info(f"  Curator kept:      {len(curated)} items")
    log.info(f"  Fact-check passed: {len(verified)} items")
    log.info(f"  Rejected:          {len(rejected)} items")
    log.info(f"  Gap Checker found: {len(gaps)} items")
    log.info(f"  Final digest:      {DIGEST_DRAFT}")
    log.info("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run the OAI News Digest pipeline")
    parser.add_argument("--skip-gap-checker", action="store_true", help="Skip Gap Checker step")
    parser.add_argument("--skip-gmail", action="store_true", help="Skip Gmail draft creation")
    parser.add_argument("--skip-git", action="store_true", help="Skip git commit/push")
    parser.add_argument("--week-start", type=str, help="Override week start (YYYY-MM-DD)")
    parser.add_argument("--week-end", type=str, help="Override week end (YYYY-MM-DD)")
    args = parser.parse_args()
    
    # Check required env vars
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY environment variable is required.")
        log.error("Set it with: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)
    
    # Calculate target week
    if args.week_start and args.week_end:
        week_start, week_end = args.week_start, args.week_end
    else:
        week_start, week_end = get_target_week()
    
    log.info("=" * 60)
    log.info("OAI NEWS DIGEST — AUTOMATED PIPELINE")
    log.info(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"Target week: {week_start} to {week_end}")
    log.info("=" * 60)
    
    # Step 1: Reporter (Claude — web search)
    step_reporter(week_start, week_end)

    # Step 2: Curator (Claude — editorial)
    step_curator()

    # Step 3a: Coverage Check₁ (after Curator)
    verdict = step_coverage_check("after Curator")
    if verdict == "needs_backfill":
        log.info("Coverage insufficient — backfill would run here (not yet wired)")
        # TODO: step_backfill_reporter() → step_curator() → step_coverage_check()

    # Step 3b: Fact-Check URLs
    step_fact_checker()

    # Step 3c: Post-Checks (staleness, date verification)
    step_post_checks()

    # Step 3d: Coverage Check₂ (after post_checks may have removed items)
    verdict = step_coverage_check("after post-checks")
    if verdict == "needs_backfill":
        log.info("Coverage dropped below floor after post-checks — backfill would run here")

    # Step 4: Feedback Loop (retry fixable rejections)
    step_feedback_loop(week_start, week_end)

    # Step 5: Editor-in-Chief (Claude — write digest)
    step_editor_in_chief(week_start, week_end)

    # Step 6: Gap Checker (OpenAI — different model family)
    if not args.skip_gap_checker:
        step_gap_checker(week_start, week_end)
    else:
        log.info("Skipping Gap Checker (--skip-gap-checker)")

    # Step 7: Confidence Calibration
    step_calibration()

    # Step 8: Audit Log
    step_audit_log()

    # Step 9: Gmail Draft (optional)
    if not args.skip_gmail:
        step_gmail_draft(week_start, week_end)
    else:
        log.info("Skipping Gmail draft (--skip-gmail)")

    # Step 10: Git Commit (optional)
    if not args.skip_git:
        step_git_commit(week_start, week_end)
    else:
        log.info("Skipping git commit (--skip-git)")

    # Summary
    print_summary(week_start, week_end)

    log.info(f"\nPipeline completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()