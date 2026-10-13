#!/usr/bin/env python3
"""One runnable check for the .design/ toolchain.

Fails if the tree, the per-task graph, the index or the divergence report
break. No framework: `python3 test_design.py`.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLI = [sys.executable, str(HERE / "design.py")]


def run(cwd, *args, expect_ok=True):
    r = subprocess.run(CLI + list(args), cwd=cwd, capture_output=True, text=True)
    if expect_ok and r.returncode != 0:
        raise AssertionError(f"{' '.join(args)} failed:\n{r.stdout}\n{r.stderr}")
    if not expect_ok and r.returncode == 0:
        raise AssertionError(f"{' '.join(args)} should have failed but did not")
    return r


def check_spec_mirrors_code():
    """graph.json and the CLI must not drift apart.

    Every round of review so far has turned up at least one divergence of this
    shape - STOP_REASONS missing four of graph.json's stop conditions, roles
    with no purpose shape, routing that never gained the roles beside it. Those
    are mechanical, so they get asserted here rather than found by a reviewer.
    """
    sys.path.insert(0, str(HERE))
    import design, fold, json as _json
    g = _json.load(open(HERE.parent / "graph.json"))

    trace = next(p for p in g["phases"] if p["id"] == "trace")
    spec_stops = {c.split(":")[0] for c in trace["stop_conditions"]}
    cli_stops = set(design.STOP_REASONS)
    assert cli_stops == spec_stops, (
        f"stop reasons drifted:\n  only in graph.json: {sorted(spec_stops - cli_stops)}"
        f"\n  only in the CLI:   {sorted(cli_stops - spec_stops)}")

    cli_choices = set(design.STOP_REASON_CHOICES)
    assert cli_choices == spec_stops | {"CLEAR"}, (
        "the --stop-reason choices must be the stop conditions plus CLEAR, no more: "
        f"{sorted(cli_choices ^ (spec_stops | {'CLEAR'}))}")

    shapes = set(g["domain_schema"]["role_purpose_shapes"])
    roles = set(design.ROLES)
    assert shapes <= roles, f"roles with a purpose shape but not accepted: {sorted(shapes - roles)}"
    assert roles <= shapes, f"roles the CLI accepts with no purpose shape: {sorted(roles - shapes)}"

    rr = {k: v for k, v in g["domain_schema"]["role_routing"].items()
          if k not in ("why", "note")}
    routing = {v for v in rr.values() if v in shapes}
    assert shapes <= routing, f"roles nothing routes to: {sorted(shapes - routing)}"
    # every value is either a role or the single documented fallback - identified
    # by not being a role, not by guessing at its shape
    non_roles = {v for v in rr.values() if v not in shapes}
    assert len(non_roles) == 1, (
        "role_routing values must be roles, plus exactly one fallback; found "
        f"{len(non_roles)} non-role values: {sorted(non_roles)}")

    documented = set(g["tooling"]["commands"])
    implemented = set(re.findall(r'add\("([a-z_]+)"', open(HERE / "design.py").read()))
    assert documented == implemented, (
        f"commands drifted:\n  documented only: {sorted(documented - implemented)}"
        f"\n  implemented only: {sorted(implemented - documented)}")

    # evidence tiers: the ladder, the CLI's --evidence choices and the tier
    # annotations in every lang file must be one vocabulary. They were three.
    ladder = [t["name"] for t in g["evidence_tiers"]["ladder"]]
    cli_ev = set(design.EVIDENCE_TIERS)
    assert set(ladder) == cli_ev, (
        f"evidence tiers drifted:\n  only in graph.json: {sorted(set(ladder)-cli_ev)}"
        f"\n  only in the CLI:   {sorted(cli_ev-set(ladder))}")
    # Scan EVERY skill markdown file, and both spellings. Scoping this to
    # lang/*.md and `tier:` alone let two renamed names survive in tracing.md
    # as `evidence: grep` and `evidence: manual` - the guard missed the very
    # strays the rename introduced.
    skilldir = HERE.parent
    used = {m for f in list(skilldir.rglob("*.md")) + [skilldir / "graph.json"]
            for pat in (r'tier:\s*([a-z_-]+)', r'evidence:\s*([a-z_-]+)')
            for m in re.findall(pat, f.read_text())}
    used -= {"the", "command"}          # prose, not annotations
    stray = used - set(ladder)
    assert not stray, (
        f"skill files name evidence tiers that are not on the ladder: {sorted(stray)}. "
        "A hedged or renamed tier is the mood evidence_tiers.note exists to replace.")

    owner = set(fold.ROLE_BUCKET)
    assert owner <= shapes, f"own roles with no purpose shape: {sorted(owner - shapes)}"
    print("spec/code mirrors: stop reasons, roles, routing, commands, own roles, evidence tiers")


def check_connecting():
    """_connecting's three cases, asserted directly.

    Two rounds of review landed on this function - a cycle through one changed
    node pulling itself in, then quadratic behaviour on many changed nodes. The
    graph shapes are cheaper to assert here than to construct through the CLI.
    """
    sys.path.insert(0, str(HERE))
    from render_graph import _connecting
    cyc = {"c": [("x", "calls")], "x": [("y", "calls")], "y": [("c", "calls")]}
    assert _connecting(cyc, {"c"}, {"c", "x", "y"}) == set(), \
        "a cycle through one changed node is not a connector"
    path = {"a": [("m", "calls")], "m": [("n", "calls")], "n": [("b", "calls")]}
    assert _connecting(path, {"a", "b"}, {"a", "m", "n", "b"}) == {"m", "n"}, \
        "intermediates between two changed nodes must be kept"
    aside = {"a": [("m", "calls")], "m": [("b", "calls")],
             "p": [("q", "calls")], "q": [("p", "calls")]}
    assert _connecting(aside, {"a", "b"}, {"a", "m", "b", "p", "q"}) == {"m"}, \
        "an unrelated cycle must stay out of scope"
    print("connectors: cycle, path, unrelated cycle")


def check_accept_indicator():
    """The acceptance indicator must show the transition, not the red alone.

    It read only red_evidence, so a requirement stayed `accept ✗` forever once
    gated - including after it went green and closed. That line is the headline
    of the report and it was reporting failure on finished work.
    """
    sys.path.insert(0, str(HERE))
    import render_graph as rg
    def head(acceptance):
        t = {"requirements": [{"id": "R1", "statement": "s", "status": "done",
                               "acceptance": acceptance}],
             "current_requirement": "R1"}
        return rg.render_tree([], None, t, []).splitlines()[0]
    assert "accept —" in head({}), head({})
    assert "accept ✗" in head({"red_evidence": {"failure": "boom"}})
    assert "accept ✓" in head({"red_evidence": {"failure": "boom"},
                               "went_green_at": "2026-01-01T00:00:00Z"})
    assert "accept ✓ manual" in head({"manual_closure": {"who": "ops"}})
    print("accept indicator: —, ✗, ✓, ✓ manual")


def check_cycle_vs_shared():
    """A cycle and a shared node are different findings and different glyphs.

    The legend documents both; ↺ was unreachable, so every cycle rendered as
    `↩ (expanded above)` - which tells a reader the node has two parents when
    in fact the graph closes a loop.
    """
    sys.path.insert(0, str(HERE))
    import render_graph as rg
    nodes = {p: {"path": p, "verdict": "change", "purpose": "x"}
             for p in ("w", "x", "y", "z")}
    trace = {"nodes": list(nodes.values()), "behaviors": [],
             "edges": [{"from": "w", "to": "y", "kind": "calls"},
                       {"from": "x", "to": "y", "kind": "calls"},
                       {"from": "y", "to": "z", "kind": "calls"},
                       {"from": "z", "to": "x", "kind": "calls"}],
             "task_id": "T1", "task_slug": "t", "gate_ledger": [],
             "ordered_change_set": [], "misplaced": []}
    out = rg.render_tree([], None, None, [("t.json", trace)])
    assert "↺" in out, f"cycle not marked with the cycle glyph:\n{out}"
    assert "(cycle)" in out, out
    print("cycle vs shared: ↺ reachable")


def main():
    check_spec_mirrors_code()
    check_connecting()
    check_cycle_vs_shared()
    check_accept_indicator()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".git").mkdir()

        run(root, "init", "--ref", "partial-refunds", "--title", "partial refunds")
        dd = root / ".design"
        assert (dd / "partial-refunds.log.jsonl").exists(), "decision log not created"
        assert (dd / "partial-refunds.json").exists(), "ticket file not derived from the log"
        t = json.loads((dd / "partial-refunds.json").read_text())
        assert t["status"] == "open"
        assert t["requirements"] == [], "template placeholders leaked into state"

        # a task with no requirement has nothing to close
        run(root, "task", "--id", "T9", "--slug", "orphan", "--requirement", "R9",
            expect_ok=False)
        # ...and no work may start before the requirement gate is red
        run(root, "requirement", "--id", "R8", "--statement", "ungated requirement")
        run(root, "task", "--id", "T8", "--slug", "ungated", "--requirement", "R8",
            expect_ok=False)
        run(root, "requirement", "--id", "R8", "--status", "descoped",
            "--statement", "ungated requirement", expect_ok=False)   # no reason
        run(root, "requirement", "--id", "R8", "--status", "descoped",
            "--statement", "ungated requirement", "--why", "the printer is being replaced")
        run(root, "requirement", "--id", "R1",
            "--statement", "a partial refund below the balance succeeds")
        run(root, "acceptance", "--id", "R1", "--altitude", "http",
            "--cmd", "go test ./acceptance -run Refund",
            "--red", "expected 200 with status closed, got 422")
        run(root, "task", "--id", "T1", "--slug", "refund-handler",
            "--requirement", "R1", "--title", "refund handler")
        assert (dd / "partial-refunds.refund-handler.trace.json").exists()
        assert (dd / "partial-refunds.refund-handler.model.json").exists()

        # a verdict without a purpose is refused - principle 7
        run(root, "node", "--slug", "refund-handler", "--path", "order/service.go",
            "--verdict", "change", expect_ok=False)
        # a no_change verdict without a stop reason is refused - principle 3
        run(root, "node", "--slug", "refund-handler", "--path", "pkg/money.go",
            "--purpose", "represents money", "--verdict", "no_change", expect_ok=False)

        run(root, "node", "--slug", "refund-handler", "--path", "order/service.go",
            "--purpose", "protects the invariant that refunds never exceed balance",
            "--role", "aggregate_root", "--verdict", "change", "--depth", "0")
        run(root, "node", "--slug", "refund-handler", "--path", "http/handler.go",
            "--purpose", "translates HTTP into an application-service call",
            "--role", "handler", "--verdict", "change", "--depth", "-1")
        run(root, "node", "--slug", "refund-handler", "--path", "pkg/money.go",
            "--purpose", "makes an invalid amount unrepresentable",
            "--role", "value_object", "--verdict", "no_change",
            "--stop-reason", "ABSORBED", "--depth", "1")
        run(root, "edge", "--slug", "refund-handler",
            "--from", "http/handler.go", "--to", "order/service.go")
        run(root, "edge", "--slug", "refund-handler",
            "--from", "order/service.go", "--to", "pkg/money.go")

        run(root, "behavior", "--slug", "refund-handler", "--id", "B1",
            "--statement", "a refund above the balance is rejected and the order is untouched",
            "--path", "order/service.go", "--symbol", "RecordRefund",
            "--kind", "error", "--status", "specified", "--requirement", "R1")
        b = json.loads((dd / "partial-refunds.refund-handler.trace.json").read_text())["behaviors"][0]
        assert b["test_name"] == b["statement"], "behavior statement and test name must match"

        # the gate refuses without observed red evidence
        run(root, "gate", "--slug", "refund-handler", "--id", "B1", expect_ok=False)
        run(root, "gate", "--slug", "refund-handler", "--id", "B1",
            "--red", "expected InsufficientBalance, got <nil>", "--cmd", "go test ./order")

        out = run(root, "show").stdout
        for want in ["order/service.go", "http/handler.go", "★", "B1", "R1"]:
            assert want in out, f"tree missing {want!r}:\n{out}"
        assert "⊘" in out, f"absorbed node not marked:\n{out}"
        assert (dd / "partial-refunds.refund-handler.graph.md").exists(), "per-task graph not written"
        assert "mermaid" in (dd / "partial-refunds.refund-handler.graph.md").read_text()

        # a task with a trace but no captured vocabulary is flagged
        assert "no model snapshot" not in out, "snapshot exists; should not be flagged"

        # an application service owns no rules - principle 19
        run(root, "own", "--slug", "refund-handler", "--name", "RefundFlow",
            "--role", "application_service", "--invariant", "refunds cap at balance",
            expect_ok=False)

        # --- the log is the source, and reversals survive the fold ---
        run(root, "node", "--slug", "refund-handler", "--path", "pkg/money.go",
            "--verdict", "change", expect_ok=False)          # reversal without --why
        # a change verdict over a recorded stop must retract it explicitly
        run(root, "node", "--slug", "refund-handler", "--path", "pkg/money.go",
            "--verdict", "change", "--why", "x", expect_ok=False)
        run(root, "node", "--slug", "refund-handler", "--path", "pkg/money.go",
            "--verdict", "change", "--stop-reason", "ABSORBED", "--why", "x",
            expect_ok=False)
        run(root, "node", "--slug", "refund-handler", "--path", "pkg/money.go",
            "--verdict", "change", "--stop-reason", "CLEAR",
            "--why", "the amount type gains a currency field", "--evidence", "compiler")
        tr = json.loads((dd / "partial-refunds.refund-handler.trace.json").read_text())
        money = next(n for n in tr["nodes"] if n["path"] == "pkg/money.go")
        assert money["verdict"] == "change"
        assert len(money["decisions"]) >= 2, "earlier decision lost in the fold"
        assert any("superseded" in d for d in money["decisions"]), \
            "reversal not recorded as superseding"
        assert money["purpose"], "a later decision blanked an earlier field"
        assert money["stop_reason"] is None, "retracted stop still recorded"
        assert "DERIVED" in tr["_"], "derived file not marked as derived"

        logout = run(root, "log").stdout
        assert "reversals" in logout and "no_change -> change" in logout, \
            f"reversal not reported:\n{logout}"
        assert "the amount type gains a currency field" in logout

        # re-folding the same log must produce the same documents
        before = (dd / "partial-refunds.refund-handler.trace.json").read_text()
        run(root, "rebuild")
        after = json.loads((dd / "partial-refunds.refund-handler.trace.json").read_text())
        after.pop("updated_at", None)
        b = json.loads(before)
        b.pop("updated_at", None)
        assert after == b, "fold is not deterministic"

        run(root, "term", "--slug", "refund-handler", "--term", "Refund",
            "--definition", "money returned against a recorded order",
            "--code", "Refund,refund_records", "--dead", "Reversal")
        run(root, "own", "--slug", "refund-handler", "--name", "Order",
            "--role", "aggregate_root",
            "--invariant", "refunds never exceed the remaining balance")

        idx = (dd / "index.md").read_text()
        assert "Refund" in idx and "Order" in idx, f"index missing entries:\n{idx}"
        assert "⚠" not in idx, "no divergence expected with one snapshot"

        # a second task defining the same term differently must be reported
        run(root, "task", "--id", "T2", "--slug", "ledger-sync", "--requirement", "R1")
        run(root, "term", "--slug", "ledger-sync", "--term", "Refund",
            "--definition", "a ledger reversal entry")
        idx = (dd / "index.md").read_text()
        assert "Divergences to resolve" in idx, f"divergence not reported:\n{idx}"
        # the latest definition is the one most recently DECIDED, even when both
        # decisions land in the same second - the log's order settles the tie
        run(root, "term", "--slug", "refund-handler", "--term", "Refund",
            "--definition", "money returned, net of fees")
        idx = (dd / "index.md").read_text()
        head = [l for l in idx.splitlines() if l.startswith("- **Refund**")][0]
        assert "net of fees" in head, f"latest definition is not the newest: {head}"
        assert "a ledger reversal entry" in idx and "money returned" in idx

        # --green with no recorded red would close a check never observed failing
        run(root, "requirement", "--id", "R2",
            "--statement", "a refund is reflected in the ledger within one minute")
        run(root, "acceptance", "--id", "R2", "--green", expect_ok=False)
        run(root, "requirement", "--id", "R2", "--status", "descoped",
            "--statement", "a refund is reflected in the ledger within one minute",
            "--why", "the ledger SLA is a separate ticket")

        # a task slug that could escape .design/ is refused
        run(root, "task", "--id", "T8", "--slug", "../evil", "--requirement", "R1",
            expect_ok=False)

        # a revised ownership decision refreshes the role's own field
        run(root, "own", "--slug", "refund-handler", "--name", "RefundLedgerView",
            "--role", "read_model", "--purpose", "what finance sees this quarter")
        run(root, "own", "--slug", "refund-handler", "--name", "RefundLedgerView",
            "--role", "read_model", "--purpose", "every refund issued, for finance")
        m = json.loads((dd / "partial-refunds.refund-handler.model.json").read_text())
        rm = next(x for x in m["read_models"] if x["name"] == "RefundLedgerView")
        assert rm["answers"] == "every refund issued, for finance", \
            f"role field left stale on revision: {rm.get('answers')!r}"

        # every stop reason graph.json defines must be recordable - COMPLETE_DOWN
        # is the normal downstream leaf and was rejected by argparse
        run(root, "node", "--slug", "refund-handler", "--path", "pkg/leaf.go",
            "--purpose", "formats a currency string", "--verdict", "no_change",
            "--stop-reason", "COMPLETE_DOWN", "--depth", "2")

        # MISPLACED without a destination is incomplete (principle 7)
        run(root, "node", "--slug", "refund-handler", "--path", "notify/mailer.go",
            "--purpose", "sends transactional email", "--verdict", "no_change",
            "--stop-reason", "MISPLACED", expect_ok=False)
        run(root, "node", "--slug", "refund-handler", "--path", "notify/mailer.go",
            "--purpose", "sends transactional email", "--verdict", "no_change",
            "--stop-reason", "MISPLACED", "--belongs-in", "notify/dispatcher.go")
        tr = json.loads((dd / "partial-refunds.refund-handler.trace.json").read_text())
        assert any(m["reached_node"] == "notify/mailer.go" and
                   m["belongs_in"] == "notify/dispatcher.go" for m in tr["misplaced"]), \
            "MISPLACED not recorded in the trace"
        run(root, "node", "--slug", "refund-handler", "--path", "notify/mailer.go",
            "--verdict", "no_change", "--stop-reason", "MISPLACED",
            "--belongs-in", "notify/outbox.go", "--why", "dispatcher was the wrong home")
        tr = json.loads((dd / "partial-refunds.refund-handler.trace.json").read_text())
        m = next(x for x in tr["misplaced"] if x["reached_node"] == "notify/mailer.go")
        assert m["belongs_in"] == "notify/outbox.go", \
            f"reroute kept the stale destination: {m['belongs_in']!r}"
        assert len([x for x in tr["misplaced"]
                    if x["reached_node"] == "notify/mailer.go"]) == 1, "duplicate entry"
        out = run(root, "show").stdout
        assert "⊗" in out, f"misplaced glyph unreachable:\n{out}"

        # a repository must name its one aggregate, and a revision must move it
        run(root, "own", "--slug", "refund-handler", "--name", "OrderRepo",
            "--role", "repository", expect_ok=False)
        run(root, "own", "--slug", "refund-handler", "--name", "OrderRepo",
            "--role", "repository", "--aggregate", "Ordr")
        run(root, "own", "--slug", "refund-handler", "--name", "OrderRepo",
            "--role", "repository", "--aggregate", "Order", "--why", "typo")
        m = json.loads((dd / "partial-refunds.refund-handler.model.json").read_text())
        repo = next(x for x in m["repositories"] if x["name"] == "OrderRepo")
        assert repo["aggregate"] == "Order", \
            f"revision kept the first aggregate: {repo['aggregate']!r}"

        # the view budget must never trim a changed node out of the tree
        for i in range(40):
            run(root, "node", "--slug", "refund-handler", "--path", f"pkg/filler{i}.go",
                "--purpose", "filler", "--verdict", "no_change",
                "--stop-reason", "ABSORBED", "--depth", "3")
            run(root, "edge", "--slug", "refund-handler",
                "--from", "order/service.go", "--to", f"pkg/filler{i}.go")
        out = run(root, "show").stdout
        assert "order/service.go" in out and "http/handler.go" in out, \
            f"a changed node was trimmed by the view budget:\n{out}"
        assert "trimmed" in out, f"budget did not engage:\n{out}"
        # the omission line promises a view; that view must exist and show them
        full = run(root, "show", "--full").stdout
        assert "pkg/filler7.go" in full, \
            f"--full did not draw an omitted node:\n{full[:600]}"
        assert "to see them" in out, "omission line does not name the command"

        # an unresolvable --belongs-in is refused; an untraced real path is not
        run(root, "node", "--slug", "refund-handler", "--path", "notify/sms.go",
            "--purpose", "sends SMS", "--verdict", "no_change",
            "--stop-reason", "MISPLACED", "--belongs-in", "typo", expect_ok=False)
        run(root, "node", "--slug", "refund-handler", "--path", "notify/sms.go",
            "--purpose", "sends SMS", "--verdict", "no_change",
            "--stop-reason", "MISPLACED", "--belongs-in", "new node: notify/sender.go")

        # a manual closure may not be combined with an observation of the check
        run(root, "acceptance", "--id", "R1", "--manual-owner", "ops",
            "--manual-evidence", "a screenshot", "--red", "boom", expect_ok=False)

        # CLEAR cannot retract the stop a no_change verdict requires - including
        # when the verdict is carried over rather than restated
        run(root, "node", "--slug", "refund-handler", "--path", "pkg/filler0.go",
            "--verdict", "no_change", "--stop-reason", "CLEAR", expect_ok=False)
        run(root, "node", "--slug", "refund-handler", "--path", "pkg/filler0.go",
            "--stop-reason", "CLEAR", expect_ok=False)
        run(root, "node", "--slug", "refund-handler", "--path", "pkg/filler0.go",
            "--verdict", "change", "--stop-reason", "CLEAR", "--why", "it does change")

        # changing the acceptance command invalidates evidence for the old one
        run(root, "acceptance", "--id", "R1", "--cmd", "go test ./acceptance -run Refund2",
            "--red", "expected 200, got 500")
        t = json.loads((dd / "partial-refunds.json").read_text())
        acc = next(x for x in t["requirements"] if x["id"] == "R1")["acceptance"]
        assert acc["red_evidence"]["command"] == "go test ./acceptance -run Refund2", \
            f"red evidence still names the old command: {acc['red_evidence']}"

        # a requirement that cannot be automated closes on a named human's evidence
        run(root, "requirement", "--id", "R7",
            "--statement", "the printed invoice is legible on thermal paper")
        run(root, "acceptance", "--id", "R7", "--manual-owner", expect_ok=False)
        run(root, "acceptance", "--id", "R7", "--manual-owner", "ops on-call",
            "--manual-evidence", "a photo of a printed invoice attached to the ticket")
        t = json.loads((dd / "partial-refunds.json").read_text())
        r7 = next(x for x in t["requirements"] if x["id"] == "R7")
        assert r7["acceptance"]["manual_closure"]["who"] == "ops on-call"
        assert r7["acceptance"]["automatable"] is False
        # a manual requirement may open a task without automated red evidence
        run(root, "task", "--id", "T7", "--slug", "invoice-print", "--requirement", "R7")
        # a later automated observation retracts the manual closure, so a
        # failure after one cannot be ignored by close
        run(root, "acceptance", "--id", "R7", "--cmd", "make print-test",
            "--red", "the barcode smears at 200dpi")
        t = json.loads((dd / "partial-refunds.json").read_text())
        a7 = next(x for x in t["requirements"] if x["id"] == "R7")["acceptance"]
        assert "manual_closure" not in a7, \
            "a later observation left the manual closure standing"
        assert a7["automatable"] is True
        # switching R7 to automated means it needs a behavior like any other
        run(root, "behavior", "--slug", "invoice-print", "--id", "B20",
            "--statement", "the barcode scans at 200dpi", "--status", "specified",
            "--requirement", "R7", "--path", "print/invoice.go", "--symbol", "Render")
        run(root, "gate", "--slug", "invoice-print", "--id", "B20",
            "--red", "barcode unreadable at 200dpi", "--cmd", "make print-test")
        run(root, "behavior", "--slug", "invoice-print", "--id", "B20", "--status", "green",
            "--statement", "the barcode scans at 200dpi")
        run(root, "requirement", "--id", "R7", "--status", "done",
            "--statement", "the printed invoice is legible on thermal paper")
        run(root, "close", expect_ok=False)          # red, no green -> refused
        run(root, "acceptance", "--id", "R7", "--green")

        # --green may not reuse red evidence from a different command
        run(root, "acceptance", "--id", "R1", "--cmd", "go test ./other", "--green",
            expect_ok=False)

        # a gate whose checks FAILED is not a passed gate
        run(root, "behavior", "--slug", "ledger-sync", "--id", "B12", "--status", "specified",
            "--statement", "a reversal is written when the card refund fails")
        run(root, "gate", "--slug", "ledger-sync", "--id", "B12",
            "--red", "no reversal written", "--failed", "G3,G7")
        run(root, "behavior", "--slug", "ledger-sync", "--id", "B12", "--status", "green",
            "--statement", "a reversal is written when the card refund fails",
            expect_ok=False)
        run(root, "gate", "--slug", "ledger-sync", "--id", "B12",
            "--red", "no reversal written", "--passed", "G1,G2")
        run(root, "behavior", "--slug", "ledger-sync", "--id", "B12", "--status", "green",
            "--statement", "a reversal is written when the card refund fails")

        # --green may not change altitude or harness either, nor supply one the
        # red never had
        run(root, "acceptance", "--id", "R1", "--altitude", "cli", "--green",
            expect_ok=False)
        run(root, "acceptance", "--id", "R1", "--harness", "playwright", "--green",
            expect_ok=False)

        # a gate proves the behavior as stated; restating it needs a fresh red
        run(root, "behavior", "--slug", "ledger-sync", "--id", "B12", "--status", "green",
            "--statement", "a reversal is written whenever the card refund fails",
            expect_ok=False)

        # an entity's identity is its id type, not the aggregate it belongs to
        run(root, "own", "--slug", "refund-handler", "--name", "RefundLine",
            "--role", "entity", "--aggregate", "Order", "--purpose", "one line of a refund")
        m = json.loads((dd / "partial-refunds.refund-handler.model.json").read_text())
        ent = next(x for x in m["entities"] if x["name"] == "RefundLine")
        assert ent["aggregate"] == "Order"
        assert ent["identity"] is None, \
            f"identity was defaulted from the aggregate: {ent['identity']!r}"
        run(root, "own", "--slug", "refund-handler", "--name", "RefundLine",
            "--role", "entity", "--identity", "RefundLineId")
        m = json.loads((dd / "partial-refunds.refund-handler.model.json").read_text())
        ent = next(x for x in m["entities"] if x["name"] == "RefundLine")
        assert ent["identity"] == "RefundLineId" and ent["aggregate"] == "Order"

        # a descoped requirement is not work to open a task against
        run(root, "task", "--id", "T6", "--slug", "descoped-work", "--requirement", "R8",
            expect_ok=False)

        # a behavior may not claim a requirement that does not exist
        run(root, "behavior", "--slug", "refund-handler", "--id", "B99",
            "--statement", "dangling", "--requirement", "R999", expect_ok=False)

        # re-recording an edge with a different kind is refused, not dropped
        run(root, "edge", "--slug", "refund-handler",
            "--from", "http/handler.go", "--to", "order/service.go",
            "--kind", "provisions", expect_ok=False)
        # ...and repeating the same kind is a harmless no-op
        run(root, "edge", "--slug", "refund-handler",
            "--from", "http/handler.go", "--to", "order/service.go", "--kind", "calls")

        # two nodes may not share one position in the edit sequence
        run(root, "order", "--slug", "refund-handler", "--path", "order/service.go",
            "--n", "1", "--reason", "aggregate first")
        run(root, "order", "--slug", "refund-handler", "--path", "http/handler.go",
            "--n", "1", "--reason", "clash", expect_ok=False)
        run(root, "order", "--slug", "refund-handler", "--path", "http/handler.go",
            "--n", "2", "--reason", "caller after")

        # a skipped phase is recorded, not silently absent
        run(root, "phase", "cross", "--skipped", "no seam on the path")
        t = json.loads((dd / "partial-refunds.json").read_text())
        assert any(x["phase"] == "cross" for x in t["skipped_phases"]), \
            "skipped phase not recorded"
        run(root, "phase", "cross", "--skipped", "the seam is internal, not crossed")
        t = json.loads((dd / "partial-refunds.json").read_text())
        cross = [x for x in t["skipped_phases"] if x["phase"] == "cross"]
        assert len(cross) == 1 and cross[0]["why"] == "the seam is internal, not crossed", \
            f"corrected skip reason not applied: {cross}"

        # a decision naming an unknown task must be refused, not silently dropped
        for bad in (["behavior", "--slug", "nope", "--id", "B9", "--statement", "x"],
                    ["edge", "--slug", "nope", "--from", "a", "--to", "b"],
                    ["phase", "trace", "--slug", "nope"],
                    ["term", "--slug", "nope", "--term", "X", "--definition", "y"]):
            run(root, *bad, expect_ok=False)

        # a ref that could escape .design/ or confuse task_key is refused
        run(root, "init", "--ref", "../evil", expect_ok=False)
        run(root, "init", "--ref", "ENG.1", expect_ok=False)

        # re-creating a task must not wipe what it already recorded
        run(root, "task", "--id", "T1", "--slug", "refund-handler", "--requirement", "R1")
        tr = json.loads((dd / "partial-refunds.refund-handler.trace.json").read_text())
        assert any(n["path"] == "order/service.go" for n in tr["nodes"]), \
            "duplicate task.create erased the trace"
        assert tr["behaviors"], "duplicate task.create erased the behaviors"

        # a damaged log line must fail loudly rather than fold around it
        log = dd / "partial-refunds.log.jsonl"
        good = log.read_text()
        log.write_text(good + "{not json\n")
        r = run(root, "rebuild", expect_ok=False)
        assert "not valid JSON" in (r.stdout + r.stderr), \
            f"damaged log folded silently:\n{r.stdout}{r.stderr}"
        log.write_text(good)

        # close refuses while a requirement is open
        run(root, "close", expect_ok=False)
        run(root, "requirement", "--id", "R1",
            "--statement", "a partial refund below the balance succeeds", "--status", "done")
        # close refuses with red evidence but no recorded green transition
        run(root, "close", expect_ok=False)
        run(root, "acceptance", "--id", "R1", "--green")

        # ...and, with acceptance now fully green, still refuses on an ungated
        # behavior alone - so this asserts the ungated rule and nothing else
        run(root, "behavior", "--slug", "ledger-sync", "--id", "B9", "--status", "todo",
            "--statement", "a ledger entry is written for every recorded refund")
        r = run(root, "close", expect_ok=False)
        assert "never gated" in (r.stdout + r.stderr), \
            f"close refused for the wrong reason:\n{r.stdout}{r.stderr}"
        # a status is a claim; the gate ledger is the evidence, so green needs one
        run(root, "behavior", "--slug", "ledger-sync", "--id", "B9", "--status", "green",
            "--statement", "a ledger entry is written for every recorded refund",
            expect_ok=False)
        run(root, "gate", "--slug", "ledger-sync", "--id", "B9",
            "--red", "expected a ledger entry, found none", "--cmd", "go test ./ledger")
        run(root, "behavior", "--slug", "ledger-sync", "--id", "B9", "--status", "green",
            "--statement", "a ledger entry is written for every recorded refund")

        # a check that regresses red after green retracts the transition
        run(root, "acceptance", "--id", "R1", "--red", "flaked on the ledger assertion")
        t = json.loads((dd / "partial-refunds.json").read_text())
        acc = next(x for x in t["requirements"] if x["id"] == "R1")["acceptance"]
        assert "went_green_at" not in acc, "a regression kept the green transition"
        run(root, "close", expect_ok=False)
        run(root, "acceptance", "--id", "R1", "--green")

        # a later stop supersedes a MISPLACED finding, and the entry goes with it
        run(root, "node", "--slug", "refund-handler", "--path", "notify/mailer.go",
            "--verdict", "no_change", "--stop-reason", "ABSORBED",
            "--why", "the dispatcher change absorbed it after all")
        tr = json.loads((dd / "partial-refunds.refund-handler.trace.json").read_text())
        assert not any(m["reached_node"] == "notify/mailer.go" for m in tr["misplaced"]), \
            "a superseded MISPLACED entry survived"

        # a requirement marked done that no behavior satisfies does not close.
        # Placed here deliberately: every other requirement is already settled, so
        # the refusal can only come from the missing behavior.
        run(root, "requirement", "--id", "R5", "--statement", "an empty requirement")
        run(root, "acceptance", "--id", "R5", "--cmd", "go test ./r5", "--red", "nope")
        run(root, "acceptance", "--id", "R5", "--green")
        run(root, "requirement", "--id", "R5", "--statement", "an empty requirement",
            "--status", "done")
        r = run(root, "close", expect_ok=False)
        assert "no behavior satisfies" in (r.stdout + r.stderr), \
            f"close accepted a requirement with no behaviors:\n{r.stdout}{r.stderr}"
        run(root, "requirement", "--id", "R5", "--statement", "an empty requirement",
            "--status", "descoped", "--why", "folded into R1")

        run(root, "close")
        assert json.loads((dd / "partial-refunds.json").read_text())["status"] == "closed"
        assert (dd / "partial-refunds.refund-handler.model.json").exists(), "snapshots must stay in place"

        # a closed ticket must not accept new decisions
        run(root, "node", "--slug", "refund-handler", "--path", "late.go",
            "--purpose", "added after close", "--verdict", "change", expect_ok=False)
        # ...but reads still work
        run(root, "log")

    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
