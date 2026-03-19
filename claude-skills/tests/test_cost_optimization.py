"""Tests for cost optimization features: model tiering, telemetry, complexity flow."""

import argparse
import io
import json
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import task_manager  # noqa: E402
from conftest import patch_env  # noqa: E402
from task_runtime.execution import (  # noqa: E402
    _DEFAULT_MODEL_MAP,
    _VALID_MODELS,
    resolve_model_for_task,
)
from task_runtime.telemetry import (  # noqa: E402
    _TIER_TOKEN_BUDGETS,
    StepTimer,
    build_telemetry_payload,
    estimate_agent_cost_usd,
    estimate_campaign_savings,
    load_pricing_config,
    measure_json_bytes,
)

# ---------------------------------------------------------------------------
# resolve_model_for_task
# ---------------------------------------------------------------------------


class TestResolveModelForTask(unittest.TestCase):
    """Tests for complexity → model mapping."""

    def test_default_mapping_low(self):
        self.assertEqual(resolve_model_for_task({"complexity": "low"}, {}), "haiku")

    def test_default_mapping_medium(self):
        self.assertEqual(resolve_model_for_task({"complexity": "medium"}, {}), "sonnet")

    def test_default_mapping_high(self):
        self.assertEqual(resolve_model_for_task({"complexity": "high"}, {}), "opus")

    def test_missing_complexity_defaults_to_haiku(self):
        self.assertEqual(resolve_model_for_task({}, {}), "haiku")

    def test_empty_complexity_defaults_to_haiku(self):
        self.assertEqual(resolve_model_for_task({"complexity": ""}, {}), "haiku")

    def test_none_complexity_defaults_to_haiku(self):
        self.assertEqual(resolve_model_for_task({"complexity": None}, {}), "haiku")

    def test_config_override(self):
        cfg = {"models": {"low": "sonnet", "medium": "opus", "high": "opus"}}
        self.assertEqual(resolve_model_for_task({"complexity": "low"}, cfg), "sonnet")
        self.assertEqual(resolve_model_for_task({"complexity": "medium"}, cfg), "opus")

    def test_config_partial_override_falls_through(self):
        cfg = {"models": {"high": "sonnet"}}
        # high overridden, low uses default
        self.assertEqual(resolve_model_for_task({"complexity": "high"}, cfg), "sonnet")
        self.assertEqual(resolve_model_for_task({"complexity": "low"}, cfg), "haiku")

    def test_invalid_model_in_config_falls_back_to_sonnet(self):
        cfg = {"models": {"low": "gpt-4"}}
        self.assertEqual(resolve_model_for_task({"complexity": "low"}, cfg), "sonnet")

    def test_unknown_complexity_value_defaults_to_haiku(self):
        self.assertEqual(resolve_model_for_task({"complexity": "extreme"}, {}), "haiku")

    def test_case_insensitive(self):
        self.assertEqual(resolve_model_for_task({"complexity": "HIGH"}, {}), "opus")
        self.assertEqual(resolve_model_for_task({"complexity": "Low"}, {}), "haiku")

    def test_whitespace_trimmed(self):
        self.assertEqual(resolve_model_for_task({"complexity": " high "}, {}), "opus")

    def test_valid_models_set(self):
        self.assertEqual(_VALID_MODELS, {"haiku", "sonnet", "opus"})

    def test_default_map_covers_all_levels(self):
        for level in ("low", "medium", "high"):
            self.assertIn(level, _DEFAULT_MODEL_MAP)
            self.assertIn(_DEFAULT_MODEL_MAP[level], _VALID_MODELS)


# ---------------------------------------------------------------------------
# telemetry.py
# ---------------------------------------------------------------------------


