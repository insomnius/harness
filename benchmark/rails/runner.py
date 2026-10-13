#!/usr/bin/env python3
"""Run paired design-thinking trials on the Rails Foundation's Fizzy tasks.

The upstream corpus and its hidden verifiers stay outside the agent workspace.
Only task instructions are sent to Codex; verification tests are copied into the
container after the agent has finished.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SKILL_SOURCE = ROOT / "plugins/design-thinking/skills/design-thinking"
DEFAULT_MODEL = "gpt-6-luna"
DEFAULT_CONDITIONS = ("baseline", "skill-cold", "skill-warm")
COMMENT_POLICY = (
    "Add a code comment only when it explains an important, non-obvious reason. "
    "Do not add comments that merely restate what the code does."
)
FIXED_GUIDANCE = f"""# Repository guidance

Keep changes focused on the requested behavior. Follow the app's existing
conventions. {COMMENT_POLICY} Run relevant tests and report what you verified.
"""
TOOL_RE = re.compile(r"^\s*(?:\+\s*)?(?:#|//|/\*|\*|<!--)")
READ_RE = re.compile(r"\b(?:cat|less|more|head|tail|sed|rg|grep|find|ls|tree|git\s+(?:show|log|diff|status))\b")
EDIT_RE = re.compile(r"\b(?:apply_patch|git\s+apply|tee|cat\s*>|sed\s+-i|perl\s+-pi|python\S*\s+-c|ruby\s+-e)\b")
VERIFY_RE = re.compile(r"(?:bin/rails\s+(?:test|spec)|\b(?:rake|bundle\s+exec\s+rspec|pytest|npm\s+test|yarn\s+test|pnpm\s+test)\b)")
DESIGN_RE = re.compile(r"(?:design\.py|\.design/|\.agents/skills/design-thinking)")
CODE_PATHS = ["*.rb", "*.js", "*.jsx", "*.ts", "*.tsx", "*.py", "*.sh", "*.css", "*.scss", "*.erb", "*.html", "*.yml", "*.yaml", "*.json"]
TEST_SUMMARY_RE = re.compile(
    r"(?m)^\s*(\d+)\s+runs?,\s*(\d+)\s+assertions?,\s*(\d+)\s+failures?,\s*(\d+)\s+errors?,\s*(\d+)\s+skips?\s*$"
)


class BenchmarkError(RuntimeError):
    pass


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    input_text: str | None = None,
    timeout: float | None = None,
    check: bool = True,
    stdout: Any = subprocess.PIPE,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            input=input_text,
            text=True,
            stdout=stdout,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise BenchmarkError(f"Command timed out after {timeout}s: {args[0]}") from exc
    if check and result.returncode:
        detail = (result.stderr or result.stdout or "").strip()
        raise BenchmarkError(f"Command failed ({result.returncode}): {' '.join(args)}\n{detail}")
    return result


def ensure_writable_tree(path: Path) -> None:
    for entry in [path, *path.rglob("*")]:
        try:
            mode = entry.stat().st_mode
            entry.chmod(mode | (0o700 if entry.is_dir() else 0o600))
        except FileNotFoundError:
            pass


def parse_task(task_dir: Path) -> dict[str, Any]:
    instruction_path = task_dir / "instruction.md"
    raw = instruction_path.read_text()
    delimiters = [i for i, line in enumerate(raw.splitlines()) if line.strip() == "---"]
    if len(delimiters) < 2:
        raise BenchmarkError(f"Missing task front matter in {instruction_path}")
    lines = raw.splitlines()
    front = lines[delimiters[0] + 1 : delimiters[1]]
    body = "\n".join(lines[delimiters[1] + 1 :]).strip()
    setup: list[str] = []
    in_setup = False
    for line in front:
        if re.match(r"^setup:\s*$", line):
            in_setup = True
            continue
        if in_setup and re.match(r"^[A-Za-z_][A-Za-z0-9_-]*:", line):
            in_setup = False
        if in_setup:
            match = re.match(r"^\s*-\s*(.+?)\s*$", line)
            if match:
                setup.append(match.group(1).strip().strip("'\""))
    required = ["instruction.md", "environment.patch", "verification_test.rb"]
    missing = [name for name in required if not (task_dir / name).is_file()]
    if missing:
        raise BenchmarkError(f"Task {task_dir.name} is missing: {', '.join(missing)}")
    return {
        "id": task_dir.name,
        "instruction": body,
        "instruction_bytes": len(body.encode()),
        "setup_commands": setup,
        "environment_patch": task_dir / "environment.patch",
        "verification_test": task_dir / "verification_test.rb",
        "task_files_sha256": sha256_files(task_dir, [path.name for path in sorted(task_dir.iterdir()) if path.is_file()]),
    }


def sha256_files(folder: Path, filenames: list[str]) -> str:
    import hashlib

    digest = hashlib.sha256()
    for filename in sorted(filenames):
        data = (folder / filename).read_bytes()
        digest.update(filename.encode())
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


def parse_jsonl(path: Path) -> dict[str, Any]:
    usage = {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "total_tokens_source": None,
        "cached_input_tokens": None,
        "reasoning_tokens": None,
    }
    counts: dict[str, int] = {}
    failed_calls = 0
    total_output_bytes = 0
    started: dict[str, float] = {}
    durations: list[float] = []
    final_message = ""
    design_cli_invocations = 0
    errors: list[str] = []
    skill_events = 0
    read_resources: set[str] = set()
    events: list[dict[str, Any]] = []

    if not path.exists():
        return {"usage": usage, "tool_calls": counts, "tool_failures": 0}

    for raw_line in path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        events.append(event)
        kind = event.get("type", "unknown")
        payload = event.get("item") or event.get("data") or {}
        if not isinstance(payload, dict):
            payload = {}
        item_type = payload.get("type", kind)
        timestamp = parse_timestamp(event.get("timestamp"))
        item_id = str(payload.get("id", ""))

        if kind in ("item.started", "item_start", "tool.started"):
            name = str(payload.get("type") or payload.get("name") or "other")
            counts[name] = counts.get(name, 0) + 1
            if item_id and timestamp is not None:
                started[item_id] = timestamp
        if kind in ("item.completed", "item_complete", "tool.completed"):
            if item_id and timestamp is not None and item_id in started:
                durations.append(max(0.0, timestamp - started[item_id]))
            status = str(payload.get("status", "")).lower()
            exit_code = payload.get("exit_code")
            if status in {"failed", "error", "cancelled", "interrupted"} or (
                isinstance(exit_code, int) and exit_code != 0
            ):
                failed_calls += 1
            for key in ("aggregated_output", "output", "result"):
                output = payload.get(key)
                if isinstance(output, str):
                    total_output_bytes += len(output.encode())
                    break

        event_text = json.dumps(event, ensure_ascii=False)
        if "design-thinking" in event_text or "design.py" in event_text:
            skill_events += 1
        if payload.get("type") in {"agent_message", "message"}:
            text_value = payload.get("text") or payload.get("message")
            if isinstance(text_value, str):
                final_message = text_value
        if kind in {"error", "turn.failed"}:
            errors.append(str(event.get("message") or event.get("error") or event))

        command = payload.get("command") or payload.get("arguments")
        if isinstance(command, str):
            if "design.py" in command:
                design_cli_invocations += 1
            if READ_RE.search(command):
                for token in re.findall(r"(?:[\w./-]+\.md|\.design/[\w./-]+)", command):
                    read_resources.add(token)

        candidate = event.get("usage") or payload.get("usage")
        if not isinstance(candidate, dict):
            candidate = event.get("total_token_usage") or payload.get("total_token_usage")
        if isinstance(candidate, dict):
            normalized = {
                "input_tokens": candidate.get("input_tokens"),
                "output_tokens": candidate.get("output_tokens"),
                "total_tokens": candidate.get("total_tokens"),
                "total_tokens_source": "reported" if candidate.get("total_tokens") is not None else None,
                "cached_input_tokens": candidate.get("cached_input_tokens"),
                "reasoning_tokens": candidate.get("reasoning_tokens"),
            }
            if normalized["input_tokens"] is not None or normalized["output_tokens"] is not None:
                usage = normalized

    if usage["total_tokens"] is None:
        input_tokens = usage["input_tokens"]
        output_tokens = usage["output_tokens"]
        if isinstance(input_tokens, int) and isinstance(output_tokens, int):
            usage["total_tokens"] = input_tokens + output_tokens
            usage["total_tokens_source"] = "input_plus_output"

    calls_by_purpose = {"discovery_read": 0, "state_or_skill": 0, "edit": 0, "verification": 0, "other": 0}
    for event in events:
        if event.get("type") not in ("item.started", "item_start", "tool.started"):
            continue
        payload = event.get("item") or event.get("data") or {}
        if not isinstance(payload, dict):
            continue
        command = str(payload.get("command") or payload.get("arguments") or "")
        item_type = str(payload.get("type") or "")
        if DESIGN_RE.search(command):
            purpose = "state_or_skill"
        elif VERIFY_RE.search(command):
            purpose = "verification"
        elif EDIT_RE.search(command) or item_type in {"file_change", "apply_patch"}:
            purpose = "edit"
        elif READ_RE.search(command):
            purpose = "discovery_read"
        else:
            purpose = "other"
        calls_by_purpose[purpose] += 1

    return {
        "usage": usage,
        "tool_calls": counts,
        "tool_calls_by_purpose": calls_by_purpose,
        "tool_failures": failed_calls,
        "tool_output_bytes": total_output_bytes,
        "tool_durations_seconds": durations,
        "tool_duration_total_seconds": sum(durations),
        "read_resources": sorted(read_resources),
        "skill_related_event_count": skill_events,
        "design_cli_invocations": design_cli_invocations,
        "final_message": final_message,
        "event_errors": errors,
        "event_count": len(events),
    }


def parse_timestamp(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def design_state_stats(workspace: Path) -> dict[str, int]:
    design = workspace / ".design"
    files = [path for path in design.rglob("*") if path.is_file()] if design.exists() else []
    log_lines = 0
    for path in files:
        if path.name.endswith(".log.jsonl"):
            try:
                log_lines += sum(1 for _ in path.open())
            except OSError:
                pass
    return {
        "file_count": len(files),
        "bytes": sum(path.stat().st_size for path in files),
        "log_records": log_lines,
    }


def estimated_documentation_read_bytes(workspace: Path, resources: list[str]) -> int:
    total = 0
    for name in resources:
        candidate = (workspace / name).resolve()
        try:
            candidate.relative_to(workspace.resolve())
        except ValueError:
            continue
        if candidate.is_file() and (candidate.suffix.lower() == ".md" or ".design" in candidate.parts):
            try:
                total += candidate.stat().st_size
            except OSError:
                pass
    return total


def changed_comment_lines(workspace: Path) -> int:
    diff = run_command(["git", "diff", "--unified=0", "HEAD", "--", *CODE_PATHS], cwd=workspace, check=False).stdout or ""
    return sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++") and TOOL_RE.match(line))


def parse_test_summary(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    matches = list(TEST_SUMMARY_RE.finditer(path.read_text(errors="replace")))
    if not matches:
        return None
    runs, assertions, failures, errors, skips = (int(value) for value in matches[-1].groups())
    evaluable_cases = max(0, runs - skips)
    passed_cases = max(0, evaluable_cases - failures - errors)
    passed_assertions = max(0, assertions - failures)
    return {
        "runs": runs,
        "assertions": assertions,
        "failures": failures,
        "errors": errors,
        "skips": skips,
        "passed_cases": passed_cases,
        "evaluable_cases": evaluable_cases,
        "passed_assertions": passed_assertions,
        "test_case_accuracy": passed_cases / evaluable_cases if evaluable_cases else None,
        "assertion_accuracy": passed_assertions / assertions if assertions and errors == 0 else None,
    }


def add_docker_mount(path: Path, target: str, readonly: bool = False) -> str:
    spec = f"{path.resolve()}:{target}"
    return spec + (":ro" if readonly else "")


class Runner:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.corpus = Path(args.corpus).expanduser().resolve()
        self.results = Path(args.results).expanduser().resolve()
        self.base = self.results / "cache" / "fizzy-base"
        self.image = args.image
        self.runtime_image = args.runtime_image
        self.codex_entry = Path(args.codex_entry or shutil.which("codex") or "").resolve()
        self.node_entry = Path(args.node_entry or shutil.which("node") or "").resolve()
        self.codex_home = Path(args.codex_home or os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().resolve()
        self.auth_home: Path | None = None
        self.metadata: dict[str, Any] = {}

    def validate(self) -> list[dict[str, Any]]:
        for label, path in (("corpus", self.corpus), ("results", self.results)):
            try:
                path.relative_to(ROOT)
            except ValueError:
                pass
            else:
                raise BenchmarkError(f"Keep benchmark {label} outside the repository to protect the upstream canary and raw trial data: {path}")
        if not (self.corpus / "bench.yml").is_file():
            raise BenchmarkError(f"No bench.yml in corpus directory: {self.corpus}")
        expected = self.args.corpus_revision
        current = run_command(["git", "-C", str(self.corpus), "rev-parse", "HEAD"], check=False).stdout.strip()
        if expected and current != expected:
            raise BenchmarkError(f"Corpus revision mismatch: expected {expected}, found {current}")
        tasks_root = self.corpus / "tasks"
        tasks = [parse_task(tasks_root / task_id) for task_id in self.args.tasks]
        return tasks

    def prepare(self) -> None:
        self.results.mkdir(parents=True, exist_ok=True)
        self.base.parent.mkdir(parents=True, exist_ok=True)
        if not self.base.exists():
            build_file = self.corpus / "docker/fizzy/Dockerfile"
            if not build_file.is_file():
                raise BenchmarkError(f"Cannot find the upstream Fizzy Dockerfile at {build_file}")
            if run_command(["docker", "image", "inspect", self.image], check=False).returncode:
                print(f"Building pinned upstream image {self.image}…", flush=True)
                run_command(
                    ["docker", "build", "-t", self.image, "-f", str(build_file), str(build_file.parent)],
                    check=True,
                )
            self.extract_base()
        runtime_exists = run_command(["docker", "image", "inspect", self.runtime_image], check=False).returncode == 0
        if self.args.build_runtime or not runtime_exists:
            runtime_file = ROOT / "benchmark/rails/Dockerfile"
            print(f"Building isolated Codex runtime {self.runtime_image}…", flush=True)
            run_command(
                [
                    "docker", "build", "-t", self.runtime_image,
                    "--build-arg", f"BASE_IMAGE={self.image}",
                    "-f", str(runtime_file), str(runtime_file.parent),
                ],
                check=True,
            )
        self.check_cli_files()
        self.metadata = {
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "corpus_revision": run_command(["git", "-C", str(self.corpus), "rev-parse", "HEAD"]).stdout.strip(),
            "model": self.args.model,
            "reasoning_effort": self.args.reasoning_effort,
            "skill_source_sha256": hash_tree(SKILL_SOURCE),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "repository_head": run_command(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=False).stdout.strip(),
            "upstream_image": self.image,
            "upstream_image_id": run_command(["docker", "image", "inspect", self.image, "--format", "{{.Id}}"], check=False).stdout.strip(),
            "runtime_image": self.runtime_image,
            "runtime_image_id": run_command(["docker", "image", "inspect", self.runtime_image, "--format", "{{.Id}}"], check=False).stdout.strip(),
            "comment_policy": COMMENT_POLICY,
            "condition_order_seed": self.args.order_seed,
            "conditions": self.args.conditions,
            "tasks": self.args.tasks,
        }
        write_json(self.results / "run-metadata.json", self.metadata)

    def extract_base(self) -> None:
        temp_name = f"harness-fizzy-base-{uuid.uuid4().hex[:8]}"
        container_id = run_command(["docker", "create", "--name", temp_name, self.image, "sleep", "infinity"]).stdout.strip()
        try:
            run_command(["docker", "cp", f"{container_id}:/app", str(self.base.parent)])
            copied = self.base.parent / "app"
            copied.rename(self.base)
            ensure_writable_tree(self.base)
            if not (self.base / ".git").exists():
                raise BenchmarkError("The upstream app snapshot did not contain its expected Git baseline")
        finally:
            run_command(["docker", "rm", "-f", container_id], check=False)

    def check_cli_files(self) -> None:
        if not self.codex_entry.is_file() or not self.node_entry.is_file():
            raise BenchmarkError("Codex CLI and Node.js are required. Pass --codex-entry/--node-entry if needed.")
        if not (self.codex_home / "auth.json").is_file():
            raise BenchmarkError(f"Codex CLI is not logged in: no auth.json under {self.codex_home}")
        if self.auth_home is None:
            self.auth_home = Path(tempfile.mkdtemp(prefix="rails-bench-codex-auth-"))
            shutil.copy2(self.codex_home / "auth.json", self.auth_home / "auth.json")
            (self.auth_home / "auth.json").chmod(0o600)

    def create_container(self, workspace: Path, container_name: str) -> None:
        self.check_cli_files()
        result = run_command(
            [
                "docker", "run", "-d", "--name", container_name,
                "-v", add_docker_mount(workspace, "/workspace"),
                "-v", add_docker_mount(self.codex_entry.parent.parent, "/opt/codex", readonly=True),
                "-v", add_docker_mount(self.node_entry, "/opt/node", readonly=True),
                "-v", add_docker_mount(self.auth_home or self.codex_home, "/codex-home"),
                "-e", "CODEX_HOME=/codex-home",
                "-e", "SAAS=false",
                "-e", "DATABASE_ADAPTER=sqlite",
                "-w", "/workspace",
                self.runtime_image,
                "sleep", "infinity",
            ]
        )
        if not result.stdout.strip():
            raise BenchmarkError(f"Could not start container {container_name}")

    def docker_exec(self, container: str, command: list[str], *, input_bytes: bytes | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[bytes]:
        try:
            return subprocess.run(
                ["docker", "exec", "-w", "/workspace", "-i", container, *command],
                input=input_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise BenchmarkError(f"Container command timed out: {' '.join(command)}") from exc

    def invoke_agent(self, container: str, prompt: str, run_dir: Path) -> dict[str, Any]:
        event_path = run_dir / "events.jsonl"
        error_path = run_dir / "codex.stderr"
        command = [
            "/opt/node", "/opt/codex/bin/codex.js", "exec", "--json", "--ephemeral",
            "--ignore-user-config", "--sandbox", "danger-full-access", "-m", self.args.model,
            "-c", f"model_reasoning_effort=\"{self.args.reasoning_effort}\"",
            "-C", "/workspace", "-",
        ]
        start = time.monotonic()
        try:
            result = self.docker_exec(
                container,
                command,
                input_bytes=prompt.encode(),
                timeout=self.args.timeout_minutes * 60,
            )
            output = result.stdout
            error_path.write_bytes(result.stderr)
            event_path.write_bytes(output)
            exit_code = result.returncode
            timed_out = False
        except BenchmarkError as exc:
            error_path.write_text(str(exc))
            event_path.write_text("")
            exit_code = 124
            timed_out = True
        elapsed = time.monotonic() - start
        parsed = parse_jsonl(event_path)
        parsed.update({"cli_exit_code": exit_code, "timed_out": timed_out, "agent_seconds": elapsed})
        if parsed.get("final_message"):
            (run_dir / "agent-final.md").write_text(parsed["final_message"])
        return parsed

    def apply_seed(self, workspace: Path, task: dict[str, Any]) -> None:
        result = run_command(
            ["git", "apply", str(task["environment_patch"])],
            cwd=workspace,
            check=False,
        )
        if result.returncode:
            raise BenchmarkError(f"Could not apply seed patch for {task['id']}: {result.stderr.strip()}")

    def execute_task(
        self,
        *,
        condition: str,
        task: dict[str, Any],
        index: int,
        workspace: Path,
        container: str,
        run_dir: Path,
    ) -> dict[str, Any]:
        run_dir.mkdir(parents=True, exist_ok=True)
        task_start = time.monotonic()
        self.apply_seed(workspace, task)
        seed_diff = run_command(["git", "diff", "HEAD", "--binary"], cwd=workspace, check=False).stdout or ""
        (run_dir / "seed.patch").write_text(seed_diff)
        run_command(
            ["git", "add", "-A"],
            cwd=workspace,
            check=False,
        )
        run_command(
            ["git", "-c", "user.name=benchmark", "-c", "user.email=benchmark@localhost", "commit", "-qm", f"seed {task['id']}"],
            cwd=workspace,
            check=False,
        )
        restore_snapshot = run_dir / "restore"
        if (workspace / "bin").exists():
            shutil.copytree(workspace / "bin", restore_snapshot / "bin")

        if condition in {"baseline", "skill-cold"}:
            shutil.rmtree(workspace / ".design", ignore_errors=True)
        if condition.startswith("skill-"):
            target = workspace / ".agents/skills/design-thinking"
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(SKILL_SOURCE, target)
        fixed_guidance = workspace / "AGENTS.md"
        fixed_guidance.write_text(FIXED_GUIDANCE)

        for command in task["setup_commands"]:
            setup = self.docker_exec(container, ["bash", "-lc", command], timeout=15 * 60)
            (run_dir / "setup.log").write_bytes(setup.stdout + setup.stderr)
            if setup.returncode:
                return self.failed_trial(condition, task, index, run_dir, task_start, "setup_failed", setup.returncode)

        before_history = design_state_stats(workspace)
        prompt = self.make_task_prompt(condition, task, container)
        result = self.invoke_agent(container, prompt, run_dir)
        agent_patch = run_command(["git", "diff", "--binary"], cwd=workspace, check=False).stdout or ""
        (run_dir / "agent.patch").write_text(agent_patch)
        added_comments = changed_comment_lines(workspace)

        # Stage-2 Fizzy tasks restore bin/ before grading. Restore precisely the
        # snapshot taken after the seed and before the agent began.
        shutil.rmtree(workspace / "bin", ignore_errors=True)
        if (restore_snapshot / "bin").exists():
            shutil.copytree(restore_snapshot / "bin", workspace / "bin")

        suite_start = time.monotonic()
        suite = self.docker_exec(container, ["bin/rails", "test"], timeout=20 * 60)
        suite_seconds = time.monotonic() - suite_start
        (run_dir / "test-suite.log").write_bytes(suite.stdout + suite.stderr)
        hidden = task["verification_test"].read_bytes()
        hidden_copy = self.docker_exec(container, ["bash", "-lc", "cat > /tmp/verification_test.rb"], input_bytes=hidden)
        if hidden_copy.returncode:
            hidden_result = hidden_copy
        elif suite.returncode:
            hidden_result = None
        else:
            hidden_result = self.docker_exec(
                container,
                ["ruby", "-Itest", "/tmp/verification_test.rb"],
                timeout=20 * 60,
            )
        if hidden_result is not None:
            (run_dir / "hidden-verifier.log").write_bytes(hidden_result.stdout + hidden_result.stderr)
        hidden_verifier_stats = parse_test_summary(run_dir / "hidden-verifier.log")
        self.docker_exec(container, ["rm", "-f", "/tmp/verification_test.rb"], timeout=30)

        passed = suite.returncode == 0 and hidden_result is not None and hidden_result.returncode == 0
        interrupted = result["timed_out"] or result["cli_exit_code"] != 0
        state = design_state_stats(workspace)
        condition_label = condition
        record = {
            "condition": condition_label,
            "repeat": int(run_dir.parent.name.removeprefix("repeat-")),
            "task_id": task["id"],
            "task_index": index,
            "status": "passed" if passed else "interrupted" if interrupted else "failed",
            "success": passed,
            "agent_exit_code": result["cli_exit_code"],
            "agent_timeout": result["timed_out"],
            "test_suite_exit_code": suite.returncode,
            "hidden_verifier_exit_code": hidden_result.returncode if hidden_result is not None else None,
            "hidden_verifier_stats": hidden_verifier_stats,
            "verification_seconds": suite_seconds,
            "elapsed_seconds": time.monotonic() - task_start,
            "model": self.args.model,
            "reasoning_effort": self.args.reasoning_effort,
            "usage": result["usage"],
            "tool_calls": result["tool_calls"],
            "tool_calls_by_purpose": result.get("tool_calls_by_purpose", {}),
            "tool_failures": result["tool_failures"],
            "tool_output_bytes": result.get("tool_output_bytes", 0),
            "tool_duration_total_seconds": result.get("tool_duration_total_seconds", 0),
            "tool_durations_seconds": result.get("tool_durations_seconds", []),
            "read_resources": result.get("read_resources", []),
            "estimated_documentation_read_bytes": estimated_documentation_read_bytes(workspace, result.get("read_resources", [])),
            "skill_usage": {
                "skill_available": condition.startswith("skill-"),
                "activation_requested": condition.startswith("skill-"),
                "skill_related_event_count": result.get("skill_related_event_count", 0),
                "design_cli_invocations": result.get("design_cli_invocations", 0),
                "design_state_before": before_history,
                "design_state_after": state,
            },
            "code_comment_additions": added_comments,
            "agent_seconds": result["agent_seconds"],
            "agent_message": result.get("final_message", ""),
            "event_errors": result.get("event_errors", []),
            "task_files_sha256": task["task_files_sha256"],
            "corpus_revision": self.metadata.get("corpus_revision"),
            "skill_source_sha256": self.metadata.get("skill_source_sha256"),
            "condition_order_seed": self.args.order_seed,
        }
        write_json(run_dir / "result.json", record)
        self.append_record(record)

        # The app state continues into the next ticket. Each Codex invocation
        # is fresh; retained context is represented only by .design/ files.
        run_command(["git", "add", "-A"], cwd=workspace, check=False)
        run_command(
            ["git", "-c", "user.name=benchmark", "-c", "user.email=benchmark@localhost", "commit", "-qm", f"{task['id']} trial"],
            cwd=workspace,
            check=False,
        )
        return record

    def run_recall_pair(self, condition_dir: Path, checkpoint: Path, task: dict[str, Any], repeat: int) -> None:
        recall_dir = condition_dir / "recall"
        recall_dir.mkdir(parents=True, exist_ok=True)
        modes = ["with-history", "fresh-history"]
        random.Random(self.args.order_seed + repeat + 1000).shuffle(modes)
        blind_key: dict[str, str] = {}
        prompt = f"""This is a code-recall task. Do not edit files.

