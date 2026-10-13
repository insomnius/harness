"""Locate, load and save .design/ state.

One directory, flat, and everything in it is TEMPORAL - captured at the time,
against a commit, never edited afterwards by a later task:

    <ref>.log.jsonl                 THE SOURCE - every decision, append-only
    <ref>.json                      derived: tier 0-1, folded from the log
    <ref>.<task-slug>.trace.json    derived: tier 2-3, folded from the log
    <ref>.<task-slug>.model.json    derived: the domain as understood for that task
    <ref>.<task-slug>.graph.md      derived: the view of that task
    index.md                        derived: recall across every snapshot

Only the log is written to. Everything else is a fold over it and is rebuilt
on every append, so a decision that was later reversed stays visible - which
is the part a reader actually needs, and the part a mutable document loses the
moment it is overwritten.

There is no shared mutable model, so there is nothing to forget to update and
nothing to go stale. Recall is search over snapshots, and disagreement between
two snapshots is a finding the index reports rather than a write that silently
wins.

Principle: the trace is the memory, context is a cache. Every read goes to
disk, so a cold agent sees exactly what a warm one does.
"""

import json
import os
import time
from pathlib import Path

DESIGN_DIR = ".design"
GRAPH_VERSION = "4.0"


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def find_design_dir(start=None):
    """Walk up from `start` looking for .design/. Returns None if absent."""
    cur = Path(start or os.getcwd()).resolve()
    for d in [cur, *cur.parents]:
        cand = d / DESIGN_DIR
        if cand.is_dir():
            return cand
        if (d / ".git").exists():
            break
    return None


def design_dir_for_write(start=None):
    """Same, but falls back to <repo root>/.design so `init` has a home."""
    found = find_design_dir(start)
    if found:
        return found
    cur = Path(start or os.getcwd()).resolve()
    for d in [cur, *cur.parents]:
        if (d / ".git").exists():
            return d / DESIGN_DIR
    return cur / DESIGN_DIR


def read_json(path):
    with open(path) as fh:
        return json.load(fh)


def write_json(path, obj):
    """Atomic write - a truncated state file is worse than a stale one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    obj["updated_at"] = now()
    obj.setdefault("graph_version", GRAPH_VERSION)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)
    return path


SNAPSHOT_SUFFIXES = (".trace.json", ".model.json")


def ticket_paths(dd):
    """Every <ref>.json - the tier 0-1 files, excluding per-task snapshots."""
    return [p for p in sorted(Path(dd).glob("*.json"))
            if not p.name.endswith(SNAPSHOT_SUFFIXES)]


def trace_paths(dd, ref=None):
    return sorted(Path(dd).glob(f"{ref}.*.trace.json" if ref else "*.trace.json"))


def model_paths(dd, ref=None):
    return sorted(Path(dd).glob(f"{ref}.*.model.json" if ref else "*.model.json"))


def task_key(path):
    """`partial-refunds.refund.trace.json` -> ('partial-refunds', 'refund'). Handles dots in slugs."""
    name = Path(path).name
    for suf in SNAPSHOT_SUFFIXES:
        if name.endswith(suf):
            stem = name[: -len(suf)]
            ref, _, slug = stem.partition(".")
            return ref, slug
    return Path(path).stem, ""


def load_all(dd=None, ref=None):
    """Load model + the active ticket + its traces.

    Active ticket: the one matching `ref`, else the most recently updated
    ticket whose status is not "closed", else the most recent of any status.
    """
    dd = Path(dd) if dd else find_design_dir()
    if dd is None or not dd.is_dir():
        return None, None, None, []

    tickets = []
    for p in ticket_paths(dd):
        try:
            tickets.append((p, read_json(p)))
        except (OSError, json.JSONDecodeError):
            continue

    active = None
    if ref:
        active = next((t for t in tickets if t[0].stem == ref), None)
    if active is None:
        open_ = [t for t in tickets if t[1].get("status") != "closed"]
        pool = open_ or tickets
        if pool:
            active = max(pool, key=lambda t: t[1].get("updated_at") or "")

    traces, models = [], []
    if active:
        ref_ = active[0].stem
        for p in trace_paths(dd, ref_):
            try:
                traces.append((p, read_json(p)))
            except (OSError, json.JSONDecodeError):
                continue
        for p in model_paths(dd, ref_):
            try:
                models.append((p, read_json(p)))
            except (OSError, json.JSONDecodeError):
                continue

    tpath, ticket = active if active else (None, None)
    return dd, models, (tpath, ticket), traces


def load_all_snapshots(dd=None):
    """Every model snapshot in the directory, for building the index."""
    dd = Path(dd) if dd else find_design_dir()
    if dd is None or not dd.is_dir():
        return None, []
    out = []
    for p in model_paths(dd):
        try:
            out.append((p, read_json(p)))
        except (OSError, json.JSONDecodeError):
            continue
    return dd, out


# --- the decision log -------------------------------------------------------

def safe_ref(ref):
    """A ref becomes a filename, so it must be one path component and no dots.

    `..` or a separator would write outside `.design/`; a dot would make
    `<ref>.<slug>.trace.json` ambiguous to `task_key`. Rejecting both at the
    single point where refs enter is cheaper than parsing around them.
    """
    if not ref or Path(ref).name != ref or any(c in ref for c in "/\\*?[]." ):
        raise ValueError(
            f"ref {ref!r} must be a single path-safe filename component "
            "with no dots, slashes or glob characters (e.g. partial-refunds)")
    return ref


def safe_slug(slug):
    """Same, for task slugs - they are the second filename component."""
    if not slug or Path(slug).name != slug or any(c in slug for c in "/\\*?[]."):
        raise ValueError(
            f"task slug {slug!r} must be a single path-safe filename component "
            "with no dots, slashes or glob characters (e.g. refund-handler)")
    return slug


def log_path(dd, ref):
    return Path(dd) / f"{safe_ref(ref)}.log.jsonl"


def append_event(dd, ref, kind, **fields):
    """Append one decision. Never rewrites, never reorders.

    A reversal is a new event that supersedes an earlier one, not an edit to
    it. `why` is the field that makes the log worth reading: the state says
    what was decided, the log says what moved it.
    """
    ev = {"at": now(), "kind": kind}
    ev.update({k: v for k, v in fields.items() if v is not None})
    p = log_path(dd, ref)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as fh:
        fh.write(json.dumps(ev, sort_keys=False) + "\n")
    return ev


def read_log(dd, ref):
    p = log_path(dd, ref)
    if not p.exists():
        return []
    out = []
    for i, line in enumerate(p.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError as exc:
            # Dropping a decision silently would let the fold render a stale
            # conclusion that looks authoritative. Refuse to fold at all.
            raise ValueError(
                f"{p}:{i} is not valid JSON ({exc.msg}). The log is the source of "
                f"truth, so it cannot be folded around a damaged line. Repair or "
                f"remove line {i}, then re-run `design.py rebuild`.") from exc
        if not isinstance(ev, dict):
            raise ValueError(
                f"{p}:{i} is valid JSON but not an event object "
                f"({type(ev).__name__}). Every line must be a JSON object. Repair or "
                f"remove line {i}, then re-run `design.py rebuild`.")
        ev["_n"] = i
        out.append(ev)
    return out


def log_refs(dd):
    return sorted(p.name[: -len(".log.jsonl")] for p in Path(dd).glob("*.log.jsonl"))
