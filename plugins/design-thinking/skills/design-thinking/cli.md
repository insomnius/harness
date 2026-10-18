# Using the bundled CLI

Resolve `scripts/design.py` relative to the installed skill directory; invoke
it with Python 3 from the target project's working directory. `design.py` below
abbreviates that absolute-path invocation. No additional runtime packages are
required. Git supplies commit evidence when available.

## Start or resume

```sh
design.py init --ref partial-refunds --title "Partial refunds" --kind feature
design.py status
design.py --ref partial-refunds status --slug refund
```

Kinds: `feature`, `fix`, `refactor`, `migration`, `infra`, `docs`, `change`
(default). Only `feature` calls for DDD modeling. Other work reuses existing
terminology and ownership; it does not need an empty model filled with DDD
concepts. Older logs without a kind are treated as `change`.

`status` is read-only: it folds the log in memory and prints the current phase,
its guide, questions, checks, exit criteria, candidate transitions and recorded
blockers, followed by the graph. Inspect another phase without entering it:

```sh
design.py status --phase gate
```

On resume, run `rebuild`, then enter `revalidate` at the ticket or task scope.
Compare traced files and contracts against current code, including uncommitted
changes and provider-side seam changes. Record the findings with `note` and
correct affected nodes through their commands. Return to the interrupted phase
only when intact, or follow the revalidation transition to triage/locate.
Rebuilding is not a semantic drift check.

```sh
design.py rebuild
design.py phase revalidate --slug refund
design.py status --slug refund
```

The original 18 phases remain in `graph.json`. `phase` validates their names
and edges; it does not infer architectural judgment. Review the printed guard
and exit criteria before advancing. `--slug` selects task state; omitting it
selects ticket state. A task starts at `keyword` after its requirement gate.

```sh
design.py phase requirements
design.py phase language --skipped "bug fix; existing terms and ownership are clear"
design.py phase acceptance
```

Only conditional phases may be skipped. A skip records its reason and permits
traversal through that phase's outgoing edges. Entering the phase later clears
its skip. Neither gate can be skipped. Task and ticket skip records are separate.

Implementation permission is per behavior, not the entire task. When more than
one behavior is pending, select the gated one explicitly; ungated behaviors
remain off limits:

```sh
design.py phase implement --slug refund --behavior B1
```

## Record decisions, not JSON files

```text
graph.json                         Packaged workflow specification: read-only
.design/<ref>.log.jsonl             Append-only source, written by the CLI
  +-- <ref>.json                    Requirements, tasks and ticket findings
  +-- <ref>.<slug>.trace.json        Nodes, edges, behaviors and task findings
  +-- <ref>.<slug>.model.json        Domain vocabulary when applicable
  +-- <ref>.<slug>.graph.md          Rendered task diagram
  `-- index.md                     Cross-task recall and divergence findings
