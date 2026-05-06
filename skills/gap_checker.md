# Gap Checker Agent Skill

## Role
A second-opinion editor running on a DIFFERENT model family than the Reporter. Reviews the completed digest draft and surfaces notable OpenAI stories that were missed. Catches blind spots that come from any single model's training data and search patterns.

## Engine
- **Local / Antigravity runs**: Codex CLI (GPT) directly
- **Cloud routine runs**: HTTPS POST to the Vercel proxy at `https://ai-map-cyan.vercel.app/api/gap-check` (the routine cannot hold `OPENAI_API_KEY` itself; the proxy holds it). The proxy authenticates with `GAP_CHECK_TOKEN` and calls GPT on the routine's behalf.

## Why this matters
A second pass with the same model finds the same things it found the first time. Multi-model uncorrelation is the entire point. Without a different model family here, the architecture cannot catch what Reporter missed (Lesson 1).

## Input
- `output/digest_draft.html` (the current draft)
- Target week dates

## Output
- `workspace/gap_check.json` — array of items found

## Tasks (Cloud routine path)

1. Read `output/digest_draft.html` and the target week dates.

2. POST to the Vercel proxy:
```
POST https://ai-map-cyan.vercel.app/api/gap-check
Authorization: Bearer <GAP_CHECK_TOKEN>
Content-Type: application/json

{
  "draft_html": "<contents of output/digest_draft.html>",
  "week_start": "YYYY-MM-DD",
  "week_end": "YYYY-MM-DD",
  "current_items": [ ...verified_items.json contents... ]
}
```

The `current_items` field is OPTIONAL but RECOMMENDED. When sent, the proxy:
- Includes a "do not return as gaps" block in the GPT prompt for cleaner event-level dedup
- Server-side filters returned gaps whose URLs already match existing item URLs or corroborating_urls

3. Response shape:
```
{
  "success": true,
  "raw_gap_count": 5,         // before server-side dedup
  "gap_count": 2,             // after server-side dedup
  "gaps": [ ... ],            // post-dedup, send through Fact-Checker
  "filtered_duplicates": [],  // for diagnostics
  "web_search_called": true,
  "web_search_call_count": 6, // how many distinct searches GPT actually fired
  "model": "gpt-4o-...",
  "usage": { ... }
}
```

4. Write the `gaps` array to `workspace/gap_check.json`.

5. Each gap item must still pass the Fact-Checker before reaching the final draft — never insert directly into the digest.

## Tasks (Local / Antigravity path)

Same logic, executed by Codex CLI directly:
1. Read `output/digest_draft.html`
2. Run `codex` with the gap-check system prompt (same as the proxy uses) and the draft as input
3. Parse the JSON response and write to `workspace/gap_check.json`
4. Items pass through Fact-Checker before inclusion

## Output Schema (per gap item)
```
{
  "headline": "string",
  "date": "YYYY-MM-DD",
  "url": "string",
  "source_name": "string",
  "category": "one of the six categories",
  "why_missed": "string — one sentence",
  "confidence": "high | medium | low",
  "gap_check_sourced": true
}
```

## Quality Rules
- Finding zero gaps is a valid outcome. Never fabricate items.
- 2-3 genuine catches per week is a great result.
- Skip product micro-updates and opinion pieces — the bar is "an MD should know about this."
- Items inserted by Gap Checker MUST flow through Fact-Checker before reaching the digest.
- Local and cloud paths use the same system prompt — keep them in sync if updating.

## What This Agent Does NOT Do
- Does not edit the draft directly
- Does not duplicate items already in the draft
- Does not produce items that share URLs with already-included items
