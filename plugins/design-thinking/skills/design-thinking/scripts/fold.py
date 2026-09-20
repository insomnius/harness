#!/usr/bin/env python3
"""Fold a decision log into the state documents it implies.

The log is the source. Ticket, trace and model files are rebuilt from it on
every append and must never be hand-edited - editing a fold is editing a view,
and the next append silently discards it.

Reversals survive the fold. Every subject carries a `decisions` list, so a
node whose verdict went change -> no_change shows both, with the reason that
moved it. That trajectory is what a cold agent reads to understand not just
what was decided but what the evidence did.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import design_state as st  # noqa: E402

TEMPLATES = Path(__file__).resolve().parent.parent
DERIVED = "DERIVED from the decision log - do not edit; the next append rebuilds it"


def _blank(obj):
    if isinstance(obj, dict):
        return {k: _blank(v) for k, v in obj.items() if k != "_"}
    if isinstance(obj, list):
        return []
    if isinstance(obj, str) and obj.startswith("<") and obj.endswith(">"):
        return ""
    if isinstance(obj, str) and " | " in obj:
        return obj.split(" | ")[0]
    return obj


def _template(name):
    return _blank(st.read_json(TEMPLATES / name))


def _rec(items, key, value):
    for it in items:
        if it.get(key) == value:
            return it
    it = {key: value}
    items.append(it)
    return it


def _decide(rec, ev, fields):
    """Apply one decision, keeping the ones it superseded.

    A field is only overwritten when the event actually carries it, so a later
    event that records a `why` does not blank out an earlier `purpose`.
    """
    changed = {k: ev[k] for k in fields if ev.get(k) is not None}
    prior = {k: rec.get(k) for k in changed}
    rec.update(changed)
    entry = {"at": ev.get("at"), "n": ev.get("_n")}
    entry.update(changed)
    if ev.get("why"):
        entry["why"] = ev["why"]
    if ev.get("evidence"):
        entry["evidence"] = ev["evidence"]
    reversed_ = {k: v for k, v in prior.items()
                 if v not in (None, "") and v != changed.get(k)}
    if reversed_:
        entry["superseded"] = reversed_
    rec.setdefault("decisions", []).append(entry)
    return rec


def fold(events):
    """events -> (ticket, {slug: trace}, {slug: model})."""
    ticket, traces, models = None, {}, {}
    reversals = []

    for ev in events:
        k = ev.get("kind")
        slug = ev.get("slug")

        if k == "ticket.init":
            ticket = _template("ticket.template.json")
            ticket.update(_="" if False else DERIVED,
                          ticket=ev.get("title") or ev.get("ticket_ref"),
                          ticket_ref=ev.get("ticket_ref"), status="open",
                          created_at=ev.get("at"),
                          opened_at_commit=ev.get("commit"),
                          current_phase="preflight")
            ticket["requirements"], ticket["tasks"] = [], []
            continue

        if ticket is None:
            continue

        if k == "requirement.set":
            r = _rec(ticket["requirements"], "id", ev.get("id"))
            r.setdefault("turns", 0)
            _decide(r, ev, ("statement", "status"))
            if ev.get("source"):
                r["source_quote"] = ev["source"]
            # P2: `or` pinned the tree to R1 forever. The requirement most
            # recently decided on is the one in motion.
            ticket["current_requirement"] = ev.get("id") or ticket.get("current_requirement")

        elif k == "acceptance.set":
            r = _rec(ticket["requirements"], "id", ev.get("id"))
            acc = r.setdefault("acceptance", {})
            if acc.get("manual_closure"):
                # ...and observing the check run retracts the manual closure, so
                # a failure after one cannot be ignored by `close`.
                acc.pop("manual_closure", None)
                acc["automatable"] = True
            for f in ("altitude", "harness", "cmd"):
                if not ev.get(f):
                    continue
                if acc.get(f) and acc[f] != ev[f]:
                    # Any of these three redefines what is being checked - a
                    # different command, a different altitude, a different
                    # harness. Evidence gathered against the old definition
                    # proves nothing about the new one, so it is retracted
                    # rather than silently carried forward.
                    acc.pop("red_evidence", None)
                    acc.pop("went_green_at", None)
                acc[f] = ev[f]
            if ev.get("red"):
                acc["red_evidence"] = {"command": ev.get("cmd") or acc.get("cmd", ""),
                                       "failure": ev["red"], "at": ev.get("at")}
                # A check that regressed is red now. Keeping the old transition
                # would let `close` close a currently failing requirement -
                # closure is observed, and this observation is a failure.
                acc.pop("went_green_at", None)
            if ev.get("green"):
                # If the command changed in this same event the red evidence was
                # just retracted, so there is nothing this green is the other
                # half of. Defensive: the CLI refuses it, a hand-edited log may not.
                if (acc.get("red_evidence") or {}).get("failure"):
                    acc["went_green_at"] = ev.get("at")
            if ev.get("cmd"):
                ticket.setdefault("checks", {}).setdefault("acceptance", {})["cmd"] = ev["cmd"]

        elif k == "acceptance.manual":
            r = _rec(ticket["requirements"], "id", ev.get("id"))
            acc = r.setdefault("acceptance", {})
            acc["automatable"] = False
            acc["manual_closure"] = {"who": ev.get("who"),
                                     "evidence": ev.get("evidence_note"),
                                     "at": ev.get("at")}
            # Deciding a requirement closes manually retracts the automated
            # evidence: the later decision defines how this requirement closes.
            acc.pop("red_evidence", None)
            acc.pop("went_green_at", None)

        elif k == "task.create":
            if slug in traces:
                # A repeated create is ignored entirely, before any ticket
                # metadata is touched. Reinitialising would erase every node and
                # term recorded after the first creation, and rewriting the task
                # row while keeping the old trace would leave the derived
                # documents describing two different tasks.
                continue
            ref = ticket["ticket_ref"]
            t = _rec(ticket["tasks"], "slug", slug)
            _decide(t, ev, ("id", "title"))
            if ev.get("requirement"):
                t["requirement_id"] = ev["requirement"]
            t["status"] = "tracing"
            t["trace_file"] = f".design/{ref}.{slug}.trace.json"
            ticket["current_task"] = ev.get("id")
            tr = _template("trace.template.json")
            tr.update(_=DERIVED, task_id=ev.get("id"), task_slug=slug,
                      requirement_id=ev.get("requirement"), created_at=ev.get("at"),
                      traced_at_commit=ev.get("commit"), current_phase="keyword")
            for key in ("nodes", "edges", "behaviors", "gate_ledger",
                        "ordered_change_set", "phases_done", "seeds"):
                tr[key] = []
            traces[slug] = tr
            m = _template("task-model.template.json")
            m.update(_=DERIVED, ticket_ref=ref, task_slug=slug,
                     created_at=ev.get("at"), captured_at_commit=ev.get("commit"))
            for key in ("glossary", "aggregates", "domain_services",
                        "application_services", "repositories", "process_managers",
                        "read_models", "anti_corruption_layers", "subdomains",
                        "contexts", "domain_events", "entities", "value_objects"):
                m[key] = []
            models[slug] = m

        elif k == "phase.set":
            if slug and slug in traces:
                traces[slug]["current_phase"] = ev.get("phase")
                done = traces[slug].setdefault("phases_done", [])
                if ev.get("phase") not in done:
                    done.append(ev.get("phase"))
            else:
                ticket["current_phase"] = ev.get("phase")

        elif k == "phase.skip":
            sk = ticket.setdefault("skipped_phases", [])
            entry = next((x for x in sk if x.get("phase") == ev.get("phase")
                          and x.get("task") == slug), None)
            if entry is None:
                sk.append({"phase": ev.get("phase"), "why": ev.get("skipped"),
                           "task": slug, "at": ev.get("at")})
            else:
                # a corrected reason is a later decision and supersedes
                entry.update(why=ev.get("skipped"), at=ev.get("at"))

        elif k == "node.set" and slug in traces:
            n = _rec(traces[slug]["nodes"], "path", ev.get("path"))
            before = n.get("verdict")
            _decide(n, ev, ("purpose", "role", "verdict", "stop_reason", "depth",
                            "aggregate", "context", "language", "discovered_via"))
            sr = ev.get("stop_reason")
            if sr and sr != "MISPLACED":
                # Any other explicit stop supersedes a MISPLACED finding, so the
                # entry goes with it - otherwise the tree keeps drawing ⊗ for a
                # node that is now absorbed.
                traces[slug]["misplaced"] = [
                    m for m in traces[slug].get("misplaced", [])
                    if m.get("reached_node") != ev.get("path")]
                if sr == "CLEAR":
                    n["stop_reason"] = None
            if sr == "MISPLACED":
                mis = traces[slug].setdefault("misplaced", [])
                entry = next((m for m in mis
                              if m.get("reached_node") == ev.get("path")), None)
                if entry is None:
                    mis.append({"reached_node": ev.get("path"),
                                # the fold retains the purpose when the decision
                                # omits it, so the record must too
                                "reached_node_purpose": ev.get("purpose") or n.get("purpose"),
                                "belongs_in": ev.get("belongs_in"),
                                "why": ev.get("why"), "resolution": None})
                else:
                    # a reroute is a later decision: the destination moves
                    entry.update({k: v for k, v in
                                  {"belongs_in": ev.get("belongs_in"),
                                   "reached_node_purpose": ev.get("purpose") or n.get("purpose"),
                                   "why": ev.get("why")}.items() if v})
            if before and ev.get("verdict") and before != ev["verdict"]:
                reversals.append({"what": ev["path"], "from": before,
                                  "to": ev["verdict"], "why": ev.get("why"),
                                  "at": ev.get("at")})

        elif k == "edge.add" and slug in traces:
            edges = traces[slug]["edges"]
            existing = next((e for e in edges
                             if e.get("from") == ev.get("from")
                             and e.get("to") == ev.get("to")
                             and e.get("kind") == ev.get("edge_kind", "calls")), None)
            if existing is None:
                edges.append({"from": ev.get("from"), "to": ev.get("to"),
                              "kind": ev.get("edge_kind", "calls"),
                              "seam_id": ev.get("seam")})
            elif ev.get("seam"):
                existing["seam_id"] = ev["seam"]

        elif k == "behavior.set" and slug in traces:
            b = _rec(traces[slug]["behaviors"], "id", ev.get("id"))
            _decide(b, ev, ("statement", "path", "symbol", "verdict", "status", "owned_by"))
            if ev.get("statement"):
                b["test_name"] = ev["statement"]   # principle 8b: one sentence
            if ev.get("behavior_kind"):
                b["kind"] = ev["behavior_kind"]
            if ev.get("requirement"):
                b.setdefault("requirement_ids", [])
                if ev["requirement"] not in b["requirement_ids"]:
                    b["requirement_ids"].append(ev["requirement"])

        elif k == "gate.record" and slug in traces:
            g = _rec(traces[slug]["gate_ledger"], "behavior_id", ev.get("id"))
            b = next((x for x in traces[slug]["behaviors"] if x.get("id") == ev.get("id")), None)
            g.update(path=(b or {}).get("path"), symbol=(b or {}).get("symbol"),
                     statement=ev.get("statement") or (b or {}).get("statement"),
                     red_evidence={"command": ev.get("cmd", ""), "failure": ev.get("red", "")},
                     checks_passed=ev.get("passed") or [],
                     checks_failed=ev.get("failed") or [], at=ev.get("at"))
            if b is not None:
                b["gate_passed"] = not ev.get("failed")
                b["status"] = "red" if ev.get("failed") else "gated"

        elif k == "order.set" and slug in traces:
            o = _rec(traces[slug]["ordered_change_set"], "path", ev.get("path"))
            _decide(o, ev, ("n", "symbol", "reason"))

        elif k == "term.set" and slug in models:
            t = _rec(models[slug]["glossary"], "term", ev.get("term"))
            _decide(t, ev, ("definition", "context", "provenance"))
            if ev.get("code"):
                t["code_terms"] = ev["code"]
            if ev.get("dead"):
                t["dead_aliases"] = ev["dead"]

        elif k == "own.set" and slug in models:
            bucket = ROLE_BUCKET.get(ev.get("role"))
            if bucket:
                rec = _rec(models[slug].setdefault(bucket, []), "name", ev.get("name"))
                _decide(rec, ev, ("purpose", "context"))
                # A generic `purpose` loses what makes each role meaningful, so
                # the field that carries the role's contract is filled too.
                field = ROLE_PURPOSE_FIELD.get(ev.get("role"))
                if field and ev.get("purpose"):
                    # assign, not setdefault: a revised purpose must not leave
                    # the role's own field describing the previous contract
                    rec[field] = ev["purpose"]
                if ev.get("role") == "read_model":
                    rec.setdefault("projected_from", [])
                    rec.setdefault("staleness", None)
                if ev.get("role") == "process_manager":
                    rec.setdefault("states", [])
                    rec.setdefault("triggers", [])
                    rec.setdefault("compensations", [])
                if ev.get("role") == "repository":
                    if ev.get("aggregate"):
                        rec["aggregate"] = ev["aggregate"]   # latest decision wins
                    rec.setdefault("aggregate", None)
                    rec.setdefault("style", "collection_oriented")
                if ev.get("role") == "entity":
                    # identity is the branded id TYPE; --aggregate names the
                    # aggregate this entity belongs to. Defaulting one from the
                    # other writes a plausible wrong value, which is worse than
                    # leaving it unset for the next decision to fill.
                    if ev.get("identity"):
                        rec["identity"] = ev["identity"]
                    rec.setdefault("identity", None)
                    rec.setdefault("transitions", [])
                    if ev.get("aggregate"):
                        rec["aggregate"] = ev["aggregate"]
                if ev.get("role") == "value_object":
                    rec.setdefault("makes_unrepresentable", ev.get("purpose"))
                if ev.get("invariant"):
                    inv = rec.setdefault("invariants", [])
                    if ev["invariant"] not in inv:
                        inv.append(ev["invariant"])
                if ev.get("role") == "application_service":
                    rec["owns_rules"] = False

        elif k == "ticket.close":
            ticket["status"] = "closed"
            ticket["closed_at_commit"] = ev.get("commit")

    if ticket is not None:
        ticket["reversals"] = reversals
    return ticket, traces, models


ROLE_PURPOSE_FIELD = {
    "read_model": "answers",
    "anti_corruption_layer": "translates",
    "value_object": "makes_unrepresentable",
}

ROLE_BUCKET = {
    "aggregate_root": "aggregates", "domain_service": "domain_services",
    "application_service": "application_services", "repository": "repositories",
    "process_manager": "process_managers", "read_model": "read_models",
    "anti_corruption_layer": "anti_corruption_layers",
    "entity": "entities", "value_object": "value_objects",
}


def rebuild(dd, ref):
    """Re-fold one ticket's log and rewrite every document it derives.

    Every filename component is validated here as well as at the CLI: a log
    written by an older build, or edited by hand, must not be able to steer a
    derived write outside `.design/`.
    """
    st.safe_ref(ref)
    events = st.read_log(dd, ref)
    ticket, traces, models = fold(events)
    if ticket is None:
        return None
    # Validate every filename component BEFORE the first write. Raising midway
    # through left the ticket on disk describing tasks whose snapshots were
    # never written.
    for slug in list(traces) + list(models):
        st.safe_slug(slug)
    st.write_json(Path(dd) / f"{ref}.json", ticket)
    for slug, tr in traces.items():
        st.write_json(Path(dd) / f"{ref}.{st.safe_slug(slug)}.trace.json", tr)
    for slug, m in models.items():
        st.write_json(Path(dd) / f"{ref}.{st.safe_slug(slug)}.model.json", m)
    return ticket


def rebuild_all(dd):
    return [rebuild(dd, ref) for ref in st.log_refs(dd)]


if __name__ == "__main__":
    dd = st.find_design_dir()
    if dd is None:
        sys.exit("no .design/ directory")
    rebuild_all(dd)
    print(f"rebuilt from {len(st.log_refs(dd))} log(s) in {dd}")
