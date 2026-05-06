"""
Dedup Within Draft — Catch event-level duplicates before Editor

URL-based dedup (in union_reporter_passes.py and post_checks.py) misses
cases where the same event is reported by two outlets with different URLs.
For example: Reuters and Bloomberg both covering the Musk settlement filing,
or The Information and Tom's Hardware both covering the Pentagon AI deal.
Both items pass URL dedup but represent the same event.

This script runs after Fact-Checker and post_checks but before Editor. It
finds event-level duplicates and merges them, keeping the higher-priority
item per event group and pushing the rest's URLs into corroborating_urls.

Two grouping strategies:
  1. GPT-based (preferred): if GAP_CHECK_TOKEN is set, calls the Vercel
     /api/event-dedup endpoint to have GPT-4o group items by event. This
     handles paraphrases like "Pentagon Classified AI Deal" vs "Pentagon
     AI Partnerships" that fuzzy matching misses.
  2. Fuzzy fallback: headline-token Jaccard similarity + date window. Catches
     obvious overlaps but misses paraphrases.

Reads:  workspace/verified_items.json
Writes: workspace/verified_items.json (dedup applied in-place)
        workspace/dedup_within_draft_report.json (audit trail)

Usage:
    GAP_CHECK_TOKEN=... python3 workspace/dedup_within_draft.py
"""

import json
import os
import re
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime

VERCEL_URL = "https://ai-map-cyan.vercel.app/api/event-dedup"

VERIFIED_PATH = "workspace/verified_items.json"
REPORT_PATH = "workspace/dedup_within_draft_report.json"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "in", "is", "it", "its", "of", "on", "or", "that", "the", "to", "with", "was",
    "were", "will", "this", "these", "about", "after", "before", "over", "up",
    "down", "says", "said", "new", "more", "than", "also", "into", "out", "off",
    "open", "openai", "ai", "company", "companies", "via", "around",
}

CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}
SOURCE_TYPE_RANK = {
    "official_blog": 8, "press_release": 7, "wire_service": 6, "tech_press": 5,
    "regulatory_filing": 4, "research_preprint": 3, "developer_docs": 2,
    "other": 1, "social_media": 0,
}


def tokens_of(text):
    if not text:
        return set()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", str(text).lower())
    return {t for t in cleaned.split() if len(t) >= 3 and t not in STOPWORDS}


def similarity(a, b):
    ta, tb = tokens_of(a), tokens_of(b)
    if not ta or not tb:
        return 0.0, 0, []
    shared = ta & tb
    union = ta | tb
    return len(shared) / max(len(union), 1), len(shared), sorted(shared)


def dates_close(a, b, max_days=3):
    if not a or not b:
        return True
    try:
        da = datetime.fromisoformat(a)
        db = datetime.fromisoformat(b)
        return abs((da - db).days) <= max_days
    except Exception:
        return True


def item_priority(item):
    conf = CONFIDENCE_RANK.get((item.get("confidence") or "").lower(), 0)
    stype = SOURCE_TYPE_RANK.get((item.get("source_type") or "").lower(), 0)
    corrob = item.get("corroboration_count") or 0
    return (conf, stype, corrob)


def find_event_groups_fuzzy(items):
    """Greedily group items by event using same heuristic as gap-check.js."""
    groups = []
    used = set()
    for i, a in enumerate(items):
        if i in used:
            continue
        group = [i]
        used.add(i)
        for j in range(i + 1, len(items)):
            if j in used:
                continue
            b = items[j]
            jaccard, shared_count, shared_tokens = similarity(
                a.get("headline", ""), b.get("headline", "")
            )
            long_shared = [t for t in shared_tokens if len(t) >= 4]
            match_a = jaccard >= 0.30
            match_b = shared_count >= 2 and len(long_shared) >= 2
            if (match_a or match_b) and dates_close(a.get("date"), b.get("date")):
                group.append(j)
                used.add(j)
        groups.append(group)
    return groups


def find_event_groups_gpt(items, token):
    """Group items via the Vercel /api/event-dedup proxy (GPT-4o).

    Returns list of lists of indices, or raises on error.
    """
    body = json.dumps({"items": items}).encode()
    req = urllib.request.Request(
        VERCEL_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    groups = []
    for g in (data.get("groups") or []):
        idx = g.get("member_indices") or []
        if isinstance(idx, list) and idx:
            groups.append(list(idx))
    return groups, data


def find_event_groups(items):
    """Try GPT first; fall back to fuzzy if token absent or call fails."""
    token = os.environ.get("GAP_CHECK_TOKEN")
    if token and len(items) > 0:
        try:
            groups, _data = find_event_groups_gpt(items, token)
            if groups:
                return groups, "gpt"
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
            print(f"  WARN: GPT event-dedup failed ({e}), falling back to fuzzy")
    return find_event_groups_fuzzy(items), "fuzzy"


def main():
    if not os.path.exists(VERIFIED_PATH):
        print(f"Error: {VERIFIED_PATH} not found.")
        return

    with open(VERIFIED_PATH) as f:
        items = json.load(f)

    if not items:
        print("No verified items to dedup.")
        with open(REPORT_PATH, "w") as f:
            json.dump({"groups": [], "before": 0, "after": 0}, f, indent=2)
        return

    print("=" * 60)
    print("DEDUP WITHIN DRAFT (event-level)")
    print("=" * 60)
    print(f"  Before: {len(items)} items")

    groups, mode = find_event_groups(items)
    print(f"  Mode:   {mode}")

    kept = []
    audit_groups = []
    for group_indices in groups:
        if len(group_indices) == 1:
            kept.append(items[group_indices[0]])
            continue

        group_items = [items[i] for i in group_indices]
        group_items.sort(key=item_priority, reverse=True)
        winner = group_items[0]
        losers = group_items[1:]

        existing_corrob = list(winner.get("corroborating_urls") or [])
        for loser in losers:
            loser_url = loser.get("url")
            if loser_url and loser_url not in existing_corrob and loser_url != winner.get("url"):
                existing_corrob.append(loser_url)
            for url in (loser.get("corroborating_urls") or []):
                if url and url not in existing_corrob and url != winner.get("url"):
                    existing_corrob.append(url)
        if existing_corrob:
            winner["corroborating_urls"] = existing_corrob

        new_count = (winner.get("corroboration_count") or 1) + len(losers)
        winner["corroboration_count"] = new_count

        kept.append(winner)
        audit_groups.append({
            "winner_headline": winner.get("headline"),
            "winner_url": winner.get("url"),
            "loser_headlines": [l.get("headline") for l in losers],
            "loser_urls": [l.get("url") for l in losers],
            "merged_corroboration_count": new_count,
        })
        print(f"\n  MERGED: {winner.get('headline', '')[:80]}")
        for loser in losers:
            print(f"    ← {loser.get('headline', '')[:80]}")

    with open(VERIFIED_PATH, "w") as f:
        json.dump(kept, f, indent=2)

    report = {
        "before": len(items),
        "after": len(kept),
        "mode": mode,
        "merged_groups": audit_groups,
    }
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n  After:  {len(kept)} items ({len(items) - len(kept)} merged into corroborations)")
    print(f"  Wrote {VERIFIED_PATH} and {REPORT_PATH}")


if __name__ == "__main__":
    main()
