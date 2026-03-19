# Analysis Schema - Version 3

## Overview

This document defines the structured analysis payload emitted by the
`scripts/analysis/` provider runtime. The CLI still returns the legacy flattened
analysis fields for compatibility, but now nests the richer payload under
`analysis_v2`.

## Compatibility Contract

- `analyze --json` keeps the existing top-level fields:
  - `root`
  - `analyzed_at`
  - `files`
  - `dependency_edges`
  - `modules`
  - `detected_stacks`
  - `project_graph`
  - `conflict_zones`
  - `totals`
- The same response now also includes `analysis_v2`.
- `analysis_v2` is the forward-compatible schema for deeper providers.

## Top-Level Fields

| Field | Type | Description |
|---|---|---|
| `schema_version` | integer | Analysis schema version. Currently `3`. |
| `root` | string | Absolute project root that was scanned. |
| `generated_at` | string | ISO 8601 timestamp for the analysis run. |
| `providers` | array | Providers that contributed to the result. |
| `selection` | object | Provider-selection metadata including requested, applied, and skipped providers. |
| `inventory` | object | File inventory, module summaries, totals, and detected stacks. |
| `graphs` | object | Dependency and project graph outputs. |
| `signals` | object | Conflict zones and other planning signals. |
| `derived` | object | Post-merge synthesized views built from the final merged analysis. |
| `planning_context` | object | Planner-facing merged context built from provider health, graphs, signals, and derived views. |

## Provider Records

Each entry in `providers` describes one provider contribution:

| Field | Type | Description |
|---|---|---|
| `name` | string | Stable provider identifier, such as `basic`. |
| `kind` | string | Parser mode, such as `heuristic` or `semantic`. |
| `implementation` | string | Runtime backend, such as `python-stdlib` or `roslyn`. |
| `confidence` | string | Planner-facing trust level for that provider output. |
| `status` | string | Provider status in the final payload. Current applied records use `applied`. |

The current shipped provider is:

- `basic`: stdlib-only heuristic scanner used as the default fallback.
- `dotnet-cli`: optional `.NET`/MSBuild-backed enrichment provider.

## Selection Object

| Field | Type | Description |
|---|---|---|
| `mode` | string | Requested analysis mode: `basic`, `auto`, or `deep`. |
| `requested` | array of string | Provider order requested after config normalization. |
| `applied` | array of string | Providers that actually contributed to the result. |
| `skipped` | array | `{name, reason}` records for unavailable, unknown, or failing providers. |

Selection is non-fatal by design. Optional providers may be skipped while the
base `basic` provider still produces a usable result.

## Inventory Object

| Field | Type | Description |
|---|---|---|
| `files` | array | Per-file records with language-specific metadata. |
| `modules` | object | Module/category summaries keyed by module name. |
| `detected_stacks` | array of string | Heuristic stack markers such as `dotnet`, `wpf`, `winui`, `cpp`, `xaml-ui`, `msix`. |
| `totals` | object | Aggregate counts for files and lines. |

`files` remains intentionally verbose because it feeds planning and ownership
decisions. Each file record always includes:

- `path`
- `lines`
- `category`

Additional keys appear when a provider can infer them, for example:

- `imports`, `classes`, `top_functions`
- `usings`, `namespaces`, `types`, `type_references`
- `includes`, `symbols`
- `xaml_class`, `root_element`, `code_behind`, `dependent_upon`, `project_item_link`
- `project`, `project_references`, `package_references`, `target_frameworks`, `output_type`
- `manifest_kind`, `package_identity`, `package_entry_point`

## Graphs Object

| Field | Type | Description |
|---|---|---|
| `dependency_edges` | array | File-to-file and project-to-project edges with `kind`. |
| `project_graph` | object | Solution/project graph with `nodes` and `edges`. |

Current `dependency_edges.kind` values include:

- `python-import`
- `cpp-include`
- `project-reference`
- `xaml-code-behind`
- `csharp-type-reference`
- `manifest-entry-point`
- `solution-project`

Future semantic providers may add new edge kinds without changing the legacy
fields.

`project_graph` may now also contain package nodes contributed by deep
providers. For the current `dotnet-cli` provider:

