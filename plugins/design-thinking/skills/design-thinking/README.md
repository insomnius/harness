# design-thinking

A portable agent skill for changing existing systems. A ticket names a behavior;
the code is a graph; the work is finding which nodes the behavior touches,
proving it, changing them in the right order, and keeping the map honest as it
changes underneath you.

```
X  →  Y  →  Z          Y is the node in hand
      │                X calls Y, Y calls Z
      ├─ A   what flows through on success
      ├─ E   where it breaks, and what happens then
      └─ R   what it needs to exist
```

## Three legs

```
DDD          new features only         vocabulary, ownership and boundaries
 ↓
GRAPH        A · E · R                 how this change flows through it
 ↓
TDD          red first, then code      proof that the behavior is what was claimed
```

DDD modeling gives new features a vocabulary and an owner. Other changes reuse
existing terminology and ownership without a DDD modeling exercise. Graph
output, the state machine and red-first TDD are mandatory for every task.
The short `SKILL.md` loads reference guidance only for the current phase;
`design.py status` supplies questions, exit criteria and allowed transitions.

## Install

```
/plugin marketplace add insomnius/harness
/plugin install design-thinking@harness
```

Restart Claude Code, then start any implementation task normally. The skill
triggers on feature work, bug fixes, refactors, migrations and CI changes, and
on resuming or auditing a trace.

The skill folder includes the decision CLI (`scripts/design.py`), templates,
and references. Install it independently with
`npx skills add insomnius/harness --skill design-thinking`, or use the plugin
commands above for the optional redraw hook (`hooks/hooks.json`). See
`INSTALL.md` for local and per-project installation.

Traces land in `.design/`. Committing them makes a PR reviewable at the level of
*which nodes were considered and why the rest were absorbed*; `echo '.design/'
>> .gitignore` if you would rather keep them local.

## Work is a loop

```
natural language requirement
  → DECIPHER   prose → a graph delta (which nodes, symbols, behaviors change)
  → SPECIFY    a red acceptance check for the requirement,
               red unit tests + annotated contracts for each behavior
  → GATE       blocking checks, per behavior
  → CHANGE     implement in passes, then re-trace
  → CLOSE      run unit → contract → acceptance; green closes it
  → next requirement, against a warmer glossary
```

## State is a log, and everything else is a fold

`.design/<ref>.log.jsonl` is the source: one decision per line, append-only. A
reversal is a new line that supersedes an earlier one, never an edit — a verdict
that went `no_change → change` because a compiler error moved it is worth more
than the verdict, and the CLI refuses a reversal with no `--why`. Everything
else in `.design/` is derived from it and rebuilt on every write:

| Fold | Holds |
|---|---|
| `<ref>.json` | tiers 0–1 — requirements and tasks |
| `<ref>.<task>.trace.json` | tiers 2–4 — nodes, symbols, behaviors |
| `<ref>.<task>.model.json` | the domain as understood while doing that task |
| `<ref>.<task>.graph.md` | the rendered Mermaid views |
| `index.md` | recall across every snapshot — two tasks defining one term differently surface as a divergence, not a silent overwrite |

Decide through the CLI; read the folds. Use a descriptive, path-safe `--ref`
such as `partial-refunds`; no external issue tracker is required.

```bash
design.py init --ref partial-refunds --title "partial refunds" --kind feature
design.py status
design.py requirement --id R1 --statement "a partial refund below the balance succeeds"
design.py acceptance  --id R1 --altitude http --cmd "go test ./acceptance -run Refund" \
  --red "expected 200 with status closed, got 422"
design.py task --id T1 --slug refund --requirement R1
design.py node --slug refund --path order/service.go --role aggregate_root \
  --purpose "protects the invariant that refunds never exceed the balance" \
  --verdict change --depth 0 --evidence compiler
design.py behavior --slug refund --id B5 --statement "a refund above balance is rejected" \
  --path order/service.go --symbol RecordRefund --requirement R1 --status specified
design.py contract --slug refund --id B5 --a "load -> check -> record" \
  --e "InsufficientBalance: propagate" --r "repository" --boundary "HTTP parser" \
  --layers "none" --scope "transaction context manager"
design.py gate --slug refund --id B5 --red "expected InsufficientBalance, got <nil>"
design.py log        # the decisions, and the reversals among them
```

Each mutating subcommand validates, appends one decision, re-folds and renders — so the
status tree reaches the transcript on every change without anyone electing to
print it. It refuses a verdict on a node with no purpose, a `no_change` with no
stop reason, a reversal with no reason, a gate with no observed red evidence, an
invariant on an application service, and a close with requirements still open.

