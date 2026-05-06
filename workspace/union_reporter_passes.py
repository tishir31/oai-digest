"""
Union Reporter Passes — Deterministic merge of three Reporter pass outputs

The Reporter runs three independent passes (web broad, web independent, Gmail
active source), each writing to its own file. This script unions them into
raw_items.json with deterministic deduplication, so the orchestrator does not
have to do this manually (which is non-deterministic and error-prone).

Reads:
    workspace/raw_items_pass1.json  (Reporter Pass 1 — web broad)
    workspace/raw_items_pass2.json  (Reporter Pass 2 — web independent)
    workspace/raw_items_pass3.json  (Reporter Pass 3 — Gmail active source)

Writes:
    workspace/raw_items.json        (unioned, deduped)
    workspace/union_report.json     (audit trail of what was kept/merged)

Dedup strategy:
    1. Group by canonical URL (lowercased, trailing slash stripped, query stripped
       except for query params that materially change the page identity).
    2. For each URL group, keep the entry with highest confidence (high > medium > low).
       Tie-break by source_type priority: official_blog > press_release > wire_service
       > tech_press > regulatory_filing > research_preprint > developer_docs > other > social_media.
    3. Merge `corroborating_urls` across the dropped entries' URLs.
    4. Annotate `passes_seen` with which passes contributed (1, 2, 3) — useful for
       diagnosing if any pass is systematically missing stories.

Usage:
    python3 workspace/union_reporter_passes.py
"""

import json
import os
import sys
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

PASSES = [
    ("workspace/raw_items_pass1.json", 1),
    ("workspace/raw_items_pass2.json", 2),
    ("workspace/raw_items_pass3.json", 3),
]
OUT_ITEMS = "workspace/raw_items.json"
OUT_REPORT = "workspace/union_report.json"

CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}
SOURCE_TYPE_RANK = {
    "official_blog": 8,
    "press_release": 7,
    "wire_service": 6,
    "tech_press": 5,
    "regulatory_filing": 4,
    "research_preprint": 3,
    "developer_docs": 2,
    "other": 1,
    "social_media": 0,
}

# Query params that materially identify a unique article (e.g. share IDs that
# point to different pages). Most query params (utm_*, ref, etc.) are noise.
KEEP_QUERY_PARAMS = {"id", "p", "story_id", "article_id", "v"}


def canonicalize_url(url):
    if not url or not isinstance(url, str):
        return ""
    try:
        parsed = urlparse(url.strip().lower())
        # Strip trailing slash from path
        path = parsed.path.rstrip("/")
        # Filter query params
        query_pairs = [(k, v) for k, v in parse_qsl(parsed.query) if k in KEEP_QUERY_PARAMS]
        query = urlencode(sorted(query_pairs))
        # Drop fragment
        return urlunparse((parsed.scheme, parsed.netloc, path, "", query, ""))
    except Exception:
        return url.strip().lower()


def load_pass(path, pass_num):
    if not os.path.exists(path):
        print(f"  Pass {pass_num}: {path} not found, skipping.")
        return []
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception as e:
        print(f"  Pass {pass_num}: failed to parse {path}: {e}")
        return []
    if not isinstance(data, list):
        print(f"  Pass {pass_num}: {path} is not a JSON array, skipping.")
        return []
    for item in data:
        if isinstance(item, dict):
            item["_pass"] = pass_num
    return [i for i in data if isinstance(i, dict)]


def item_priority(item):
    """Higher is better. Used to pick the canonical entry per URL group."""
    conf = CONFIDENCE_RANK.get((item.get("confidence") or "").lower(), 0)
    stype = SOURCE_TYPE_RANK.get((item.get("source_type") or "").lower(), 0)
    return (conf, stype)


def main():
    print("=" * 60)
    print("UNION REPORTER PASSES")
    print("=" * 60)

    all_items = []
    pass_counts = {}
    for path, pass_num in PASSES:
        items = load_pass(path, pass_num)
        all_items.extend(items)
        pass_counts[pass_num] = len(items)
        print(f"  Pass {pass_num}: {len(items)} items")

    print(f"\n  Total before dedup: {len(all_items)}")

    if not all_items:
        print("  No items found across any pass. Writing empty raw_items.json.")
        with open(OUT_ITEMS, "w") as f:
            json.dump([], f, indent=2)
        with open(OUT_REPORT, "w") as f:
            json.dump({
                "pass_counts": pass_counts,
                "total_before_dedup": 0,
                "total_after_dedup": 0,
                "merged_groups": 0,
            }, f, indent=2)
        return

    # Group by canonical URL
    groups = {}
    for item in all_items:
        key = canonicalize_url(item.get("url", ""))
        if not key:
            # Items without a URL are kept individually, keyed by headline
            key = "no-url::" + (item.get("headline") or "")[:100].lower()
        groups.setdefault(key, []).append(item)

    merged_count = 0
    unioned = []
    for key, items in groups.items():
        if len(items) == 1:
            chosen = items[0]
            chosen["passes_seen"] = [chosen.pop("_pass", None)]
            chosen["passes_seen"] = [p for p in chosen["passes_seen"] if p is not None]
            unioned.append(chosen)
            continue

        # Multiple items with the same canonical URL — pick the best one
        merged_count += 1
        items_sorted = sorted(items, key=item_priority, reverse=True)
        chosen = items_sorted[0]
        passes_seen = sorted({i.get("_pass") for i in items if i.get("_pass") is not None})
        chosen["passes_seen"] = passes_seen

        # Merge corroborating_urls from the dropped entries (keeping any pre-existing list)
        existing_corrob = list(chosen.get("corroborating_urls") or [])
        for other in items_sorted[1:]:
            other_url = other.get("url")
            if other_url and other_url not in existing_corrob and other_url != chosen.get("url"):
                existing_corrob.append(other_url)
            for url in (other.get("corroborating_urls") or []):
                if url and url not in existing_corrob and url != chosen.get("url"):
                    existing_corrob.append(url)
        if existing_corrob:
            chosen["corroborating_urls"] = existing_corrob

        chosen.pop("_pass", None)
        unioned.append(chosen)

    # Sort: by date desc, then by source_type/confidence
    def sort_key(item):
        date = item.get("date") or "0000-00-00"
        return (date, item_priority(item))

    unioned.sort(key=sort_key, reverse=True)

    # Write outputs
    with open(OUT_ITEMS, "w") as f:
        json.dump(unioned, f, indent=2)

    pass_overlap = {}
    for p in (1, 2, 3):
        items_in_p = [i for i in unioned if p in (i.get("passes_seen") or [])]
        only_in_p = [i for i in unioned if i.get("passes_seen") == [p]]
        pass_overlap[f"pass_{p}_total"] = len(items_in_p)
        pass_overlap[f"pass_{p}_unique_to_this_pass"] = len(only_in_p)

    report = {
        "pass_counts": pass_counts,
        "total_before_dedup": len(all_items),
        "total_after_dedup": len(unioned),
        "merged_groups": merged_count,
        "pass_overlap": pass_overlap,
    }
    with open(OUT_REPORT, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n  Merged duplicate URLs: {merged_count} groups collapsed")
    print(f"  Total after dedup:     {len(unioned)}")
    print(f"\n  Pass uniqueness (items only that pass found):")
    for p in (1, 2, 3):
        print(f"    Pass {p}: {pass_overlap[f'pass_{p}_unique_to_this_pass']} unique / {pass_overlap[f'pass_{p}_total']} total")
    print(f"\n  Wrote {OUT_ITEMS} and {OUT_REPORT}")


if __name__ == "__main__":
    main()