class TestStepTimer(unittest.TestCase):
    def test_records_elapsed_ms(self):
        with StepTimer("test") as t:
            time.sleep(0.01)
        self.assertGreater(t.elapsed_ms, 5)
        self.assertEqual(t.label, "test")

    def test_elapsed_is_zero_before_exit(self):
        t = StepTimer("x")
        self.assertEqual(t.elapsed_ms, 0.0)

    def test_context_manager_sets_elapsed(self):
        t = StepTimer("a")
        with t:
            time.sleep(0.005)
        self.assertGreaterEqual(t.elapsed_ms, 0)


class TestBuildTelemetryPayload(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(build_telemetry_payload(), {})

    def test_timers(self):
        t = StepTimer("analyze")
        t.elapsed_ms = 42.5
        payload = build_telemetry_payload(timers=[t])
        self.assertEqual(payload["analyze_ms"], 42.5)

    def test_multiple_timers(self):
        t1 = StepTimer("preflight")
        t1.elapsed_ms = 10.0
        t2 = StepTimer("verify")
        t2.elapsed_ms = 20.0
        payload = build_telemetry_payload(timers=[t1, t2])
        self.assertEqual(payload["preflight_ms"], 10.0)
        self.assertEqual(payload["verify_ms"], 20.0)

    def test_counts(self):
        payload = build_telemetry_payload(launched_agents=4, failed_agents=1)
        self.assertEqual(payload["launched_agents"], 4)
        self.assertEqual(payload["failed_agents"], 1)

    def test_model_breakdown(self):
        payload = build_telemetry_payload(model_breakdown={"haiku": 2, "opus": 1})
        self.assertEqual(payload["model_breakdown"], {"haiku": 2, "opus": 1})

    def test_analysis_bytes(self):
        payload = build_telemetry_payload(analysis_json_bytes=35000)
        self.assertEqual(payload["analysis_json_bytes"], 35000)

    def test_zero_values_omitted(self):
        payload = build_telemetry_payload(launched_agents=0, analysis_json_bytes=0)
        self.assertNotIn("launched_agents", payload)
        self.assertNotIn("analysis_json_bytes", payload)

    def test_extra(self):
        payload = build_telemetry_payload(extra={"custom": "value"})
        self.assertEqual(payload["custom"], "value")


class TestMeasureJsonBytes(unittest.TestCase):
    def test_simple_dict(self):
        obj = {"key": "value"}
        result = measure_json_bytes(obj)
        expected = len(json.dumps(obj, separators=(",", ":")).encode("utf-8"))
        self.assertEqual(result, expected)

    def test_empty_dict(self):
        self.assertEqual(measure_json_bytes({}), 2)  # "{}"

    def test_unicode(self):
        obj = {"emoji": "\u2713"}
        result = measure_json_bytes(obj)
        self.assertGreater(result, 0)


class TestLoadPricingConfig(unittest.TestCase):
    """Tests for load_pricing_config() function."""

    def test_empty_config_returns_defaults(self):
        """No [pricing] section → returns _MODEL_PRICING defaults."""
        cfg = {}
        result = load_pricing_config(cfg)
        # Should return default pricing
        self.assertEqual(result["haiku"]["input"], 1.00)
        self.assertEqual(result["haiku"]["output"], 5.00)
        self.assertEqual(result["sonnet"]["input"], 3.00)
        self.assertEqual(result["sonnet"]["output"], 15.00)
        self.assertEqual(result["opus"]["input"], 5.00)
        self.assertEqual(result["opus"]["output"], 25.00)

    def test_full_override(self):
        """All keys set → returns overridden values."""
        cfg = {
            "pricing": {
                "haiku_input": 0.5,
                "haiku_output": 2.5,
                "sonnet_input": 1.5,
                "sonnet_output": 7.5,
                "opus_input": 2.5,
                "opus_output": 12.5,
            }
        }
        result = load_pricing_config(cfg)
        self.assertEqual(result["haiku"]["input"], 0.5)
        self.assertEqual(result["haiku"]["output"], 2.5)
        self.assertEqual(result["sonnet"]["input"], 1.5)
        self.assertEqual(result["sonnet"]["output"], 7.5)
        self.assertEqual(result["opus"]["input"], 2.5)
        self.assertEqual(result["opus"]["output"], 12.5)

    def test_partial_override(self):
        """Some keys set → partial override, rest from defaults."""
        cfg = {
            "pricing": {
                "haiku_input": 0.75,
                "opus_output": 30.0,
            }
        }
        result = load_pricing_config(cfg)
        # Overridden values
        self.assertEqual(result["haiku"]["input"], 0.75)
        self.assertEqual(result["opus"]["output"], 30.0)
        # Default values
        self.assertEqual(result["haiku"]["output"], 5.00)
        self.assertEqual(result["sonnet"]["input"], 3.00)
        self.assertEqual(result["sonnet"]["output"], 15.00)
        self.assertEqual(result["opus"]["input"], 5.00)

    def test_string_values_converted(self):
        """String values like "1.00" properly float()-ed."""
        cfg = {
            "pricing": {
                "haiku_input": "1.00",
                "haiku_output": "5.00",
                "sonnet_input": "3.00",
                "sonnet_output": "15.00",
                "opus_input": "5.00",
                "opus_output": "25.00",
            }
        }
        result = load_pricing_config(cfg)
        # All should be floats
        self.assertEqual(result["haiku"]["input"], 1.00)
        self.assertEqual(result["haiku"]["output"], 5.00)
        self.assertEqual(result["sonnet"]["input"], 3.00)
        self.assertEqual(result["sonnet"]["output"], 15.00)
        self.assertEqual(result["opus"]["input"], 5.00)
        self.assertEqual(result["opus"]["output"], 25.00)
        # Verify they are floats, not strings
        self.assertIsInstance(result["haiku"]["input"], float)
        self.assertIsInstance(result["sonnet"]["output"], float)


class TestEstimateAgentCostUsd(unittest.TestCase):
    def test_haiku_cheapest(self):
        haiku = estimate_agent_cost_usd("haiku", input_tokens=50000, output_tokens=10000)
        sonnet = estimate_agent_cost_usd("sonnet", input_tokens=50000, output_tokens=10000)
        opus = estimate_agent_cost_usd("opus", input_tokens=50000, output_tokens=10000)
        self.assertLess(haiku, sonnet)
        self.assertLess(sonnet, opus)

    def test_zero_tokens_zero_cost(self):
        self.assertEqual(estimate_agent_cost_usd("opus", input_tokens=0, output_tokens=0), 0.0)

    def test_unknown_model_uses_sonnet_pricing(self):
        unknown = estimate_agent_cost_usd("gpt-5", input_tokens=1000, output_tokens=1000)
        sonnet = estimate_agent_cost_usd("sonnet", input_tokens=1000, output_tokens=1000)
        self.assertEqual(unknown, sonnet)

    def test_case_insensitive(self):
        lower = estimate_agent_cost_usd("OPUS", input_tokens=10000, output_tokens=5000)
        upper = estimate_agent_cost_usd("opus", input_tokens=10000, output_tokens=5000)
        self.assertEqual(lower, upper)


class TestEstimateCampaignSavings(unittest.TestCase):
    def test_mixed_models_cheaper_than_all_opus(self):
        agents = [{"model": "haiku"}, {"model": "sonnet"}, {"model": "opus"}]
        result = estimate_campaign_savings(agents)
        self.assertGreater(result["savings_pct"], 0)
        self.assertLess(result["tiered_usd"], result["opus_usd"])
        self.assertGreater(result["savings_usd"], 0)

    def test_all_opus_zero_savings(self):
        agents = [{"model": "opus"}, {"model": "opus"}]
        result = estimate_campaign_savings(agents)
        self.assertEqual(result["savings_pct"], 0.0)
        self.assertEqual(result["savings_usd"], 0.0)

    def test_empty_agents(self):
        result = estimate_campaign_savings([])
        self.assertEqual(result["tiered_usd"], 0)
        self.assertEqual(result["opus_usd"], 0)


# ---------------------------------------------------------------------------
# TrackActualTokens
# ---------------------------------------------------------------------------


class TestTrackActualTokens(unittest.TestCase):
    def test_empty_agent_result_has_token_fields(self):
        result = task_manager._empty_agent_result()
        self.assertIn("input_tokens", result)
        self.assertIn("output_tokens", result)
        self.assertEqual(result["input_tokens"], 0)
        self.assertEqual(result["output_tokens"], 0)

    def test_savings_uses_actual_tokens_when_available(self):
        # Agent with actual tokens should have different cost than using defaults
        agent_with_actual = {
            "model": "sonnet",
            "input_tokens": 5000,
            "output_tokens": 1000,
        }
        agent_with_defaults = {
            "model": "sonnet",
        }

        # With actual tokens
        result_actual = estimate_campaign_savings([agent_with_actual])
        # With defaults (50_000 input, 10_000 output)
        result_defaults = estimate_campaign_savings([agent_with_defaults])

        # The actual cost should be significantly lower since we're using much smaller token counts
        self.assertLess(result_actual["tiered_usd"], result_defaults["tiered_usd"])
        self.assertLess(result_actual["opus_usd"], result_defaults["opus_usd"])


# ---------------------------------------------------------------------------
# Integration: cmd_run includes model field
# ---------------------------------------------------------------------------


class TestCmdRunModelField(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.agents_dir = self.root / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.root / "data"
        self.plans_dir = self.data_dir / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "tasks.json"
        self.tracker_file = self.root / "custom-tracker.md"
        self.conventions_file = self.root / "CLAUDE.md"
        self.conventions_file.write_text("Test.\n", encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_spec(self, letter, name, *, deps="(none)", files="`example.py`"):
        import textwrap

        path = self.agents_dir / f"agent-{letter}-{name}.md"
        path.write_text(
            textwrap.dedent(f"""\
                # Agent Task — {name}

                **Scope:** Test agent

                **Depends on:** {deps}

                **Output files:** {files}

                ## Exit Criteria

                - Scope is implemented.

                ## Context — read before doing anything

                1. CLAUDE.md

                ## Task

                ### Part 1 — Do the thing

                Implement it.

                ## Constraints

                - None.

                ## Verification

                ```bash
                echo ok
                ```

                ## Do NOT

                - Nothing.
            """),
            encoding="utf-8",
        )
        return path

    def test_cmd_run_output_includes_model_field(self):
        cfg = {
            "project": {"name": "Test", "conventions": "CLAUDE.md"},
            "commands": {"test": "echo ok"},
            "models": {"low": "haiku", "medium": "sonnet", "high": "opus"},
        }
        with patch_env(self, project_name="Test", tracker=False, commands={"test": "echo ok"}) as stack:
            stack.enter_context(unittest.mock.patch.object(task_manager, "_CFG", cfg))
            self._write_spec("a", "alpha")
            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_run(argparse.Namespace(agents="a", json=True))

        payload = json.loads(buf.getvalue())
        self.assertEqual(len(payload["agents"]), 1)
        self.assertIn("model", payload["agents"][0])
        # Default complexity is "low" → "haiku"
        self.assertEqual(payload["agents"][0]["model"], "haiku")

    def test_cmd_run_model_reflects_task_complexity(self):
        cfg = {
            "project": {"name": "Test", "conventions": "CLAUDE.md"},
            "commands": {"test": "echo ok"},
            "models": {"low": "haiku", "medium": "sonnet", "high": "opus"},
        }
        with patch_env(self, project_name="Test", tracker=False, commands={"test": "echo ok"}) as stack:
            stack.enter_context(unittest.mock.patch.object(task_manager, "_CFG", cfg))
            self._write_spec("a", "alpha")
            # Manually set complexity on the task after sync
            task_manager.sync_state()
            state = task_manager.load_state()
            state["tasks"]["a"]["complexity"] = "high"
            task_manager.save_state(state)

            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_run(argparse.Namespace(agents="a", json=True))

        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["agents"][0]["model"], "opus")


# ---------------------------------------------------------------------------
# Integration: complexity flows through plan execute → task state
# ---------------------------------------------------------------------------


class TestComplexityFlowThroughPlanExecute(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.agents_dir = self.root / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.root / "data"
        self.plans_dir = self.data_dir / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "tasks.json"
        self.tracker_file = self.root / "custom-tracker.md"
        self.conventions_file = self.root / "CLAUDE.md"
        self.conventions_file.write_text("Test.\n", encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_plan_execute_preserves_complexity(self):
        with patch_env(
            self,
            project_name="Test",
            tracker=False,
            commands={"test": "echo ok", "compile": "echo ok"},
        ):
            # Create + approve a plan
            with redirect_stdout(io.StringIO()):
                task_manager.cmd_plan(argparse.Namespace(plan_command="create", description="Test plan", json=False))

            state = task_manager.load_state()
            plan_id = state["plans"][0]["id"]

            # Add agents with different complexity
            with redirect_stdout(io.StringIO()):
                task_manager.cmd_plan_add_agent(
                    argparse.Namespace(
                        plan_id=plan_id,
                        letter="a",
                        name="simple",
                        scope="Simple task",
                        deps="",
                        files="a.py",
                        group="",
                        complexity="low",
                    )
                )
                task_manager.cmd_plan_add_agent(
                    argparse.Namespace(
                        plan_id=plan_id,
                        letter="b",
                        name="complex",
                        scope="Complex task",
                        deps="a",
                        files="b.py",
                        group="",
                        complexity="high",
                    )
                )

            # Finalize + approve + execute
            with redirect_stdout(io.StringIO()):
                task_manager.cmd_plan(
                    argparse.Namespace(
                        plan_command="finalize",
                        plan_id=plan_id,
                        json=False,
                        goal="Test complexity flow",
                        exit_criterion=["Tests pass"],
                        verification_step=["echo ok"],
                        documentation_update=["None"],
                    )
                )
                task_manager.cmd_plan(argparse.Namespace(plan_command="approve", plan_id=plan_id, json=False))
                task_manager.cmd_plan(argparse.Namespace(plan_command="execute", plan_id=plan_id, json=False))

            state = task_manager.load_state()

        self.assertEqual(state["tasks"]["a"]["complexity"], "low")
        self.assertEqual(state["tasks"]["b"]["complexity"], "high")


# ---------------------------------------------------------------------------
# Integration: normalize backfills complexity on legacy state
# ---------------------------------------------------------------------------


class TestNormalizeBackfillsComplexity(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.agents_dir = self.root / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.root / "data"
        self.plans_dir = self.data_dir / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "tasks.json"
        self.tracker_file = self.root / "custom-tracker.md"
        self.conventions_file = self.root / "CLAUDE.md"
        self.conventions_file.write_text("Test.\n", encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_legacy_task_without_complexity_gets_default(self):
        # Simulate a legacy state file without complexity field
        legacy_state = {
            "version": 2,
            "tasks": {
                "a": {
                    "id": "a",
                    "name": "legacy-agent",
                    "spec_file": "",
                    "scope": "",
                    "status": "done",
                    "deps": [],
                    "files": [],
                    "group": 0,
                    "tracker_id": "",
                    "started_at": "",
                    "completed_at": "",
                    "summary": "",
                    "error": "",
                }
            },
            "groups": {},
            "plans": [],
        }

        with patch_env(self, project_name="Test", tracker=False):
            task_manager.save_state(legacy_state)
            state = task_manager.load_state()

        self.assertEqual(state["tasks"]["a"].get("complexity"), "low")


# ---------------------------------------------------------------------------
# Integration: analyze --json includes telemetry
# ---------------------------------------------------------------------------


class TestAnalyzeTelemetry(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.agents_dir = self.root / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.root / "data"
        self.plans_dir = self.data_dir / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "tasks.json"
        self.tracker_file = self.root / "custom-tracker.md"
        self.conventions_file = self.root / "CLAUDE.md"
        self.conventions_file.write_text("Test.\n", encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_analyze_json_includes_telemetry(self):
        with patch_env(self, project_name="Test", tracker=False):
            buf = io.StringIO()
            with redirect_stdout(buf):
                task_manager.cmd_analyze(argparse.Namespace(json=True))

        payload = json.loads(buf.getvalue())
        self.assertIn("telemetry", payload)
        self.assertIn("analyze_ms", payload["telemetry"])
        self.assertGreaterEqual(payload["telemetry"]["analyze_ms"], 0)
        self.assertIn("analysis_json_bytes", payload["telemetry"])
        self.assertGreater(payload["telemetry"]["analysis_json_bytes"], 0)


class TestAnalysisCache(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.agents_dir = self.root / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.root / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_cache_file = self.data_dir / "analysis-cache.json"
        self.plans_dir = self.data_dir / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "tasks.json"
        self.tracker_file = self.root / "custom-tracker.md"
        self.conventions_file = self.root / "CLAUDE.md"
        self.conventions_file.write_text("Test.\n", encoding="utf-8")
        (self.root / "app.py").write_text("print('ok')\n", encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_analyze_project_reuses_cached_snapshot_when_key_matches(self):
        analysis = {
            "root": str(self.root),
            "files": [{"path": "app.py", "lines": 1, "category": "scripts"}],
            "totals": {"files": 1, "lines": 1},
            "modules": {"scripts": {"file_count": 1, "total_lines": 1, "files": ["app.py"]}},
            "conflict_zones": [],
            "dependency_edges": [],
            "project_graph": {"nodes": [], "edges": []},
            "analysis_v2": {"schema_version": 2, "planning_context": {}, "providers": []},
        }

        with (
            patch_env(self, project_name="Test", tracker=False),
            mock.patch.object(task_manager, "_analysis_cache_key", side_effect=["cache-key", "cache-key"]),
            mock.patch.object(task_manager, "run_analysis", return_value=analysis) as run_analysis,
        ):
            first = task_manager.analyze_project()
            second = task_manager.analyze_project()

        self.assertEqual(run_analysis.call_count, 1)
        self.assertEqual(first["totals"]["files"], 1)
        self.assertEqual(second["totals"]["files"], 1)
        self.assertTrue(self.analysis_cache_file.exists())

    def test_analyze_project_recomputes_when_key_changes(self):
        first_analysis = {
            "root": str(self.root),
            "files": [],
            "totals": {"files": 1, "lines": 1},
            "modules": {},
            "conflict_zones": [],
            "dependency_edges": [],
            "project_graph": {"nodes": [], "edges": []},
            "analysis_v2": {"schema_version": 2, "planning_context": {}, "providers": []},
        }
        second_analysis = {
            **first_analysis,
            "totals": {"files": 2, "lines": 2},
        }

        with (
            patch_env(self, project_name="Test", tracker=False),
            mock.patch.object(task_manager, "_analysis_cache_key", side_effect=["key-1", "key-2"]),
            mock.patch.object(task_manager, "run_analysis", side_effect=[first_analysis, second_analysis]) as run_analysis,
        ):
            first = task_manager.analyze_project()
            second = task_manager.analyze_project()

        self.assertEqual(run_analysis.call_count, 2)
        self.assertEqual(first["totals"]["files"], 1)
        self.assertEqual(second["totals"]["files"], 2)

    def test_analyze_project_recomputes_when_key_is_unavailable(self):
        first_analysis = {
            "root": str(self.root),
            "files": [],
            "totals": {"files": 1, "lines": 1},
            "modules": {},
            "conflict_zones": [],
            "dependency_edges": [],
            "project_graph": {"nodes": [], "edges": []},
            "analysis_v2": {"schema_version": 2, "planning_context": {}, "providers": []},
        }
        second_analysis = {
            **first_analysis,
            "totals": {"files": 3, "lines": 3},
        }

        with (
            patch_env(self, project_name="Test", tracker=False),
            mock.patch.object(task_manager, "_analysis_cache_key", side_effect=[None, None]),
            mock.patch.object(task_manager, "run_analysis", side_effect=[first_analysis, second_analysis]) as run_analysis,
        ):
            first = task_manager.analyze_project()
            second = task_manager.analyze_project()

        self.assertEqual(run_analysis.call_count, 2)
        self.assertEqual(first["totals"]["files"], 1)
        self.assertEqual(second["totals"]["files"], 3)


# ---------------------------------------------------------------------------
# _analysis_cache_key_segments
# ---------------------------------------------------------------------------


class TestAnalysisCacheSegments(unittest.TestCase):
    """Tests for the granular per-provider cache key segments."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        # Create a minimal project layout so that _analysis_cache_file resolves
        # correctly when ROOT is patched.
        (self.root / "data").mkdir(parents=True, exist_ok=True)
        (self.root / "CLAUDE.md").write_text("Test.\n", encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _compute_segments(self):
        """Patch ROOT then call _analysis_cache_key_segments."""
        with mock.patch.object(task_manager, "ROOT", self.root):
            return task_manager._analysis_cache_key_segments()

    # ------------------------------------------------------------------
    # tests
    # ------------------------------------------------------------------

    def test_segments_returns_expected_keys(self):
        segments = self._compute_segments()
        self.assertIsNotNone(segments)
        self.assertEqual(set(segments.keys()), {"base", "basic", "dotnet-cli"})

    def test_md_only_change_preserves_dotnet_segment(self):
        # Seed a .csproj so dotnet segment is non-trivial
        (self.root / "App.csproj").write_text("<Project/>", encoding="utf-8")

        segments_before = self._compute_segments()
        self.assertIsNotNone(segments_before)

        # Modify only a .md file
        md_file = self.root / "README.md"
        md_file.write_text("# Hello\n", encoding="utf-8")

        segments_after = self._compute_segments()
        self.assertIsNotNone(segments_after)

        # dotnet-cli segment must be unchanged — .md is not a dotnet file
        self.assertEqual(segments_before["dotnet-cli"], segments_after["dotnet-cli"])

    def test_csproj_change_affects_dotnet_segment(self):
        csproj = self.root / "App.csproj"
        csproj.write_text("<Project/>", encoding="utf-8")

        segments_before = self._compute_segments()
        self.assertIsNotNone(segments_before)

        # Touch the .csproj — update mtime by rewriting with different content
        import time as _time

        _time.sleep(0.01)
        csproj.write_text("<Project><!-- changed --></Project>", encoding="utf-8")

        segments_after = self._compute_segments()
        self.assertIsNotNone(segments_after)

        # dotnet-cli segment must differ because the .csproj changed
        self.assertNotEqual(segments_before["dotnet-cli"], segments_after["dotnet-cli"])


# ---------------------------------------------------------------------------
# TestTieredTokenEstimates
# ---------------------------------------------------------------------------


class TestTieredTokenEstimates(unittest.TestCase):
    """Tests for per-tier token budgets in estimate_campaign_savings."""

    def test_low_tier_cheapest(self):
        """Agent with complexity 'low' produces lower cost than 'high'."""
        low_agent = [{"model": "sonnet", "complexity": "low"}]
        high_agent = [{"model": "sonnet", "complexity": "high"}]
        result_low = estimate_campaign_savings(low_agent, use_tiered=True)
        result_high = estimate_campaign_savings(high_agent, use_tiered=True)
        self.assertLess(result_low["tiered_usd"], result_high["tiered_usd"])
        self.assertLess(result_low["opus_usd"], result_high["opus_usd"])

    def test_high_tier_most_expensive(self):
        """Agent with complexity 'high' produces higher cost than 'medium'."""
        medium_agent = [{"model": "sonnet", "complexity": "medium"}]
        high_agent = [{"model": "sonnet", "complexity": "high"}]
        result_medium = estimate_campaign_savings(medium_agent, use_tiered=True)
        result_high = estimate_campaign_savings(high_agent, use_tiered=True)
        self.assertGreater(result_high["tiered_usd"], result_medium["tiered_usd"])
        self.assertGreater(result_high["opus_usd"], result_medium["opus_usd"])

    def test_tiered_differs_from_flat(self):
        """use_tiered=True gives different result than use_tiered=False when agents have complexity set."""
        agents = [{"model": "sonnet", "complexity": "low"}, {"model": "sonnet", "complexity": "high"}]
        result_tiered = estimate_campaign_savings(agents, use_tiered=True)
        result_flat = estimate_campaign_savings(agents, use_tiered=False)
        # The flat averages (50k input / 10k output) differ from the tiered budgets, so totals must differ
        self.assertNotEqual(result_tiered["tiered_usd"], result_flat["tiered_usd"])
        self.assertNotEqual(result_tiered["opus_usd"], result_flat["opus_usd"])

    def test_missing_complexity_falls_back(self):
        """Agent with no complexity key falls back to 'medium' tier budget."""
        no_complexity = [{"model": "sonnet"}]
        medium_complexity = [{"model": "sonnet", "complexity": "medium"}]
        result_no_key = estimate_campaign_savings(no_complexity, use_tiered=True)
        result_medium = estimate_campaign_savings(medium_complexity, use_tiered=True)
        # Both should use the medium budget, so costs must be identical
        self.assertEqual(result_no_key["tiered_usd"], result_medium["tiered_usd"])
        self.assertEqual(result_no_key["opus_usd"], result_medium["opus_usd"])

        # Also verify the actual token count matches _TIER_TOKEN_BUDGETS["medium"]
        expected_cost = estimate_agent_cost_usd(
            "sonnet",
            input_tokens=_TIER_TOKEN_BUDGETS["medium"]["input"],
            output_tokens=_TIER_TOKEN_BUDGETS["medium"]["output"],
        )
        self.assertEqual(result_no_key["tiered_usd"], expected_cost)


# ---------------------------------------------------------------------------
# TestCachePerformance
# ---------------------------------------------------------------------------


class TestCachePerformance(unittest.TestCase):
    """Tests for compact cache JSON and cache-key correctness."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        (self.root / "data").mkdir(parents=True, exist_ok=True)
        self.cache_file = self.root / "data" / "analysis-cache.json"

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_compact_cache_json(self):
        """_save_analysis_cache_snapshot writes compact JSON with no newlines/indentation."""
        analysis = {"files": [], "totals": {"files": 0, "lines": 0}}
        cache_key = "test-key-abc123"

        task_manager._save_analysis_cache_snapshot(self.cache_file, cache_key, analysis)

        self.assertTrue(self.cache_file.exists())
        content = self.cache_file.read_text(encoding="utf-8")
        # Strip trailing newline for inspection
        stripped = content.strip()
        # Compact JSON has no internal newlines
        self.assertNotIn("\n", stripped)
        # Compact JSON has no indentation (no leading spaces before keys)
        self.assertNotIn("  ", stripped)
        # Verify it is still valid JSON with the right content
        payload = json.loads(content)
        self.assertEqual(payload["key"], cache_key)
        self.assertEqual(payload["analysis"], analysis)

    def test_nested_source_change_updates_basic_segment(self):
        """Nested source edits must invalidate the basic analysis cache segment."""
        src_dir = self.root / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        source_file = src_dir / "app.py"
        source_file.write_text("print('one')\n", encoding="utf-8")

        with mock.patch.object(task_manager, "ROOT", self.root):
            first = task_manager._analysis_cache_key_segments()
            self.assertIsNotNone(first)
            source_file.write_text("print('two')\n", encoding="utf-8")
            second = task_manager._analysis_cache_key_segments()

        self.assertIsNotNone(second)
        self.assertNotEqual(first["basic"], second["basic"])


if __name__ == "__main__":
    unittest.main()
