#!/usr/bin/env python3
"""
run_pipeline.py — Fact-Checker ↔ Reporter retry loop orchestrator.

Reads rejections.json, filters to fixable items, writes retry_items.json,
and prints instructions for re-running the Reporter agent in Retry Mode.
"""

import json
import sys
from pathlib import Path

REJECTIONS_PATH = Path("workspace/rejections.json")
RETRY_ITEMS_PATH = Path("workspace/retry_items.json")
MAX_RETRIES = 2

# Rejection reasons that the Reporter can potentially fix
FIXABLE_REASONS = [
    "URL returned HTTP 404",
    "Content does not match headline",
]

# Rejection reasons that are editorial decisions — no retry
EDITORIAL_REASONS = [
    "Outside date range",
    "Not OpenAI-specific",
    "Duplicate",
]


def load_rejections():
    if not REJECTIONS_PATH.exists():
        print("No rejections.json found. Nothing to retry.")
        return []
    with open(REJECTIONS_PATH) as f:
        return json.load(f)


def filter_fixable(rejections):
    fixable = []
    skipped = []
    for item in rejections:
        reason = item.get("rejection_reason", "")
        if any(r in reason for r in FIXABLE_REASONS):
            fixable.append(item)
        elif any(r in reason for r in EDITORIAL_REASONS):
            skipped.append(item)
        else:
            # Unknown reason — treat as not fixable, flag it
            skipped.append(item)
            print(f"  ⚠ Unknown rejection reason, skipping: {reason}")
    return fixable, skipped


def check_retry_count(fixable):
    """Track iteration count per item. Drop items that hit MAX_RETRIES."""
    eligible = []
    exhausted = []
    for item in fixable:
        count = item.get("retry_count", 0)
        if count >= MAX_RETRIES:
            exhausted.append(item)
        else:
            item["retry_count"] = count + 1
            eligible.append(item)
    return eligible, exhausted


def write_retry_items(items):
    with open(RETRY_ITEMS_PATH, "w") as f:
        json.dump(items, f, indent=2)


def main():
    print("=" * 60)
    print("OAI-Digest Retry Pipeline")
    print("=" * 60)

    rejections = load_rejections()
    if not rejections:
        print("\nAll items passed fact-checking. No retries needed.")
        sys.exit(0)

    print(f"\nFound {len(rejections)} rejection(s) in {REJECTIONS_PATH}")

    fixable, skipped = filter_fixable(rejections)
    print(f"  Fixable (bad URL / content mismatch): {len(fixable)}")
    print(f"  Editorial (skipped):                  {len(skipped)}")

    if skipped:
        print("\n  Skipped items (editorial decisions):")
        for item in skipped:
            print(f"    - {item.get('headline', 'Unknown')}: {item.get('rejection_reason', 'N/A')}")

    if not fixable:
        print("\nNo fixable rejections. Pipeline complete.")
        sys.exit(0)

    eligible, exhausted = check_retry_count(fixable)

    if exhausted:
        print(f"\n  {len(exhausted)} item(s) exhausted max retries ({MAX_RETRIES}):")
        for item in exhausted:
            print(f"    - {item.get('headline', 'Unknown')}")

    if not eligible:
        print("\nAll fixable items have exhausted retries. Pipeline complete.")
        sys.exit(0)

    write_retry_items(eligible)
    print(f"\nWrote {len(eligible)} item(s) to {RETRY_ITEMS_PATH}")

    print("\n" + "=" * 60)
    print("ACTION REQUIRED: Re-run the Reporter agent in Retry Mode")
    print("=" * 60)
    print(f"""
Paste this into Claude Code:

  You are the Reporter agent in Retry Mode.
  Read skills/reporter.md (Retry Mode section) and workspace/retry_items.json.
  For each item, find a working replacement URL from an authoritative source.
  Update workspace/raw_items.json with the fixed items.

Then re-run the Fact-Checker:
  python3 workspace/fact_check_urls.py
""")


if __name__ == "__main__":
    main()
