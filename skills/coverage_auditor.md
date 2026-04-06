# Coverage Auditor Agent Skill

## Role
You are a coverage auditor. Your sole job is to check whether the Curator's output meets minimum coverage thresholds for the weekly digest. You do NOT search for news, write summaries, or edit anything. You count, measure, and report.

## Engine
Python script (`workspace/coverage_check.py`). No model needed.

## Input
- `workspace/curated_items.json`

## Output
- `workspace/coverage_report.json`

## Logic

### 1. Count Check
Count items where `curated: true`. Compare against the coverage floor (default: 7).

### 2. Category Distribution
Check how many of the 6 categories have at least one curated item:
1. Product Launches & Updates
2. Partnerships & Deals
3. Earnings / Financials / Fundraising
4. Regulatory & Policy
5. Key Hires / Departures
6. Technical Research / Model Releases

Flag any category with 0 items.

### 3. Cut Analysis
Summarize why items were cut:
- How many were clustering cuts (healthy — means Reporter found the story from multiple angles)
- How many were quality cuts (concerning — means Reporter fed in weak items)

### 4. Verdict
Output one of:
- `"sufficient"` — item count >= floor AND no more than 1 empty category
- `"needs_backfill"` — item count < floor OR 2+ categories empty

### 5. Output Schema
```json
{
  "verdict": "sufficient | needs_backfill",
  "curated_count": 11,
  "coverage_floor": 7,
  "categories_covered": 6,
  "empty_categories": [],
  "thin_categories": ["category_name"],
  "cut_summary": {
    "clustering": 6,
    "quality": 0,
    "other": 0
  },
  "backfill_instructions": null
}
```

If `needs_backfill`, the `backfill_instructions` field should list the empty/thin categories so the Backfill Reporter knows exactly where to search.

## What This Agent Does NOT Do
- Does not search for news
- Does not edit or rewrite items
- Does not make editorial judgments about item quality
- Does not run any model — it's pure counting logic
