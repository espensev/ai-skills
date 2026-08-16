"""Contracts for the repository-local DevHome lifecycle plugin."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PACKAGE_ROOT.parent
MARKETPLACE_PATH = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
PLUGIN_NAME = "devhome-lifecycle"
PLUGIN_ROOT = PACKAGE_ROOT / "local-hooks" / PLUGIN_NAME
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
PLUGIN_HOOKS_PATH = PLUGIN_ROOT / "hooks" / "hooks.json"
RELEASE_MANIFEST_PATH = REPO_ROOT / "release-manifest.json"
INSTALL_MANIFEST_PATH = PACKAGE_ROOT / "package" / "install-manifest.json"
INSTALL_SCRIPT_PATH = REPO_ROOT / "scripts" / "Install-AgentSkills.ps1"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected a JSON object in {path}")
    return payload


def _string_values(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _string_values(key)
            yield from _string_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _string_values(child)


class TestLocalPluginContract(unittest.TestCase):
    def _resolve_inside(self, root: Path, relative_path: Any) -> Path:
        self.assertIsInstance(relative_path, str)
        resolved_root = root.resolve(strict=True)
        resolved_path = (root / relative_path).resolve(strict=True)
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError:
            self.fail(f"Path escapes {resolved_root}: {relative_path}")
        return resolved_path

    def test_plugin_json_documents_parse(self):
        for path in (MARKETPLACE_PATH, PLUGIN_MANIFEST_PATH, PLUGIN_HOOKS_PATH):
            with self.subTest(path=path):
                self.assertIsInstance(_load_json(path), dict)

    def test_marketplace_resolves_local_plugin_inside_repository(self):
        marketplace = _load_json(MARKETPLACE_PATH)
        self.assertEqual(marketplace["name"], "ai-skills")

        plugins = marketplace["plugins"]
        matching_plugins = [plugin for plugin in plugins if plugin.get("name") == PLUGIN_NAME]
        self.assertEqual(len(matching_plugins), 1)
        plugin = matching_plugins[0]

        self.assertEqual(plugin["source"]["source"], "local")
        resolved_source = self._resolve_inside(REPO_ROOT, plugin["source"]["path"])
        self.assertEqual(resolved_source, PLUGIN_ROOT.resolve(strict=True))
        self.assertEqual(
            plugin["policy"],
            {
                "installation": "AVAILABLE",
                "authentication": "ON_INSTALL",
            },
        )

    def test_plugin_manifest_references_existing_hook_and_skill_paths(self):
        manifest = _load_json(PLUGIN_MANIFEST_PATH)
        self.assertEqual(manifest["name"], PLUGIN_NAME)
        self.assertRegex(manifest["version"], re.compile(r"^\d+\.\d+\.\d+$"))

        hooks_path = self._resolve_inside(PLUGIN_ROOT, manifest["hooks"])
        skills_path = self._resolve_inside(PLUGIN_ROOT, manifest["skills"])
        self.assertTrue(hooks_path.is_file())
        self.assertTrue(skills_path.is_dir())
        self.assertEqual(hooks_path, PLUGIN_HOOKS_PATH.resolve(strict=True))

        skill_path = skills_path / PLUGIN_NAME / "SKILL.md"
        self.assertTrue(skill_path.is_file())
        lines = skill_path.read_text(encoding="utf-8").splitlines()
        self.assertGreater(len(lines), 2)
        self.assertEqual(lines[0], "---")
        frontmatter_end = lines.index("---", 1)
        name_lines = [line for line in lines[1:frontmatter_end] if line.startswith("name:")]
        self.assertEqual(len(name_lines), 1)
        frontmatter_name = name_lines[0].split(":", 1)[1].strip().strip("'\"")
        self.assertEqual(frontmatter_name, PLUGIN_NAME)

    def test_plugin_defines_only_one_session_start_reconciliation_command(self):
        hooks_document = _load_json(PLUGIN_HOOKS_PATH)
        hooks_by_event = hooks_document["hooks"]
        self.assertEqual(set(hooks_by_event), {"SessionStart"})

        session_start = hooks_by_event["SessionStart"]
        self.assertEqual(len(session_start), 1)
        self.assertEqual(session_start[0]["matcher"], "startup|resume")
        command_hooks = session_start[0]["hooks"]
        self.assertEqual(len(command_hooks), 1)

        command_hook = command_hooks[0]
        self.assertEqual(command_hook["type"], "command")
        expected_command = (
            'pwsh -NoProfile -NonInteractive -ExecutionPolicy Bypass -File '
            '"${PLUGIN_ROOT}/Sync-DevHomeCodexHooks.ps1" -SourcePackageRoot '
            '"D:/Development/AI-related/Ai-Skills/codex-skills/local-hooks/'
            'devhome-lifecycle" -Quiet'
        )
        self.assertEqual(command_hook["command"], expected_command)
        self.assertEqual(command_hook.get("commandWindows", expected_command), expected_command)
        self.assertIn("${PLUGIN_ROOT}", command_hook["command"])
        self.assertIn("Sync-DevHomeCodexHooks.ps1", command_hook["command"])
        self.assertIn("-SourcePackageRoot", command_hook["command"])

    def test_agent_skill_installer_exposes_explicit_local_plugin_choice(self):
        installer_text = INSTALL_SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn('$CodexLocalPlugin = "None"', installer_text)
        self.assertIn('"DevHomeLifecycle"', installer_text)
        self.assertIn("Sync-DevHomeLifecyclePlugin.ps1", installer_text)

    def test_machine_local_behavior_stays_out_of_portable_manifests(self):
        forbidden_values = (
            "devhome-lifecycle",
            "local-hooks",
            "hooks.json",
            "Sync-DevHomeCodexHooks.ps1",
            "Sync-DevHomeLifecyclePlugin.ps1",
        )
        for path in (RELEASE_MANIFEST_PATH, INSTALL_MANIFEST_PATH):
            manifest_values = "\n".join(_string_values(_load_json(path))).replace("\\", "/")
            with self.subTest(path=path):
                for forbidden_value in forbidden_values:
                    self.assertNotIn(forbidden_value, manifest_values)


if __name__ == "__main__":
    unittest.main()
