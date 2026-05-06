"""
Coverage Check (Content-based) — Coverage Auditor 2.0

The original coverage_check.py is shape-based: it asks "does the digest have
≥7 items across enough categories?" That gate passes even when major news of
the week is missing (Lesson 19).

This script is content-based: it sends the current item list to the Vercel
proxy (which uses GPT-4o + web_search_preview) and asks "what major OpenAI
stories from this week are NOT in this list?" Anything returned here is a
mandatory backfill candidate — it must flow through Fact-Checker and into
the digest before delivery.

Reads:
    workspace/curated_items.json
    Environment: GAP_CHECK_TOKEN (the routine prompt will export this)

Writes:
    workspace/content_coverage_report.json
    workspace/content_gap_items.json  (items to be added; empty if none)

Usage:
    GAP_CHECK_TOKEN=... python3 workspace/coverage_check_content.py <week_start> <week_end>

If GAP_CHECK_TOKEN is not set, prints a warning and writes an empty report
(non-blocking — pipeline continues without this check).
"""

import json
import os
import sys
import urllib.request
import urllib.error

CURATED_PATH = "workspace/curated_items.json"
REPORT_PATH = "workspace/content_coverage_report.json"
GAP_ITEMS_PATH = "workspace/content_gap_items.json"

VERCEL_URL = "https://ai-map-cyan.vercel.app/api/gap-check"


def build_synthetic_draft(items):
    """Build a compact text summary of curated items for the gap-check call.

    The Vercel proxy expects a `draft_html` string. We synthesize one from the
    curated items so the proxy can compare against the same content the Editor
    would write — but earlier in the pipeline.
    """
    lines = ["<html><body>", "<h1>Curated digest items (pre-Editor)</h1>"]
    by_category = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        if not item.get("curated"):
            continue
        cat = item.get("category", "Uncategorized")
        by_category.setdefault(cat, []).append(item)

    for cat, cat_items in by_category.items():
        lines.append(f"<h2>{cat}</h2>")
        for item in cat_items:
            headline = item.get("headline", "(no headline)")
            date = item.get("date", "")
            url = item.get("url", "")
            source = item.get("source_name", "")
            lines.append(
                f"<p><b>{headline}</b> ({date}) — Source: {source}. "
                f"<a href='{url}'>{url}</a></p>"
            )

    lines.append("</body></html>")
    return "\n".join(lines)


def call_gap_check(draft_html, week_start, week_end, token):
    body = json.dumps({
        "draft_html": draft_html,
        "week_start": week_start,
        "week_end": week_end,
    }).encode()

    req = urllib.request.Request(
        VERCEL_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gap-check HTTP {e.code}: {body}") from e


def normalize_url(url):
    if not url:
        return ""
    return url.strip().lower().rstrip("/").split("?")[0].split("#")[0]


def filter_against_existing(gaps, items):
    """Drop gap items whose URLs are already in curated items (false positives)."""
    existing_urls = set()
    for it in items:
        if isinstance(it, dict):
            existing_urls.add(normalize_url(it.get("url", "")))
            for u in (it.get("corroborating_urls") or []):
                existing_urls.add(normalize_url(u))
    return [g for g in gaps if normalize_url(g.get("url", "")) not in existing_urls]


def main():
    if len(sys.argv) < 3:
        print("Usage: coverage_check_content.py <week_start YYYY-MM-DD> <week_end YYYY-MM-DD>")
        sys.exit(2)

    week_start, week_end = sys.argv[1], sys.argv[2]

    token = os.environ.get("GAP_CHECK_TOKEN")
    if not token:
        # Non-blocking: write empty outputs and exit cleanly.
        print("WARNING: GAP_CHECK_TOKEN not set. Skipping content coverage check.")
        with open(REPORT_PATH, "w") as f:
            json.dump({
                "verdict": "skipped",
                "reason": "GAP_CHECK_TOKEN not set in environment",
                "gap_count": 0,
            }, f, indent=2)
        with open(GAP_ITEMS_PATH, "w") as f:
            json.dump([], f, indent=2)
        return

    if not os.path.exists(CURATED_PATH):
        print(f"Error: {CURATED_PATH} not found.")
        sys.exit(1)

    with open(CURATED_PATH) as f:
        items = json.load(f)

    print("=" * 60)
    print("CONTENT COVERAGE CHECK (calling Vercel proxy)")
    print("=" * 60)
    print(f"  Curated items: {sum(1 for i in items if isinstance(i, dict) and i.get('curated'))}")
    print(f"  Week: {week_start} to {week_end}")

    draft_html = build_synthetic_draft(items)

    try:
        result = call_gap_check(draft_html, week_start, week_end, token)
    except Exception as e:
        print(f"  ERROR calling Vercel proxy: {e}")
        with open(REPORT_PATH, "w") as f:
            json.dump({
                "verdict": "error",
                "reason": str(e),
                "gap_count": 0,
            }, f, indent=2)
        with open(GAP_ITEMS_PATH, "w") as f:
            json.dump([], f, indent=2)
        return

    raw_gaps = result.get("gaps", []) or []
    filtered_gaps = filter_against_existing(raw_gaps, items)

    print(f"  Gap-check returned: {len(raw_gaps)} candidates")
    print(f"  After URL dedup vs curated: {len(filtered_gaps)} new candidates")

    for g in filtered_gaps:
        print(f"    + {g.get('headline', '(no headline)')[:80]} | {g.get('source_name', '')} | {g.get('url', '')}")

    # Mark items so downstream can identify them
    for g in filtered_gaps:
        g["from_content_coverage_check"] = True
        g["confidence"] = g.get("confidence", "medium")

    verdict = "needs_backfill" if filtered_gaps else "sufficient"

    report = {
        "verdict": verdict,
        "raw_gap_count": len(raw_gaps),
        "filtered_gap_count": len(filtered_gaps),
        "web_search_called": result.get("web_search_called"),
        "model": result.get("model"),
        "usage": result.get("usage"),
        "week_start": week_start,
        "week_end": week_end,
    }

    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    with open(GAP_ITEMS_PATH, "w") as f:
        json.dump(filtered_gaps, f, indent=2)

    print(f"\n  Verdict: {verdict.upper()}")
    print(f"  Wrote {REPORT_PATH} and {GAP_ITEMS_PATH}")
    if filtered_gaps:
        print(f"\n  These items MUST flow through Fact-Checker and into the digest:")
        for g in filtered_gaps:
            print(f"    - {g.get('headline', '')}")


if __name__ == "__main__":
    main()
