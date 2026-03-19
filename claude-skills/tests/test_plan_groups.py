"""Tests for _plan_assign_groups() — plan agent group assignment."""

import unittest

import task_manager


class TestPlanGroups(unittest.TestCase):
    """Tests for _plan_assign_groups() — plan agent group assignment."""

    def test_plan_assign_groups_no_deps(self):
        """All agents with no deps get group 0."""
        plan = {
            "agents": [
                {"letter": "a", "name": "alpha", "deps": []},
                {"letter": "b", "name": "beta", "deps": []},
                {"letter": "c", "name": "gamma", "deps": []},
            ],
            "groups": {},
        }
        task_manager._plan_assign_groups(plan)

        for a in plan["agents"]:
            self.assertEqual(a["group"], 0, f"Agent {a['letter']} should be group 0")
        self.assertEqual(plan["groups"], {"0": ["a", "b", "c"]})

    def test_plan_assign_groups_chain(self):
        """A -> B -> C gets groups 0, 1, 2."""
        plan = {
            "agents": [
                {"letter": "a", "name": "first", "deps": []},
                {"letter": "b", "name": "second", "deps": ["a"]},
                {"letter": "c", "name": "third", "deps": ["b"]},
            ],
            "groups": {},
        }
        task_manager._plan_assign_groups(plan)

        agents_by_letter = {a["letter"]: a for a in plan["agents"]}
        self.assertEqual(agents_by_letter["a"]["group"], 0)
        self.assertEqual(agents_by_letter["b"]["group"], 1)
        self.assertEqual(agents_by_letter["c"]["group"], 2)
        self.assertEqual(plan["groups"]["0"], ["a"])
        self.assertEqual(plan["groups"]["1"], ["b"])
        self.assertEqual(plan["groups"]["2"], ["c"])

    def test_plan_assign_groups_diamond(self):
        """A -> C, B -> C — C gets group 1 (max dep depth + 1)."""
        plan = {
            "agents": [
                {"letter": "a", "name": "left", "deps": []},
                {"letter": "b", "name": "right", "deps": []},
                {"letter": "c", "name": "merge", "deps": ["a", "b"]},
            ],
            "groups": {},
        }
        task_manager._plan_assign_groups(plan)

        agents_by_letter = {a["letter"]: a for a in plan["agents"]}
        self.assertEqual(agents_by_letter["a"]["group"], 0)
        self.assertEqual(agents_by_letter["b"]["group"], 0)
        self.assertEqual(agents_by_letter["c"]["group"], 1)
        self.assertIn("a", plan["groups"]["0"])
        self.assertIn("b", plan["groups"]["0"])
        self.assertEqual(plan["groups"]["1"], ["c"])


if __name__ == "__main__":
    unittest.main()
