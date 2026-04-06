"""
Confidence Calibration — Post-Pipeline Quality Check

Run AFTER the Editor-in-Chief produces the final digest.
Compares Reporter confidence scores against what actually survived the pipeline.
Over time, this tells you if "high confidence" items actually make it to the final draft
and if "low confidence" items are consistently cut.

Usage:
    python workspace/calibrate_confidence.py

Reads:
    workspace/raw_items.json    (Reporter output with confidence scores)
    workspace/curated_items.json (Curator output — what survived filtering)
    workspace/verified_items.json (Fact-Checker output — what survived verification)
    output/digest_draft.html     (Final output — what made the email)
    workspace/calibration_log.json (historical calibration data, created if missing)

Output:
    Prints a calibration report to stdout
    Appends this run's data to workspace/calibration_log.json
"""

import json
import os
from datetime import datetime
from collections import Counter

def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)

def get_headlines(items):
    """Extract headlines from a list of items, handling both curated=true and raw formats."""
    return {item["headline"] for item in items if item.get("curated", True)}

def main():
    raw = load_json("workspace/raw_items.json")
    curated = [i for i in load_json("workspace/curated_items.json") if i.get("curated")]
    verified = load_json("workspace/verified_items.json")

    curated_headlines = {i["headline"] for i in curated}
    verified_headlines = {i["headline"] for i in verified}

    # Count survival rates by confidence level
    confidence_stats = {"high": {"total": 0, "survived_curation": 0, "survived_verification": 0},
                        "medium": {"total": 0, "survived_curation": 0, "survived_verification": 0},
                        "low": {"total": 0, "survived_curation": 0, "survived_verification": 0}}

    for item in raw:
        conf = item.get("confidence", "medium")
        if conf not in confidence_stats:
            conf = "medium"
        confidence_stats[conf]["total"] += 1
        if item["headline"] in curated_headlines:
            confidence_stats[conf]["survived_curation"] += 1
        if item["headline"] in verified_headlines:
            confidence_stats[conf]["survived_verification"] += 1

    # Print report
    print("=" * 60)
    print("CONFIDENCE CALIBRATION REPORT")
    print(f"Run date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    print(f"\nReporter produced: {len(raw)} items")
    print(f"Curator kept:      {len(curated)} items")
    print(f"Fact-check passed:  {len(verified)} items")
    print()

    for level in ["high", "medium", "low"]:
        s = confidence_stats[level]
        if s["total"] == 0:
            continue
        curation_rate = s["survived_curation"] / s["total"] * 100
        verification_rate = s["survived_verification"] / s["total"] * 100
        print(f"  {level.upper()} confidence: {s['total']} items")
        print(f"    → {s['survived_curation']}/{s['total']} survived curation ({curation_rate:.0f}%)")
        print(f"    → {s['survived_verification']}/{s['total']} survived verification ({verification_rate:.0f}%)")
        print()

    # Check calibration quality
    high = confidence_stats["high"]
    low = confidence_stats["low"]
    well_calibrated = True

    if high["total"] > 0 and low["total"] > 0:
        high_survival = high["survived_verification"] / high["total"]
        low_survival = low["survived_verification"] / low["total"]
        if high_survival <= low_survival:
            print("⚠️  MISCALIBRATED: High-confidence items don't survive better than low-confidence.")
            print("    The Reporter's confidence scoring needs tuning.")
            well_calibrated = False
        else:
            print("✅ Confidence scores are directionally correct (high > low survival rate).")
    elif high["total"] > 0 and low["total"] == 0:
        print("ℹ️  No low-confidence items to compare against. Can't fully assess calibration.")

    # Save to calibration log
    log_path = "workspace/calibration_log.json"
    log = load_json(log_path)
    log.append({
        "run_date": datetime.now().isoformat(),
        "raw_count": len(raw),
        "curated_count": len(curated),
        "verified_count": len(verified),
        "confidence_stats": confidence_stats,
        "well_calibrated": well_calibrated
    })
    with open(log_path, "w") as f:
        json.dump(log, f, indent=2)
    print(f"\nCalibration data saved to {log_path}")

if __name__ == "__main__":
    main()
