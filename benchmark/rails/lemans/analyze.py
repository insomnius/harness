#!/usr/bin/env python3
"""Summarize accuracy and usage metrics from Lemans result directories."""

from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def trajectory_for(result_path: Path) -> dict[str, Any] | None:
    candidates = sorted(result_path.parent.glob("**/*trajectory.json"))
    for candidate in candidates:
        trajectory = load_json(candidate)
        if trajectory and isinstance(trajectory.get("steps"), list):
            return trajectory
    return None


def collect_tool_usage(trajectory: dict[str, Any] | None) -> tuple[dict[str, int] | None, int | None, int | None, int | None]:
    if trajectory is None:
        return None, None, None, None

    tools: collections.Counter[str] = collections.Counter()
    skill_references = 0
    design_cli_calls = 0
    for step in trajectory["steps"]:
        if not isinstance(step, dict):
            continue
        calls = step.get("tool_calls", [])
        if not isinstance(calls, list):
            continue
        for call in calls:
            if not isinstance(call, dict):
                continue
            name = str(call.get("function_name") or "unknown")
            tools[name] += 1
            arguments = json.dumps(call.get("arguments", ""), ensure_ascii=False).lower()
            if ".agents/skills/design-thinking" in arguments:
                skill_references += 1
            if "design.py" in arguments or "design_cli.py" in arguments:
                design_cli_calls += 1

    return dict(sorted(tools.items())), sum(tools.values()), skill_references, design_cli_calls


def verifier_accuracy(result_path: Path) -> tuple[int | None, int | None]:
    checks_path = result_path.parent / "checks.json"
    checks_data = load_json(checks_path)
    checks = checks_data.get("checks") if checks_data else None
    if not isinstance(checks, dict):
        return None, None

    statuses = [str(status).lower() for status in checks.values()]
    scored = [status for status in statuses if status in {"pass", "fail"}]
    if not scored:
        return None, None
    return sum(status == "pass" for status in scored), len(scored)


def trial_record(path: Path, result: dict[str, Any]) -> dict[str, Any]:
    metadata = result.get("metadata") or {}
    metadata = metadata if isinstance(metadata, dict) else {}
    usage = result.get("usage") or {}
    usage = usage if isinstance(usage, dict) else {}
    outcome = result.get("outcome") or {}
    outcome = outcome if isinstance(outcome, dict) else {}
    phases = result.get("phases") or []
    phases = phases if isinstance(phases, list) else []
    agent_seconds = None
    for phase in phases:
        if not isinstance(phase, dict) or phase.get("name") != "agent":
            continue
        started = phase.get("started_at")
        finished = phase.get("finished_at")
        if started and finished:
            try:
                agent_seconds = round(
                    (datetime.fromisoformat(finished.replace("Z", "+00:00"))
                     - datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds(),
                    3,
                )
            except ValueError:
                pass
        break
    passed_cases, evaluable_cases = verifier_accuracy(path)
    tool_counts, tool_calls, skill_references, design_cli_calls = collect_tool_usage(trajectory_for(path))
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = input_tokens + output_tokens if isinstance(input_tokens, int) and isinstance(output_tokens, int) else None
    reward = result.get("reward")

    return {
        "trial": result.get("trial", path.parent.name),
        "task": result.get("task"),
        "source_task": metadata.get("source_task"),
        "condition": metadata.get("condition", "unknown"),
        "model": result.get("model"),
        "agent": result.get("agent"),
        "outcome": outcome.get("name"),
        "scored": outcome.get("scored"),
        "reward": reward,
        "success": reward >= 1.0 if isinstance(reward, (float, int)) else None,
        "passed_cases": passed_cases,
        "evaluable_cases": evaluable_cases,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": usage.get("cached_tokens"),
        "model_steps": usage.get("steps"),
        "cost_usd": usage.get("cost_usd"),
        "elapsed_seconds": result.get("duration"),
        "agent_seconds": agent_seconds,
        "tool_calls": tool_calls,
        "tool_counts": tool_counts,
        "skill_path_references": skill_references,
        "design_cli_calls": design_cli_calls,
    }


def mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 3) if values else None


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


def p90(values: list[float]) -> float | None:
    return round(sorted(values)[math.ceil(len(values) * 0.9) - 1], 3) if values else None


