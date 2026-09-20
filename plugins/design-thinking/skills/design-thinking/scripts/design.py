#!/usr/bin/env python3
"""Record decisions about a change. The agent's tool call, one per phase move.

Every subcommand APPENDS ONE DECISION to `.design/<ref>.log.jsonl` and then
re-folds that log into the trace, the model snapshot, the tree, the per-task
graph and the index. Nothing is edited in place, so a verdict that was later
reversed stays readable with the reason that moved it.

Pass `--why` whenever the decision is not self-evident. The state says what
was decided; the log says what decided it, and that is the part worth reading
on the next ticket.
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import design_state as st  # noqa: E402
import fold as fd  # noqa: E402
import render_graph as rg  # noqa: E402

ROLES = ["entrypoint", "handler", "application_service", "aggregate_root", "entity",
         "value_object", "domain_service", "repository", "process_manager",
         "anti_corruption_layer", "read_model", "adapter", "util", "script",
         "workflow", "migration", "config", "fixture", "test"]
OWNER_ROLES = sorted(fd.ROLE_BUCKET)
EDGE_KINDS = ["calls", "imports", "invokes", "requests", "publishes", "subscribes",
              "reads_writes", "provisions"]
# Mirrors graph.json's evidence_tiers.ladder, strongest first. A constant so the
# spec-mirror check reads the value instead of parsing this file's formatting.
EVIDENCE_TIERS = ["compiler", "coverage", "references", "text", "reasoning"]
# Mirrors graph.json's trace.stop_conditions exactly. FAN_OUT and DEPTH are
# deliberately absent: a hop count is not a stop condition, and PASS_THROUGH
# superseded FAN_OUT.
STOP_REASONS = ["ABSORBED", "MISPLACED", "CROSSING", "OPAQUE", "VISITED",
                "COMPLETE_UP", "COMPLETE_DOWN", "PASS_THROUGH", "NO_ABSORPTION"]
# CLEAR is not a stop condition - it retracts one. Exposed as a constant so the
# spec-mirror check can assert it without reaching into argparse internals.
STOP_REASON_CHOICES = STOP_REASONS + ["CLEAR"]


def head():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, timeout=5).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def dd_or_die():
    dd = st.find_design_dir()
    if dd is None:
        sys.exit("no .design/ directory - run `design.py init --ref <REF>` first")
    return dd


def active_ref(dd, ref, mutating=True):
    """The ticket this decision belongs to.

    `mutating` is the important half: a read may fall back to a closed ticket,
    but appending to one would reopen it by side effect and leave `close`
    meaning nothing.
    """
    refs = st.log_refs(dd)
    if ref:
        if not st.log_path(dd, ref).exists():
            sys.exit(f"no log for {ref} - run `design.py init --ref {ref}` first")
        if mutating and closed(dd, ref):
            sys.exit(f"{ref} is closed. Appending to a closed ticket reopens it by "
                     "side effect - open a new ticket, or re-open this one deliberately.")
        return ref
    if not refs:
        sys.exit(f"no ticket in {dd} - run `design.py init --ref <REF>`")
    open_ = [r for r in refs if not closed(dd, r)]
    if mutating:
        if not open_:
            sys.exit(f"every ticket in {dd} is closed ({', '.join(refs)}) - "
                     "run `design.py init --ref <REF>` to start the next one.")
        pool = open_
    else:
        pool = open_ or refs
    if len(pool) > 1:
        sys.exit(f"more than one open ticket ({', '.join(pool)}) - pass --ref")
    return pool[0]


def closed(dd, ref):
    return (fd.fold(st.read_log(dd, ref))[0] or {}).get("status") == "closed"


def require_task(dd, ref, slug, what):
    """A decision naming an unknown task folds into nothing and looks like it worked."""
    _, traces, models = state(dd, ref)
    if slug not in traces and slug not in models:
        known = ", ".join(sorted(set(traces) | set(models))) or "none yet"
        sys.exit(f"no task {slug!r} on {ref}, so this {what} would be recorded and then "
                 f"silently dropped by the fold. Known tasks: {known}. "
                 f"Run `design.py task --slug {slug} ...` first.")
    return traces, models


def state(dd, ref):
    return fd.fold(st.read_log(dd, ref))


def record(dd, ref_, kind, msg, **fields):
    st.append_event(dd, ref_, kind, **fields)
    fd.rebuild(dd, ref_)
    _, tree = rg.render(dd, ref=ref_)
    print(msg)
    print()
    print(tree)
    print()
    print(rg.LEGEND)
    return 0


def csv(v):
    return [x.strip() for x in v.split(",") if x.strip()] if v else None


# --- subcommands -----------------------------------------------------------

def cmd_init(a):
    dd = st.design_dir_for_write()
    dd.mkdir(parents=True, exist_ok=True)
    if st.log_path(dd, a.ref).exists():
        print(f"ticket {a.ref} already exists")
        _, tree = rg.render(dd, ref=a.ref)
        print()
        print(tree)
        return 0
    return record(dd, a.ref, "ticket.init", f"initialised {dd}/{a.ref}.log.jsonl",
                  ticket_ref=a.ref, title=a.title, commit=head())


def cmd_requirement(a):
    dd = dd_or_die()
    ref = active_ref(dd, a.ref)
    if a.status == "descoped" and not a.why:
        sys.exit(f"descoping {a.id} drops it from the ticket without any evidence being "
                 "required, so the reason is the only record that it was a decision "
                 "rather than an omission - pass --why.")
    return record(dd, ref, "requirement.set", f"{a.id} recorded",
                  id=a.id, statement=a.statement, source=a.source,
                  status=a.status, why=a.why)


def cmd_acceptance(a):
    """Record the requirement-altitude check and the red it produced.

    The requirement gate: no work on a requirement without a check that is red
    for it first. `close` reads this back, which is what makes closure observed
    rather than asserted.
    """
    dd = dd_or_die()
    ref = active_ref(dd, a.ref)
    ticket, _, _ = state(dd, ref)
    if not any(r.get("id") == a.id for r in (ticket or {}).get("requirements", [])):
        sys.exit(f"no requirement {a.id} - record it before its acceptance check")
    prior_red = next((((r.get("acceptance") or {}).get("red_evidence") or {}).get("failure")
                      for r in (ticket or {}).get("requirements", [])
                      if r.get("id") == a.id), None)
    if a.manual_owner or a.manual_evidence:
        if a.red or a.green:
            sys.exit("a manual closure and an observation of the check are two different "
                     "decisions about how this requirement closes - record one, then the "
                     "other if the mode really changed. Combining them would discard the "
                     "observation silently.")
        if not (a.manual_owner and a.manual_evidence):
            sys.exit("a manual closure needs both --manual-owner (who closes it) and "
                     "--manual-evidence (what they will look at). Naming neither is the "
                     "assertion principle 2 refuses; naming only one is half a record.")
        return record(dd, ref, "acceptance.manual",
                      f"{a.id} closes manually, owned by {a.manual_owner}",
                      id=a.id, who=a.manual_owner, evidence_note=a.manual_evidence,
                      why=a.why)
    if a.red and a.green:
        sys.exit("--red and --green are two different observations of the same check "
                 "and must be two decisions. The whole point is the transition, and a "
                 "single line claiming both records neither.")
    if not a.red and not a.green:
        sys.exit("record what the check did: --red '<observed failure>' before any "
                 "code, or --green once it passes on its own")
    cur_cmd = next(((r.get("acceptance") or {}).get("cmd")
                    for r in (ticket or {}).get("requirements", [])
                    if r.get("id") == a.id), None)
    if a.green and not a.red:
        if not prior_red:
            sys.exit(f"{a.id} has no recorded red evidence, so --green would close a "
                     "check that was never observed failing. No work on a requirement "
                     "without a red check for it first (principle 26) - record --red "
                     "before any code.")
        cur_acc = next(((r.get("acceptance") or {})
                        for r in (ticket or {}).get("requirements", [])
                        if r.get("id") == a.id), {})
        red_cmd = (cur_acc.get("red_evidence") or {}).get("command")
        for flag, given, current in (("--cmd", a.cmd, cur_cmd or red_cmd),
                                     ("--altitude", a.altitude, cur_acc.get("altitude")),
                                     ("--harness", a.harness, cur_acc.get("harness"))):
            if given and given != current:
                sys.exit(f"--green names a different {flag} than the check that went red "
                         f"({current!r}). Any of command, altitude or harness redefines "
                         "what is being checked, so the new one's red must be observed "
                         "first - record --red for it before its green.")
    return record(dd, ref, "acceptance.set",
                  f"{a.id} acceptance {'green' if a.green else 'red'}",
                  id=a.id, altitude=a.altitude, harness=a.harness, cmd=a.cmd,
                  red=a.red, green=a.green, why=a.why)


def cmd_task(a):
    dd = dd_or_die()
    ref = active_ref(dd, a.ref)
    try:
        st.safe_slug(a.slug)          # becomes a filename; must not escape .design/
    except ValueError as exc:
        sys.exit(str(exc))
    ticket, _, _ = state(dd, ref)
    req = next((r for r in (ticket or {}).get("requirements", [])
                if r.get("id") == a.requirement), None)
    if req is None:
        sys.exit(f"no requirement {a.requirement} - record it before opening a task "
                 "against it (a task with no requirement has nothing to close)")
    if req.get("status") in ("descoped", "done"):
        sys.exit(f"{a.requirement} is {req['status']}, so a task against it is not work "
                 "this ticket is doing. Re-open the requirement, or open the task "
                 "against the one that is in motion.")
    acc = req.get("acceptance") or {}
    manual = (acc.get("manual_closure") or {}).get("who")
    if not (acc.get("red_evidence") or {}).get("failure") and not manual:
        sys.exit(f"{a.requirement} has no recorded red acceptance evidence, so opening a "
                 "task against it would start work before the requirement gate. Run "
                 f"`design.py acceptance --id {a.requirement} --cmd '<check>' "
                 "--red '<observed failure>'` first (principle 26), or record a manual "
                 "closure owner if the requirement genuinely cannot be automated.")
    return record(dd, ref, "task.create",
                  f"task {a.id} ({a.slug}): trace + model snapshot derived",
                  id=a.id, slug=a.slug, title=a.title,
                  requirement=a.requirement, commit=head(), why=a.why)


def cmd_phase(a):
    dd = dd_or_die()
    ref = active_ref(dd, a.ref)
    if a.slug:
        # Without this, a typo'd slug silently advances the ticket phase instead.
        require_task(dd, ref, a.slug, "phase change")
    if a.skipped:
        # A phase silently not run is indistinguishable from one forgotten.
        return record(dd, ref, "phase.skip", f"phase {a.phase} skipped: {a.skipped}",
                      phase=a.phase, slug=a.slug, skipped=a.skipped, why=a.why)
    return record(dd, ref, "phase.set", f"phase -> {a.phase}",
                  phase=a.phase, slug=a.slug, why=a.why)


def cmd_node(a):
    dd = dd_or_die()
    ref = active_ref(dd, a.ref)
    traces, _ = require_task(dd, ref, a.slug, "node")
    known = {n.get("path"): n for n in traces[a.slug]["nodes"]}
    if a.path not in known and not a.purpose:
        sys.exit("every node gets a purpose, read from the code, before it gets a "
                 "verdict (principle 7) - pass --purpose")
    prior_node = known.get(a.path, {})
    if a.verdict == "no_change" and not a.stop_reason:
        sys.exit(f"a no_change verdict needs --stop-reason ({' | '.join(STOP_REASONS)}) "
                 "- stopping is a finding, not a default (principle 3)")
    effective_verdict = a.verdict or prior_node.get("verdict")
    if a.stop_reason == "CLEAR" and effective_verdict == "no_change":
        sys.exit("--stop-reason CLEAR retracts a stop, and a no_change verdict requires "
                 "one - including when the verdict is simply carried over from the "
                 "previous decision. Give the replacement stop reason, or pass "
                 "--verdict change|unsure alongside CLEAR.")
    if a.stop_reason == "MISPLACED" and not a.belongs_in:
        sys.exit("MISPLACED needs --belongs-in: a behavior this node's purpose does not "
                 "cover belongs in a node whose purpose does, or in one that does not "
                 "exist yet ('new node: <path>'). Those are the only two options without "
                 "a human (principle 7).")
    if a.belongs_in and a.belongs_in not in known \
            and not a.belongs_in.startswith("new node:") \
            and not ("/" in a.belongs_in or "." in a.belongs_in):
        # A shape check, not an existence check: the destination is often a real
        # file this task has not traced yet, and principle 7's second option is a
        # node that does not exist at all. Neither can be verified here. What can
        # be caught is a value that is not a path and not the declared new-node
        # form, which is unresolvable however it was meant.
        sys.exit(f"--belongs-in {a.belongs_in!r} is not a path and not "
                 "'new node: <path>', so nothing can act on it. Give the node whose "
                 "purpose covers the behavior, or declare a new one (principle 7). "
                 "Traced on this task: " + (", ".join(sorted(known)) or "none yet"))
    if (a.verdict in ("change", "unsure")
            and prior_node.get("stop_reason") and a.stop_reason != "CLEAR"):
        sys.exit(f"{a.path} is recorded with stop_reason "
                 f"{prior_node['stop_reason']}, and a {a.verdict} verdict has no stop. "
                 "Pass --stop-reason CLEAR to retract it, or the folded trace and the "
                 "rendered tree keep showing the old stop.")
    prior = known.get(a.path, {}).get("verdict")
    if prior and a.verdict and prior != a.verdict and not a.why:
        sys.exit(f"{a.path} was {prior}, now {a.verdict} - a reversal needs --why. "
                 "That reason is the most informative line in the log.")
    return record(dd, ref, "node.set", f"node {a.path}: {a.verdict or 'recorded'}",
                  slug=a.slug, path=a.path, purpose=a.purpose, role=a.role,
                  verdict=a.verdict, stop_reason=a.stop_reason, depth=a.depth,
                  aggregate=a.aggregate, context=a.context, language=a.language,
                  discovered_via=a.via, evidence=a.evidence,
                  belongs_in=a.belongs_in, why=a.why)


def cmd_edge(a):
    dd = dd_or_die()
    ref = active_ref(dd, a.ref)
    traces, _ = require_task(dd, ref, a.slug, "edge")
    prior = next((e for e in traces[a.slug].get("edges", [])
                  if e.get("from") == a.src and e.get("to") == a.dst), None)
    if prior and prior.get("kind") != a.kind:
        sys.exit(f"{a.src} -> {a.dst} is already recorded as {prior['kind']!r}. An edge "
                 f"carries one kind; recording it again as {a.kind!r} would either be "
                 "dropped silently or contradict the first. Decide which it is - and if "
                 "the nodes really relate two ways, that is two edges through different "
                 "symbols, not one edge with two kinds.")
    return record(dd, ref, "edge.add", f"edge {a.src} -{a.kind}-> {a.dst}",
                  slug=a.slug, **{"from": a.src}, to=a.dst,
                  edge_kind=a.kind, seam=a.seam, why=a.why)


def cmd_behavior(a):
    dd = dd_or_die()
    ref = active_ref(dd, a.ref)
    traces, _ = require_task(dd, ref, a.slug, "behavior")
    if a.requirement:
        ticket, _, _ = state(dd, ref)
        known_reqs = [r.get("id") for r in (ticket or {}).get("requirements", [])]
        if a.requirement not in known_reqs:
            sys.exit(f"no requirement {a.requirement} on {ref}, so this behavior would "
                     "claim to satisfy something that does not exist and the "
                     "requirement-to-behavior chain would be broken silently. Known: "
                     + (", ".join(x for x in known_reqs if x) or "none yet"))
    if a.status in ("gated", "green"):
        prior = next((x for x in traces[a.slug].get("behaviors", [])
                      if x.get("id") == a.id), {})
        wants = a.statement or prior.get("statement")
        entry = next((g for g in traces[a.slug].get("gate_ledger", [])
                      if g.get("behavior_id") == a.id), None)
        gated = bool(entry and (entry.get("red_evidence") or {}).get("failure")
                     and not entry.get("checks_failed"))
        if gated and entry.get("statement") and entry["statement"] != wants:
            sys.exit(f"{a.id} was gated as {entry['statement']!r} and is now stated as "
                     f"{wants!r}. The gate proves the behavior as stated, so a changed "
                     "statement needs a fresh red - re-run `design.py gate` for it.")
        if not gated:
            sys.exit(f"{a.id} has no gate ledger entry, so --status {a.status} would be a "
                     "claim rather than a record. No code for a behavior until its test "
                     "is red for the intended reason (the behavior gate) - run "
                     f"`design.py gate --slug {a.slug} --id {a.id} --red '<observed "
                     "failure>'` first.")
    return record(dd, ref, "behavior.set", f"{a.id} {a.status or 'recorded'}",
                  slug=a.slug, id=a.id, statement=a.statement, path=a.path,
                  symbol=a.symbol, behavior_kind=a.kind, verdict=a.verdict,
                  status=a.status, owned_by=a.owner, requirement=a.requirement,
                  why=a.why)


def cmd_gate(a):
    dd = dd_or_die()
    ref = active_ref(dd, a.ref)
    traces, _ = require_task(dd, ref, a.slug, "gate")
    b = next((x for x in traces.get(a.slug, {}).get("behaviors", [])
              if x.get("id") == a.id), None)
    if b is None:
        sys.exit(f"no behavior {a.id} - record it before gating it")
    if not a.red:
        sys.exit("the gate needs the observed failure verbatim: --red '<output>'. "
                 "A test red because the suite will not build proves nothing "
                 "(principle 27)")
    statement = b.get("statement")
    msg = f"{a.id} gated" if not a.failed else f"{a.id} gate FAILED: {a.failed}"
    return record(dd, ref, "gate.record", msg, slug=a.slug, id=a.id, red=a.red,
                  cmd=a.cmd, passed=csv(a.passed), failed=csv(a.failed),
                  statement=statement, why=a.why)


def cmd_order(a):
    dd = dd_or_die()
    ref = active_ref(dd, a.ref)
    traces, _ = require_task(dd, ref, a.slug, "ordering")
    if not any(n.get("path") == a.path for n in traces.get(a.slug, {}).get("nodes", [])):
        sys.exit(f"no node {a.path} in this trace - record it before ordering it")
    clash = next((o for o in traces[a.slug].get("ordered_change_set", [])
                  if o.get("n") == a.n and o.get("path") != a.path), None)
    if clash:
        sys.exit(f"position #{a.n} is already {clash['path']}. The ordered change set is "
                 "the edit sequence, so two nodes in one slot leave it ambiguous which "
                 "goes first - give this one its own position, or renumber the other.")
    return record(dd, ref, "order.set", f"#{a.n} {a.path}",
                  slug=a.slug, path=a.path, n=a.n, symbol=a.symbol,
                  reason=a.reason, why=a.why)


def cmd_term(a):
    dd = dd_or_die()
    ref = active_ref(dd, a.ref)
    require_task(dd, ref, a.slug, "term")
    return record(dd, ref, "term.set", f"term {a.term!r} captured",
                  slug=a.slug, term=a.term, definition=a.definition,
                  context=a.context, code=csv(a.code), dead=csv(a.dead),
                  provenance=a.provenance, why=a.why)


def cmd_own(a):
    dd = dd_or_die()
    ref = active_ref(dd, a.ref)
    require_task(dd, ref, a.slug, "ownership record")
    if a.role == "application_service" and a.invariant:
        sys.exit("an application service owns no rules (principle 19) - that invariant "
                 "belongs to an aggregate or a domain service")
    if a.role == "repository" and not a.aggregate:
        sys.exit("a repository stores exactly one aggregate root - pass --aggregate")
    return record(dd, ref, "own.set", f"{a.name} recorded as {a.role}",
                  slug=a.slug, name=a.name, role=a.role, purpose=a.purpose,
                  context=a.context, invariant=a.invariant, aggregate=a.aggregate,
                  identity=a.identity, why=a.why)


def cmd_close(a):
    dd = dd_or_die()
    ref = active_ref(dd, a.ref)
    ticket, _, _ = state(dd, ref)
    reqs = (ticket or {}).get("requirements", [])
    open_ = [r["id"] for r in reqs if r.get("status") not in ("done", "descoped")]
    if open_ and not a.force:
        sys.exit(f"requirements still open: {', '.join(open_)}. One requirement closes "
                 "before the next opens - pass --force to override deliberately.")

    # Principle 2: closure is observed, not asserted. A requirement marked done
    # with no recorded red evidence is an opinion, and an ungated behavior is a
    # claim - neither is proof that anything went green on its own.
    if not a.force:
        _, traces, _ = state(dd, ref)
        unproven, ungreen, unreasoned, unbehaved = [], [], [], []
        satisfied = {rid for tr in traces.values()
                     for b in tr.get("behaviors", [])
                     for rid in (b.get("requirement_ids") or [])}
        for r in reqs:
            if r.get("status") == "descoped":
                # Descoping skips every evidence check, so the reason is the only
                # thing distinguishing a decision from a quiet omission.
                if not any(d.get("why") for d in (r.get("decisions") or [])):
                    unreasoned.append(r["id"])
                continue
            if r.get("status") != "done":
                continue
            acc = r.get("acceptance") or {}
            manual = acc.get("manual_closure") or {}
            if manual.get("who") and manual.get("evidence"):
                continue        # closed by a named human on stated evidence
            if not (acc.get("red_evidence") or {}).get("failure"):
                unproven.append(r["id"])
            elif not acc.get("went_green_at"):
                ungreen.append(r["id"])
            # A requirement is satisfied BY BEHAVIORS (principle 8); a green
            # acceptance check with nothing behind it closes an empty box.
            if r["id"] not in satisfied:
                unbehaved.append(r["id"])
        ungated = []
        for slug, tr in traces.items():
            ledger = {g.get("behavior_id"): g for g in tr.get("gate_ledger", [])}
            for b in tr.get("behaviors", []):
                if b.get("status") not in ("green", "gated"):
                    ungated.append(f"{slug}:{b['id']} (status {b.get('status')})")
                    continue
                entry = ledger.get(b.get("id"))
                # A status is a claim; the ledger entry with its observed red is
                # the evidence. Without it the behavior gate was never passed,
                # however green the status says it is.
                if not entry or not (entry.get("red_evidence") or {}).get("failure"):
                    ungated.append(f"{slug}:{b['id']} (no gate ledger entry)")
                elif entry.get("checks_failed"):
                    ungated.append(f"{slug}:{b['id']} (gate checks failed: "
                                   + ", ".join(entry["checks_failed"]) + ")")
                elif entry.get("statement") and entry["statement"] != b.get("statement"):
                    ungated.append(f"{slug}:{b['id']} (restated since it was gated)")
        problems = []
        if unproven:
            problems.append("requirements marked done with no recorded red evidence: "
                            + ", ".join(unproven))
        if ungreen:
            problems.append("requirements with red evidence but no recorded green "
                            "transition: " + ", ".join(ungreen)
                            + " (run `design.py acceptance --id <R> --green`)")
        if unreasoned:
            problems.append("requirements descoped with no recorded reason: "
                            + ", ".join(unreasoned))
        if unbehaved:
            problems.append("requirements marked done that no behavior satisfies: "
                            + ", ".join(unbehaved)
                            + " (a requirement with no behavior is not implemented, "
                              "however much code was written - principle 8)")
        if ungated:
            problems.append("behaviors never gated or green: " + ", ".join(ungated[:8])
                            + (" ..." if len(ungated) > 8 else ""))
        if problems:
            sys.exit("; ".join(problems)
                     + ". Closure is observed, not asserted (principle 2) - "
                       "record the evidence, or pass --force to close deliberately.")
    return record(dd, ref, "ticket.close",
                  f"{ref} closed - the log and every snapshot stay in place",
                  commit=head(), force=a.force, why=a.why)


def cmd_log(a):
    """Print the decisions, and the reversals among them."""
    dd = dd_or_die()
    ref = active_ref(dd, a.ref, mutating=False)
    events = st.read_log(dd, ref)
    for ev in events[-a.tail:] if a.tail else events:
        subject = ev.get("path") or ev.get("id") or ev.get("term") or \
            ev.get("name") or ev.get("slug") or ev.get("ticket_ref") or ""
        why = f"  — {ev['why']}" if ev.get("why") else ""
        print(f"{ev.get('_n'):>4}  {ev.get('at','')}  {ev.get('kind',''):<16} "
              f"{subject}{why}")
    ticket, _, _ = state(dd, ref)
    rev = (ticket or {}).get("reversals") or []
    if rev:
        print()
        print("reversals — where the evidence moved a verdict:")
        for r in rev:
            print(f"  {r['what']}: {r['from']} -> {r['to']}"
                  f"{'  — ' + r['why'] if r.get('why') else ''}")
    return 0


def cmd_rebuild(a):
    """Re-fold every log. Use after editing a log by hand, or on resume."""
    dd = dd_or_die()
    fd.rebuild_all(dd)
    _, tree = rg.render(dd, ref=a.ref)
    print(f"rebuilt {len(st.log_refs(dd))} log(s)")
    print()
    print(tree)
    return 0


def cmd_show(a):
    dd = st.find_design_dir()
    if dd is None:
        print("no .design/ directory - run `design.py init --ref <REF>` to start")
        return 0
    _, tree = rg.render(dd, ref=a.ref, level=a.level, full=a.full)
    print(tree)
    print()
    print(rg.LEGEND)
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="design.py", description=__doc__)
    ap.add_argument("--ref", help="ticket ref; defaults to the single open ticket")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, help_, fn, why=True):
        s = sub.add_parser(name, help=help_)
        if why:
            s.add_argument("--why", help="what decided this; required on a reversal")
        s.set_defaults(fn=fn)
        return s

    s = add("init", "start a decision log for a ticket", cmd_init, why=False)
    s.add_argument("--ref", required=True)
    s.add_argument("--title")

    s = add("requirement", "record a requirement (tier 0)", cmd_requirement)
    s.add_argument("--id", required=True)
    s.add_argument("--statement", required=True)
    s.add_argument("--source", help="the ticket's own words")
    s.add_argument("--status", choices=["todo", "tracing", "implementing",
                                        "verifying", "done", "blocked", "descoped"])

    s = add("acceptance", "record a requirement's check and its red evidence", cmd_acceptance)
    s.add_argument("--id", required=True)
    s.add_argument("--cmd", help="the exact command, mirrored into checks.acceptance")
    s.add_argument("--altitude", choices=["browser", "http", "cli", "event",
                                          "workflow", "data"])
    s.add_argument("--harness")
    s.add_argument("--red", help="the observed failure, verbatim, before any code")
    s.add_argument("--green", action="store_true",
                   help="the check now passes on its own")
    s.add_argument("--manual-owner", dest="manual_owner",
                   help="for a requirement that genuinely cannot be automated: who "
                        "closes it")
    s.add_argument("--manual-evidence", dest="manual_evidence",
                   help="and on what evidence they close it")

    s = add("task", "open a task; derives its trace and model snapshot", cmd_task)
    s.add_argument("--id", required=True)
    s.add_argument("--slug", required=True)
    s.add_argument("--title")
    s.add_argument("--requirement", required=True)

    s = add("phase", "advance the phase", cmd_phase)
    s.add_argument("phase")
    s.add_argument("--slug", help="set the task's phase instead of the ticket's")
    s.add_argument("--skipped", metavar="WHY",
                   help="record that this phase's predicate did not hold, "
                        "instead of advancing to it")

    s = add("node", "record a node and its verdict (tier 2)", cmd_node)
    s.add_argument("--slug", required=True)
    s.add_argument("--path", required=True)
    s.add_argument("--purpose", help="one sentence, read from the code, as a capability")
    s.add_argument("--role", choices=ROLES)
    s.add_argument("--verdict", choices=["change", "no_change", "unsure"])
    s.add_argument("--stop-reason", dest="stop_reason",
                   choices=STOP_REASON_CHOICES,
                   help="CLEAR retracts a stop recorded by an earlier decision")
    s.add_argument("--depth", type=int, help="signed, relative to the seed")
    s.add_argument("--aggregate")
    s.add_argument("--context")
    s.add_argument("--language")
    s.add_argument("--via", help="keyword | up_from:<path> | down_from:<path>")
    s.add_argument("--evidence", choices=EVIDENCE_TIERS)
    s.add_argument("--belongs-in", dest="belongs_in",
                   help="required with --stop-reason MISPLACED: the node whose purpose "
                        "covers the behavior, or 'new node: <path>'")

    s = add("edge", "record an edge between two nodes", cmd_edge)
    s.add_argument("--slug", required=True)
    s.add_argument("--from", dest="src", required=True)
    s.add_argument("--to", dest="dst", required=True)
    s.add_argument("--kind", default="calls", choices=EDGE_KINDS)
    s.add_argument("--seam")

    s = add("behavior", "record a behavior (tier 4)", cmd_behavior)
    s.add_argument("--slug", required=True)
    s.add_argument("--id", required=True)
    s.add_argument("--statement", required=True,
                   help="also stored as the test name - they are one sentence")
    s.add_argument("--path")
    s.add_argument("--symbol")
    s.add_argument("--kind", choices=["happy", "error", "boundary",
                                      "concurrency", "effect"])
    s.add_argument("--verdict", choices=["new", "modified", "unchanged", "removed"])
    s.add_argument("--status", choices=["todo", "specified", "red", "gated", "green"])
    s.add_argument("--owner", help="the aggregate or service that owns it")
    s.add_argument("--requirement")

    s = add("gate", "record a gate verdict with its red evidence", cmd_gate)
    s.add_argument("--slug", required=True)
    s.add_argument("--id", required=True)
    s.add_argument("--red", help="the observed failure, verbatim")
    s.add_argument("--cmd")
    s.add_argument("--passed", help="comma-separated check ids")
    s.add_argument("--failed", help="comma-separated check ids")

    s = add("order", "position a node in the ordered change set", cmd_order)
    s.add_argument("--slug", required=True)
    s.add_argument("--path", required=True)
    s.add_argument("--n", type=int, required=True)
    s.add_argument("--symbol")
    s.add_argument("--reason")

    s = add("term", "capture a glossary term in this task's snapshot", cmd_term)
    s.add_argument("--slug", required=True)
    s.add_argument("--term", required=True)
    s.add_argument("--definition", required=True)
    s.add_argument("--context")
    s.add_argument("--code", help="comma-separated code terms")
    s.add_argument("--dead", help="comma-separated dead aliases")
    s.add_argument("--provenance", choices=["mined", "invented"], default="mined")

    s = add("own", "record what owns a rule or a sequence", cmd_own)
    s.add_argument("--slug", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--role", required=True, choices=OWNER_ROLES)
    s.add_argument("--purpose")
    s.add_argument("--context")
    s.add_argument("--invariant")
    s.add_argument("--aggregate", help="required for --role repository: the one aggregate root it loads and persists, whole")
    s.add_argument("--identity", help="for --role entity: the branded id type it carries")

    s = add("close", "close the ticket; nothing is moved or deleted", cmd_close)
    s.add_argument("--force", action="store_true")

    s = add("log", "print the decisions, and the reversals among them", cmd_log, why=False)
    s.add_argument("--tail", type=int, default=0)

    add("rebuild", "re-fold every log into its documents", cmd_rebuild, why=False)

    s = add("show", "render without deciding anything", cmd_show, why=False)
    s.add_argument("--level", type=int, default=2,
                   help="3+ expands symbols on unchanged nodes too")
    s.add_argument("--full", action="store_true",
                   help="draw every traced node, not just the changed subgraph")
    return ap


def main(argv):
    a = build_parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
