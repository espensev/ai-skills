# Antigravity Skill Adapter Portability Notes

Current portability status for the `antigravity-skills` package.

## Intent

This folder is an Antigravity adapter, not a full runtime fork. It owns the
Antigravity-facing package surface while sharing skill behavior with the other
provider packages where possible.

Antigravity-specific behavior should be expressed through:

- `AGENTS.md` for persistent project guidance
- `.agents/skills/<skill>/SKILL.md` for workspace Agent Skills
- `.agent/workflows/<workflow>.md` for reusable slash-invoked workflows

The package should stay adapter-first until any shared runtime is extracted
into a neutral core.

## Package Layout

- `README.md`
- `AGENTS.md`
- `skills/`
- `.agent/workflows/`
- `scripts/bootstrap.ps1`
- `package/install-manifest.json`
- `docs/skill-portability-notes.md`

These files define the installable Antigravity adapter. They do not imply a
separate Antigravity backend runtime.

## Installed Target Layout

After bootstrap, the expected consumer repo surface is:

- `AGENTS.md`
- `.agents/skills/`
- `.agent/workflows/`

The bootstrap script copies only manifest-listed skills and workflows.

## Documentation Rules

- Package docs must describe package-root files when talking about this folder.
- Consumer runtime docs may describe `AGENTS.md`, `.agents/skills/...`, and
  `.agent/workflows/...`.
- Do not describe a provider backend runtime that does not exist.
- Do not copy inherited `.claude`, `.codex`, or `.gemini` runtime paths into
  Antigravity-facing examples.
- Keep workflow instructions artifact-driven so they can later be backed by a
  shared runtime without re-interpreting vague personas.

## Migration Notes

`gemini-skills` remains in this repository as the legacy Gemini CLI adapter.
For active consumer Google tooling, use `antigravity-skills`.

Before changing install paths again, verify the current Antigravity docs:

- Agent Skills: `https://antigravity.google/docs/skills`
- Rules and workflows: `https://antigravity.google/docs/rules-workflows`
- Gemini CLI migration: `https://antigravity.google/docs/gcli-migration`

## Verification Expectations

Before calling this package ready:

- `package/install-manifest.json` lists every shipped skill and workflow
- every manifest-listed skill has `skills/<name>/SKILL.md`
- every manifest-listed workflow has `.agent/workflows/<name>.md`
- `scripts/bootstrap.ps1` installs into `.agents/skills` and `.agent/workflows`
- root export validation passes