Invoke `$design-thinking` and use the available source code and repository context to answer this question:

{task['instruction']}

Explain where the owning rules are enforced, the invariant each protects and its important reason when the code or recorded context supports it, which callers and boundaries would be affected by a change, and where you would change the code and what you would test. Cite concrete file paths, symbols, and tests. If the code does not establish historical intent, say so rather than guessing. Keep the answer concise but evidence-based.
"""
        for blind_id, mode in zip((f"recall-r{repeat:02d}-a", f"recall-r{repeat:02d}-b"), modes, strict=True):
            blind_key[blind_id] = mode
            attempt_dir = recall_dir / blind_id
            workspace = attempt_dir / "workspace"
            if workspace.exists():
                shutil.rmtree(workspace)
            shutil.copytree(checkpoint, workspace)
            ensure_writable_tree(workspace)
            if mode == "fresh-history":
                shutil.rmtree(workspace / ".design", ignore_errors=True)
            target = workspace / ".agents/skills/design-thinking"
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(SKILL_SOURCE, target)
            container = f"harness-recall-{uuid.uuid4().hex[:10]}"
            self.create_container(workspace, container)
            started = time.monotonic()
            try:
                result = self.invoke_agent(container, prompt, attempt_dir)
            finally:
                run_command(["docker", "rm", "-f", container], check=False)
            state = design_state_stats(workspace)
            record = {
                "blind_id": blind_id,
                "checkpoint_task": task["id"],
                "success": result["cli_exit_code"] == 0 and bool(result.get("final_message")),
                "agent_exit_code": result["cli_exit_code"],
                "agent_timeout": result["timed_out"],
                "elapsed_seconds": time.monotonic() - started,
                "agent_seconds": result["agent_seconds"],
                "model": self.args.model,
                "reasoning_effort": self.args.reasoning_effort,
                "usage": result["usage"],
                "tool_calls": result["tool_calls"],
                "tool_calls_by_purpose": result.get("tool_calls_by_purpose", {}),
                "tool_failures": result["tool_failures"],
                "tool_output_bytes": result.get("tool_output_bytes", 0),
                "tool_duration_total_seconds": result.get("tool_duration_total_seconds", 0),
                "read_resources": result.get("read_resources", []),
                "estimated_documentation_read_bytes": estimated_documentation_read_bytes(workspace, result.get("read_resources", [])),
                "skill_related_event_count": result.get("skill_related_event_count", 0),
                "design_cli_invocations": result.get("design_cli_invocations", 0),
                "design_state_after": state,
                "answer_file": f"{condition_dir.relative_to(self.results).as_posix()}/recall/{blind_id}/agent-final.md",
            }
            with (self.results / "recall.jsonl").open("a") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            if not self.args.keep_workspaces:
                shutil.rmtree(workspace, ignore_errors=True)
        private_key = self.results / "private" / f"recall-key-repeat-{repeat:02d}.json"
        write_json(private_key, blind_key)
        write_recall_score_sheet(self.results, task["id"], repeat)

    def failed_trial(
        self,
        condition: str,
        task: dict[str, Any],
        index: int,
        run_dir: Path,
        task_start: float,
        status: str,
        exit_code: int | None,
    ) -> dict[str, Any]:
        record = {
            "condition": condition,
            "repeat": int(run_dir.parent.name.removeprefix("repeat-")),
            "task_id": task["id"],
            "task_index": index,
            "status": status,
            "success": False,
            "agent_exit_code": None,
            "test_suite_exit_code": None,
            "hidden_verifier_exit_code": None,
            "elapsed_seconds": time.monotonic() - task_start,
            "error_exit_code": exit_code,
            "model": self.args.model,
            "reasoning_effort": self.args.reasoning_effort,
            "usage": {"input_tokens": None, "output_tokens": None, "total_tokens": None},
            "tool_calls": {},
            "tool_calls_by_purpose": {},
            "tool_failures": 0,
            "skill_usage": {"skill_available": condition.startswith("skill-"), "activation_requested": condition.startswith("skill-")},
        }
        write_json(run_dir / "result.json", record)
        self.append_record(record)
        return record

    def make_task_prompt(self, condition: str, task: dict[str, Any], container: str) -> str:
        skill_instruction = (
            "At the start of this task, invoke the `$design-thinking` skill and follow its workflow. "
            "Its installed instructions are in `.agents/skills/design-thinking/SKILL.md`.\n\n"
            if condition.startswith("skill-")
            else "No design-thinking skill or design history is available in this condition.\n\n"
        )
        return f"""You are making a change in the Fizzy Rails application in the current workspace.

