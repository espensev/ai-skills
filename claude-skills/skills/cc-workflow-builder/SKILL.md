---
name: cc-workflow-builder
description: Use whenever building, editing, generalizing, debugging, or reviewing a CC Workflow Studio workflow — the visual node-graph editor driven through its MCP server (tools named mcp__cc-workflow-studio__*, e.g. get_workflow_schema / apply_workflow / update_nodes / list_available_agents). Trigger this even when the user doesn't say "skill": phrasings like "build a workflow for <process> in cc-wf-studio", "add a node to my workflow on the canvas", "the workflow won't validate / a branch is disconnected / it has a dead end", "make my workflow reusable or parameterized", "wire a sub-agent (or code-reviewer) node", "pin opus on this node", or "switch the canvas to another config" all qualify. It encodes the studio's hard schema constraints (only End nodes accept multiple inputs, so no fan-in and no loop-back; pin a model only via the inline sub-agent form; ifElse/switch/askUserQuestion port and default-branch rules; variables live only on prompt nodes) plus a repeatable method for going from vague intent to a validated, diff-gated canvas. Do NOT use it for importing an existing SKILL.md file into a workflow — that is the separate import-skill skill.
---

# Building CC Workflow Studio workflows

CC Workflow Studio is a visual node-graph editor for agent workflows, driven
through an MCP server (`mcp__cc-workflow-studio__*`). This skill exists because
the studio's schema has a few hard, non-obvious constraints that quietly shape
every design — get them wrong and the canvas won't validate, or worse, validates
but doesn't express what you meant. It bundles those constraints plus a method
for authoring a good workflow from a vague request.

## Always do first

1. Call `get_workflow_schema` (authoritative TOON spec — do not guess node
   shapes) and `get_current_workflow` (for the `revision`, needed for
   conflict-safe applies). Call `list_available_agents` if you may wire a custom
   sub-agent. The editor must be open or applies won't land.
2. If the workflow encodes a real process the user already has (a runbook, a
   coordination doc, a pipeline), **read that process and map its stages onto
   nodes** rather than inventing a flow. The best workflows encode something
   real.

## The constraints that shape every design

These are the ones people get wrong. Full detail in
`references/cc-workflow-studio-reference.md` — read it before your first
`apply_workflow` on any non-trivial graph.

- **Only `end` nodes accept multiple incoming connections.** Every other node
  has exactly one input port. So there is **no fan-in / merge** and **no
  loop-back** — "gate fails → jump back to author" is not expressible as an edge.
  Model failure/alternate outcomes as **extra End nodes** (converge several
  fail-branches on one shared End), and express **parallel work as one sub-agent
  that runs the parts internally**, or as sequential nodes. You cannot fan out
  and then merge.
- **Model pinning.** Built-in agents (`builtInType: explore|plan|general-purpose`)
  auto-control their model — do not set `model`/`tools`. To pin a model (e.g.
  `opus` for a rigorous verify step), use the **inline** sub-agent form: omit
  `builtInType`, set `model` + `agentType`. Custom agents use `commandFilePath` +
  `commandScope` (from `list_available_agents`).
- **Variables live only on prompt nodes.** Parameterize a workflow by resolving a
  "profile" (names + paths) on one prompt node's `variables` and having it emit
  those values downstream; sub-agents read them from upstream context, not their
  own `{{}}`.
- **Branch/port rules.** `ifElse` = 2 branches (`branch-0` true / `branch-1`
  else). `switch` = 2–10 branches; the **last must be `isDefault:true`, label
  `default`, condition `Other cases`**. `askUserQuestion` single-select = one
  port per option; `multiSelect`/`useAiSuggestions` collapse to one `output`.
- **Names/completeness (validated on apply).** Workflow name `^[a-z0-9_-]+$`,
  node name `^[a-zA-Z0-9_-]+$` (no spaces). Every non-Start needs exactly one
  input; every non-End has every output port connected; all nodes reachable from
  Start; all paths reach an End.

## The method

Detailed version with anti-patterns in
`references/workflow-authoring-playbook.md`. In short:

1. **Brainstorm intent** — ask, one question at a time, only what changes the
   graph's shape: what does *one run* do (scope); how autonomous vs. how many
   `askUserQuestion` pauses; per-item or batch (there are no canvas loops, so
   "one run per item, invoked repeatedly" is the natural unit); and which steps
   are irreversible/outward-facing.
2. **Map stages → nodes** — `prompt` for orchestrator-side steps (git, CI,
   talking to the user), `subAgent` for isolated reasoning/editing; branch with
   `ifElse`/`switch`; give each terminal outcome its own End.
3. **Choose agents & models deliberately** — `explore` to read/classify,
   `general-purpose` to edit, `plan` to design; pin `opus` only where rigor
   matters; wire custom specialists sequentially (they can't merge).
4. **Templatize (optional, cheap)** — a profile-resolving prompt node + emit
   downstream; ship paste-ready `update_nodes` presets so switching context is
   one call.
5. **Build & verify** — `apply_workflow` for the whole graph (pass `revision`)
   or `update_nodes` for tweaks; both are diff-gated, so the **user's
   accept/reject is the review gate** — you don't need a heavyweight written plan
   for a canvas build. Confirm with `get_current_workflow`.

## Running a workflow (it doesn't self-run)

A workflow is a definition an **agent** executes — there is no Run button and no
run MCP tool, and **clicking Start does nothing** (the `▷` on Start only marks the
entry node; this is the most common confusion). To run it, use the **right-hand
agent panel**: pick the agent/model (the `Model ▾` dropdown; switch Claude Code /
Copilot / Codex via the pane's agent-name header or **⚙** settings — location
varies by build), then tell that agent to "execute the workflow from Start to End,
carrying out each node in order." Detail in
`references/cc-workflow-studio-reference.md` → "Running a workflow".

## Keep the host environment's rules

Even a "fully autonomous" workflow should honor the surrounding repo's rules. A
promote/deploy step in a repo that says "commit only when asked" should **stage
and end there**, not push — surface the irreversible step rather than letting the
autonomy run through it.

## References

- `references/cc-workflow-studio-reference.md` — full platform + schema truth:
  MCP tools, all 12 node types, every constraint, side effects, the build loop.
- `references/workflow-authoring-playbook.md` — the method in depth, with the
  anti-patterns learned the hard way.
