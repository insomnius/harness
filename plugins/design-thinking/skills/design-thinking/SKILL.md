---
name: design-thinking
description: "Name the domain, trace the existing call graph before changing it, then prove each behavior with a test that was red first. Use at the start of every implementation task - feature, bug fix, refactor, migration, CI or infra change - and especially when the task arrives as a product requirement with no technical detail. Also use to resume an in-progress trace, to revalidate one after pulling others' changes, or to audit someone else's change set. Records every decision in an append-only log under .design/ and renders the graph on each one. Tiers: requirement, task, file, symbol, behavior. Works in Go, Rust, Java, TypeScript, JavaScript, Effect, Ruby, Python, Bash, GitHub Actions and Terraform."
---

# Design thinking

## Bundled CLI

This skill is self-contained. Resolve `scripts/design.py` relative to this
SKILL.md's directory and invoke it with Python 3 from the project being changed:
`python3 /absolute/path/to/installed/design-thinking/scripts/design.py <command>`.
The abbreviated `design.py` examples below mean that invocation; do not assume
the command is on PATH. Keep the working directory in the target project so
`.design/` is written there. Templates and reference files are bundled here.

A ticket names a behavior. The code is a graph. The work is to find which nodes
the behavior touches, prove it, change them in the right order, and keep the map
honest as it changes underneath you.

```
X  ->  Y  ->  Z
│      │      │
│      │      └─ what Y calls        (downstream, depth +1)
│      └──────── the node in hand    (depth 0)
└─────────────── what calls Y        (upstream, depth -1)
```

## Three legs

```
DDD          name the shapes           what exists, and what owns which rule
 ↓
GRAPH        A · E · R                 how this change flows through it
 ↓
TDD          red first, then code      proof that the behavior is what was claimed
```

DDD says who owns a rule, so a change has a legal destination before anyone
looks for a file. The graph says what this particular change touches, in the
direction the system runs. TDD says the behavior is real, because a check that
was red went green on its own. Skip the first and rules land wherever the trace
happened to arrive; skip the last and "done" is an opinion.

## State is a log, and everything else is a fold

```
.design/
  ENG-1234.log.jsonl                 THE SOURCE — one decision per line, append-only
  ENG-1234.json                      derived: tier 0-1
  ENG-1234.refund.trace.json         derived: tiers 2-4 (nodes, symbols, behaviors)
  ENG-1234.refund.model.json         derived: the domain as understood for that task
  ENG-1234.refund.graph.md           derived: the rendered view
  index.md                           derived: recall across every snapshot
```

**Log the decision, not the state.** A verdict that went `no_change → change`
because a compiler error moved it is worth more than the verdict, and
overwriting a record is what destroys it. A reversal is a new line that
supersedes an earlier one, never an edit, and the CLI refuses a reversal with
no `--why`.

Everything is temporal and captured at a commit. There is no shared mutable
model, so nothing can be forgotten and nothing goes stale — two tasks that
define one term differently produce a **divergence in `index.md`**, which is a
finding rather than a write that silently wins.

**Decide through the CLI; read the folds.**

```bash
design.py init --ref ENG-1234 --title "partial refunds"
design.py requirement --id R1 --statement "a partial refund below the balance succeeds"
design.py acceptance  --id R1 --altitude http --cmd "go test ./acceptance -run Refund" \
  --red "expected 200 with status closed, got 422"
design.py task --id T1 --slug refund --requirement R1
design.py node --slug refund --path order/service.go --role aggregate_root \
  --purpose "protects the invariant that refunds never exceed the balance" \
  --verdict change --depth 0 --evidence compiler
design.py behavior --slug refund --id B5 --status specified \
  --statement "a refund above the balance is rejected and the order is untouched"
design.py gate --slug refund --id B5 --red "expected InsufficientBalance, got <nil>"
design.py log        # the decisions, and the reversals among them
```

Every subcommand validates, appends one decision, re-folds and renders — so the
tree reaches the transcript on every change without anyone electing to print
it. It refuses a verdict on a node with no purpose, a `no_change` with no stop
reason, a reversal with no reason, a gate with no observed red evidence, an
invariant on an application service, and a close with requirements still open.
`graph.json`'s `tooling` block is the full command list.

## Tiers

