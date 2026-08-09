# PASS 0 And Gate Checklist

Use this reference for full audit-gated campaigns. Keep the controller in charge
of scope, safety, integration, and final acceptance.

## PASS 0 Structural Map

Collect:

- tracked files by top-level directory;
- module or file line counts;
- public types, functions, commands, scripts, targets, or docs authority;
- imports, includes, references, and project links;
- consumers or callers, based on includes, project references, textual type
  references, documented target links, or repo-native graph tooling;
- modules importing more than five sources;
- modules imported by more than ten consumers;
- generated or vendor files that should be counted but excluded from detailed
  review.

Do not overclaim a full call graph unless tooling actually produced one. Say
when consumers are inferred.

## Marker Scan

Search for:

- TODO, FIXME, HACK, XXX;
- stale source comments contradicting current behavior;
- stale docs contradicting source or authoritative docs;
- repeated function or test bodies separated by large distance;
- duplicated string vocabularies across producer/consumer paths;
- mid-file style or convention shifts;
- prompt/session/AI-specific instructions in active plans.

Classify each hit:

- current source risk;
- active docs drift;
- historical or harmless context;
- vendor/generated noise;
- false positive.

## Iteration-Depth Estimate

Use git history as a risk signal only:

- total commits on HEAD and all refs;
- first and latest commit dates;
- author/committer distribution;
- daily burst counts;
- merge/review/fix/test subject patterns;
- blame concentration for large files;
- WIP/checkpoint commits.

High-risk patterns include compressed history, single-author dominance, huge
one-commit files, and weak review/test follow-up. Low commit count is not
required for risk; high velocity can also require audit.

## Findings-First Review Template

```markdown
# <Review Title>

Date:
Reviewer:
Scope:
Verdict: PASS | FAIL | FOLLOW-UP REQUIRED

## Findings

1. Severity - finding title
   Evidence: file:line, command output, artifact path.
   Impact:
   Recommendation:

## Safety And Dirty-Tree Notes

## Inventory Summary

## Deferred Work

## Validation
```

## Agent Packet Template

```markdown
# Agent <Letter>: <Name>

## Scope
## Dependencies
## Output Files
## Owned Files
## Exit Criteria
## Required Reads
## Task Instructions
## Constraints
## Verification Commands
## Do NOT
```

Every editing packet needs exact owned files. Every reviewer packet needs the
artifacts it must read and the verdict it must produce.

## Independent Review Gates

Plan/spec reviewer checks:

- review-only gate respected;
- every lane has owned files;
- no overlapping write ownership;
- safety stops cover live/system side effects;
- validation is appropriate;
- PASS 0 findings are represented in specs;
- verifier packet covers all lanes.

Post-implementation reviewer checks:

- final diff only touches owned files;
- no live/system actions occurred;
- validation commands were run or explicitly justified;
- PASS 0 findings were fixed, deferred with reason, or converted into follow-up;
- generated artifacts are linked and readable.

## What To Skip

Skip:

- ceremony that does not create evidence;
- broad refactors before structural review;
- more subagents than the file ownership split supports;
- implementation before independent plan review;
- reviewer agents that also fix their own findings;
- chat-only plans for repo-grounded work;
- ad hoc build commands when repo wrappers exist;
- live/system operations during ordinary review or docs work.

Keep:

- map first;
- findings first;
- explicit lanes;
- independent reviewers;
- main-thread verification;
- durable artifacts;
- safety stops.
