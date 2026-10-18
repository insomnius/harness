"""Read the packaged workflow specification without creating project state."""

from pathlib import Path

import design_state as st

SPEC_PATH = Path(__file__).resolve().parent.parent / "graph.json"


def spec():
    return st.read_json(SPEC_PATH)


def phase_definition(name):
    phase = next((p for p in spec()["phases"] if p["id"] == name), None)
    if phase is None:
        raise ValueError(f"unknown phase {name!r}; use `design.py status` for guidance")
    return phase


def transitions(current, skipped=(), resume_phase=None, failed_checks=()):
    graph = spec()
    owners = {c["id"]: c["owner_phase"] for p in graph["phases"]
              if p["id"] == "gate" for c in p["checks"]}
    found = []

    def visit(source, seen):
        if source in seen:
            return
        for edge in graph["edges"]:
            if edge["from"] != source:
                continue
            target = edge["to"]
            targets = [target]
            if target == "return":
                targets = [resume_phase] if resume_phase else []
            elif target == "owner_phase":
                targets = sorted({owners[c] for c in (failed_checks or owners) if c in owners})
            for destination in targets:
                if destination in skipped:
                    visit(destination, seen | {source})
                elif not any(x["to"] == destination for x in found):
                    found.append({**edge, "to": destination})

    visit(current, set())
    if current != "revalidate":
        found.extend(e for e in graph["edges"] if e["from"] == "*")
    return found


def gate_problem(behavior, ledger):
    entry = next((g for g in ledger if g.get("behavior_id") == behavior["id"]), None)
    if not behavior.get("contract"):
        return "contract missing; run contract"
    if not entry or not (entry.get("red_evidence") or {}).get("failure"):
        return "red evidence missing; run check --kind behavior --expect red or gate"
    if entry.get("checks_failed"):
        return "failed checks: " + ", ".join(entry["checks_failed"])
    if entry.get("statement") != behavior.get("statement"):
        return "statement changed; observe a fresh red and re-gate"
    if entry.get("contract") != behavior.get("contract"):
        return "contract changed; observe a fresh red and re-gate"
    if entry.get("path") != behavior.get("path") or entry.get("symbol") != behavior.get("symbol"):
        return "behavior moved; observe a fresh red and re-gate"
    return None
