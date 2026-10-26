"""Opt-in, sequential CLI probes for automatic skill selection (stdlib only).

Exit zero means routing checks passed. Task results always require manual review.
This module never launches a CLI on import. Each invocation retains its fixtures,
prompts, process logs, hashes, and report under a fresh system-temp directory.
Inherited provider instructions/configuration remain active and are not fully
snapshotted; requested skill-root hashes do not prove the effective catalog.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import uuid
from pathlib import Path, PurePosixPath

DEFAULT_SPEC = Path(__file__).resolve().parents[1] / "docs/reviews/fixtures/invocation-controls-2026-10-03.json"
SKILL_PATH = re.compile(r"[\\/]+([A-Za-z0-9_.-]+)[\\/]+SKILL\.md\b", re.I)
SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
SHELL_TOKENS = re.compile(r"'([^']*(?:''[^']*)*)'|\"((?:\\.|[^\"])*)\"|([;&|]+)|([^\s;&|]+)")


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fixture_path(value):
    if not isinstance(value, str) or not value or ":" in value or "\x00" in value:
        raise ValueError(f"Invalid fixture path: {value!r}")
    value = value.replace("\\", "/")
    parts = value.split("/")
    if PurePosixPath(value).is_absolute() or any(
        not part or part.startswith(".") or part.rstrip(". ") != part
        or part.casefold() in {"agents.md", "claude.md", "gemini.md"}
        for part in parts
    ):
        raise ValueError(f"Unsafe fixture path: {value!r}")
    return value


def select_cases(spec, args):
    if not isinstance(spec, dict) or spec.get("schema_version") != 1 or not isinstance(spec.get("fixtures"), dict) or not spec["fixtures"]:
        raise ValueError("Require schema_version 1 and nonempty fixtures")
    seen_paths = set()
    for name, value in spec["fixtures"].items():
        normalized = fixture_path(name).casefold()
        if normalized in seen_paths or not isinstance(value, (str, dict)):
            raise ValueError("Duplicate fixture path or unsupported fixture content")
        seen_paths.add(normalized)
    if not isinstance(spec.get("cases"), list) or not spec["cases"]:
        raise ValueError("Require a nonempty case list")
    seen_ids = set()
    for case in spec["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not SLUG.fullmatch(case["id"]):
            raise ValueError("Invalid case id")
        if case["id"].casefold() in seen_ids:
            raise ValueError("Duplicate case id")
        seen_ids.add(case["id"].casefold())
        providers = case.get("providers")
        if not isinstance(providers, list) or not providers or any(not isinstance(p, str) or p not in ("codex", "claude") for p in providers) or len(set(providers)) != len(providers):
            raise ValueError("Invalid case providers")
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            raise ValueError("Empty case prompt")
        skills = [case[key] for key in ("expected_skill", "forbidden_skill") if key in case]
        if len(skills) != 1 or not isinstance(skills[0], str) or not SLUG.fullmatch(skills[0]) or ".." in skills[0]:
            raise ValueError("Each case needs one safe expected_skill or forbidden_skill")
    if args.repeat < 1 or not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError("repeat and timeout must be positive")
    providers = list(dict.fromkeys(args.provider or ["codex", "claude"]))
    if "both" in providers:
        providers = ["codex", "claude"]
    requested = set(args.case or [])
    if requested - {case["id"] for case in spec["cases"]}:
        raise ValueError("Unknown case selection")
    selected = [(provider, case) for case in spec["cases"] if not requested or case["id"] in requested
                for provider in providers if provider in case["providers"]]
    if not selected or any(not any(case["id"] == wanted for _, case in selected) for wanted in requested):
        raise ValueError("Empty or incompatible provider/case selection")
    return selected


def snapshot(directory):
    files, metadata, errors = {}, {}, []
    for parent, dirs, names in os.walk(directory, followlinks=False):
        for name in list(dirs) + names:
            path = Path(parent) / name
            relative = path.relative_to(directory).as_posix()
            info = path.lstat()
            if path.is_symlink() or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                errors.append(f"Unexpected link: {relative}")
                if name in dirs:
                    dirs.remove(name)
            elif path.is_file():
                (metadata if relative.startswith(".remember/") else files)[relative] = digest(path)
            elif not path.is_dir():
                errors.append(f"Unexpected special file: {relative}")
    return {"files": files, "remember_metadata": metadata, "errors": errors}


def run_process(command, cwd, prompt_path, stdout_path, stderr_path, timeout):
    started = time.monotonic()
    result = {"command": command, "returncode": None, "timed_out": False, "errors": []}
    with Path(prompt_path).open("rb") as inp, Path(stdout_path).open("wb") as out, Path(stderr_path).open("wb") as err:
        options = {"start_new_session": True} if os.name != "nt" else {
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
        try:
            process = subprocess.Popen(command, cwd=cwd, stdin=inp, stdout=out, stderr=err, **options)
        except OSError as exc:
            result["errors"].append(f"Launch failed: {exc}")
        else:
            result["pid"] = process.pid
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                result["timed_out"] = True
                try:
                    if os.name == "nt":
                        killed = subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                                                capture_output=True, timeout=10)
                        if killed.returncode:
                            result["errors"].append(f"Owned-tree termination exited {killed.returncode}")
                            process.kill()
                    else:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    result["errors"].append(f"Owned-tree termination failed: {exc}")
            result["returncode"] = process.poll()
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def reader_targets(command, depth=0):
    """Recognize literal reader targets; arbitrary shell programs remain unknown."""
    segments, segment = [], []
    for match in SHELL_TOKENS.finditer(command):
        if match.group(3):
            if segment:
                segments.append(segment)
            segment = []
        else:
            segment.append(next(group for group in (match.group(1), match.group(2), match.group(4)) if group is not None))
    if segment:
        segments.append(segment)
    targets = []
    pure = len(segments) == 1
    for words in segments:
        verb = words[0].replace("\\", "/").split("/")[-1].lower().removesuffix(".exe")
        if verb in {"powershell", "pwsh", "sh", "bash"} and depth < 2:
            flags = {"-noprofile", "-nologo", "-noninteractive"} if verb in {"powershell", "pwsh"} else {"--noprofile", "--norc"}
            command_flags = {"-command", "-c"} if verb in {"powershell", "pwsh"} else {"-c"}
            index = 1
            while index < len(words) and words[index].casefold() in flags:
                index += 1
            if index == len(words) - 2 and words[index].casefold() in command_flags:
                nested, simple = reader_targets(words[index + 1], depth + 1)
                targets.extend(nested)
                pure = pure and simple
                continue
        if verb not in {"get-content", "cat"}:
            pure = False
            continue
        index = 1
        while index < len(words):
            word = words[index]
            option = word.casefold()
            if verb == "get-content" and option in {"-path", "-literalpath", "-delimiter", "-encoding", "-totalcount", "-tail", "-readcount"}:
                if index + 1 >= len(words):
                    pure = False
                    break
                if option in {"-path", "-literalpath"}:
                    targets.append(words[index + 1])
                index += 2
                continue
            if (verb == "get-content" and option in {"-raw", "-force"}) or (
                verb == "cat" and word in {"-n", "-b", "-s", "-v", "-e", "-t", "-A", "-E", "-T",
                                           "--number", "--number-nonblank", "--squeeze-blank", "--show-all",
                                           "--show-nonprinting", "--show-ends", "--show-tabs"}
            ):
                index += 1
                continue
            if word.startswith("-"):
                pure = False
                break
            targets.append(word)
            index += 1
    if any(any(character in target for character in "$`*?[](){}<>") for target in targets):
        pure = False
    return targets, pure and len(targets) == 1


def plain_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(block.get("text", "") for block in content if isinstance(block, dict) and isinstance(block.get("text"), str))
    return ""


def skill_name(name):
    return name.split(":")[-1].casefold() if isinstance(name, str) else ""


def record_completion(tool, completion, errors):
    """Keep the first result; contradictory repeats invalidate the evidence."""
    if "completion" in tool:
        if tool["completion"] != completion:
            errors.append(f"Conflicting completed results for {tool['id']}")
            tool.setdefault("conflicting_completions", []).append(completion)
            tool["success"] = False
        return False
    tool["completion"] = completion
    return True


def parse_trace(provider, path, case, trusted_entries=None, fixture_dir=None):
    errors, tools, final, usage, catalog = [], {}, [], [], {}
    terminal = False
    target = skill_name(case.get("expected_skill", case.get("forbidden_skill")))
    if trusted_entries is not None:
        trusted_entries = {skill_name(name): entry for name, entry in trusted_entries.items()}
    for number, line in enumerate(Path(path).read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("record is not an object")
            kind = event.get("type")
            if provider == "codex":
                if kind in {"thread.started", "turn.started"}:
                    continue
                if kind == "turn.completed":
                    terminal = True
                    usage.append(event.get("usage"))
                elif kind in {"item.started", "item.updated", "item.completed"}:
                    item = event["item"]
                    item_type = item["type"]
                    if item_type == "agent_message":
                        if kind == "item.completed":
                            final.append(item.get("text", ""))
                    elif item_type == "reasoning":
                        continue
                    elif item_type == "command_execution":
                        identifier, command = item["id"], item["command"]
                        if not isinstance(identifier, str) or not identifier or not isinstance(command, str):
                            raise ValueError("Invalid command id/payload")
                        tool = tools.setdefault(identifier, {"id": identifier, "name": "command_execution", "payload": command})
                        if tool["payload"] != command:
                            errors.append(f"Changed command payload for {identifier}")
                            identifier = f"{identifier}:line:{number}"
                            tool = tools.setdefault(identifier, {"id": item["id"], "name": "command_execution", "payload": command})
                        tool["started"] = tool.get("started", False) or kind == "item.started"
                        if kind == "item.completed":
                            if not record_completion(tool, item, errors):
                                continue
                            tool["completed"] = True
                            tool["output"] = item.get("aggregated_output", "")
                            if not isinstance(tool["output"], str) or type(item.get("exit_code")) is not int:
                                raise ValueError("Malformed command completion")
                            tool["success"] = item["exit_code"] == 0 and item.get("status") == "completed"
                    else:
                        errors.append(f"Unrecognized Codex item: {item_type}")
                        tools[f"unknown-{number}"] = {"name": item_type, "payload": item}
                else:
                    errors.append(f"Unrecognized or failed Codex event: {kind}")
            else:
                if kind == "system":
                    if event.get("subtype") == "init" and "skills" in event:
                        skills = event["skills"]
                        if not isinstance(skills, list):
                            raise ValueError("Malformed exposed skill catalog")
                        catalog = {"skills": skills, "target_advertised": target in [skill_name(s.get("name") if isinstance(s, dict) else s) for s in skills]}
                elif kind in {"assistant", "user"}:
                    blocks = event["message"]["content"]
                    if not isinstance(blocks, list):
                        raise ValueError("Malformed message content")
                    for block in blocks:
                        if block.get("type") == "tool_use":
                            identifier, name, payload = block["id"], block["name"], block["input"]
                            if not isinstance(identifier, str) or not identifier or not isinstance(payload, dict):
                                raise ValueError("Malformed tool payload")
                            tool = tools.setdefault(identifier, {"id": identifier, "name": name, "payload": payload, "started": True})
                            if tool["payload"] != payload or tool["name"] != name:
                                errors.append(f"Changed tool payload for {identifier}")
                                tools[f"{identifier}:line:{number}"] = {"id": identifier, "name": name, "payload": payload, "started": True}
                            if name not in {"Skill", "Read", "Glob", "Grep"}:
                                errors.append(f"Unrecognized Claude tool: {name}")
                        elif block.get("type") == "tool_result":
                            identifier = block["tool_use_id"]
                            if identifier not in tools:
                                errors.append(f"Unmatched tool result: {identifier}")
                                continue
                            if not record_completion(tools[identifier], block, errors):
                                continue
                            tools[identifier].update(completed=True, success=not block.get("is_error", False),
                                                     output=plain_content(block.get("content")))
                        elif block.get("type") == "text" and kind == "assistant":
                            final.append(block.get("text", ""))
                        elif block.get("type") not in {"text", "thinking", "redacted_thinking"}:
                            errors.append(f"Unrecognized Claude content: {block.get('type')}")
                            tools[f"unknown-{number}-{len(tools)}"] = {"name": block.get("type"), "payload": block}
                elif kind == "result":
                    terminal = event.get("subtype") == "success" and event.get("is_error") is False
                    usage.append(event.get("usage"))
                    final.append(event.get("result", ""))
                    if not terminal:
                        errors.append("Claude result was not successful")
                    if not isinstance(event.get("result"), str) or not event["result"].strip():
                        errors.append("Claude result lacked a nonempty final answer")
                elif kind != "rate_limit_event":
                    errors.append(f"Unrecognized Claude event: {kind}")
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            errors.append(f"Malformed trace line {number}: {exc}")
    attempts, fixture_reads, ambiguous = [], [], []
    for identifier, tool in tools.items():
        if not tool.get("started") or not tool.get("completed"):
            errors.append(f"Incomplete/unpaired tool: {identifier}")
        success = bool(tool.get("started") and tool.get("completed") and tool.get("success") and str(tool.get("output", "")).strip())
        targets, references, direct_skill = [], [], None
        if tool["name"] == "command_execution":
            targets, pure = reader_targets(tool["payload"])
            references = [skill_name(name) for name in SKILL_PATH.findall(tool["payload"])]
            success = success and pure
        elif tool["name"] == "Read":
            path_value = tool["payload"].get("file_path")
            if isinstance(path_value, str):
                targets = [path_value]
            else:
                errors.append(f"Malformed Read target: {identifier}")
        elif tool["name"] == "Skill":
            direct_skill = skill_name(tool["payload"].get("skill"))
            if not direct_skill:
                errors.append(f"Malformed Skill target: {identifier}")
            launch = re.search(r"Launching skill:\s*([\w:.-]+)", str(tool.get("output", "")))
            success = success and launch is not None and skill_name(launch.group(1)) == direct_skill
        read_skills = {}
        for path_value in targets:
            match = SKILL_PATH.search(path_value)
            if match:
                skill = skill_name(match.group(1))
                resolved = (Path(fixture_dir or Path.cwd()) / path_value).resolve()
                trusted = trusted_entries is None or (
                    skill in trusted_entries and resolved == Path(trusted_entries[skill]).resolve())
                read_skills[skill] = read_skills.get(skill, False) or trusted
            elif success:
                resolved = (Path(fixture_dir or Path.cwd()) / path_value).resolve()
                if fixture_dir is None:
                    fixture_reads.append(path_value)
                elif resolved.is_relative_to(fixture_dir):
                    fixture_reads.append(resolved.relative_to(fixture_dir).as_posix())
        for skill in sorted(set(read_skills) | ({direct_skill} if direct_skill else set())):
            attempts.append({"skill": skill, "tool_id": identifier,
                             "success": success and (skill == direct_skill or read_skills.get(skill, False))})
        ambiguous.extend({"skill": skill, "tool_id": identifier} for skill in set(references) - set(read_skills))
    if not terminal:
        errors.append("Missing successful terminal completion")
    if not any(isinstance(text, str) and text.strip() for text in final):
        errors.append("Missing nonempty final answer")
    forbidden = skill_name(case.get("forbidden_skill"))
    if forbidden and any(attempt["skill"] == forbidden for attempt in attempts):
        status = "FAIL"
    elif errors or ambiguous or (forbidden and catalog.get("target_advertised") is False):
        status = "INCONCLUSIVE"
    elif case.get("expected_skill") and not any(a["skill"] == target and a["success"] for a in attempts):
        status = "INCONCLUSIVE"
    else:
        status = "PASS"
    return {"routing_status": status, "task_result_status": "MANUAL_REVIEW_REQUIRED", "terminal_completion": terminal,
            "skill_attempts": attempts, "ambiguous_skill_references": ambiguous, "tools": list(tools.values()),
            "fixture_reads": sorted(set(fixture_reads)), "catalog": catalog, "native_usage": usage,
            "final_output": final, "errors": errors}


def resolve_cli(provider, override):
    executable = shutil.which(override or (provider + ".exe" if os.name == "nt" else provider))
    if not executable or Path(executable).suffix.lower() in {".ps1", ".cmd", ".bat"}:
        raise ValueError(f"Direct executable not found for {provider}")
    return str(Path(executable).resolve())


def cli_version(executable, directory, label, timeout):
    prompt, out, err = (directory / f"{label}.{suffix}" for suffix in ("stdin", "stdout", "stderr"))
    prompt.write_bytes(b"")
    process = run_process([executable, "--version"], directory, prompt, out, err, min(timeout, 30))
    return {"path": executable, "sha256": digest(executable), "version": out.read_text(encoding="utf-8", errors="replace").strip(),
            "process": process, "stdout_path": str(out), "stderr_path": str(err)}


def run(args):
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    selected = select_cases(spec, args)
    entries, executables = {}, {}
    for provider, case in selected:
        root = getattr(args, f"{provider}_skill_root")
        if root is None:
            raise ValueError(f"Explicit --{provider}-skill-root is required")
        skill = case.get("expected_skill", case.get("forbidden_skill"))
        entry = root / skill / "SKILL.md"
        if not entry.is_file():
            raise ValueError(f"Missing targeted skill entry: {entry}")
        entries[f"{provider}:{skill}"] = str(entry.resolve())
    before = {key: {"path": path, "sha256": digest(path)} for key, path in entries.items()}
    for provider, _ in selected:
        if provider not in executables:
            executables[provider] = resolve_cli(provider, getattr(args, f"{provider}_cli"))
    artifact = Path(tempfile.mkdtemp(prefix="skill-invocation-"))
    evidence = artifact / "evidence"
    evidence.mkdir()
    save_json(artifact / "case-spec.json", spec)
    report = {"case_spec_path": str(args.spec.resolve()), "case_spec_sha256": digest(args.spec), "skill_hashes_before": before,
              "coverage": "Routing only. Inherited instructions/configuration remain active and are not fully snapshotted; requested root hashes do not prove the effective catalog.",
              "versions_before": {}, "runs": [], "errors": []}
    for provider, executable in executables.items():
        version = cli_version(executable, evidence, f"{provider}-before", args.timeout)
        report["versions_before"][provider] = version
        if version["process"]["returncode"] != 0 or version["process"]["timed_out"] or not version["version"]:
            report["errors"].append(f"Could not establish {provider} CLI version")
    if not report["errors"]:
        for provider, case in selected:
            for repeat in range(1, args.repeat + 1):
                identifier = str(uuid.uuid4())
                fixture, run_dir = artifact / identifier, evidence / identifier
                fixture.mkdir()
                run_dir.mkdir()
                for name, value in spec["fixtures"].items():
                    path = fixture / fixture_path(name)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2) + "\n", encoding="utf-8")
                prompt, out, err = (run_dir / name for name in ("prompt.txt", "stdout.jsonl", "stderr.txt"))
                prompt.write_text(case["prompt"], encoding="utf-8")
                fixture_before = snapshot(fixture)
                command = [executables[provider]] + (
                    ["exec", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral", "--json", "-C", str(fixture), "-"]
                    if provider == "codex" else ["-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence",
                                                "--tools", "Read,Glob,Grep,Skill", "--allowedTools", "Read,Glob,Grep,Skill",
                                                "--permission-mode", "dontAsk", "--permission-prompts", "none"])
                process = run_process(command, fixture, prompt, out, err, args.timeout)
                trusted = {key.split(":", 1)[1]: path for key, path in entries.items() if key.startswith(provider + ":")}
                result = parse_trace(provider, out, case, trusted_entries=trusted, fixture_dir=fixture)
                fixture_after = snapshot(fixture)
                result.update(provider=provider, case=case, repeat=repeat, fixture_dir=str(fixture), prompt_path=str(prompt),
                              stdout_path=str(out), stderr_path=str(err), process=process,
                              fixture_before=fixture_before, fixture_after=fixture_after)
                result["errors"].extend(process["errors"] + fixture_before["errors"] + fixture_after["errors"])
                if process["returncode"] != 0 or process["timed_out"]:
                    result["errors"].append("CLI launch, exit, or timeout failure")
                    result["routing_status"] = "FAIL"
                if fixture_before["files"] != fixture_after["files"] or fixture_after["errors"]:
                    result["errors"].append("Fixture file set/content changed")
                    result["routing_status"] = "FAIL"
                save_json(run_dir / "result.json", result)
                report["runs"].append(result)
    after = {key: {"path": path, "sha256": digest(path) if Path(path).is_file() else None} for key, path in entries.items()}
    report["skill_hashes_after"] = after
    if before != after:
        report["errors"].append("Targeted skill hash drift")
    report["versions_after"] = {provider: cli_version(executable, evidence, f"{provider}-after", args.timeout)
                                for provider, executable in executables.items()}
    for provider, current in report["versions_after"].items():
        previous = report["versions_before"][provider]
        if any(current[key] != previous[key] for key in ("path", "sha256", "version")) or current["process"]["returncode"] != 0 or current["process"]["timed_out"]:
            report["errors"].append(f"{provider} CLI version/hash drift or verification failure")
    statuses = [result["routing_status"] for result in report["runs"]]
    report["routing_status"] = "FAIL" if report["errors"] or "FAIL" in statuses else "INCONCLUSIVE" if not statuses or "INCONCLUSIVE" in statuses else "PASS"
    report["task_result_status"] = "MANUAL_REVIEW_REQUIRED"
    save_json(artifact / "report.json", report)
    return report, artifact


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--provider", action="append", choices=("codex", "claude", "both"))
    parser.add_argument("--case", action="append")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=240)
    for provider in ("codex", "claude"):
        parser.add_argument(f"--{provider}-skill-root", f"--{provider}-skills-root", type=Path)
        parser.add_argument(f"--{provider}-cli")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        report, artifact = run(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Preflight failed: {exc}")
        return 2
    for result in report["runs"]:
        print(f"{result['provider']} {result['case']['id']} #{result['repeat']}: routing {result['routing_status']}; task result needs manual review")
    print(f"Routing: {report['routing_status']}. Evidence: {artifact}")
    return 0 if report["routing_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