- project nodes stay `kind: "project"`
- solution nodes stay `kind: "solution"`
- NuGet package nodes use `kind: "package"` and ids like `nuget:Newtonsoft.Json`
- package edges use `kind: "package-reference"`

## Signals Object

| Field | Type | Description |
|---|---|---|
| `conflict_zones` | array | `{files, reason}` records for ownership and merge-risk hotspots. |

Conflict zones may come from either:

- explicit config under `[conflict-zones]`
- provider-inferred desktop/UI/package surfaces
- auto-discovered mutual Python imports

## Derived Object

| Field | Type | Description |
|---|---|---|
| `ui_surfaces` | array | Higher-level desktop/UI surfaces synthesized from merged files and the merged project graph. |
| `ownership_summary` | object | Per-project ownership summary synthesized from merged file ownership and merged project graph metadata. |

Current `ui_surfaces.kind` values include:

- `startup`
- `shell`
- `resources`
- `packaging`
- `process-manifest`

`ownership_summary` currently includes:

- `project_count`
- `assigned_file_count`
- `assigned_line_count`
- `unassigned_file_count`
- `unassigned_paths`
- `projects`

Each `projects` entry summarizes one project with fields such as:

- `project`
- `name`
- `startup`
- `file_count`
- `line_count`
- `xaml_file_count`
- `resource_file_count`
- `code_behind_file_count`
- `package_reference_count`
- `ui_surface_count`

## Planning Context Object

`planning_context` is the preferred machine-facing planning surface. It carries
the final merged analysis signals in one stable object so planners and manager
workflows do not need to reconstruct meaning from flat legacy fields.

| Field | Type | Description |
|---|---|---|
| `analysis_health` | object | Provider selection state, degraded-analysis flags, confidence, and planner warnings. |
| `detected_stacks` | array of string | Final merged stack markers. |
| `project_graph` | object | Final merged project graph. |
| `conflict_zones` | array | Final merged conflict zones. |
| `ui_surfaces` | array | Final merged UI surfaces. |
| `ownership_summary` | object | Final merged ownership summary. |
| `priority_projects` | object | Startup and packaging project lists useful for decomposition ordering. |
| `coordination_hotspots` | array | Normalized startup/shell/resources/packaging/conflict hotspots for planner use. |

`analysis_health` currently includes:

- `mode`
- `requested_providers`
- `applied_providers`
- `skipped_providers`
- `partial_analysis`
- `fallback_only`
- `heuristic_only`
- `confidence`
- `warnings`

## Plan Snapshot Use

`plan create` stores a compact snapshot of this analysis under
`analysis_summary` in the plan JSON. The stored summary includes:

- `total_files`
- `total_lines`
- `conflict_zones`
- `modules`
- `detected_stacks`
- `project_graph`
- `analysis_schema_version`
- `analysis_providers`
- `analysis_health`
- `planning_context`

That plan snapshot is intentionally smaller than the full `analysis_v2` output,
but it now preserves the planner-facing merged context and degraded-analysis
signals instead of only the older flat summary fields.

## Provider Evolution

The long-term design supports multiple providers contributing to a single
`analysis_v2` payload. The current runtime ships the `basic` provider plus the
optional `dotnet-cli` enrichment provider, and the schema is prepared for
future semantic providers such as:

- Roslyn-backed C# analysis
- XAML graph augmentation
- Clang-backed C++ analysis

Those providers should enrich `analysis_v2` first. The legacy top-level fields
remain a compatibility projection, not the canonical internal shape.

## Merge Semantics

When multiple providers contribute to one payload:

- file records merge by `path`
- project graph nodes merge by `id`
- dependency edges are resynthesized from the final merged file set for merge-sensitive relationships such as `xaml-code-behind`, then deduplicated by structural equality
- conflict zones are resynthesized from the final merged file set, then deduplicated with any provider-supplied zones
- derived UI surfaces and ownership summaries are synthesized from the final merged file and project graph state
- planning context is synthesized from the final merged graphs, signals, derived views, and provider-selection health
- module totals and line totals are recomputed from the final merged file set

That keeps the legacy flat response stable while allowing deeper providers to
overlay more accurate ownership and graph metadata.