| Tier | Node | Id | Where it lives |
|---|---|---|---|
| 0 | requirement | `R1` | `.design/<ref>.json` |
| 1 | task / sub-task | `T1`, `T1.2` | `.design/<ref>.json` |
| 2 | file — has one **purpose** | repo-relative path | `.design/<task-slug>.trace.json` |
| 2f | **flow** — an end-to-end path | `F1` | same trace file |
| 3 | symbol | function, method, job, workflow step | same trace file |
| 4 | **behavior** | `B1` | same trace file |

The domain model — glossary, subdomains, contexts, aggregates, services, process
managers, events — is captured per task in `.design/<ref>.<task-slug>.model.json`,
as the domain was understood while doing that task. It is a record, not a
document: a later task never edits it, it writes its own. Recall across tasks is
`index.md`, derived from every snapshot on every write.

Tier 4 is where the method actually operates. You do not change a file, you
change a behavior. Tier 2 is for addressing and drift detection, tier 3 holds
contracts, and tiers 0-1 are shared across the whole ticket — each task gets its
own trace file so the agent is not re-reading the whole ticket's graph per turn.

**A belongs to a flow, not a node.** A flow is a named end-to-end path in the
direction the system runs, and it is annotated *before* its nodes are — a node's
A is then its slice of the flow's A, and if the two disagree one of them is
wrong. The flow owns the layer error table and the union of dependencies the
acceptance harness must supply. `retrace` checks conformance at flow level too,
since every node can conform individually while the path through them is wrong.

**Purpose and behavior are the two things that make the graph mean something.**

A node's purpose is one sentence naming the single reason it exists, stated as a
capability: *"decides whether a refund is permitted and records it"*, not
*"refund helpers"*. It is read off the existing code and tests on first trace,
not invented. Its job is triage: it separates *reachable from here* from
*belongs here*. A change that reaches a node whose purpose does not cover it is
`MISPLACED` — it goes to the node whose purpose does cover it, or to a new node.
That single rule is what stops a helper file accreting a decade of unrelated
behavior.

A behavior is one observable thing a node does, stated from outside: given some
condition, the caller sees some result. It is the traceability spine — a
requirement is satisfied by behaviors, and a behavior is proven by tests. That
chain is the only acceptable evidence that a requirement is done.

Phases, schemas and stop conditions: `graph.json`. Traversal per language:
`tracing.md`, with one file per language in `lang/`. Shapes and the A/E/R
channels: `shapes.md`.
Translating a requirement into the domain: `domain.md`. Crossing
into other services and layers: `crossing.md`. Diagram generation:
`visualize.md`.

## Principles first

`principles.md` is the method: 43 statements with no tools in them. The other
reference files are illustrations of those principles in particular stacks, and
they are the first thing to adapt or discard. **When a recipe conflicts with a
principle, the principle wins.** When a stack is not covered, ask the
principle's question — who calls this, where does it break, what does it need,
is it substitutable — and find that stack's answer. A language with no compiler
still has dependencies; they just get written down instead of proven.

Two things are constraints rather than guidance: the requirement gate and the
behavior gate. Everything else is tunable.

## Work is a loop

```
natural language requirement
  → DECIPHER   requirements → language → keyword → locate → trace → cross
               → triage → order          ⇒ a graph delta
  → SPECIFY    acceptance (red, requirement altitude)
               channels + test (red, behavior altitude)
  → GATE       ten checks, per behavior, blocking
  → CHANGE     implement in passes → retrace
  → CLOSE      run unit → contract → acceptance
               green closes it; red routes back with the reason
  → next requirement, against a warmer glossary
```

**Closure is observed, not asserted.** A requirement is closed when a check that
was red before any code went green on its own — never because the work looks
done. If a requirement cannot be made observable, say so, name who closes it
manually and on what evidence, and do not close it yourself.

The harness follows the altitude, not preference: a user-visible flow gets a
browser check, an HTTP contract gets an API check, a command gets a CLI check,
an event gets a consumer check, a pipeline gets a real run. The exact commands
live in a check manifest so the loop runs the same thing every turn instead of
improvising.

**Reading the close** is where the loop earns its keep:

| unit | contract | acceptance | Means |
|---|---|---|---|
| ✓ | ✓ | ✓ | closed, with the red→green transition recorded |
| ✓ | ✓ | ✗ | behaviors right, requirement unmet — the most informative failure available |
| ✓ | ✗ | ✗ | the seam is wrong → `cross` |
| ✗ | — | ✗ | a behavior is wrong → `implement` |
| ✓ | ✓ | ✓ on retry | not green. Fix the check's determinism |

