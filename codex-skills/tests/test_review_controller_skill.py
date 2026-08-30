import json
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent
SKILL_ROOT = PACKAGE_ROOT / "skills" / "review-controller"
SKILL_PATH = SKILL_ROOT / "SKILL.md"
AGENT_METADATA_PATH = SKILL_ROOT / "agents" / "openai.yaml"
INSTALL_MANIFEST_PATH = PACKAGE_ROOT / "package" / "install-manifest.json"
SOURCE_MANIFEST_PATH = REPO_ROOT / "skills-src" / "manifest.json"
PACKAGE_README_PATH = PACKAGE_ROOT / "README.md"
ROOT_README_PATH = REPO_ROOT / "README.md"
EVAL_CASES_PATH = PACKAGE_ROOT / "eval" / "cases" / "light-skill-cases.json"


class ReviewControllerSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL_PATH.read_text(encoding="utf-8")
        cls.policy = " ".join(cls.text.split())

    def test_skill_is_installable_documented_and_a_declared_provider_fork(self):
        install_manifest = json.loads(
            INSTALL_MANIFEST_PATH.read_text(encoding="utf-8")
        )
        source_manifest = json.loads(SOURCE_MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertIn("review-controller", install_manifest["optional_skills"])
        self.assertIn(
            "review-controller", source_manifest["provider_owned_shared_skills"]
        )
        fork_reason = source_manifest["declared_provider_forks"]["review-controller"]
        for phrase in ("product-review", "Claude", "Codex"):
            self.assertIn(phrase, fork_reason)
        source_manifest_notes = source_manifest["notes"]
        for phrase in (
            "same-name skill pairs present in both provider source trees",
            "independent of portable export/install selection",
        ):
            self.assertIn(phrase, source_manifest_notes)

        self.assertTrue(SKILL_PATH.is_file())
        self.assertTrue(AGENT_METADATA_PATH.is_file())
        package_readme = PACKAGE_README_PATH.read_text(encoding="utf-8")
        self.assertIn("| Review Controller | auto |", package_readme)
        self.assertEqual(package_readme.count("skills/review-controller"), 2)

        root_readme = ROOT_README_PATH.read_text(encoding="utf-8")
        self.assertIn("| **review-controller** |", root_readme)
        self.assertIn("provider-owned shared skills", root_readme)
        self.assertNotIn("`telemetry-live-ops` is the only remaining", root_readme)

    def test_frontmatter_routes_product_review_without_colliding_with_code_review(self):
        self.assertTrue(self.text.startswith("---\nname: review-controller\n"))
        description = next(
            line.removeprefix("description:").strip().strip('"')
            for line in self.text.splitlines()
            if line.startswith("description:")
        )
        for phrase in (
            "Use when",
            "product",
            "feature",
            "system",
            "user journey",
            "screens",
            "Do not use",
            "branch, PR, diff",
            "use review",
            "source symbol named ReviewController",
        ):
            self.assertIn(phrase, description)

    def test_evidence_manifest_is_content_addressed_and_stale_returns_are_rejected(self):
        for phrase in (
            "numbered evidence manifest E-1...E-n",
            "byte length and SHA-256",
            "A changing URL alone is not frozen evidence",
            "hash the canonical manifest bytes",
            "re-read every local or captured E-id artifact",
            "recalculate its current byte length and SHA-256",
            "Rebuild the sorted canonical manifest from those fresh observations",
            "compare every entry and the resulting fingerprint with the frozen baseline",
            "Re-hashing the stored manifest alone is not a freshness check",
            "full evidence revalidation after Wave 1 before accepting returns",
            "reject stale returns",
            "Never combine claims from different states",
        ):
            self.assertIn(phrase, self.policy)

    def test_controller_verifies_every_claim_and_workers_cannot_mutate(self):
        for phrase in (
            "Workers are read-only",
            "must not edit or create files",
            "or spawn descendants",
            "Only the controller may",
            "for every proposed finding, regardless of severity",
            "verify every accepted no-significant-issue coverage claim",
            "never by vote or worker agreement",
            "Do not post it to any external destination",
            "complete and report the review first",
        ):
            self.assertIn(phrase, self.policy)

    def test_parallelism_is_bounded_model_neutral_and_has_sequential_fallback(self):
        for phrase in (
            "Use two read-only workers by default",
            "Use three only",
            "never assume a fixed slot count or pin a model name",
            "Launch all initially ready workers together",
            "run the same lens packets sequentially",
            "Use At Most One Targeted Second Wave",
        ):
            self.assertIn(phrase, self.policy)
        self.assertNotIn("Opus", self.text)
        self.assertNotIn("Fable", self.text)
        self.assertNotIn("model:", self.text)

    def test_product_positive_and_code_review_boundary_eval_cases_exist(self):
        cases = {
            case["id"]: case
            for case in json.loads(EVAL_CASES_PATH.read_text(encoding="utf-8"))
        }
        positive = cases["review-controller-basic-001"]
        boundary = cases["review-controller-routing-boundary-001"]
        self.assertEqual(positive["skill"], "review-controller")
        self.assertIn("product journey", positive["prompt"])
        self.assertIn("screens", positive["prompt"])
        self.assertEqual(boundary["skill"], "review")
        self.assertIn("staged diff", boundary["prompt"])

    def test_metadata_and_report_contract_are_product_focused(self):
        metadata = AGENT_METADATA_PATH.read_text(encoding="utf-8")
        self.assertIn('display_name: "Review Controller"', metadata)
        self.assertIn("$review-controller", metadata)
        self.assertIn("product journey", metadata)
        self.assertIn("## Findings", self.text)
        self.assertLess(self.text.index("## Findings"), self.text.index("## Leader Judgement"))
        self.assertIn("docs/reviews/review-controller-{date}-{slug}.md", self.text)


if __name__ == "__main__":
    unittest.main()
