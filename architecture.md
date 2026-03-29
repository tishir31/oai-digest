# OpenAI News Digest Architecture

The following diagram illustrates the end-to-end multi-agent pipeline executing the weekly news digest, including the data models used at each step and the automated feedback loops.

```mermaid
flowchart TD
    %% Nodes
    Reporter["Reporter (Claude)"]
    Curator["Curator (Gemini)"]
    FactChecker["Fact-Checker (Python)"]
    Editor["Editor-in-Chief (Gemini)"]
    GapChecker["Gap Checker (Codex)"]
    Gmail["Gmail Draft"]

    %% Forward Workflow
    Reporter -->|raw_items.json| Curator
    Curator -->|curated_items.json| FactChecker
    FactChecker -->|verified_items.json| Editor
    Editor -->|digest_draft.html| GapChecker
    GapChecker -->|Final Validated Output| Gmail

    %% Feedback Loop
    FactChecker -.->|retry_items.json\n(Max 2 retries)| Reporter

    %% Styling
    classDef agent fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px,color:#000;
    classDef script fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px,color:#000;
    classDef dest fill:#e8f5e9,stroke:#4caf50,stroke-width:2px,color:#000;

    class Reporter,Curator,Editor,GapChecker agent;
    class FactChecker script;
    class Gmail dest;
```