Row two routes two ways and guessing is expensive: either the graph delta missed
a node (→ `trace`, with the failure as the new seed) or the requirement was
misunderstood (→ `language`, and no amount of implementation fixes it). Read the
expected-versus-observed diff before choosing.

**Ambiguities become assertions.** Every `assumed` expectation in the register
gets one in the acceptance check. When it fails, the assumption was wrong — that
is a requirement finding to report to the user, not a bug to quietly fix, and it
is the highest-value output of the loop.

**Stop rather than grind.** Halt on the first turn with the acceptance check
still red that produces no new failure, node, behavior, falsified assumption,
resolved `unsure`, or materially different diagnosis of the same failure; report the
expected-versus-observed diff, what was tried each turn, and the most likely
misunderstanding in the requirement, then ask.

## Every node carries three channels

```
X  →  Y  →  Z
      │
      ├─ A   what flows through on success
      ├─ E   where it breaks, and what happens then
      └─ R   what it needs to exist
```

The `channels` phase annotates all three before the node's tests are written,
in this order: **shapes → A → cardinality → E → R → boundary → layers →
scope**. The order is load-bearing; doing E before A is how a happy path becomes
unreadable. `shapes.md` gives the rendering for Go, Ruby, TypeScript, Python,
Bash and Actions — a language that cannot prove R at compile time still has an
R, it just gets written down instead of enforced.

The rules that carry the most weight:

- **A reads top to bottom with no error handling in it.** If following the
  success path means stepping over retries and catches, A and E are tangled.
