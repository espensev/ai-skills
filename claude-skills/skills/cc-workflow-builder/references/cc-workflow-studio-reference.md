# CC Workflow Studio — platform & schema reference

The technical truth an agent needs to drive the studio correctly. Verified
against `get_workflow_schema` and by building the `lane-pipeline` workflow.
**When in doubt, call `get_workflow_schema` — it is authoritative (TOON format);
do not guess node shapes.**

## MCP surface

Local HTTP MCP server (this machine: `http://127.0.0.1:6282/mcp`, see `.mcp.json`).

| Tool | Use |
|---|---|
| `get_workflow_schema` | Authoritative node/connection spec. Call first. |
| `get_current_workflow` | Current canvas JSON + `revision` (for conflict detection) + `isStale`. |
| `list_available_agents` | `.claude/agents/*.md` custom agents (name, scope, `commandPath`). |
| `apply_workflow` | Replace the whole graph. Validated + shown to user as a diff (review gate). Pass `revision`. |
| `update_nodes` | Partial edit by node id. Shallow-merges `data` (set a field `null` to remove). Add/remove nodes needs `apply_workflow`. |
| `highlight_group_node` | Visually mark a group node as executing. |

Editor must be open or applies fail. `apply_workflow` may return "User rejected
the changes" if the user declines the diff.

## Node types (12)

`start, end, prompt, subAgent, askUserQuestion, ifElse, switch, skill, mcp,
subAgentFlow, codex, group`

- **prompt** — runs in the **main orchestrator session** (can talk to the user,
  run Bash/git/CI). 1 in → 1 out. Has a `variables` object for `{{templating}}`.
- **subAgent** — isolated Task invocation (reasoning/editing). 1 in → 1 out.
  Built-in via `builtInType: explore|plan|general-purpose`, or custom via
  `commandFilePath` + `commandScope`, or inline (neither) to pin a `model`.
- **ifElse** — exactly 2 branches; ports `branch-0` (true/if), `branch-1` (else).
- **switch** — 2–10 branches; **last branch must be `isDefault:true`, label
  `default`, condition `Other cases`**. Ports `branch-0..N`.
- **askUserQuestion** — single-select → one port per option (`branch-0..N`);
  `multiSelect:true` or `useAiSuggestions:true` → single `output` port.
- **skill** — reference a real installed Skill (never fabricate one). 1 out.
- **mcp** — call an external MCP tool; prefer `aiParameterConfig` mode.
- **subAgentFlow** — a reusable sub-flow; **cannot contain subAgent/subAgentFlow/
  askUserQuestion**, runs strictly sequential. (So a parallel fan-out can't live
  here.)
- **codex** — Phase-1 UI/data-model only; **CLI execution not implemented**.
- **group** — visual container, no execution effect.

## The constraints that shape every design

1. **Only `end` nodes accept multiple incoming connections.** Every other node
   has exactly ONE input port. Consequences:
   - **No fan-in / merge** and **no loop-back** (e.g. "gate fails → back to
     author" is not expressible as an edge).
   - Model failure / alternate outcomes as **extra End nodes**; multiple
     fail-branches may converge on one shared End.
   - **Parallelism** (e.g. a multi-lens verify) must be folded **inside a single
     subAgent** whose prompt runs the lenses internally, or expressed as
     **sequential** nodes — you cannot fan-out then fan-in.
2. **Model pinning.** For built-in agents (`builtInType` set) do **NOT** set
   `model`/`tools`/`commandFilePath` — auto-controlled. To pin a model (e.g.
   `opus` for rigorous QC), use the **inline** subAgent form: omit `builtInType`,
   set `model` + `agentType: claudeCode`. Custom agents (`commandFilePath` +
   `commandScope`) may set `model`.
3. **Variables live on prompt nodes only.** Parameterize by putting `variables`
   on one prompt node (e.g. `intake`) and having it **emit the resolved values
   downstream**; sub-agents read them from upstream context, not their own
   `{{}}`. This is how `lane-pipeline` became a template (swap 4 intake vars →
   whole pipeline retargets).
4. **Naming/limits.** Workflow name `^[a-z0-9_-]+$`; node name
   `^[a-zA-Z0-9_-]+$` (no spaces/non-ASCII). `description` ≤200,
   `prompt`/`agentDefinition` ≤10000, ≤100 nodes.
5. **Connection completeness** (validated on apply/export): exactly one Start;
   ≥1 End; every non-Start has exactly one input; every non-End has every output
   port connected; all nodes reachable from Start; all paths reach an End; all
   conditional branches connected.

## Positioning (readability only, not validity)

x left→right in execution order, +300/step; linear flows share one y; branches
fan out vertically (±175 for 2, ±350/0 for 3); return to parent y after a branch.

## Side effects to expect

- subAgent nodes **without** `commandFilePath` auto-create `.claude/agents/*.md`.
- Applying a workflow can **auto-register it as a `/skill`** and surface its
  sub-agents as agent types in the session.

## Build loop

1. `get_workflow_schema` → 2. design on paper against the constraints →
3. `apply_workflow` (whole graph, pass `revision`) or `update_nodes` (tweaks) →
4. `get_current_workflow` to verify → the user accepts/rejects the diff.

## Running a workflow (how to actually start it)

**A workflow does not run itself, and there is no "Run" button.** The canvas holds
a *definition*; an **agent** executes it. There is no run/execute MCP tool — the
only tools are get/apply/update/list-agents/highlight/schema, and
`highlight_group_node` exists precisely so the *executing agent* can mark progress
on the canvas. So execution = an agent reads the workflow (`get_current_workflow`)
and carries out each node in order.

- **Clicking Start does nothing.** The `▷` glyph next to `start(Start)` in the
  node inspector only marks/anchors the entry node — it is not a run trigger.
  This is the single most common confusion.
- **Where you actually start it:** the **agent panel on the right-hand side** of
  the studio (the pane headed by the agent's name, e.g. `CLAUDE`, with a chat
  input box at the bottom). Click into that input and **tell the agent to execute
  the workflow**, e.g.:
  > "Execute the workflow on the canvas from Start to End — read it with
  > get_current_workflow and carry out each node in order, highlighting progress."

  The agent then walks the nodes doing the real work each one describes. (This is
  exactly how these workflows get test-run — the docked agent classifies, routes,
  and reports, node by node.)

### Choosing which agent runs it (Claude / Copilot / Codex …)

The workflow is driven by whichever agent is docked in that right-hand pane, so
**switching the agent = switching who executes**. Look in that pane for:

- a **`Model ▾`** dropdown (bottom of the agent pane) — picks the model for the
  active agent;
- an **agent selector** — usually the agent-name header (e.g. the `CLAUDE`
  label) or the settings **⚙** at the top-right — to switch between Claude Code,
  GitHub Copilot, Codex, etc.

Then send the same "execute this workflow" instruction. Codex is also a
first-class node **type** in the schema (`codex`), so Codex-driven steps can live
inside a workflow too. **Caveat:** the exact location/label of the agent switcher
varies by studio build — if you only see a `Model ▾` dropdown and no agent list,
that build is Claude-only for now. (Verify against your actual UI; don't assume a
label that isn't there.)
