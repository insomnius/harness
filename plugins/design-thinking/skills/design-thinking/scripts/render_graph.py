#!/usr/bin/env python3
"""Render .design/ state as a status tree and a Mermaid diagram.

A pure function of state on disk: two agents rendering the same state produce
the same view. Nothing here decides anything - it draws what the state says.

Writes one .design/<ref>.<task-slug>.graph.md per task and one derived
.design/index.md across every snapshot. Prints the tree to stdout. Run by the
PostToolUse hook on every write under .design/, and by design.py after every
mutation - so the index is regenerated too often to ever be stale.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import design_state as st  # noqa: E402
import workflow as wf  # noqa: E402

VIEW_BUDGET = 28

EDGE_GLYPH = {
    "calls": "→", "imports": "→",
    "invokes": "⋯>",
    "requests": "⇉", "publishes": "⇉", "subscribes": "⇉",
    "reads_writes": "⇄",
    "provisions": "⊢",
}
DONE, DOING, TODO = "✓", "◐", "○"
ABSORBED, UNSURE, MISPLACED, DRIFT = "⊘", "?", "⊗", "⚠"

LEGEND = (
    "✓ done · ◐ doing · ○ todo · ⊘ absorbed · ? unsure · "
    "⊗ misplaced · ⚠ drift · — not gated\n"
    "→ calls · ⋯> invokes · ⇉ requests · ⇄ reads/writes · "
    "⊢ provisions · ↩ shared · ↺ cycle"
)


def _idx(trace):
    """Index one trace file for lookup by node path."""
    nodes = {n["path"]: n for n in trace.get("nodes", []) if n.get("path")}
    behaviors = {}
    for b in trace.get("behaviors", []):
        behaviors.setdefault(b.get("path", ""), []).append(b)
    order = {}
    for o in trace.get("ordered_change_set", []):
        if o.get("path"):
            order.setdefault(o["path"], o.get("n"))
    misplaced = {m.get("reached_node") for m in trace.get("misplaced", []) if m.get("reached_node")}
    gated = set()
    for path, items in behaviors.items():
        if path and items and all(not wf.gate_problem(b, trace.get("gate_ledger", [])) for b in items):
            gated.add(path)
    adj = {}
    for e in trace.get("edges", []):
        f, t = e.get("from"), e.get("to")
        if f and t:
            adj.setdefault(f, []).append((t, e.get("kind", "calls")))
    return dict(nodes=nodes, behaviors=behaviors, order=order,
                misplaced=misplaced, gated=gated, adj=adj)


def node_glyph(node, ix):
    path = node.get("path", "")
    if path in ix["misplaced"] or node.get("stop_reason") == "MISPLACED":
        return MISPLACED
    drift = (node.get("drift") or {}).get("outcome")
    if drift and drift not in ("not_checked", "contract_intact"):
        return DRIFT
    verdict = node.get("verdict")
    if verdict == "unsure":
        return UNSURE
    if verdict == "no_change":
        return ABSORBED
    bs = ix["behaviors"].get(path, [])
    if bs:
        states = [b.get("status") for b in bs]
        if all(s == "green" for s in states):
            return DONE
        if any(s in ("red", "gated", "green", "specified") for s in states):
            return DOING
    passes = [p for s in node.get("symbols", []) for p in (s.get("passes") or {}).values()]
    if passes and all(p == "done" for p in passes):
        return DONE
    if passes and any(p == "done" for p in passes):
        return DOING
    return TODO


def behavior_glyph(b):
    return {"green": DONE, "gated": DOING, "red": DOING,
            "specified": DOING}.get(b.get("status"), TODO)


def in_scope(ix):
    """The changed subgraph plus one hop of absorption frontier.

    Everything else traced and unaffected is omitted, not collapsed - the
    absorbed set only grows, and spending lines on it trains the reader to
    skim.
    """
    nodes = ix["nodes"]
    changed = {p for p, n in nodes.items()
               if n.get("verdict") in ("change", "unsure") or p in ix["misplaced"]}
    keep = set(changed)
    # one hop out from every changed node, both directions - the absorption
    # frontier that shows where the change stopped
    for p in changed:
        for t, _ in ix["adj"].get(p, []):
            keep.add(t)
        for src, outs in ix["adj"].items():
            if any(t == p for t, _ in outs):
                keep.add(src)
    # ...plus every node on a path BETWEEN two changed nodes. Without this a
    # change set spanning three hops renders as disconnected fragments and the
    # call chain - the thing the tree exists to show - is lost.
    if len(changed) > 1:
        # Connectors only mean something between two distinct changed nodes. With
        # one, a cycle through it makes it its own endpoint and drags the whole
        # cycle into the view.
        keep |= _connecting(ix["adj"], changed, set(nodes))
    keep &= set(nodes)
    return keep or set(nodes), changed


def _connecting(adj, changed, universe):
    """Nodes on a directed path from one changed node to a DIFFERENT changed node.

    Two multi-source sweeps, each labelling a node with up to two distinct
    changed endpoints - two is all it takes to know a differing pair exists.
    Intersecting reachability per ordered pair was quadratic in the number of
    changed nodes; this is O(V+E) with a constant factor of two.
    """
    fwd = {src: [t for t, _ in outs] for src, outs in adj.items()}
    rev = {}
    for src, outs in adj.items():
        for t, _ in outs:
            rev.setdefault(t, []).append(src)

    def sweep(edges):
        """node -> up to two distinct changed nodes that reach it along `edges`."""
        label = {c: {c} for c in changed}
        stack = list(changed)
        while stack:
            n = stack.pop()
            for nxt in edges.get(n, ()):
                if nxt not in universe:
                    continue
                have = label.setdefault(nxt, set())
                if len(have) >= 2:
                    continue
                merged = have | label[n]
                if len(merged) > len(have):
                    label[nxt] = set(list(merged)[:2])
                    stack.append(nxt)
        return label

    downstream_of = sweep(fwd)      # which changed nodes reach this one
    upstream_of = sweep(rev)        # which changed nodes this one reaches

    out = set()
    for n in universe:
        if n in changed:
            continue
        srcs, dsts = downstream_of.get(n), upstream_of.get(n)
        if not srcs or not dsts:
            continue
        # a connector needs a source and a destination that differ
        if len(srcs | dsts) > 1:
            out.add(n)
    return out


def roots(ix, keep):
    """Entrypoint-most nodes: no in-edge from inside the kept set."""
    has_parent = set()
    for src, outs in ix["adj"].items():
        if src not in keep:
            continue
        for t, _ in outs:
            if t in keep:
                has_parent.add(t)
    rs = [p for p in keep if p not in has_parent]
    if not rs:  # every node has a parent -> pure cycle; seed the most negative depth
        rs = [min(keep, key=lambda p: ix["nodes"][p].get("depth") or 0)]
    return sorted(rs, key=lambda p: (ix["nodes"][p].get("depth") or 0, p))


def render_tree(models, tpath, ticket, traces, level=2, full=False):
    out = []
    if ticket:
        reqs = ticket.get("requirements", [])
        cur = ticket.get("current_requirement")
        r = next((x for x in reqs if x.get("id") == cur), reqs[0] if reqs else None)
        if r:
            # The acceptance indicator is the headline of the report, so it has
            # to show the TRANSITION, not merely that a red was once recorded:
            # green once it went green, ✗ while red evidence stands unanswered,
            # ✓ for a manual closure, — when nothing has been observed yet.
            accept = r.get("acceptance") or {}
            manual = accept.get("manual_closure") or {}
            if accept.get("went_green_at"):
                accs = "✓"
            elif (accept.get("red_evidence") or {}).get("failure"):
                accs = "✗"
            elif manual.get("who"):
                accs = "✓ manual"
            else:
                accs = "—"
            g = {"done": DONE, "blocked": DRIFT}.get(r.get("status"), DOING)
            out.append(f"{r['id']} {r.get('statement','')[:52]:<52} {g}  "
                       f"turn {r.get('turns',0)} · accept {accs}")

    for tf, trace in traces:
        ix = _idx(trace)
        keep, changed = in_scope(ix)
        if full:
            keep = set(ix["nodes"])       # every traced node, not just the delta
        tid = trace.get("task_id", "T?")
        bs = [b for b in trace.get("behaviors", [])]
        ndone = sum(1 for b in bs if b.get("status") == "green")
        tg = DONE if bs and ndone == len(bs) else (DOING if ndone else TODO)
        out.append(f"└─ {tid} {trace.get('task_slug',''):<44} {tg}  "
                   f"{ndone}/{len(bs)} behaviors")
        if not ix["nodes"]:
            # The task exists and has no trace yet. Saying so beats omitting it.
            out.append(f"   (no nodes traced yet · phase {trace.get('current_phase','?')})")
            continue

        seen, lines = set(), []   # lines are (text, belongs_to_changed_node)
        stack = [(p, 1, None, ()) for p in roots(ix, keep)]
        while stack:
            path, ind, kind, ancestors = stack.pop(0)
            n = ix["nodes"].get(path)
            if n is None:
                continue
            pad = "   " * ind
            glyph = EDGE_GLYPH.get(kind, "→") if kind else ""
            if path in ancestors:
                # back-edge onto this node's own chain: a cycle, never followed.
                # Distinct from a shared node below - a cycle is structural, a
                # shared node is a contract that two parents depend on.
                lines.append((f"{pad}↺ {path} (cycle)", path in changed))
                continue
            if path in seen:
                lines.append((f"{pad}↩ {path} (expanded above)", path in changed))
                continue
            seen.add(path)
            d = n.get("depth")
            dl = f"d{d:+d}" if isinstance(d, int) and d else "d0"
            star = " ★" if d == 0 else ""
            num = ix["order"].get(path)
            nm = f"#{num}" if num else "  "
            gate = "gate ✓" if path in ix["gated"] else "gate —"
            head = f"{pad}{glyph + ' ' if glyph else ''}{path}"
            lines.append((f"{head:<48} {dl}{star} {nm} {node_glyph(n, ix)}  {gate}",
                          "header" if path in changed else False))
            if level >= 3 or path in changed:
                bs = ix["behaviors"].get(path, [])
                by_sym = {}
                for sym in n.get("symbols", []):
                    if sym.get("symbol"):
                        by_sym[sym["symbol"]] = sym
                for b in bs:  # a behavior can name a symbol the node never recorded
                    by_sym.setdefault(b.get("symbol") or "", {})
                for name, sym in by_sym.items():
                    glyphs = " ".join(f"{b['id']}{behavior_glyph(b)}"
                                      for b in bs if (b.get("symbol") or "") == name)
                    label = name or "(node-level)"
                    lines.append((f"{pad}   │  {label:<28} {glyphs}", path in changed))
                    if level >= 4 or path in changed:
                        for b in bs:
                            contract = b.get("contract") or {}
                            if (b.get("symbol") or "") == name and contract:
                                lines.append((f"{pad}   │  {b['id']} A: {contract['A']} · "
                                              f"{contract['cardinality']} · E: {contract['E']} · R: {contract['R']}",
                                              path in changed))
                    ch = sym.get("channels") or {}
                    flow = (ch.get("A") or {}).get("flow") or []
                    if flow and (level >= 4 or path in changed):
                        lines.append((
                            f"{pad}   │  A: {'→'.join(flow)} · "
                            f"{ch.get('cardinality','?')} · "
                            f"{len(ch.get('E') or [])}E · {len(ch.get('R') or [])}R",
                            path in changed))
            for t, k in ix["adj"].get(path, []):
                if t in keep:
                    stack.insert(0, (t, ind + 1, k, ancestors + (path,)))

        omitted = len(ix["nodes"]) - len(seen)
        if len(lines) > VIEW_BUDGET and not full:
            # --full is the escape hatch the omission line points at, so the
            # budget must not re-hide what it promised to show.
            # Never trim a changed node out of the view: the node in motion is
            # the one thing that must not be the casualty of the budget. Drop
            # absorbed and connector lines first, oldest last.
            # Only the changed nodes' HEADER lines are unconditional. Their
            # behavior and channel rows are trimmable, or one busy node alone
            # blows past the budget and the cap means nothing.
            must = [i for i, (_, chg) in enumerate(lines) if chg == "header"]
            room = max(VIEW_BUDGET - len(must), 0)
            rest = [i for i, (_, chg) in enumerate(lines) if chg != "header"]
            rest.sort(key=lambda i: 0 if lines[i][1] else 1)   # changed detail first
            optional = rest[:room]
            keep = sorted(set(must) | set(optional))
            dropped = len(lines) - len(keep)
            lines = [lines[i] for i in keep]
            if dropped:
                lines.append((f"   ⊕ {dropped} absorbed/connector lines trimmed "
                              f"(view budget {VIEW_BUDGET})", False))
        out += [t for t, _ in lines]
        if omitted > 0:
            out.append(f"   ⊕ {omitted} nodes traced, unaffected "
                       "(`design.py show --full` to see them)")

    have = {st.task_key(p)[1] for p, _ in models}
    missing = [trace.get("task_slug") for _, trace in traces
               if trace.get("task_slug") and trace.get("task_slug") not in have]
    if missing:
        out.append("")
        out.append(f"⚠ no model snapshot for: {', '.join(missing)} — "
                   "the task traced a graph without naming what flows through it")
    return "\n".join(out)


def render_mermaid(ticket, traces):
    lines = ["```mermaid", "graph TD"]
    style = {"change": "fill:#fde68a,stroke:#b45309",
             "no_change": "fill:#e5e7eb,stroke:#9ca3af",
             "unsure": "fill:#fecaca,stroke:#b91c1c"}
    ids, seen = {}, 0
    for _, trace in traces:
        ix = _idx(trace)
        keep, _ = in_scope(ix)
        for p in sorted(keep):
            n = ix["nodes"][p]
            seen += 1
            nid = f"n{seen}"
            ids[p] = nid
            num = ix["order"].get(p)
            label = f"{'#' + str(num) + ' ' if num else ''}{p}"
            lines.append(f'  {nid}["{label}<br/><i>{(n.get("role") or "")}</i>"]')
            lines.append(f"  style {nid} {style.get(n.get('verdict'), style['no_change'])}")
        for src, outs in ix["adj"].items():
            for t, k in outs:
                if src in ids and t in ids:
                    lines.append(f"  {ids[src]} -->|{k}| {ids[t]}")
    lines.append("```")
    return "\n".join(lines)


def build_index(dd):
    """Derived recall across every model snapshot in the directory.

    Never hand-maintained, regenerated on every write, so it cannot drift.
    Where two snapshots define one term differently that is reported as a
    divergence - a finding, not a conflict to silently resolve.
    """
    dd, snaps = st.load_all_snapshots(dd)
    if dd is None:
        return None
    terms, owners = {}, {}
    # NOT by the file's updated_at: rebuild() rewrites every snapshot on every
    # append, so those timestamps say when the fold last ran, not when the term
    # was decided. Each entry carries its own decision time; order by that.
    for path, m in snaps:
        ref, slug = st.task_key(path)
        origin = f"{ref}.{slug}"
        for g in m.get("glossary") or []:
            t = (g.get("term") or "").strip()
            if not t or t.startswith("<"):
                continue
            # (timestamp, log line). Timestamps are second-resolution, so two
            # decisions in the same second tied and broke alphabetically by task
            # name - the log's line number is the strict order that settles it.
            decs = g.get("decisions") or []
            decided = (max((d.get("at") or "") for d in decs) if decs else "",
                       max((d.get("n") or 0) for d in decs) if decs else 0)
            terms.setdefault(t, []).append((origin, (g.get("definition") or "").strip(),
                                            g.get("context") or "", decided))
        for kind in ("aggregates", "domain_services", "application_services",
                     "repositories", "process_managers", "read_models"):
            for item in m.get(kind) or []:
                n = (item.get("name") or "").strip()
                if n and not n.startswith("<"):
                    owners.setdefault(n, []).append((origin, kind))

    lines = ["# Design index", "",
             "Derived from every `*.model.json` snapshot. Regenerated on every write —",
             "do not edit. A divergence is a finding: two tasks understood one term",
             "differently, and the disagreement is the information.", "",
             f"{len(snaps)} snapshot(s).", "", "## Glossary", ""]
    divergences = []
    for t in sorted(terms):
        entries = sorted(terms[t], key=lambda e: (e[3], e[0]))
        defs = {d for _, d, _, _ in entries if d}
        latest = entries[-1]      # latest by when the term was decided   # newest, by the snapshot ordering above
        lines.append(f"- **{t}** — {latest[1] or '(undefined)'}  "
                     f"<sub>{latest[0]}</sub>")
        if len(defs) > 1:
            divergences.append((t, entries))
            lines.append(f"  - ⚠ {len(defs)} differing definitions across "
                         f"{len(entries)} snapshots")
            for origin, d, _, _ in entries:
                lines.append(f"    - `{origin}`: {d or '(undefined)'}")
    if not terms:
        lines.append("_no terms captured yet_")

    lines += ["", "## Who owns what", ""]
    for n in sorted(owners):
        kinds = sorted({k for _, k in owners[n]})
        origins = ", ".join(sorted({o for o, _ in owners[n]}))
        flag = " ⚠ role disagreement" if len(kinds) > 1 else ""
        lines.append(f"- **{n}** — {', '.join(kinds)}{flag}  <sub>{origins}</sub>")
    if not owners:
        lines.append("_no aggregates or services captured yet_")

    if divergences:
        lines += ["", "## Divergences to resolve", ""]
        for t, entries in divergences:
            lines.append(f"- `{t}` defined {len({d for _, d, _, _ in entries})} ways — "
                         "one term, one meaning, one context (principle 18)")

    (Path(dd) / "index.md").write_text("\n".join(lines) + "\n")
    return len(divergences)


def render(dd=None, ref=None, level=2, full=False):
    dd, models, active, traces = st.load_all(dd, ref)
    if dd is None:
        return None, "no .design/ directory found - run `design.py init` first"
    tpath, ticket = active if active else (None, None)
    tree = render_tree(models, tpath, ticket, traces, level, full)

    # one graph.md per task - the view is as temporal as the artifact it draws
    for tf, trace in traces:
        r, slug = st.task_key(tf)
        one = render_tree(models, tpath, ticket, [(tf, trace)], level, full)
        md = "\n".join([
            f"# {r} · {slug}", "",
            f"_captured at {trace.get('traced_at_commit') or 'unknown commit'}, "
            f"updated {trace.get('updated_at', '')}_", "",
            "```", one, "```", "", LEGEND, "",
            render_mermaid(ticket, [(tf, trace)]), ""])
        (Path(dd) / f"{r}.{slug}.graph.md").write_text(md)

    build_index(dd)
    return dd, tree


def main(argv):
    ref, level = None, 2
    full = "--full" in argv
    if_touched = "--if-touched" in argv
    for a in argv:
        if a.startswith("--ref="):
            ref = a.split("=", 1)[1]
        elif a.startswith("--level="):
            level = int(a.split("=", 1)[1])

    if if_touched:
        # Hook mode: the tool payload arrives on stdin. Redraw only when the
        # write actually landed in .design/, so every other edit stays silent.
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            return 0
        # Match the write PATH only. Matching the serialised payload also matched
        # `new_string`, so editing any file that merely mentions .design/ - SKILL.md,
        # visualize.md, this file - triggered a full re-render.
        ti = payload.get("tool_input") or {}
        touched = ti.get("file_path") or ti.get("notebook_path") or ""
        if not touched:
            return 0
        # It must be THIS repository's state directory, not merely a directory
        # named `.design` somewhere in the tree - a project can legitimately have
        # `src/.design/` and writes there are none of our business.
        parent = Path(str(touched)).expanduser().resolve().parent
        if parent.name != st.DESIGN_DIR:
            return 0
        here = st.find_design_dir()
        if here is None or Path(here).resolve() != parent:
            return 0

    dd, tree = render(ref=ref, level=level, full=full)
    if dd is None:
        return 0  # nothing to draw is not an error - the hook fires on every write
    print(tree)
    print()
    print(LEGEND)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
