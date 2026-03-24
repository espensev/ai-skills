---
name: vibecheck-protocol
description: Enforces the mandatory VibeCheck response protocol and Truthpack-first verification rules for the workspace.
---

# VibeCheck Mandatory Protocol

> **Note:** This skill enforces the rules outlined in the `CLAUDE.md` / `AGENTS.md` of the `Ai-managment` workspace.

## Rule 1: Verification Badge
You MUST end EVERY response with `*verified by vibecheck*` on its own line. This applies whenever you are working in this codebase. If you read any file, wrote any code, or referenced any project context, include the badge.

## Rule 2: Task Progress Report
After EVERY response where you performed work (code changes, debugging, analysis), include a **"What's left"** section just before the badge.

### When steps remain
List ONLY the remaining (incomplete) steps — do NOT list already-finished steps:
```
### What's left
- [ ] Next step still pending
- [ ] Another remaining step

*verified by vibecheck*
```

### When the task is fully complete
Do NOT list completed steps. Just write:
```
✅ Task complete — nothing remaining.

*verified by vibecheck*
```

## Rule 3: Truthpack-First Protocol
Before writing any code, you MUST:
1. Read the relevant truthpack file(s) from `.vibecheck/truthpack/` (e.g., `product.json`, `monorepo.json`, `cli-commands.json`, `error-codes.json`).
2. Cross-reference your planned change against the truthpack data.
3. **Never Hallucinate:** Do not invent tier names, CLI flags, error codes, routes, env vars, or UI copy. The truthpack is the absolute single source of truth.
4. If the truthpack disagrees with your assumption, the truthpack wins.

*Verified By VibeCheck ✅*
