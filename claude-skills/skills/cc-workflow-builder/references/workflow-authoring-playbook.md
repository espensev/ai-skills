# Workflow authoring playbook (intent → validated canvas)

A repeatable method for turning "build me a workflow for X" into a correct CC
Workflow Studio graph. Pairs with `cc-workflow-studio-reference.md` (the
constraints). Derived from the `lane-pipeline` build.

## 0. Orient before designing

- Call `get_workflow_schema` and `get_current_workflow` (+ `list_available_agents`).
- **Look for an existing real process to map.** The best workflows encode a
  process the user already has (a runbook, a coordination doc, a pipeline), not
  an invented one. Read it; map its stages 1:1 where you can.

## 1. Brainstorm intent (don't skip — the spec is usually vague)

Ask, one at a time, only what changes the shape:

- **Scope** — what does *one run* do? (the whole process end-to-end, one
  sub-piece, or one item through it?)
- **Autonomy** — how many human-pause (`askUserQuestion`) nodes? Fully
  autonomous = zero, terminating only at End states. More pauses = more branches.
- **Granularity** — per-item or batch? Remember: **no loops on the canvas**, so
  "run once per item, invoke repeatedly" is the natural unit; batching means an
  internal loop inside a sub-agent.
- **Irreversible / outward steps** — surface them explicitly. Keep the host
  environment's rules even in an "autonomous" flow (e.g. a promote/deploy step
  that *stages* instead of pushing when the repo says "commit only when asked").

## 2. Map stages → nodes (respecting the constraints)

- **prompt node** for orchestrator-side steps (git, CI, talking to the user).
  **subAgent** for isolated reasoning/editing.
- **Branch points** → `ifElse` (2-way) or `switch` (3–10, last = default). Each
  branch must connect to something that reaches an End.
- **No fan-in:** converge failure/alt paths on shared **End** nodes (e.g.
  `end_promoted` / `end_rework` / `end_offpath`). Give each terminal state its
  own End for legibility.
- **No fan-out+merge:** express parallel work as **one sub-agent that runs the
  parts internally**, or as **sequential** nodes. (e.g. a 3-lens QC harness → one
  opus sub-agent; or split into 2 sequential QC nodes if you want a specialist
  agent per slice.)
- **Separate concerns into passes** when the domain demands independence (author
  vs. verify must be different nodes so the verifier doesn't trust the author).

## 3. Choose agents & models deliberately

- Built-in `explore` for read/classify/analyze; `general-purpose` for edits;
  `plan` for design. Leave their model auto-controlled.
- **Pin a model only where rigor matters** — use the inline sub-agent form
  (no `builtInType`, set `model: opus`). Overusing opus is waste.
- Wire **custom agents** (`commandFilePath` from `list_available_agents`) when the
  user wants a specialist (e.g. a code-reviewer for the code/a11y slice, a
  simplifier post-assembly). Custom agents can be sequenced but not merged.

## 4. Parameterize into a template (optional but cheap)

Put a `variables` block on the first prompt node that resolves a "profile"
(names + paths), have it emit the profile, and make every downstream node read
from it. Then switching context is one `update_nodes` call swapping those
variables. Ship **paste-ready presets** so the user can flip in one call.

## 5. Build, verify, hand off

- `apply_workflow` for the whole graph (pass `revision`); `update_nodes` for
  tweaks. Both are diff-gated — the **user's accept/reject is the review gate**,
  so you don't need a heavyweight written plan for a canvas build.
- `get_current_workflow` to confirm node/connection counts and that custom-agent
  paths + switch defaults validated.
- Record the design where the host repo's doc contract wants it, and register it
  in that directory's index.

## Anti-patterns (learned the hard way)

- Designing a loop-back or a fan-in edge — **impossible**; rework into extra Ends
  or an internal sub-agent step.
- Setting `model` on a built-in agent — ignored/invalid; use the inline form.
- Using `{{var}}` in a node that has no `variables` block — it won't substitute;
  only prompt nodes template.
- Writing the design into a path the host repo's directory contract forbids —
  check the repo's CLAUDE.md/altitude rules first.
- Treating "autonomous" as license to do the irreversible step — stage it and
  end there unless the user opted into auto-push.