- **Every break point in E gets exactly one policy** — retry (with a bound),
  fall back (with a stated loss), propagate (in this layer's vocabulary), or
  die. An unbounded retry is an outage amplifier. `die` is for violated
  invariants and is not caught.
- **Each layer scopes its own E.** It enumerates what it received and maps it
  into its own vocabulary: `SqlError → DatabaseError → RefundRejected → 422`.
  Callers never see the vocabulary of three layers down. Watch for *leaking* a
  driver error outward and *collapsing* two errors the caller must distinguish.
- **A hidden R is the core failure.** A dependency reached through a global, a
  singleton, `Time.now`, `SecureRandom` or a mid-function env read is invisible
  in the signature, and it is why a node cannot be tested without mocking the
  world. `shapes.md` has greps for finding them.
- **Cardinality is stated, not defaulted.** `many` requires deciding ordering,
  backpressure and what a mid-stream failure means; `time_bounded` requires a
  cache key, a TTL and a dedupe decision.
- **Untrusted input has one parse point at the edge.** One definition serves as
  type, validator and transformer. Validation inside a node means the boundary
  is not doing its job, or a caller is bypassing it.
- **Layers wrap, they do not entangle.** If deleting the retry or the logging
  would require editing the happy path, it is not a layer.
- **Cleanup is structural.** If a panic, early return or cancellation can skip
  it, the resource is not scoped.
- **Test by substituting R alone**, with the graph shape unchanged. *If you have
  to mock the world to test one node, the node is doing too much* — that is a
  design finding, recorded before implementation, not a fixture to grow.
- **The code is the graph.** `retrace` checks conformance: same A order, same E
  enumeration, same R. A divergence is resolved in one direction or the other,
  never left as a silent mismatch.

## The requirement is translated before it is searched

A PM's prose is not searchable and not assignable. The `language` phase turns it
into the ubiquitous language and assigns every needed behavior a home, and
everything downstream depends on its output: `keyword` searches the glossary,
`triage` checks aggregate ownership, `cross` reads the context map.

**Mine the model, do not invent it.** The domain model is already in the
codebase — in table names, type names, test names, event names — usually in an
older dialect than the PM's. A glossary the code does not share is just a second
vocabulary to maintain.

The glossary records four columns per term: the canonical domain word, what
product calls it, what the code calls it, and **dead aliases still in the code**.
That last column is not housekeeping — the code usually speaks the older
language, and skipping the aliases is the most common reason a trace misses the
node that matters.

**Every behavior gets a role, not a file.** Ask what kind of thing it is, and
`graph.json`'s `role_routing` gives the owner: an invariant over one consistency
boundary goes to the **aggregate**; a rule belonging to no single aggregate to a
**domain service**; a sequence that owns no rule to an **application service**;
a flow spanning more than one transaction to a **process manager**, with a named
compensation per undoable step; loading or persisting one aggregate whole to a
**repository**; answering without writing to a **read model**; translating a
foreign model to an **anti-corruption layer**; translating a transport to a
**handler**. A threshold comparison or status check inside an application
service, process manager, handler or controller is a displaced invariant, and
`triage` flags it as misplaced with a known destination. When a rule fits no existing
aggregate, a concept is missing a name, and naming it is often the real work of
the ticket.

**One transaction, one aggregate.** If a behavior needs two aggregates to commit
atomically, either the boundary is wrong or it is a policy: emit a domain event,
handle it eventually, name the compensation.

**Context relationship predicts blast radius, before any tracing.** An
anti-corruption layer absorbs a foreign change at the ACL node, so the trace
stops there. Conformist means their model is your model, so their change reaches
as far as yours does. Shared kernel is the only legitimate lockstep deploy. A
seam to a foreign context with no ACL and no published language is the
highest-risk shape in the method — worth raising even when the ticket did not
ask about it.

## The graph does not stop at the process boundary

It continues over HTTP, RPC, queues, databases and infra config into other
services, other repos and other layers. Only the mechanics change.

A **seam** is a node: `seam:http:POST /v2/refunds`, `seam:topic:refund.recorded`,
`seam:table:orders`, `seam:config:REFUND_MAX_CENTS`. It has its own contract —
shape, errors, error translation, semantics, auth — and it can drift while the
code on both sides stays still. Nodes on the far side are addressed
`<service>:<path>` so one trace holds both.

Two rules follow, and they matter more than anything else in this file:

**Provider-side caller sets are unprovable.** In-process the compiler enumerates
every caller. Across a published seam you get evidence, never proof. So for a
provider-side change, stop trying to complete the upstream trace and make the
contract backward compatible instead. Anything removed or narrowed — a field, a
status code, an enum value, a column, a permission, a timeout, an ordering
guarantee — is breaking regardless of how few consumers you found.

**Crossing a layer translates the contract, errors most of all.** A domain error
becomes a status code at an HTTP seam, a retry or dead letter at a queue seam.
Record the mapping in both directions and watch for the two failure patterns:
*collapsing* two distinct errors into one code the consumer cannot distinguish,
and *leaking* an implementation error outward so consumers couple to your
internals. Changing that mapping is a behavior with a test, not a refactor.

## Non-negotiables

1. **THE GATE. No production code for a behavior until its contract is
   annotated and its test is red for the intended reason.** Evaluated per
   behavior, not per node, and recorded in a ledger. Everything else in this
   file is guidance; this is not. Refuse the edit even when asked to proceed —
   an agent that can be talked past the gate does not have one. A test failing
   because a fixture is missing or the suite will not build is not red for the
   intended reason: capture the suite's baseline failures first, then record the
   observed failure verbatim. See `gate.md`.
2. **Never guess a verdict.** `unsure` is legitimate. Resolve it by reading
   code, running an experiment, or asking - not by defaulting to `no_change`.
3. **Stop at absorption or at a structural terminator — never at a hop count.**
   Keep walking while the delta reaches the neighbour. Upstream finishes at the
   flow's entrypoint, downstream at a leaf or an opaque seam; a chain of three
   hops that transform nothing is a pass-through to collapse. A delta still
   propagating at the entrypoint means nothing absorbed it, which is a finding,
   not a stop. A network boundary is `CROSSING`; only a genuinely unreachable
   far side is `OPAQUE`.
4. **Caller count decides nothing — compatibility does.** Forty-seven callers of
   a shared type cost nothing if the delta is additive; one caller costs a
   migration if it is breaking. So: additive means do not expand upstream at
   all. Breaking means enumerate exhaustively with the compiler, or with a
   coverage run where there is none — and if neither is available, do not break
   the contract in place. Add beside it and migrate under observation. Fan-in
   affects only how the node is drawn.
5. **Evidence has tiers, and languages do not have moods.** `compiler` >
   `coverage` > `references` > `text` > `reasoning` — those five names, which
   are the values `design.py --evidence` accepts; a hedged variant of one is not
   a tier at all. Record the best tier reached. A contract-changing symbol needs
   tier 1 or 2, and anything weaker is `unsure` — which must be resolved before
   the gate. A dynamic language is not condemned to guessing; it is condemned to
   running its tests.
6. **Purpose shape follows role.** An aggregate's purpose is the invariant it
   protects; an application service's is the sequence it coordinates; a process
   manager's is the flow it drives and the compensations it owns; an ACL's is the
   foreign model it translates. If an application service's purpose reads like an
   invariant, it has absorbed a rule that belongs elsewhere.
7. **Every node gets a purpose, read from the code, before it gets a verdict.**
   A purpose that needs "and" between unrelated capabilities means two nodes.
   A purpose generic enough to fit anything ("utilities", "helpers") is not a
   purpose — such nodes attract everything, and that is the fan-out problem at
   its root.
8. **Behaviors, not files, get changed.** Every behavior names the purpose it
   serves, maps to at least one test, and links to the requirements it
   satisfies. A behavior with no test is a claim. A requirement with no
   behavior is not implemented, however much code was written.
9. **Implement in four passes, in order:** happy behaviors → re-check behaviors
   → error behaviors → finalize. The re-check pass is not optional; the
   predicted behavior list is always incomplete and this is the cheapest moment
   to learn that.
10. **Re-trace after every changed node.** Implementation adds callers and
   dependencies the first trace could not see.
11. **One requirement closes before the next opens.**
12. **A failing test on a `no_change` node means the trace was wrong.** Go back
   to `trace`. Do not edit the test to agree with the new code.
13. **Revalidate on resume and after every pull.** A trace is only valid at the
   commit it was taken against.

## Dependencies

Two third-party skills, declared in `graph.json` under `dependencies.required`.
`preflight` checks for them, reports absence once, and continues — a missing
optional skill never silently changes the method.

**ponytail** (`DietrichGebert/ponytail`) — lazy-senior-dev minimality. Hands off
at `locate` and greenfield (does the platform already do this? then no node is
needed), at `triage` (prefer the change set touching fewest nodes), at pass A
(smallest happy path), and at `retrace` via `ponytail-review` over the diff. Its
`ponytail:` shortcut comments are recorded as accepted debt with their upgrade
paths.

**caveman** (`JuliusBrussee/caveman`) — prose compression. Applies to the
narration around the graph only. Safe because it leaves code blocks and error
messages verbatim, and the status tree, red evidence and check output are all
blocks.

**Both gates outrank both skills.** ponytail governs how much code is written,
never what must be specified — it may not waive an annotated contract, an error
policy, a boundary parse, a scoped release or a red test, and its proposed
deletions are bounded by the behavior list. caveman may not compress a gate
verdict, a check failure, an expected-versus-observed line, a falsified
assumption, or anything escalated for a human decision. Where either conflicts
with a gate, the gate wins and the conflict is stated rather than resolved
silently. Detail in `dependencies.md`.

## No lanes, no dials

Every phase carries a predicate over the change itself, so the phase set is
computed rather than chosen: `cross` runs only when a seam is on the path,
`order` only when more than one node changes, `channels` annotates only the
delta for a body-only change, `language` degenerates to a lookup when every term
already resolves. A one-line fix therefore runs a handful of phases and a
cross-service migration runs all eighteen, with nobody selecting a mode — the
selecting is where judgment leaks out.

Both gates are exempt. On a one-line fix they cost one red test and one contract
annotation; skipping them saves minutes and forfeits the entire method. State
which conditional phases were skipped, once, in the first status tree — a phase
silently not run is indistinguishable from one forgotten.

**Widening a purpose is not the agent's to grant.** For a misplaced behavior
there are two options: place it where a purpose already covers it, or create a
node whose purpose does. Widening an existing purpose is a third option only a
human can take — record the request with the current purpose, the proposed one,
what else it would admit, and `ratified_by: null`, then take the placement
option and carry on rather than blocking.

**The loop halts on absence of new information, not on a turn count.** A turn
that ends red and produces none of the new information listed in
`graph.json`'s `halt_condition.new_information_is` is a loop that will not close
— halt there, even on turn two. A materially different diagnosis of the same
failure counts as new information; relabeling it does not. While each turn
yields something new, continuing is legitimate.

## Protocol

Load `graph.json`. Run `preflight` first — and its first action is
`design.py init --ref <REF>`, because a method that never writes state never
starts. Then: dependencies, existing state, the check manifest, and the suite's
baseline failures. Both gates depend on knowing
what was already red, so establishing the baseline is not optional. Read the folds — `.design/<ref>.json` (tiers 0-1) and the current task's
`.design/<ref>.<task-slug>.trace.json` (tiers 2-4) — and write only through the
CLI. They are derived from `.design/<ref>.log.jsonl`; hand-editing one is
editing a view, and the next decision rebuilds over it.

**If either exists, run `revalidate` before anything else** — report drift,
resolve it, then resume from `current_phase`. Never restart a live trace, and
never trust a trace taken against an older commit without checking it.

Then walk: `preflight` → `requirements` → `language` → per requirement (`acceptance` →
`keyword` → `locate` → `trace` → `cross` → `triage` → `order` → per node (`channels` → `test` →
**`gate`** → `implement` → `retrace`) → `verify_requirement`) → `close` → next
task.

The gate is also the resume guard: on resuming, a behavior with implementation
started and no ledger entry is a violation. Stop, rebuild the missing contract
and test, and re-gate before continuing.

Answer every phase's `ask` questions against the repository, not from
assumption. Write each phase's `produces` into state before advancing. Check
`exit_criteria` before moving. Regenerate the diagram on every state write.

Ask the user only what the codebase cannot answer: which product term maps to
which code term when genuinely ambiguous, whether an old contract must stay
compatible, which invariant wins when two collide, and any ambiguity whose
basis is `assumed` and whose `risk_if_wrong` is high. Everything else, read.

## Reporting: always a multi-level graph

Status renders on every state write — the CLI draws it after each decision and
the hook draws it after any other write under `.design/`, so it is not something
to remember. That covers every phase transition, the first edit of
a requirement, after each behavior closes, at every loop close, and on resume.
Not a flat list — sibling bullets hide who calls whom, and hide the edit order
with it. Prose explains the tree; it never replaces it. A paragraph describing
what changed with no graph is the one forbidden output.

```
R2 partial refunds                              ◐  turn 2/3 · accept ✗
└─ T4 refund handler                            ◐  4/7 behaviors
   │
   ⋯> .github/workflows/deploy.yml      d-2  #6 ○  gate —
      │  deploy                                B9○
      └─→ http/refund_handler.go        d-1  #5 ◐  gate ✓
         │  Handle                             B7✓ B8◐
         ├─→ order/refund_service.go    d0 ★ #3 ✓  gate ✓
         │  │  RecordRefund                    B4✓ B5✓ B6✓
         │  │  A: load→policy→record→publish · one · 4E · 4R
         │  ├─→ order/repository.go     d+1  #1 ✓
         │  │  └─⇄ seam:table orders           #2 ✓ additive column
         │  ├─→ pkg/money/money.go      d+1     ⊘ absorbed · fan-in 47
         │  ├─⇉ seam:http /v2/ledger    d+1  #4 ✓ additive · provider first
         │  │  └─→ payments:ledger/api.go d+2    ✓ far side
         │  └─⊗ notify/mailer.go                  B11 → notify/dispatcher.go
         └─→ order/policy.go            d+1     ⊘ absorbed
   ↩ worker/reconcile.rb                d-1     ⚠ drifted a3f91c2 · re-triage
                                                  (also calls RecordRefund)

✗ accept: expected order status 'closed', got 'reopened'
  → units green, accept red: the delta missed a node, or R2 was misread
```

`✓ done · ◐ doing · ○ todo · ⊘ absorbed · ? unsure · ⊗ misplaced · ⚠ drift · — not gated`
`→ calls · ⋯> invokes · ⇉ requests · ⇄ reads/writes · ⊢ provisions · ↩ shared · ↺ cycle`
Legend once per conversation, not per report.

**One tree, five tiers.** Requirement, task, node chain, symbol, behaviors —
indentation is call depth, not category. The tree is rooted at the
entrypoint-most node reached, so it reads in the direction the system actually
runs; the seed is marked `★` because it is where the search landed, not where
the flow starts.

**Depth labels are signed relative to the seed.** `d-1` is a caller, `d+1` a
callee. Once nesting goes past two levels, indentation alone stops telling you
direction, and the sign restores it.

**Order markers are the edit plan.** `#1 #2 #3` are positions in the ordered
change set. Deep nodes carry low numbers because callees go first — so a node
numbered *lower* than its own parent is correct and expected, while a node
numbered higher than something it depends on is a sequencing bug the shape makes
visible.

**A shared node is expanded once.** Second and later parents get
`↩ path (expanded above)`. Expanding twice doubles the tree and hides that the
node is shared, and shared nodes are precisely the ones whose contract must not
change casually. Cycles get `↺` and are never followed.

**Detail goes where the motion is.** Levels: L0 requirement only, L1 with tasks,
L2 node tree (the default), L3 adds symbols, L4 adds behaviors, gates and
channels. Default output is L2 for the whole tree with the node in motion
expanded to L4. A full L4 tree of a real trace is unreadable and buries the one
node that matters.

**Subtrees roll up.** Nothing changing collapses to `⊘ pkg/… ⊕ 6 nodes
absorbed`; entirely finished collapses to `✓ … ⊕ 4 nodes · 9 behaviors`.
Absorbed nodes never disappear, though — they are the reviewable evidence of
where the change stopped.

**Past a seam, keep nesting.** Far-side nodes carry their service prefix
(`payments:internal/ledger/api.go`) and hang off the seam node, since the seam
is what holds the contract.

**Draw the changed subgraph, not the whole trace.** Nodes that change, the path
connecting them, and one hop of absorption frontier — the absorbed nodes
*adjacent* to a changing node, which are what prove where the change stopped.
Everything else traced and unaffected is omitted, not collapsed, behind one
line: `⊕ 14 nodes traced, unaffected (L2-full to show)`. The absorbed set grows
with every trace and never shrinks; spending lines on it each turn trains the
reader to skim. The evidence stays in the trace file, one command away.

Show node status with its symbol, behavior ids and their state, gate state per
node, frontier nodes with why they absorbed, seams with compatibility, drift,
and the loop turn with check results.

`visualize.md` has the Mermaid forms written to
`.design/<ref>.<task-slug>.graph.md` — one per task — on every
state write: context map, file graph, channel view, coverage chain, deploy
sequence.

### During a phase

Expanding a node:

```
[trace] internal/order/service.go  (depth 0, seed: "checkout", R2)
  role: aggregate_root · aggregate: Order · context: Ordering
  purpose: protects the invariant that an order's refunds never exceed its balance
  up   ← internal/http/order_handler.go     change    (response shape moves)
  up   ← internal/worker/reconcile.go       no_change ABSORBED
  up   ← .github/workflows/deploy.yml       change    (invokes: new env var)
  down → internal/order/repository.go       change    (new column read)
  down → pkg/money/money.go                 no_change (fan-in 47)
  down → seam:http:POST /v2/ledger/entries  CROSSING → payments
         └→ payments:internal/ledger/api.go change    (far side reachable)
  down → seam:table:orders                  change    (new column)
  down → seam:http:api.stripe.com/refunds   OPAQUE    (contract recorded)
  down → internal/notify/mailer.go          -         MISPLACED: "email the
         customer" does not serve this purpose → belongs in notify/dispatcher.go
```

Triaging behaviors:

```
[triage] internal/order/service.go :: CreateOrder   (R2)
  aggregate: Order · invariant: refunds never exceed remaining balance
  B4  new       happy  partial refund below balance succeeds
  B5  new       error  refund above balance is rejected, order untouched
  B6  modified  happy  full refund now records the reason code
  B7  unchanged error  refund on a cancelled order still rejected  ← regression
```

Implementing a node:

```
[impl] internal/order/service.go :: CreateOrder
  channels  ✓  A: loadOrder→checkPolicy→record→publish · one · 4 E · 4 R
               boundary: handler DTO · layers: retry(3),trace · scope: tx
  gate      ✓  B4 G1-G10 · red: "expected InsufficientBalance, got <nil>"
  A         ✓  B4 B6 green
  A_recheck +  B8 concurrent double-refund is idempotent (found in code)
               → back through channels → test → gate before any code for B8
  E         ✓  B5 propagate, B8 retry-once, B9 die on negative balance
  finalize  ✓  B10 emits refund.recorded · full suite green · purpose intact
```

Before the first edit of a requirement, show the ordered change set with
one-line reasons and the `no_change` nodes with their invariants. Correcting a
wrong trace is far cheaper than correcting a wrong diff, so this list is the
thing worth the user's attention.

## Language independence

The method never changes. Only the mechanics of "who calls this" change, and
`lang/<name>.md` covers them per stack — Go, Rust, Java, TypeScript, JavaScript,
Effect, Ruby, Python, Bash, GitHub Actions, Terraform — each answering the same
six questions.
`lang/TEMPLATE.md` is that question set, so an uncovered stack is a fill-in. Prefer an LSP or the compiler, use grep as
fallback, and mark grep-only edges as weak evidence so triage can see the
uncertainty.

Two edge kinds carry the graph across language boundaries and are what let a Go
service, a Ruby script and a workflow file sit in one graph:

- **`invokes`** — same host, different process. A workflow `run:` step calls a
  shell script; the script calls a binary; a job `needs:` another job.
- **`requests`** — synchronous network call: HTTP, gRPC, GraphQL.
- **`publishes` / `subscribes`** — a topic or queue. The far side is unknown by
  design, which is exactly why the consumer set is unprovable.
- **`reads_writes`** — shared state instead of control flow. A table, a view, a
  cache key, a bucket, an env var. No static tool will find these.
- **`provisions`** — infra defines runtime behavior: Terraform, k8s manifests,
  gateway or mesh config, DNS, feature flags. These change behavior with no code
  diff at all, which makes them the easiest edges to forget and the hardest
  breakages to explain.

## Where the tiers meet

When a task's requirements are all done, `close` ascends: update tier 0-1
statuses, regenerate the diagram, and pick the next task by dependency rather
than by the ticket's bullet order. When a task's trace reveals work belonging to
a different requirement, do not absorb it — create the task, link the
dependency, and keep the current requirement's scope intact.

## Files

- `graph.json` — tiers, phases, stop conditions, contract and fingerprint
  schemas. Edit this to tune the method; the skill reads it.
- `ticket.template.json` — tiers 0-1, the shape the log folds into.
- `trace.template.json` — tiers 2-4, the shape the log folds into.
- `task-model.template.json` — the per-task domain snapshot.
- `scripts/design.py` — the CLI: one subcommand per decision.
- `scripts/render_graph.py`, `scripts/fold.py`, `scripts/design_state.py` — the fold
  and the rendered views.
- `hooks/hooks.json` — PostToolUse, so any write under `.design/` redraws.
- `principles.md` — the method in 43 tool-free statements. Precedence over
  everything else here.
- `INSTALL.md` — local, per-repo, and plugin install; the `boon-plugins` layout;
  team rollout.
- `dependencies.md` — ponytail and caveman: handoff phases, what each may not
  override, and how conflicts resolve.
- `loop.md` — the loop, the two gates, harness selection, the check manifest,
  reading the close, the stop condition.
- `gate.md` — the ten checks, verifying red-for-the-right-reason per language,
  and the ledger.
- `shapes.md` — records, ids, variants, errors; the A/E/R channels; boundary
  parsing, layering, scope and substitutability, rendered per language.
- `domain.md` — mining the ubiquitous language, subdomain classification,
  aggregate sizing, the role taxonomy and service discipline, entities vs value objects, domain events, the context map.
- `tracing.md` — evidence tiers, cross-language edges, reading purpose off
  existing code, and the pointer table into `lang/`.
- `lang/*.md` — one per stack: walk up, walk down, prove R, render A/E/R, detect
  drift, and what defeats static tracing there.
- `crossing.md` — seams: consumer discovery, error translation, deploy order,
  and seam drift.
- `visualize.md` — the Mermaid diagram, and when to regenerate it.

## Install

```
/plugin marketplace add getboon/boon-plugins
/plugin install design-thinking@boon-plugins
```

This repository's skill folder includes its scripts and can be installed alone
using `npx skills add /path/to/harness --skill design-thinking`. The commands
above refer to the original upstream marketplace, not this repository.
Skill installation renders graphs through the CLI. The optional PostToolUse
hook is available only with a full Claude plugin installation.
See `INSTALL.md` for this copy's installation instructions.

Keep `.design/` committed if traces should be reviewable in PRs — a reviewer
seeing which nodes you marked `no_change` and why is a better review than
reading the diff alone.
