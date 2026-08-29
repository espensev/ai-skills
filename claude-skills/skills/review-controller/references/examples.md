# Review Controller — reference

## Wave compositions that usually fit

| Objective shape | Wave 1 (parallel) | Wave 2 (conditional) |
|---|---|---|
| UX flow / screens | Journey · Usability · Information Architecture | Verification on Critical/High; Adversarial on top 3 |
| Feature or system behaviour | Functional · Risk & Edge-Case · Journey | Verification on disputed claims |
| Broad-impact action (move, delete, merge, bulk) | Functional · Risk & Edge-Case · Usability · Journey | Adversarial |
| Accessibility-led | Accessibility · Usability · Journey | Verification |
| Small (≤ 3 screens/files) or tightly coupled | solo — no agents | direct check by the controller |

Model: every specialist is `review-specialist` (Opus, pinned in the agent
file). The only override is `model: "sonnet"` for a pure inventory pass during
Map ("list every screen, route and state in E-1…E-6") whose output is treated
as inventory, not findings.

## Example Wave 1 packet — Usability lens

```
ROLE      Usability
OBJECTIVE Can an admin move an organisation to another group without error, and do they know it worked?
CONTEXT   B2B admin console. Admins manage 50–500 organisations grouped by region.
          Moving an organisation changes billing roll-up and member visibility.
          Journey under review: Organisations list → select → Move → pick destination → confirm → done.
          Decision this supports: ship as-is vs fix before the Q3 rollout.
SCOPE     Inspect: the five screens of the Move journey, their confirmation and completion states.
          Exclude: bulk move, the permissions model, billing back-end behaviour.
EVIDENCE  Use only:
          E-1 D:/DevHome/tmp/rc-move-org/e1-org-list.png
          E-2 D:/DevHome/tmp/rc-move-org/e2-move-dialog.png
          E-3 D:/DevHome/tmp/rc-move-org/e3-destination-picker.png
          E-4 D:/DevHome/tmp/rc-move-org/e4-confirm.png
          E-5 D:/DevHome/tmp/rc-move-org/e5-done.png
          E-6 D:/DevHome/tmp/rc-move-org/e6-move-dialog.dom.txt
CRITERIA  clarity; discoverability; efficiency; error prevention; feedback; recovery;
          fit with the wider journey;
          destination clarity; completion feedback; findability afterward
RETURN    ≤ 8 findings, ≤ 600 words, your standard return shape
STOP      Halt and report instead of guessing on: insufficient evidence; conflicting
          requirements; cross-area dependency; broad impact; major trade-off; scope change needed.
```

Agent call: `subagent_type: "review-specialist"`, `description: "review:usability:move-org"`,
no `model` override. Launch it in the same message as the other Wave 1 calls.

## Example Wave 2 packet — Verification

```
ROLE      Verification
OBJECTIVE Are claims C-1…C-3 supported by the cited evidence?
CONTEXT   B2B admin console; Move-organisation journey; ship/fix decision for Q3.
SCOPE     Inspect only the cited locations. Exclude everything else.
EVIDENCE  Use only:
          E-3 D:/DevHome/tmp/rc-move-org/e3-destination-picker.png
          E-4 D:/DevHome/tmp/rc-move-org/e4-confirm.png
          E-5 D:/DevHome/tmp/rc-move-org/e5-done.png
CLAIMS    C-1 | destination picker has no search; > 100 groups listed unfiltered | [E-3]
          C-2 | confirm step does not state the billing effect of the move   | [E-4]
          C-3 | no undo path is offered after completion                       | [E-5]
RETURN    V-n per claim (CONFIRMED / REFUTED / UNVERIFIABLE with evidence), then any new F-n
STOP      Halt on insufficient evidence; do not widen scope to decide a claim.
```

The Verification packet carries the claims and the E-ids only — never the
originating agent's reasoning or the controller's notes.

## Example redirect (SendMessage to the same agent)

> F-2 has no evidence pointer. Cite the E-id and location that shows the
> missing confirmation text, or move F-2 to OPEN. Return only the corrected
> F-2 line.

## Domain checklist — sorting / moving organisations

- Discovery, naming, destination clarity, mental model
- Temporary vs personal vs shared vs persistent
- Effects on grouping, ownership, permissions, billing, reporting, visibility,
  members, child objects
- Confirmation, undo, audit history, concurrency, bulk actions, partial
  failure, recovery
- Completion feedback, preserved context, navigation / search / filters /
  counts / saved views, findability afterward

## Registry row format (`registry.md`)

```
| ID | area | source | severity | confidence | status | evidence | resolution |
|---|---|---|---|---|---|---|---|
| R-1 | Move: destination | usability, journey | High | High | verified (V-1) | E-3:picker list | fix before rollout |
| R-2 | Move: confirm | usability | Medium | Medium | conflict → open | E-4 vs E-6 | requirement unclear: billing text |
```

Status vocabulary: `accepted` · `merged into R-n` · `conflict` · `verified (V-n)`
· `refuted` · `open question` · `rejected (reason)`.