```

Use `--help` on each command; use `--why` for reversals. Never write custom
scripts to edit these files or hand-edit derived JSON. Changing `graph.json`
is skill development, not an implementation decision in a target project.

| Decision | Command |
|---|---|
| Observable requirement | `requirement --id R1 --statement '...'` |
| Requirement check | `check --kind acceptance --id R1 ...` |
| Task after acceptance red | `task --id T1 --slug refund --requirement R1` |
| Node purpose and verdict | `node --slug refund --path src/refund.py --purpose '...' --verdict change` |
| Caller/callee edge | `edge --slug refund --from src/handler.py --to src/refund.py` |
| Observable behavior | `behavior --slug refund --id B1 --statement '...' --path src/refund.py --symbol refund --requirement R1 --status specified` |
| Behavior contract | `contract --slug refund --id B1 ...` |
| Edit order | `order --slug refund --path src/refund.py --n 1 --reason 'callee first'` |
| Feature vocabulary / ownership | `term` / `own` |
| Supplemental phase outputs | `note --phase <id> [--slug refund] --json '...'` |
| Decision history / graph | `log` / `show [--level 4] [--full]` |

`note` accepts a nonempty JSON object keyed by that phase's `produces` names,
without `[]` or explanatory suffixes. It preserves findings in `phase_notes`;
it does **not** replace first-class node, edge, behavior, contract, gate or
acceptance commands. Notes cannot overwrite current phase or pass a gate.

```sh
design.py note --phase preflight --json '{"baseline_failures": [], "missing_dependencies": []}'
design.py note --phase channels --slug refund --json '{"hidden_r": [], "split_proposals": []}'
```

Use notes for richer flow, seam, ambiguity and drift findings not exposed by a
specialized command. Their semantic schemas remain in `graph.json`; the CLI
validates their top-level output names, not every nested architectural claim.
If an operation still cannot be expressed, report the missing capability rather
than inventing another writer.

## Contracts and captured checks

Establish the baseline before changing code:

```sh
design.py check --kind baseline --cmd 'python3 -m unittest discover'
design.py requirement --id R1 --statement 'a refund above balance is rejected'
design.py check --kind acceptance --id R1 --altitude cli --expect red \
  --cmd 'python3 -m unittest tests.test_refund_cli' \
  --reason 'assertion shows the above-balance refund incorrectly succeeds'
```

Create the task and behavior using the commands above, then annotate:

```sh
design.py contract --slug refund --id B1 \
  --a 'load order -> check balance -> record refund' \
  --e 'InsufficientBalance: propagate; storage timeout: retry at most 3 times' \
  --r 'order repository, clock' --boundary 'CLI parser' \
  --layers 'tracing' --scope 'transaction context manager' --cardinality one
design.py check --kind behavior --slug refund --id B1 --expect red \
  --cmd 'python3 -m unittest tests.test_refund' \
  --reason 'assertion expected InsufficientBalance but refund succeeded'
```

Assess G1-G10 with `status --phase gate`; captured failure alone does not prove
all semantic checks. A contract change invalidates the old gate, even when its
behavior statement has not changed. Re-gate after observing a fresh red.

`check` executes the explicitly supplied **trusted shell command** with the
current working directory/environment. Review commands before running them;
checks may modify files or contact external systems. The default timeout is
120 seconds; override with `--timeout`. It records command, exit status,
stdout/stderr, cwd, commit, timestamp and the explanation for intended red.
Do not run commands that print secrets into the decision log.

A nonzero exit is not automatically red for the intended reason. Inspect the
actual output against the baseline. `--reason` records the agent's assessment;
it cannot prove that assessment. Baseline runs record inherited failures without
passing either gate. Timeout/execution errors never count as red evidence.

For remote or already-executed checks, `acceptance --red '<output>'` and
`gate --red '<output>' --cmd '<check>'` remain available. These are reported
observations, not execution captured by the CLI. Use captured checks when
practical; do not fabricate failure output to populate the ledger.

## Verify and close

After gated implementation, run unit, contract and acceptance checks. Reuse
the red command on green so a different command cannot borrow its evidence:

```sh
design.py check --kind behavior --slug refund --id B1 --expect green
design.py check --kind acceptance --id R1 --expect green
design.py requirement --id R1 --statement 'a refund above balance is rejected' --status done
design.py close
```

An observed regression retracts green; it is not accepted merely because the
command expected green. A behavior must be green with a current valid gate to
close, not just gated. `--force` cannot waive evidence. Descope intentionally
with `requirement --status descoped --why '...'` rather than inventing success.
Manual acceptance uses `--manual-owner` and `--manual-evidence`; its human
owner closes it on the stated evidence, not an agent's automated-green claim.

The CLI enforces structural transitions and recorded evidence, not universal
agent obedience. It cannot prevent direct filesystem bypasses or prove all
semantic guards. `scripts/audit_gates.py` checks supported refusal paths;
inspect logs and diffs when auditing a trace. Existing gates without contract
snapshots need a contract and fresh observed red before continuing.
