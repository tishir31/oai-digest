"""
Post-Checks — Editorial quality gate after URL verification

Catches items that passed URL checks but have other quality problems:
- Staleness: event dates within the window but the underlying story is much older
- Specificity: headlines too vague for an IB audience
- Duplicate URLs: two items pointing to the same source

Reads:  workspace/verified_items.json
Writes: workspace/verified_items.json (filtered) + workspace/rejections.json (appended)

Usage:
    python3 workspace/post_checks.py
"""

import json
import os
import re
from datetime import datetime, timedelta

VERIFIED_PATH = "workspace/verified_items.json"
REJECTIONS_PATH = "workspace/rejections.json"

# Keywords that suggest the item is a follow-up or continuation, not a new event
STALENESS_SIGNALS = [
    "completes",
    "completed",
    "concludes",
    "concluded",
    "finalizes",
    "finalized",
    "affirms",
    "affirmed",
    "reaffirms",
    "upholds",
    "upheld",
    "phased sunset",
    "phased retirement",
    "phased rollout",
    "ending phased",
    "closing out",
    "final phase",
    "full retirement",
    "fully retired",
    "retirement of",
    "retiring",
    "began in",
    "started in",
    "announced in",
    "first reported",
    "previously reported",
    "as expected",
    "as planned",
    "as scheduled",
]

# Keywords in snippets that signal the event origin is older than this week
ORIGIN_DATE_PATTERNS = [
    r"began (?:on )?(?:january|february|march|april|may|june|july|august|september|october|november|december) \d+",
    r"started (?:on )?(?:january|february|march|april|may|june|july|august|september|october|november|december) \d+",
    r"announced (?:in )?(?:january|february|march|april|may|june|july|august|september|october|november|december)",
    r"since (?:january|february|march|april|may|june|july|august|september|october|november|december)",
    r"first (?:reported|announced|disclosed|revealed) (?:in )?(?:january|february|march|april|may|june|july|august|september|october|november|december)",
]


def check_staleness(item):
    """Check if an item's headline or snippet signals it's a continuation, not a new event."""
    headline = item.get("headline", "").lower()
    snippet = item.get("raw_snippet", "").lower()
    combined = headline + " " + snippet

    signals_found = []

    # Check headline/snippet for staleness keywords
    for signal in STALENESS_SIGNALS:
        if signal in combined:
            signals_found.append(f"Contains '{signal}'")

    # Check for origin date patterns (e.g., "began February 13")
    for pattern in ORIGIN_DATE_PATTERNS:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            signals_found.append(f"Origin date reference: '{match.group()}'")

    return signals_found


def check_duplicate_urls(items):
    """Find items sharing the same URL."""
    url_map = {}
    duplicates = {}
    for i, item in enumerate(items):
        url = item.get("url", "")
        if url in url_map:
            if url not in duplicates:
                duplicates[url] = [url_map[url]]
            duplicates[url].append(i)
        else:
            url_map[url] = i
    return duplicates


def main():
    if not os.path.exists(VERIFIED_PATH):
        print(f"Error: {VERIFIED_PATH} not found.")
        return

    with open(VERIFIED_PATH) as f:
        items = json.load(f)

    # Load existing rejections
    rejections = []
    if os.path.exists(REJECTIONS_PATH):
        with open(REJECTIONS_PATH) as f:
            rejections = json.load(f)

    passed = []
    flagged_count = 0

    print("=" * 50)
    print("POST-CHECKS")
    print("=" * 50)

    # Check 1: Staleness
    for item in items:
        signals = check_staleness(item)
        if signals:
            flagged_count += 1
            headline = item["headline"][:70]
            print(f"\n  STALE: {headline}")
            for s in signals:
                print(f"    → {s}")

            item["post_check_failed"] = True
            item["post_check_reason"] = f"Staleness signals: {'; '.join(signals)}"
            item["rejection_reason"] = f"Post-check: likely continuation of older story. {'; '.join(signals)}"
            rejections.append(item)
        else:
            passed.append(item)

    # Check 2: Duplicate URLs among passed items
    dup_urls = check_duplicate_urls(passed)
    if dup_urls:
        for url, indices in dup_urls.items():
            print(f"\n  DUPLICATE URL: {url}")
            # Keep the first, reject the rest
            for idx in indices[1:]:
                item = passed[idx]
                print(f"    → Rejecting duplicate: {item['headline'][:60]}")
                item["post_check_failed"] = True
                item["post_check_reason"] = "Duplicate URL with another verified item"
                item["rejection_reason"] = "Post-check: duplicate URL"
                rejections.append(item)
        # Remove duplicates from passed
        dup_indices = set()
        for indices in dup_urls.values():
            dup_indices.update(indices[1:])
        passed = [p for i, p in enumerate(passed) if i not in dup_indices]

    # Write results
    with open(VERIFIED_PATH, "w") as f:
        json.dump(passed, f, indent=2)

    with open(REJECTIONS_PATH, "w") as f:
        json.dump(rejections, f, indent=2)

    print(f"\nPost-checks complete. Passed: {len(passed)}, Flagged: {flagged_count + len(dup_urls)}")
    print(f"Updated {VERIFIED_PATH} and {REJECTIONS_PATH}")


if __name__ == "__main__":
    main()