## The two hard rules

> **No work on a requirement until an automated check for it exists and is red.**
> **No code for a behavior until its contract is annotated and its test is red.**

Same discipline at two altitudes. Closure is then *observed* rather than
asserted: a requirement is done when the check that was red before any code goes
green on its own — not because an agent judged the work complete. The harness
follows from where the requirement is observable (browser, HTTP, CLI, event,
pipeline, data), never from preference.

Both gates, graph output and the state-machine protocol are mandatory.
Use the bundled CLI, never generated scripts or hand-edited state JSON. Prefer
`check` for captured execution evidence; `gate`/`acceptance` accept reported
observations for external checks. See [cli.md](cli.md) for commands and limits.

## Principles over recipes

`principles.md` is the method: 43 statements with no tools in them. Every other
reference file illustrates those principles in particular stacks, and is the
first thing to adapt or discard. When a recipe conflicts with a principle, the
principle wins. When a stack is not covered, ask the principle's question and
find that stack's answer.

## Output is a multi-level graph

Status is reported as a tree spanning all five tiers — indentation is call
depth, `d±n` is direction relative to the seed, `#n` is position in the edit
order:

```
R2 partial refunds                          ◐  turn 2/3 · accept ✗
└─ T4 refund handler                        ◐  4/7 behaviors
   ⋯> workflows/deploy.yml           d-2 #6 ○  gate —
      └─→ http/refund_handler.go     d-1 #5 ◐  Handle  B7✓ B8◐
         ├─→ order/refund_service.go d0★ #3 ✓  RecordRefund  B4✓ B5✓ B6✓
         │  ├─→ order/repository.go  d+1 #1 ✓
         │  │  └─⇄ seam:table orders     #2 ✓  additive column
         │  ├─→ pkg/money/money.go   d+1    ⊘  absorbed · fan-in 47
         │  └─⇉ seam:http /v2/ledger d+1 #4 ✓  additive · provider first
         │     └─→ payments:ledger/api.go d+2 ✓  far side
         └─→ order/policy.go         d+1    ⊘  absorbed
   ↩ worker/reconcile.rb             d-1    ⚠  drifted · re-triage
```

Deep nodes carry low order numbers because callees go first, so the shape *is*
the edit plan. A shared node is expanded once and referenced with `↩`
afterward. Detail defaults to the node tree, with only the node in motion
expanded down to behaviors and gates.

## Tiers

| Tier | Node | Id | State file |
|---|---|---|---|
| 0 | requirement | `R1` | `.design/<ref>.json` |
| 1 | task / sub-task | `T1`, `T1.2` | `.design/<ref>.json` |
| 2 | file, or seam | path, or `seam:http:...` | `.design/<ref>.<task>.trace.json` |
| 2f | flow — an end-to-end path | `F1` | same |
| 3 | symbol | function, method, job, step | same |
| 4 | behavior | `B1` | same |

A flow is annotated *before* its nodes are: it owns the layer error table and
the union of dependencies the acceptance harness must supply, and a node's A is
then its slice of the flow's A. Every node can conform individually while the
path through them is wrong, so `retrace` checks conformance at flow level too.

Behaviors are where the method operates — you do not change a file, you change a
behavior. Requirements are satisfied by behaviors; behaviors are proven by
tests. That chain is the only accepted evidence of done.

## Phases

| Phase | Does |
|---|---|
| `preflight` | establish available dependencies, baseline failures, and existing state |
| `requirements` | split the ticket into verifiable expectations; register ambiguities |
| `language` | new features: model needed vocabulary, ownership and contexts; other changes: reuse existing terms or record a skip |
| **`acceptance`** | **requirement gate: an automated check for the requirement, red, before any work** |
| `keyword` | derive search terms from the glossary, including dead aliases |
| `locate` | seed nodes from search hits |
| `trace` | walk up (callers) and down (callees) until the change is absorbed |
| `cross` | continue through seams; decide compatibility and deploy order |
| `triage` | verdict every behavior; route misplaced ones |
| `order` | sequence edits and deploys so each lands on a stable base |
| `channels` | annotate A, E, R, cardinality, boundary, layers, scope |
| `test` | write the behavior's test; make it red |
| **`gate`** | **ten blocking checks, per behavior** |
| `implement` | four passes: happy → re-check → errors → finalize |
| `retrace` | walk X and Z again; check code matches the annotated graph |
| `verify_requirement` | run the checks and let them close the loop; route the failure |
| `revalidate` | drift check against others' commits and provider deploys |
| `close` | ascend to the task tier; update the glossary |

