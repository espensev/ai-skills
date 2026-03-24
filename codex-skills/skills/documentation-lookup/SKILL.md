---
name: documentation-lookup
description: "Fetch current library, framework, and API documentation before answering library-specific questions. Use when a request depends on up-to-date behavior, setup, migrations, configuration, or code examples for a named library or framework."
---

# Documentation Lookup

Use current docs instead of memory when the answer depends on a library or
framework's actual behavior.

## Scope

- Prefer this skill for named libraries and frameworks.
- Prefer an OpenAI-specific docs skill when the question is about OpenAI
  products or APIs and that skill is available.
- Prefer a broader research skill when the task is market research, product
  comparison, or news synthesis rather than library behavior.

## Dependencies

- Required: none
- Optional: Context7 or another docs MCP
- Fallback: official docs, primary documentation sites, and framework release
  notes via built-in web search

## Workflow

1. Identify the exact library, framework, product, and version if the user gave
   one.
2. Prefer primary sources:
   - official docs
   - official migration guides
   - official API references
   - official release notes
3. If Context7 is available:
   - resolve the library ID first
   - query the docs with the user's exact question
   - keep calls focused and minimal
4. If Context7 is not available, use built-in web search and restrict yourself
   to official sources when possible.
5. Verify the version before answering. If the docs differ across versions, say
   which version your answer reflects.
6. Return the smallest answer that solves the task:
   - direct answer
   - minimal code example
   - one or two source links
   - note any uncertainty or version mismatch

## Rules

- Do not answer library-behavior questions from memory when the docs are easy
  to fetch.
- Do not mix community tutorials with official API facts unless you label them
  clearly.
- Do not pass secrets or tokens to any docs tool.
- Do not over-query. One resolution call plus one or two focused doc queries is
  usually enough.
- Separate sourced facts from your own inference.

## Output

Default response shape:

1. Direct answer
2. Minimal example or config snippet
3. Version or source note when it matters