{skill_instruction}Task:
{task['instruction']}

{COMMENT_POLICY}

Use the project as your working directory. Run Rails commands directly in this isolated container (for example `bin/rails test`). Do not access benchmark task files or hidden verifier files. Make the requested change, verify it, and report the result concisely. You have up to {self.args.timeout_minutes} minutes.
"""

    def append_record(self, record: dict[str, Any]) -> None:
        path = self.results / "trials.jsonl"
        with path.open("a") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    def run(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if (self.results / "trials.jsonl").exists() or (self.results / "recall.jsonl").exists():
            raise BenchmarkError(f"Results already exist in {self.results}; use a fresh --results directory for a new run.")
        self.prepare()
        if self.args.prepare_only:
            print(json.dumps({"prepared": True, "metadata": self.metadata, "base_snapshot": str(self.base)}, indent=2))
            if self.auth_home:
                shutil.rmtree(self.auth_home, ignore_errors=True)
            return []
        order_seed = self.args.order_seed
        all_records: list[dict[str, Any]] = []
        conditions = list(self.args.conditions)
        for repeat in range(1, self.args.repeats + 1):
            order = conditions[:]
            random.Random(order_seed + repeat).shuffle(order)
            execution_order = self.metadata.setdefault("condition_execution_order", {})
            execution_order[str(repeat)] = order
            write_json(self.results / "run-metadata.json", self.metadata)
            for condition in order:
                safe_condition = condition.replace("/", "-")
                run_id = f"{safe_condition}/repeat-{repeat:02d}"
                run_dir = self.results / "runs" / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                workspace = run_dir / "workspace"
                if workspace.exists():
                    shutil.rmtree(workspace)
                shutil.copytree(self.base, workspace)
                ensure_writable_tree(workspace)
                container = f"harness-rails-{uuid.uuid4().hex[:10]}"
                self.create_container(workspace, container)
                records = []
                try:
                    for index, task in enumerate(tasks, 1):
                        task_dir = run_dir / f"{index:02d}-{task['id']}"
                        print(f"[{condition} repeat {repeat}] {task['id']}", flush=True)
                        task_start = time.monotonic()
                        try:
                            record = self.execute_task(
                                condition=condition,
                                task=task,
                                index=index,
                                workspace=workspace,
                                container=container,
                                run_dir=task_dir,
                            )
                        except BenchmarkError as exc:
                            record = self.failed_trial(condition, task, index, task_dir, task_start, "setup_failed", None)
                            record["error"] = str(exc)
                            write_json(task_dir / "result.json", record)
                            if self.args.verbose:
                                print(str(exc), file=sys.stderr)
                        records.append(record)
                        all_records.append(record)
                        if not record.get("success") and not self.args.continue_after_failure:
                            break
                    if (
                        condition == "skill-warm"
                        and records
                        and records[-1].get("agent_exit_code") == 0
                        and not records[-1].get("agent_timeout")
                    ):
                        self.run_recall_pair(run_dir, workspace, tasks[min(len(records), len(tasks)) - 1], repeat)
                    if self.args.keep_workspaces:
                        (run_dir / "workspace-kept.txt").write_text("Workspace retained for audit.\n")
                    else:
                        shutil.rmtree(workspace, ignore_errors=True)
                finally:
                    run_command(["docker", "rm", "-f", container], check=False)
        if self.auth_home:
            shutil.rmtree(self.auth_home, ignore_errors=True)
        self.summarize()
        return all_records

    def refresh_saved_results(self) -> dict[str, Any]:
        """Rebuild derived trial records and summaries from saved Codex events."""
        trials_path = self.results / "trials.jsonl"
        if not trials_path.is_file():
            raise BenchmarkError(f"No saved trials to refresh in {self.results}")
        records: list[dict[str, Any]] = []
        for line in trials_path.read_text().splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            repeat = int(record.get("repeat", 1))
            task_dir = (
                self.results
                / "runs"
                / str(record.get("condition", "unknown"))
                / f"repeat-{repeat:02d}"
                / f"{int(record.get('task_index', 0)):02d}-{record.get('task_id', 'unknown')}"
            )
            event_path = task_dir / "events.jsonl"
            if event_path.is_file():
                parsed = parse_jsonl(event_path)
                record["usage"] = parsed["usage"]
                record["tool_calls"] = parsed["tool_calls"]
                record["tool_calls_by_purpose"] = parsed.get("tool_calls_by_purpose", {})
                record["tool_failures"] = parsed["tool_failures"]
                record["tool_output_bytes"] = parsed.get("tool_output_bytes", 0)
                record["tool_durations_seconds"] = parsed.get("tool_durations_seconds", [])
                record["tool_duration_total_seconds"] = parsed.get("tool_duration_total_seconds", 0)
                record["read_resources"] = parsed.get("read_resources", [])
                record["event_errors"] = parsed.get("event_errors", [])
                record["hidden_verifier_stats"] = parse_test_summary(task_dir / "hidden-verifier.log")
                if record.get("agent_timeout") or record.get("agent_exit_code") not in {0, None}:
                    record["status"] = "interrupted"
                    record["success"] = False
                result_path = task_dir / "result.json"
                write_json(result_path, record)
            records.append(record)
        with trials_path.open("w") as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        return self.summarize()

    def summarize(self) -> dict[str, Any]:
        records = []
        jsonl = self.results / "trials.jsonl"
        if jsonl.exists():
            for line in jsonl.read_text().splitlines():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        summary: dict[str, Any] = {"created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "trials": len(records), "conditions": {}}
        for condition in sorted({str(item.get("condition", "unknown")) for item in records}):
            selected = [item for item in records if item.get("condition") == condition]
            completed = [item for item in selected if item.get("status") not in {"setup_failed", "interrupted"}]
            successes = [item for item in selected if item.get("success")]
            accuracy_records = [item for item in completed if isinstance(item.get("hidden_verifier_stats"), dict)]
            verifier_runs = [item["hidden_verifier_stats"] for item in accuracy_records]
            passed_cases = sum(int(item["passed_cases"]) for item in verifier_runs)
            evaluable_cases = sum(int(item["evaluable_cases"]) for item in verifier_runs)
            passed_assertions = sum(int(item["passed_assertions"]) for item in verifier_runs)
            assertion_count = sum(int(item["assertions"]) for item in verifier_runs)
            assertion_accuracy_available = all(int(item["errors"]) == 0 for item in verifier_runs)
            success_times = [float(item["elapsed_seconds"]) for item in successes if item.get("elapsed_seconds") is not None]
            all_times = [float(item["elapsed_seconds"]) for item in selected if item.get("elapsed_seconds") is not None]
            token_values = [item.get("usage", {}).get("total_tokens") for item in selected]
            token_values = [int(value) for value in token_values if isinstance(value, int)]
            input_values = [item.get("usage", {}).get("input_tokens") for item in selected]
            input_values = [int(value) for value in input_values if isinstance(value, int)]
            output_values = [item.get("usage", {}).get("output_tokens") for item in selected]
            output_values = [int(value) for value in output_values if isinstance(value, int)]
            cached_values = [item.get("usage", {}).get("cached_input_tokens") for item in selected]
            cached_values = [int(value) for value in cached_values if isinstance(value, int)]
            summary["conditions"][condition] = {
                "attempts": len(selected),
                "completed_attempts": len(completed),
                "interrupted_attempts": len(selected) - len(completed),
                "completion_rate": len(completed) / len(selected) if selected else None,
                "successes": len(successes),
                "success_rate": len(successes) / len(completed) if completed else None,
                "mean_seconds_to_verified_success": statistics.mean(success_times) if success_times else None,
                "median_seconds_to_verified_success": statistics.median(success_times) if success_times else None,
                "p90_seconds_to_verified_success": percentile(success_times, 0.90) if success_times else None,
                "mean_seconds_all_attempts": statistics.mean(all_times) if all_times else None,
                "all_attempt_seconds_per_success": (sum(all_times) / len(successes)) if successes else None,
                "input_tokens": sum(input_values) if len(input_values) == len(selected) else None,
                "output_tokens": sum(output_values) if len(output_values) == len(selected) else None,
                "cached_input_tokens": sum(cached_values) if len(cached_values) == len(selected) else None,
                "total_tokens": sum(token_values) if len(token_values) == len(selected) else None,
                "observed_total_tokens": sum(token_values),
                "token_records": len(token_values),
                "tokens_per_success": (sum(token_values) / len(successes)) if successes and len(token_values) == len(selected) else None,
                "accuracy": {
                    "trials_with_verifier_summary": len(accuracy_records),
                    "passed_test_cases": passed_cases,
                    "evaluable_test_cases": evaluable_cases,
                    "test_case_accuracy": passed_cases / evaluable_cases if evaluable_cases else None,
                    "passed_assertions": passed_assertions,
                    "assertions": assertion_count,
                    "assertion_accuracy": passed_assertions / assertion_count if assertion_count and assertion_accuracy_available else None,
                },
                "tool_failures": sum(int(item.get("tool_failures", 0)) for item in selected),
                "tool_calls": sum(sum(item.get("tool_calls", {}).values()) for item in selected),
                "comment_lines_added": sum(int(item.get("code_comment_additions", 0)) for item in selected),
                "design_state_bytes": sum(int(item.get("skill_usage", {}).get("design_state_after", {}).get("bytes", 0)) for item in selected),
                "estimated_documentation_read_bytes": sum(int(item.get("estimated_documentation_read_bytes", 0)) for item in selected),
            }
        recall_records = []
        recall_path = self.results / "recall.jsonl"
        if recall_path.exists():
            for line in recall_path.read_text().splitlines():
                try:
                    recall_records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        summary["recall"] = {
            "paired_answers": len(recall_records),
            "by_blind_id": {
                blind_id: {
                    "elapsed_seconds": [item.get("elapsed_seconds") for item in recall_records if item.get("blind_id") == blind_id],
                    "total_tokens": [item.get("usage", {}).get("total_tokens") for item in recall_records if item.get("blind_id") == blind_id],
                    "tool_calls": [sum(item.get("tool_calls", {}).values()) for item in recall_records if item.get("blind_id") == blind_id],
                    "tool_failures": [item.get("tool_failures") for item in recall_records if item.get("blind_id") == blind_id],
                }
                for blind_id in sorted({str(item.get("blind_id")) for item in recall_records})
            },
        }
        write_json(self.results / "summary.json", summary)
        return summary


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile of empty sequence")
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * p)))
    return ordered[index]


def write_recall_score_sheet(results_dir: Path, task_id: str, repeat: int) -> Path:
    sheet = results_dir / "recall-score-sheet.csv"
    new_file = not sheet.exists()
    with sheet.open("a", newline="") as stream:
        writer = csv.writer(stream)
        if new_file:
            writer.writerow(["blind_id", "checkpoint_task", "owning_rule_0_2", "invariant_and_reason_0_2", "callers_and_boundaries_0_2", "change_location_and_verification_0_2", "unsupported_claims", "reviewer_notes"])
        writer.writerow([f"recall-r{repeat:02d}-a", task_id, "", "", "", "", "", ""])
        writer.writerow([f"recall-r{repeat:02d}-b", task_id, "", "", "", "", "", ""])
    return sheet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, help="Local checkout of rails/ai-evals (keep outside the agent workspace).")
    parser.add_argument("--corpus-revision", default="168d25fae0b9a1df857e9db90440998011fbb350", help="Required pinned corpus commit (empty disables the check).")
    parser.add_argument("--results", default="/tmp/harness-rails-benchmark", help="Directory for raw logs and trial workspaces.")
    parser.add_argument("--tasks", required=True, help="Comma-separated task IDs, in sequence order.")
    parser.add_argument("--conditions", default=",".join(DEFAULT_CONDITIONS), help="Comma-separated baseline,skill-cold,skill-warm conditions.")
    parser.add_argument("--repeats", type=int, default=1, help="Independent repetitions per condition.")
    parser.add_argument("--order-seed", type=int, default=92713)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", choices=("low", "medium", "high", "xhigh", "max"), default="max")
    parser.add_argument("--timeout-minutes", type=int, default=90)
    parser.add_argument("--image", default="harness-fizzy:rails-ai-evals-168d25f")
    parser.add_argument("--runtime-image", default="harness-fizzy-codex:rails-ai-evals-168d25f")
    parser.add_argument("--codex-entry", default=None)
    parser.add_argument("--node-entry", default=None)
    parser.add_argument("--codex-home", default=None)
    parser.add_argument("--build-runtime", action="store_true", help="Rebuild the derived runtime image with Python 3 for design.py.")
    parser.add_argument("--keep-workspaces", action="store_true")
    parser.add_argument("--continue-after-failure", action="store_true", help="Continue a sequence after a task fails; default stops so later tickets do not inherit broken code.")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--plan", action="store_true", help="Validate task files and print the planned run matrix without Docker or model calls.")
    parser.add_argument("--prepare-only", action="store_true", help="Build/extract app images and validate the container runtime without a model call.")
    parser.add_argument("--refresh-existing", action="store_true", help="Reparse saved event logs and rebuild summaries without model calls.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.tasks = [item.strip() for item in args.tasks.split(",") if item.strip()]
    args.conditions = [item.strip() for item in args.conditions.split(",") if item.strip()]
    valid = set(DEFAULT_CONDITIONS)
    if not args.conditions or set(args.conditions) - valid:
        parser.error(f"--conditions must be drawn from {', '.join(sorted(valid))}")
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.timeout_minutes < 1:
        parser.error("--timeout-minutes must be at least 1")
    try:
        runner = Runner(args)
        if args.refresh_existing:
            print(json.dumps(runner.refresh_saved_results(), indent=2))
            return 0
        tasks = runner.validate()
        if args.plan:
            matrix = [{"repeat": repeat, "condition": condition, "tasks": [task["id"] for task in tasks]} for repeat in range(1, args.repeats + 1) for condition in args.conditions]
            print(json.dumps({"model": args.model, "reasoning_effort": args.reasoning_effort, "corpus_revision": args.corpus_revision, "planned_trials": len(matrix) * len(tasks), "matrix": matrix}, indent=2))
            return 0
        runner.run(tasks)
        print(json.dumps(runner.summarize(), indent=2))
        return 0
    except BenchmarkError as exc:
        print(f"benchmark error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
