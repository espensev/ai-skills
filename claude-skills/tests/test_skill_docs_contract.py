"""Contract tests for package docs and exported file layout."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
README = ROOT / "README.md"
PORTABILITY_NOTES = ROOT / "docs" / "skill-portability-notes.md"
PLAN_006 = ROOT / "examples" / "plan-006-skill-ecosystem.json"
INSTALL_MANIFEST = ROOT / "package" / "install-manifest.json"
JSON_OUTPUT_EXAMPLES = ROOT / "docs" / "json-output-examples.md"
PROGRAM_FLOW = ROOT / "docs" / "program-flow.md"
PRODUCT_BACKLOG = ROOT / "docs" / "product-cost-optimization-backlog.md"
FILE_MAP = ROOT / "docs" / "file-map.md"
EXAMPLES_README = ROOT / "examples" / "README.md"
MANAGER_SKILL = SKILLS / "manager" / "SKILL.md"
PLANNER_SKILL = SKILLS / "planner" / "SKILL.md"
DEEP_AUDIT_SKILL = SKILLS / "deep-audit" / "SKILL.md"
DEEP_AUDIT_MODE_CONTRACT = SKILLS / "deep-audit" / "references" / "mode-contracts.md"
DEEP_AUDIT_STATE_CONTRACT = SKILLS / "deep-audit" / "references" / "state-and-report-contracts.md"
BROWSER_CONTROL_SKILL = SKILLS / "browser-control" / "SKILL.md"
BROWSER_CONTROL_CDP = SKILLS / "browser-control" / "cdp.mjs"
USAGE_STATS_SKILL = SKILLS / "usage-stats" / "SKILL.md"


class TestSkillDocsContract(unittest.TestCase):
    def test_expected_export_files_exist(self):
        expected = [
            ROOT / "CLAUDE.md",
            ROOT / "planning-contract.md",
            ROOT / "plan-schema.md",
            ROOT / "analysis-schema.md",
            ROOT / "project.toml.template",
            ROOT / "pyproject.toml",
            ROOT / "package" / "install-manifest.json",
            ROOT / "scripts" / "task_constants.py",
            ROOT / "scripts" / "task_manager.py",
            ROOT / "scripts" / "task_models.py",
            ROOT / "scripts" / "analysis" / "__init__.py",
            ROOT / "scripts" / "analysis" / "basic_provider.py",
            ROOT / "scripts" / "analysis" / "derived.py",
            ROOT / "scripts" / "analysis" / "dotnet_cli_provider.py",
            ROOT / "scripts" / "analysis" / "engine.py",
            ROOT / "scripts" / "analysis" / "models.py",
            ROOT / "scripts" / "analysis" / "planning_context.py",
            ROOT / "scripts" / "analysis" / "relations.py",
            ROOT / "scripts" / "analysis" / "signals.py",
            ROOT / "scripts" / "task_runtime" / "__init__.py",
            ROOT / "scripts" / "task_runtime" / "artifacts.py",
            ROOT / "scripts" / "task_runtime" / "bootstrap.py",
            ROOT / "scripts" / "task_runtime" / "config.py",
            ROOT / "scripts" / "task_runtime" / "execution.py",
            ROOT / "scripts" / "task_runtime" / "plans.py",
            ROOT / "scripts" / "task_runtime" / "specs.py",
            ROOT / "scripts" / "task_runtime" / "state.py",
            ROOT / "scripts" / "task_runtime" / "telemetry.py",
            ROOT / "scripts" / "task_runtime" / "validation.py",
            ROOT / "docs" / "skill-portability-notes.md",
            SKILLS / "deep-audit" / "SKILL.md",
            SKILLS / "deep-audit" / "examples" / "depth-test.md",
            SKILLS / "deep-audit" / "references" / "mode-contracts.md",
            SKILLS / "deep-audit" / "references" / "state-and-report-contracts.md",
            SKILLS / "discover" / "SKILL.md",
            SKILLS / "manager" / "SKILL.md",
            SKILLS / "planner" / "SKILL.md",
            SKILLS / "qa" / "SKILL.md",
            SKILLS / "ship" / "SKILL.md",
            SKILLS / "skill-authoring" / "SKILL.md",
            SKILLS / "usage-stats" / "SKILL.md",
        ]
        for path in expected:
            self.assertTrue(path.exists(), f"Missing exported file: {path}")

    def test_project_template_uses_init_placeholders(self):
        template_text = (ROOT / "project.toml.template").read_text(encoding="utf-8")
        self.assertIn("{{PROJECT_NAME}}", template_text)
        self.assertIn("{{TEST_LINE}}", template_text)
        self.assertIn("{{TEST_FAST_LINE}}", template_text)
        self.assertIn("{{TEST_FULL_LINE}}", template_text)
        self.assertIn("{{COMPILE_LINE}}", template_text)
        self.assertNotIn('test = ""', template_text)
        self.assertIn("[analysis]", template_text)
        self.assertIn('mode = "auto"', template_text)
        self.assertIn('providers = ["dotnet-cli"]', template_text)
        self.assertIn("include-globs", template_text)

    def test_readme_describes_install_flow(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("python scripts/task_manager.py init --force", text)
        self.assertIn("python -m pip install -e .[dev]", text)
        self.assertIn('cp -r "$d"', text)
        self.assertIn("cp -r scripts/analysis", text)
        self.assertIn("cp -r scripts/task_runtime", text)
        self.assertIn("analysis-schema.md", text)
        self.assertIn("planning_context", text)
        self.assertIn("13 standard plan elements", text)
        self.assertIn("--mode refactor", text)
        self.assertIn("skills/deep-audit", text)
        self.assertIn("skills/diagnosing-bugs", text)
        self.assertIn("skills/skill-authoring", text)

    def test_readme_has_valid_code_fences_and_no_pasted_python(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("```bash", text)
        self.assertIn("```toml", text)
        self.assertNotIn('cp -r ""', text)
        self.assertNotIn("from __future__ import annotations", text)
        self.assertNotIn("unittest.main()", text)

    def test_readme_install_examples_cover_manifest_skills(self):
        text = README.read_text(encoding="utf-8")
        manifest = json.loads(INSTALL_MANIFEST.read_text(encoding="utf-8"))
        for skill in manifest["default_skills"] + manifest["optional_skills"]:
            self.assertIn(f"skills/{skill}", text, skill)

    def test_portability_notes_distinguish_package_and_installed_layouts(self):
        text = PORTABILITY_NOTES.read_text(encoding="utf-8")
        self.assertIn("## Package Layout", text)
        self.assertIn("## Installed Target Layout", text)
        self.assertIn("scripts/analysis/", text)
        self.assertIn("scripts/task_runtime/", text)
        self.assertIn("Do not describe the package `README.md`", text)
        self.assertNotIn(".claude/skills/README.md", text)

    def test_plan_006_no_longer_points_at_missing_readme(self):
        plan = json.loads(PLAN_006.read_text(encoding="utf-8"))
        serialized = json.dumps(plan, ensure_ascii=False)
        self.assertNotIn(".claude/skills/README.md", serialized)
        self.assertNotIn("AiSupervision.Launcher", serialized)

    def test_install_manifest_lists_default_skill_set(self):
        manifest = json.loads(INSTALL_MANIFEST.read_text(encoding="utf-8"))
        self.assertIn("manager", manifest["default_skills"])
        self.assertIn("planner", manifest["default_skills"])
        self.assertIn("discover", manifest["default_skills"])
        self.assertIn("qa", manifest["default_skills"])
        self.assertIn("ship", manifest["default_skills"])
        self.assertIn("delegate", manifest["optional_skills"])
        self.assertIn("deep-audit", manifest["optional_skills"])
        self.assertIn("diagnosing-bugs", manifest["optional_skills"])
        self.assertIn("review", manifest["optional_skills"])
        self.assertIn("skill-authoring", manifest["optional_skills"])
        self.assertIn("usage-stats", manifest["optional_skills"])
        self.assertNotIn("telemetry-live-ops", manifest["optional_skills"])
        self.assertIn("telemetry-live-ops", manifest["source_only_skills"])
        for removed in (
            "agent-report",
            "observer-test",
            "refactor-planner",
            "session-stats",
            "token-audit",
            "worktree-manager",
        ):
            self.assertNotIn(removed, manifest["optional_skills"])
            self.assertNotIn(removed, manifest["source_only_skills"])
            self.assertFalse((SKILLS / removed).exists(), f"Deleted skill still present: {removed}")
        self.assertIn("scripts/task_manager.py", manifest["runtime_files"])
        self.assertIn("scripts/analysis", manifest["runtime_directories"])
        self.assertIn("scripts/hooks", manifest["runtime_directories"])
        self.assertIn("scripts/task_runtime", manifest["runtime_directories"])

    def test_always_off_skills_disable_model_invocation(self):
        demoted = (
            "delegate",
            "diagnosing-bugs",
            "docs-sync",
            "skill-authoring",
            "smart-test",
            "usage-stats",
        )
        for skill in demoted:
            text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("disable-model-invocation: true", text, skill)

    def test_manager_uses_progressive_disclosure(self):
        manager = MANAGER_SKILL.read_text(encoding="utf-8")
        self.assertNotIn("### Phase 1: Load context", manager)
        self.assertIn("planning policy is loaded on demand", manager)

    def test_collision_prone_skills_use_trigger_first_descriptions(self):
        for skill in (
            "deep-audit",
            "diagnosing-bugs",
            "qa",
            "planner",
            "manager",
            "review",
            "discover",
            "usage-stats",
        ):
            text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
            description = next(line for line in text.splitlines() if line.startswith("description:"))
            description = description.removeprefix("description:").strip().strip('"')
            self.assertTrue(description.startswith("Use "), skill)
            self.assertIn("Do not use", description, skill)

    def test_browser_control_requires_devhome_cdp_attachment(self):
        skill_text = BROWSER_CONTROL_SKILL.read_text(encoding="utf-8")
        cdp_text = BROWSER_CONTROL_CDP.read_text(encoding="utf-8")

        self.assertIn("--browser-url http://127.0.0.1:9000", skill_text)
        self.assertIn("use `9001` for the headless instance", skill_text)
        self.assertIn("Do not start it bare", skill_text)
        self.assertIn("MCP attachment preflight (required)", skill_text)
        self.assertIn("effective MCP command in the active Claude configuration", skill_text)
        self.assertIn("Do not call `list_pages`", skill_text)
        self.assertNotIn("one popup, acceptable", skill_text)
        for command in ("status", "tabs", "new", "goto", "eval", "text", "screenshot", "close"):
            self.assertIn(command, cdp_text)

    def test_current_docs_match_runtime_verify_surface(self):
        self.assertIn("validates build, tests, and readiness", README.read_text(encoding="utf-8"))
        self.assertIn("readiness check", PLANNER_SKILL.read_text(encoding="utf-8"))
        manager_text = MANAGER_SKILL.read_text(encoding="utf-8")
        self.assertIn("optional follow-up audit findings", manager_text)
        self.assertIn("Do not claim that", manager_text)
        json_examples_text = JSON_OUTPUT_EXAMPLES.read_text(encoding="utf-8")
        self.assertIn("does not independently prove each natural-language", json_examples_text)
        self.assertIn("--poll SECONDS", PROGRAM_FLOW.read_text(encoding="utf-8"))

    def test_deep_audit_guards_live_eval_regressions(self):
        skill_text = DEEP_AUDIT_SKILL.read_text(encoding="utf-8")
        self.assertIn("ceil(D / I)", skill_text)
        self.assertIn("redundant = total - required", skill_text)
        self.assertIn("explicit narrower user restriction", skill_text)
        self.assertIn("do not claim an activity was skipped", skill_text)
        state_text = DEEP_AUDIT_STATE_CONTRACT.read_text(encoding="utf-8")
        self.assertIn("every persisted state", state_text)
        mode_text = DEEP_AUDIT_MODE_CONTRACT.read_text(encoding="utf-8")
        self.assertIn("state transition, not an add-only note", mode_text)
        self.assertIn("denormalized current-state surfaces", mode_text)
        self.assertIn("live ownership and lifecycle accounting", mode_text)
        self.assertIn("MUST NOT recommend clearing", mode_text)
        self.assertIn("`Original:` or `Superseded:`", mode_text)

    def test_usage_stats_closeout_contract_is_portable(self):
        usage_text = USAGE_STATS_SKILL.read_text(encoding="utf-8")
        self.assertIn("## Command: `closeout`", usage_text)
        self.assertIn("current user message timestamp", usage_text)
        self.assertIn("unambiguously bound the current turn", usage_text)
        for field in ("Outcome", "Elapsed", "Tokens", "Execution", "Verification", "Remaining"):
            self.assertIn(field, usage_text)
        self.assertNotIn("task_started", usage_text)
        self.assertNotIn("`event_msg` whose `payload.type` is `token_count`", usage_text)

    def test_current_docs_do_not_reference_removed_contracts(self):
        self.assertIn("historical", EXAMPLES_README.read_text(encoding="utf-8").lower())
        self.assertNotIn("verify --profile {fast,full,auto}", PRODUCT_BACKLOG.read_text(encoding="utf-8"))
        self.assertIn("verify --profile {default,fast,full}", PRODUCT_BACKLOG.read_text(encoding="utf-8"))
        self.assertNotIn("docs/developer-handoff.md", FILE_MAP.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