Loop-back edges matter as much as the forward ones. The two most important: a
failing test on a `no_change` node means the trace was wrong, not the test; and
a behavior discovered during implementation returns through `channels`, `test`
and `gate` before any code is written for it.

## Files

| File | Contents |
|---|---|
| `SKILL.md` | short entry point with mandatory discipline and reference loading triggers |
| `cli.md` | supported writer, status guidance, contracts, notes and captured checks |
| `reporting.md` | compact mandatory graph-report guidance |
| `scripts/workflow.py` | reads canonical phases and transitions from graph.json |
| `principles.md` | the method in 43 tool-free statements — precedence over all the rest |
| `loop.md` | the loop, both gates, harness selection, the check manifest, the stop condition |
| `graph.json` | canonical phases, transitions, guards and schemas; read-only during ordinary task work |
| `gate.md` | how to assess the canonical gate checks, intended red and the ledger |
| `shapes.md` | records/ids/variants/errors, A/E/R, boundary, layers, scope, per language |
| `domain.md` | ubiquitous language, subdomains, aggregates, the role taxonomy, events, context map |
| `tracing.md` | evidence tiers, cross-language edges, reading purpose off existing code |
| `lang/*.md` | one per stack — Go, Rust, Java, TypeScript, JavaScript, Effect, Ruby, Python, Bash, GitHub Actions, Terraform — each answering the same six questions. `lang/TEMPLATE.md` makes an uncovered stack a fill-in |
| `crossing.md` | seams: consumer discovery, error translation, deploy order, seam drift |
| `visualize.md` | Mermaid views: context map, file graph, channels, coverage, deploy |
| `ticket.template.json` | tier 0–1, the shape the decision log folds into |
| `task-model.template.json` | the domain as understood for one task |
| `trace.template.json` | tier 2–4 state, one per task |
| `dependencies.md` | ponytail and caveman: handoff phases, what neither may override |
| `INSTALL.md` | standalone skill and optional Claude plugin installation |
| `scripts/design.py` | the CLI — one subcommand per decision, validating and re-folding on each |
| `scripts/fold.py`, `design_state.py`, `render_graph.py` | the fold and the rendered views |
| `scripts/test_design.py` | the runnable check, including the spec-mirror assertions between `graph.json` and the CLI |
| `hooks/hooks.json` | PostToolUse — any write under `.design/` redraws the tree |

This edition bundles scripts inside the skill folder alongside templates and
references. The folder installs independently with npx. Only the optional
Claude hook stays at the plugin root. See INSTALL.md for current instructions.

## No lanes, no dials

Applicability follows the work: `init --kind feature` enables DDD modeling;
other kinds reuse existing ownership. Neither changes graph/TDD obligations.
Traversal decisions derive from properties of the change:

| Instead of | The rule |
|---|---|
| a fan-in threshold | additive deltas never expand upstream; breaking deltas are enumerated with a compiler or a coverage run; unenumerable ones are not broken in place |
| a depth limit | upstream ends at the flow's entrypoint, downstream at a leaf or opaque seam; three transform-free hops are a pass-through to collapse; still propagating at the entrypoint is a finding |
| a lane or mode | each phase has a predicate — `cross` only with a seam on the path, `order` only with more than one node changing, `channels` annotates only the delta for a body-only change. Both gates always apply |
| a turn cap | halt on the first turn that ends red having produced no new information, which can be turn two |
| "dynamic languages, hesitate more" | an evidence ladder: `compiler`, `coverage`, `references`, `text`, `reasoning`. A contract change needs one of the top two; weaker is `unsure`. Tier 2 exists in any language with a test suite, so a dynamic language is condemned to running its tests, not to guessing |
| an escape hatch for purpose | the agent may place a behaviour correctly or create a node; widening a purpose requires human ratification |

The one number left is the view budget — 28 printed lines — and it only affects
drawing, never a decision.

## Dependencies

**ponytail** (`DietrichGebert/ponytail`) for minimality — hands off at `locate`,
`triage`, pass A and `retrace`. **caveman** (`JuliusBrussee/caveman`) for prose
compression, on narration only.

Both gates outrank both skills: ponytail governs how much code is written, never
what must be specified; caveman may not compress a gate verdict, a check
failure, or a falsified assumption. See `dependencies.md`.
