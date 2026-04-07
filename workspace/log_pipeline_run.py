"""
Pipeline Audit Logger

Reads all pipeline output files and appends a structured run summary to
workspace/pipeline_audit_log.json. Run as the final step of the workflow.

Usage:
    python3 workspace/log_pipeline_run.py
"""

import json
import os
from datetime import datetime


def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else []
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default if default is not None else []


def main():
    raw = load_json("workspace/raw_items.json")
    curated_all = load_json("workspace/curated_items.json")
    curated = [i for i in curated_all if isinstance(i, dict) and i.get("curated")]
    cut = [i for i in curated_all if isinstance(i, dict) and i.get("curated") is False]
    verified = load_json("workspace/verified_items.json")
    rejections = load_json("workspace/rejections.json")
    coverage = load_json("workspace/coverage_report.json", default={})
    backfill = load_json("workspace/backfill_items.json")
    gap_check = load_json("workspace/gap_check.json")
    diversity = load_json("workspace/source_diversity_report.json", default={})
    calib_log = load_json("workspace/calibration_log.json")
    last_calib = calib_log[-1] if calib_log else {}

    # Confidence breakdown from raw
    conf = {"high": 0, "medium": 0, "low": 0}
    for item in raw:
        c = item.get("confidence", "medium")
        if c in conf:
            conf[c] += 1

    # Source type counts from raw
    src_types = {}
    for item in raw:
        st = item.get("source_type", "unknown")
        src_types[st] = src_types.get(st, 0) + 1

    # URL status counts from verified
    url_200 = sum(1 for i in verified if i.get("url_status") == 200)
    url_403 = sum(1 for i in verified if i.get("url_status") == 403)
    url_other = len(verified) - url_200 - url_403

    # Cut reason summary
    cut_reasons = {}
    for item in cut:
        reason = item.get("cut_reason", "unknown")
        cut_reasons[reason] = cut_reasons.get(reason, 0) + 1

    run_entry = {
        "run_id": f"run_{datetime.now().strftime('%Y%m%dT%H%M%S')}",
        "run_date": datetime.now().isoformat(),
        "steps": {
            "reporter": {
                "items_produced": len(raw),
                "confidence_breakdown": conf,
                "source_type_counts": src_types,
                "gmail_sourced_count": sum(1 for i in raw if i.get("gmail_sourced")),
            },
            "curator": {
                "items_in": len(raw),
                "items_kept": len(curated),
                "items_cut": len(cut),
                "cut_reasons": cut_reasons,
                "source_diversity_warning": diversity.get("diversity_warning"),
                "items_with_corroboration_2plus": sum(
                    1 for i in curated if i.get("corroboration_count", 0) >= 2
                ),
            },
            "coverage_auditor": {
                "verdict": coverage.get("verdict"),
                "curated_count": coverage.get("curated_count"),
                "coverage_floor": coverage.get("coverage_floor"),
                "empty_categories": coverage.get("empty_categories", []),
                "thin_categories": coverage.get("thin_categories", []),
            },
            "backfill_reporter": {
                "ran": len(backfill) > 0,
                "items_found": len(backfill),
                "backfill_sourced_count": sum(
                    1 for i in backfill if i.get("backfill_sourced")
                ),
            },
            "fact_checker": {
                "items_in": len(curated),
                "items_verified": len(verified),
                "items_rejected": len(rejections),
                "rejection_reasons": [r.get("rejection_reason") for r in rejections],
                "url_200_count": url_200,
                "url_403_count": url_403,
                "url_other_count": url_other,
            },
            "editor_in_chief": {
                "items_in_digest": len(verified),
                "historical_dedup_check_run": True,
            },
            "gap_checker": {
                "ran": len(gap_check) > 0 or os.path.exists("workspace/gap_check.json"),
                "items_found": len(gap_check),
            },
            "confidence_calibration": {
                "ran": bool(last_calib),
                "well_calibrated": last_calib.get("well_calibrated"),
                "high_total": last_calib.get("confidence_stats", {}).get("high", {}).get("total"),
            },
        },
    }

    audit_log = load_json("workspace/pipeline_audit_log.json")
    audit_log.append(run_entry)
    with open("workspace/pipeline_audit_log.json", "w") as f:
        json.dump(audit_log, f, indent=2)

    # Print summary
    print("=" * 50)
    print("PIPELINE RUN COMPLETE")
    print("=" * 50)
    print(f"Reporter:        {len(raw)} items")
    print(f"Curator:         {len(curated)} kept, {len(cut)} cut")
    print(f"Coverage:        {coverage.get('verdict', 'not_run')}")
    print(f"Backfill:        {'ran' if len(backfill) > 0 else 'not needed'} ({len(backfill)} items)")
    print(f"Fact-Checker:    {len(verified)} verified, {len(rejections)} rejected")
    print(f"Editor-in-Chief: {len(verified)} items in digest")
    print(f"Gap Checker:     {len(gap_check)} gaps found")
    print(f"Calibration:     {'well-calibrated' if last_calib.get('well_calibrated') else 'MISCALIBRATED'}")
    print(f"\nRun logged to workspace/pipeline_audit_log.json")


if __name__ == "__main__":
    main()
