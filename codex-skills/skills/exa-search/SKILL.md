---
name: exa-search
description: "Use Exa as an optional research accelerator for current web, code, company, or people search. Use when Exa MCP is available and the task benefits from higher-quality search or page extraction than the default web workflow alone."
---

# Exa Search

Use Exa when it is available and materially better than the default search path.
Do not assume Exa exists in every Codex environment.

## Dependencies

- Required: none
- Optional: Exa MCP tools
- Fallback: built-in web search, primary-source browsing, and the broader
  `deep-research` workflow

## When to Use

- current technical references or code examples
- company or competitor research
- people or organization lookup
- page extraction after search results identify strong sources
- research tasks where semantic ranking helps reduce search noise

## Workflow

1. Check whether Exa tools are actually available in the current runtime.
2. If Exa is available, choose the narrowest useful capability:
   - broad web search
   - filtered or advanced search
   - code-context search
   - company or people research
   - page crawl or extraction
3. Prefer primary sources and official domains when the task is technical.
4. Use Exa to find and narrow sources, then read the best sources directly.
5. If Exa is unavailable, say so briefly and fall back to built-in web search.

## Tool Mapping

Different Exa MCP servers may expose different tool names. Map the current
runtime's Exa tools to these capability buckets instead of assuming one exact
schema:

- web search
- advanced or filtered search
- code-context search
- company research
- people search
- page crawl or extraction
- async deep research, if present

## Rules

- Do not hardcode any harness-specific config path or assume one provider-specific setup flow.
- Do not assume async Exa research agents exist.
- Do not answer from snippets alone when the decision depends on nuance.
- Use Exa as an accelerator, not as a replacement for source judgment.

## Deliverable

When using Exa, provide:

1. what Exa capability you used
2. the key findings
3. source links
4. any fallback used when Exa tools were missing or insufficient

