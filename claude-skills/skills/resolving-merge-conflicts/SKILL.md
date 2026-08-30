---
name: resolving-merge-conflicts
description: "Resolve an in-progress git merge or rebase conflict from the original intent of each change, then verify and finish. Use when the user is mid-merge/mid-rebase with conflicts, or asks to resolve, finish, or untangle a conflicted merge/rebase."
argument-hint: "[during a merge/rebase conflict]"
allowed-tools: Read, Glob, Grep, Bash, Edit, Write
user-invocable: true
---

# Resolving Merge Conflicts

1. **See the current state** of the merge/rebase. Check git history and the
   conflicting files (`git status`, `git diff`, the conflict markers).

2. **Find the primary sources** for each conflict. Understand deeply *why* each
   change was made and what the original intent was — read the commit messages,
   check the PRs, check the original issues/tickets.

3. **Resolve each hunk.** Preserve both intents where possible. Where
   incompatible, pick the one matching the merge's stated goal and note the
   trade-off. Do **not** invent new behaviour.

4. **Run the project's automated checks** — typically typecheck, then tests,
   then format. Fix anything the merge broke.

5. **Finish the merge/rebase.** Stage everything and commit. If rebasing,
   continue (`git rebase --continue`) until all commits are rebased.

## When to stop instead of force a resolution

Prefer to resolve. But **abort or escalate** (`git merge --abort` /
`git rebase --abort`) when forcing a resolution would lose work or guess at
intent you can't recover — e.g. you can't determine why a conflicting change was
made, the two sides encode genuinely incompatible decisions only the user can
arbitrate, or local uncommitted work is at risk. Surface the trade-off to the
user rather than silently picking a side or fabricating behaviour. Aborting and
asking is cheaper than a wrong merge.
