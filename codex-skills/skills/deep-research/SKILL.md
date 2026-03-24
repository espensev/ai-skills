---
name: deep-research
description: "Run current, cited research workflows for technical or product decisions. Use when the user wants a research-backed answer, comparison, or recommendation and the work requires multiple current sources rather than memory alone."
---

# Deep Research

Produce decision-ready research with current sources and explicit uncertainty.

## Scope

- Use this skill for market, tool, vendor, standards, and technology research.
- Use `documentation-lookup` when the task is really a library-doc question.
- Use a more specialized docs skill when the topic is OpenAI-specific and such a
  skill is available.

## Dependencies

- Required: built-in web search
- Optional: Exa, Firecrawl, Context7, or other research-oriented MCPs
- Fallback: primary websites, official docs, release notes, filings, and
  reputable reporting

## Workflow

1. Clarify the decision being supported if the user did not state it.
2. Break the topic into a few sub-questions.
3. Search broadly, then narrow to primary or high-quality sources.
4. Prefer current evidence. If older data is unavoidable, label it as such.
5. Read enough source material to separate:
   - fact
   - inference
   - recommendation
6. Synthesize into a concise recommendation with citations.

## Research Rules

- Every important claim needs a source.
- Say when evidence is weak, mixed, or stale.
- Prefer primary sources over summaries when available.
- Do not use parallel subagents unless the user explicitly asks for delegated or
  parallel work.
- Keep the source list tight; quality matters more than count.

## Deliverable

Default structure:

1. recommendation or executive summary
2. key findings
3. tradeoffs and risks
4. explicit assumptions or unknowns
5. source links