def summarize_attempts(trials: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [trial for trial in trials if trial["scored"] is True]
    cases = [trial for trial in trials if isinstance(trial["passed_cases"], int)]
    tool_records = [trial for trial in trials if isinstance(trial["tool_calls"], int)]
    tool_totals: collections.Counter[str] = collections.Counter()
    for trial in tool_records:
        tool_totals.update(trial["tool_counts"] or {})
    input_values = [trial["input_tokens"] for trial in trials if isinstance(trial["input_tokens"], (int, float))]
    output_values = [trial["output_tokens"] for trial in trials if isinstance(trial["output_tokens"], (int, float))]
    token_values = [trial["total_tokens"] for trial in trials if isinstance(trial["total_tokens"], (int, float))]
    duration_values = [trial["elapsed_seconds"] for trial in trials if isinstance(trial["elapsed_seconds"], (int, float))]
    successful_durations = [
        trial["elapsed_seconds"] for trial in trials
        if trial["success"] is True and isinstance(trial["elapsed_seconds"], (int, float))
    ]
    agent_values = [trial["agent_seconds"] for trial in trials if isinstance(trial["agent_seconds"], (int, float))]
    total_cases = sum(trial["evaluable_cases"] for trial in cases if isinstance(trial["evaluable_cases"], int))
    passed_cases = sum(trial["passed_cases"] for trial in cases if isinstance(trial["passed_cases"], int))
    has_trajectory = bool(tool_records)
    return {
        "attempts": len(trials),
        "scored_attempts": len(scored),
        "invalid_attempts": len(trials) - len(scored),
        "successes": sum(trial["success"] is True for trial in scored),
        "task_accuracy": mean([float(trial["success"]) for trial in scored if trial["success"] is not None]),
        "passed_hidden_cases": passed_cases if cases else None,
        "evaluable_hidden_cases": total_cases if cases else None,
        "hidden_case_accuracy": round(passed_cases / total_cases, 4) if total_cases else None,
        "mean_input_tokens": mean(input_values),
        "mean_output_tokens": mean(output_values),
        "mean_total_tokens": mean(token_values),
        "median_total_tokens": median(token_values),
        "mean_elapsed_seconds": mean(duration_values),
        "median_elapsed_seconds": median(duration_values),
        "mean_success_elapsed_seconds": mean(successful_durations),
        "median_success_elapsed_seconds": median(successful_durations),
        "p90_success_elapsed_seconds": p90(successful_durations),
        "mean_agent_seconds": mean(agent_values),
        "mean_tool_calls": mean([trial["tool_calls"] for trial in tool_records]),
        "tool_call_trials": len(tool_records),
        "skill_path_reference_calls": sum(trial["skill_path_references"] or 0 for trial in trials) if has_trajectory else None,
        "design_cli_calls": sum(trial["design_cli_calls"] or 0 for trial in trials) if has_trajectory else None,
        "tool_counts": dict(sorted(tool_totals.items())),
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for record in records:
        groups[str(record["condition"])].append(record)

    summary = []
    for condition in sorted(groups):
        trials = groups[condition]
        by_task: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for trial in trials:
            by_task[str(trial["source_task"] or trial["task"])].append(trial)
        summary.append({
            "condition": condition,
            **summarize_attempts(trials),
            "by_task": [
                {"source_task": task, **summarize_attempts(task_trials)}
                for task, task_trials in sorted(by_task.items())
            ],
        })
    return {"trials": len(records), "conditions": summary, "runs": records}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", required=True, type=Path, help="Lemans --runs-dir containing result.json files")
    parser.add_argument("--agent", default="miniswen", help="Only include this Lemans agent (default: miniswen)")
    parser.add_argument("--output-dir", type=Path, help="Optional directory for summary.json and trials.csv")
    args = parser.parse_args()

    records = []
    for result_path in sorted(args.runs_dir.expanduser().glob("**/result.json")):
        result = load_json(result_path)
        if result and (args.agent is None or result.get("agent") == args.agent):
            records.append(trial_record(result_path, result))
    if not records:
        parser.error(f"No readable result.json files for agent {args.agent!r} found under {args.runs_dir}")

    report = summarize(records)
    serialized = json.dumps(report, indent=2) + "\n"
    if args.output_dir:
        output = args.output_dir.expanduser()
        output.mkdir(parents=True, exist_ok=True)
        (output / "summary.json").write_text(serialized)
        fields = [key for key, value in records[0].items() if key != "tool_counts"] + ["tool_counts"]
        with (output / "trials.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for record in records:
                writer.writerow({**record, "tool_counts": json.dumps(record["tool_counts"], sort_keys=True)})
        print(f"Wrote {output / 'summary.json'} and {output / 'trials.csv'}")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
