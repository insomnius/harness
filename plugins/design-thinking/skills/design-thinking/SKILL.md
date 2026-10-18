---
name: design-thinking
description: "Trace the affected graph before changing code and prove behavior with red-first tests. Use for features, fixes, refactors, migrations, CI and infrastructure changes, or to resume or audit an implementation trace. Mandatory state machine, graph reports and TDD; DDD modeling only for new features. Bundled Python CLI records append-only decisions under .design/."
---

# Design thinking

A requirement names a behavior; code is a graph. Discover the affected nodes,
specify their contracts, observe the tests fail, implement, and verify the
requirement. Keep the graph honest as the code changes.

## Start with the bundled CLI

Resolve `scripts/design.py` relative to this installed `SKILL.md`. Invoke it
with Python 3 **from the project being changed**. Below, `design.py` means:

```sh
python3 /absolute/path/to/installed/design-thinking/scripts/design.py <command>
```

Start a new trace, or inspect an existing one:

```sh
design.py init --ref partial-refunds --title "Partial refunds" --kind feature
design.py status
```

Use `--kind fix`, `refactor`, `migration`, `infra`, `docs`, or `change` for
non-feature work. Refs and task slugs must have no dots, slashes or glob characters.
When multiple tickets exist, put `--ref <ref>` **before** the subcommand.

**One supported writer:** use this CLI for every workflow-state mutation.
Do not generate Python scripts, hand-edit JSON state, or rewrite the log.
The packaged `graph.json` is the workflow specification, **not task state**;
it is read-only unless the user explicitly asks to change the skill itself.
If the CLI cannot express a needed record, report that limitation rather than
inventing a second writer. Command examples and persistence details: [cli.md](cli.md).

## Mandatory discipline

1. **Follow the state machine.** `status` shows the current phase, its questions,
   exit criteria, transitions and recorded blockers. Load guidance for that
   phase only. Use `phase <id>` to advance; evaluate semantic guards against
   the repository before advancing, not merely whether the command accepts it.
2. **Report as a graph, always.** Show requirement -> task -> caller/callee
   nodes -> symbols/behaviors, with status and gate evidence. Prose explains
   the tree; it never replaces it. The CLI renders after every mutation.
   Include its graph in progress and final reports. Small tasks get small graphs.
3. **TDD at both altitudes.** Observe an acceptance check red before starting
   implementation work on a requirement. Before production code for each
   behavior, annotate its contract and observe its test red for the intended
   reason. A broken harness or inherited failure is not evidence.
4. **Preserve evidence.** Record decisions before acting on them. Requirements
   link to behaviors, behaviors to tests. A passed red gate permits implementation;
   it does not mean green. Close only after observed verification.
5. **Revalidate on resume.** Rebuild derived files, compare the trace against
   current code and seam versions, resolve drift, then resume. Rebuild alone
   does not establish that contracts are still intact.

Graph and TDD obligations are never skipped. If an acceptance check genuinely
cannot be automated, name its human closure owner and required evidence; do
not claim automated closure. The behavior gate still applies.

## Workflow overview

These headings group the existing phases; they are not another state machine.

```text
UNDERSTAND  preflight -> requirements -> language
TRACE       acceptance red -> keyword -> locate -> trace -> cross? -> triage -> order?
SPECIFY     channels -> test red -> gate
CHANGE      implement -> retrace -> next node or verification
VERIFY      verify_requirement -> close or loop back with evidence
RESUME      revalidate -> resolve drift -> recorded phase
```

- **Understand:** establish suite baseline and separately observable requirements.
  Translate ambiguous terms using existing code and tests. Escalate high-risk
  assumptions the repository cannot answer; make other assumptions testable.
- **Trace:** walk callers and callees while the delta propagates. Stop at
  absorption or a structural end, never a hop count. Record node purpose,
  edges, changed behaviors, unaffected invariants and compatibility evidence.
- **Specify:** annotate **A** (success flow), **E** (failures and policies),
  **R** (dependencies), cardinality, boundary, layers and resource scope.
  This Effect-inspired separation applies in every language; adopting Effect
  itself is not required. Record the contract with `contract`, not custom JSON.
- **Change:** implement only gated behaviors. Keep success, error handling and
  dependencies explicit. Any newly discovered behavior returns through
  contract -> red test -> gate before implementation. Retrace each changed node.
- **Verify:** run unit -> contract -> acceptance checks. Green units with red
  acceptance mean a missing node or a misunderstood requirement, not completion.
  A retry-only pass is not reliable green. Finish one requirement before the next.

## Load only what the current work needs

| Trigger | Reference |
|---|---|
| Starting, resuming, recording state or discovering commands | [cli.md](cli.md) |
| Requirement checks, harness selection or verification failure | [loop.md](loop.md) |
| Tracing callers/callees, purpose, evidence or drift | [tracing.md](tracing.md), then only the relevant `lang/*.md` |
| Annotating success/errors/dependencies and scope | [shapes.md](shapes.md) |
| Before evaluating a behavior gate | [gate.md](gate.md) |
| A seam lies on the change path | [crossing.md](crossing.md) |
| **Developing a new feature** | [domain.md](domain.md): model only its needed vocabulary, ownership and boundaries |
| Formatting the mandatory status graph | [reporting.md](reporting.md) |
| Detailed Mermaid or specialized diagram examples needed | [visualize.md](visualize.md) |
| Resolving a philosophical conflict | Relevant section of [principles.md](principles.md) |
| Explicitly using optional ponytail/caveman companions | [dependencies.md](dependencies.md) |

**DDD is conditional; graph and TDD are not.** For fixes, refactors, migrations,
infrastructure and documentation, reuse existing terminology and ownership.
Do not introduce aggregates, context maps or architectural restructuring just
because the guide has a DDD taxonomy. Record a `language` skip when no lookup
is needed. Mixed work models only the genuinely new feature portion.

## Stop and reporting rules

- `unsure` is legitimate; resolve it with code, experiments or a question.
  Never turn weak evidence into a confident `no_change`.
- A failing check on an unaffected node reopens the trace; do not rewrite the
  check to agree with the new code. Compatibility matters more than caller count.
- If a turn ends red without a new failure, node, behavior, falsified assumption,
  resolved uncertainty or materially different diagnosis, stop. Show the graph,
  expected versus observed, what was tried, and the question needing a human.
- Add comments/docstrings only for important non-obvious reasons, not narration
  or copied traces. Preserve required documentation, licenses and unrelated comments.
- Keep decisions and useful evidence in `.design/`; avoid duplicating code or
  creating extra prose documents for recall. Append reversals with `--why`.
- Final report: graph, checks and their observed results, remaining uncertainty.
  No prose-only completion claims and no `--force` waiver of TDD evidence.
