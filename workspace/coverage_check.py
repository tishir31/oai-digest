"""
Coverage Auditor — Post-Curator quality gate

Checks whether the Curator's output meets minimum coverage thresholds.
If coverage is insufficient, outputs instructions for the Backfill Reporter.

Usage:
    python3 workspace/coverage_check.py

Reads:
    workspace/curated_items.json

Output:
    workspace/coverage_report.json
    Prints summary to stdout
"""

import json
import os

COVERAGE_FLOOR = 7
ALL_CATEGORIES = [
    "Product Launches & Updates",
    "Partnerships & Deals",
    "Earnings / Financials / Fundraising",
    "Regulatory & Policy",
    "Key Hires / Departures",
    "Technical Research / Model Releases",
]


def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def main():
    items = load_json("workspace/curated_items.json")

    curated = [i for i in items if isinstance(i, dict) and i.get("curated")]
    cut = [i for i in items if isinstance(i, dict) and i.get("curated") is False]

    curated_count = len(curated)

    # Category distribution
    category_counts = {}
    for item in curated:
        cat = item.get("category", "Unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    empty_categories = [c for c in ALL_CATEGORIES if category_counts.get(c, 0) == 0]
    thin_categories = [c for c in ALL_CATEGORIES if category_counts.get(c, 0) == 1]

    # Cut analysis
    clustering_cuts = 0
    quality_cuts = 0
    other_cuts = 0
    for item in cut:
        reason = (item.get("cut_reason") or "").lower()
        if "cluster" in reason:
            clustering_cuts += 1
        elif any(w in reason for w in ["weak", "vague", "stale", "duplicate", "quality"]):
            quality_cuts += 1
        else:
            other_cuts += 1

    # Verdict
    if curated_count >= COVERAGE_FLOOR and len(empty_categories) <= 1:
        verdict = "sufficient"
    else:
        verdict = "needs_backfill"

    backfill_instructions = None
    if verdict == "needs_backfill":
        gaps = []
        if curated_count < COVERAGE_FLOOR:
            gaps.append(f"Only {curated_count} items (floor is {COVERAGE_FLOOR}). Search broadly for any notable stories missed.")
        if empty_categories:
            gaps.append(f"Empty categories: {', '.join(empty_categories)}. Search specifically for stories in these areas.")
        backfill_instructions = " ".join(gaps)

    report = {
        "verdict": verdict,
        "curated_count": curated_count,
        "coverage_floor": COVERAGE_FLOOR,
        "categories_covered": len(ALL_CATEGORIES) - len(empty_categories),
        "category_counts": category_counts,
        "empty_categories": empty_categories,
        "thin_categories": thin_categories,
        "cut_summary": {
            "clustering": clustering_cuts,
            "quality": quality_cuts,
            "other": other_cuts,
        },
        "backfill_instructions": backfill_instructions,
    }

    with open("workspace/coverage_report.json", "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print("=" * 50)
    print("COVERAGE AUDIT")
    print("=" * 50)
    print(f"Curated items:    {curated_count} (floor: {COVERAGE_FLOOR})")
    print(f"Categories:       {len(ALL_CATEGORIES) - len(empty_categories)}/{len(ALL_CATEGORIES)}")
    print(f"Cuts:             {clustering_cuts} clustering, {quality_cuts} quality, {other_cuts} other")
    if empty_categories:
        print(f"Empty categories: {', '.join(empty_categories)}")
    if thin_categories:
        print(f"Thin categories:  {', '.join(thin_categories)}")
    print(f"\nVerdict: {verdict.upper()}")
    if backfill_instructions:
        print(f"Backfill: {backfill_instructions}")
    print(f"\nSaved to workspace/coverage_report.json")


if __name__ == "__main__":
    main()
