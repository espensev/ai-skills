import json
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent
SKILL_PATH = PACKAGE_ROOT / "skills" / "codex-state-cleanup" / "SKILL.md"
MANIFEST_PATH = PACKAGE_ROOT / "package" / "install-manifest.json"
PACKAGE_README = PACKAGE_ROOT / "README.md"
ROOT_README = REPO_ROOT / "README.md"


class CodexStateCleanupSkillTests(unittest.TestCase):
    def test_skill_is_installable_and_documented(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertIn("codex-state-cleanup", manifest["optional_skills"])
        self.assertTrue(SKILL_PATH.is_file())

        package_readme = PACKAGE_README.read_text(encoding="utf-8")
        self.assertIn("| Codex State Cleanup | auto |", package_readme)
        self.assertEqual(package_readme.count("skills/codex-state-cleanup"), 2)
        self.assertIn("codex-state-cleanup", ROOT_README.read_text(encoding="utf-8"))

    def test_frontmatter_has_narrow_discovery_scope(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: codex-state-cleanup\n"))
        description = next(
            line.removeprefix("description:").strip().strip('"')
            for line in text.splitlines()
            if line.startswith("description:")
        )
        self.assertIn("Use when", description)
        self.assertIn("Do not use", description)
        self.assertIn("$CODEX_HOME", description)

    def test_cleanup_contract_is_fail_closed(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        required = (
            "Never hand-edit generated native memory",
            "Verify the archive before deleting its source",
            "Never VACUUM an active database",
            "Preserve active sessions",
            "Do not put live Codex state in synchronized storage",
            "stop that lane",
            "Run closeout",
        )
        for phrase in required:
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
