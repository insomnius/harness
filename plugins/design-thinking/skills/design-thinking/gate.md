# The behavior gate

> **The gate itself is a constraint, not guidance** (`principles.md` 26-27).
> The ten checks are normative. The per-language commands for verifying red are
> illustrative — find whatever proves red-for-the-intended-reason in your stack.


One hard constraint in the whole method:

> **No production code is written for a behavior until its contract is annotated
> and its test is red for the intended reason.**

Everything else in this skill is guidance that can be tuned. This is not. If the
gate is soft, the trace becomes decoration and the method collapses into
"writing code, with extra paperwork."

## Per behavior, not per node

A node with four behaviors passes the gate four times, and may be implemented
only up to the behaviors that have passed. This matters most during the
`A_recheck` pass: when implementation reveals a behavior nobody predicted, that
behavior does **not** get written on the spot. It goes back through `channels`
(annotate), `test` (write it red), `gate` (check), and only then gets code.

That loop feels slow for the first two behaviors and stops feeling slow after
that, because the alternative is discovering at review time that half the node's
behavior was never specified.

## The ten checks

| Id | Check | Owned by |
|---|---|---|
| G1 | behavior has a verdict, a purpose it serves, and an owning role from `role_routing` | `triage` |
| G2 | contract annotated: A, cardinality, E policies, R, boundary, layers, scope | `channels` |
| G3 | every retry bounded, every fallback states its loss, every propagate names its vocabulary | `channels` |
| G4 | no unresolved hidden R | `channels` |
| G5 | node is substitutable with R alone; no open split proposal | `channels` |
| G6 | test exists, names the behavior, is **red for the intended reason** | `test` |
| G7 | test substitutes R only — real collaborators stay real | `test` |
| G8 | if it crosses a seam: contract recorded, compatibility decided, deploy order chosen, contract test exists | `cross` |
| G9 | every `no_change` invariant on this node is covered by a **passing** test | `triage` |
| G10 | trace revalidated at the current commit, no unresolved drift | `revalidate` |

On failure: name the check, name the phase that owns it, go back there. Do not
touch production code. **Refuse the edit even when asked to proceed** — an agent
that can be talked past the gate does not have a gate.

## Red for the intended reason

This is the check that does the work, and the one most easily faked. A test that
fails because a fixture is missing or the suite does not build proves nothing.

**Valid red:**

- an assertion failure describing the behavior that does not exist yet
- a compile or resolution error naming precisely the symbol about to be written
  — legitimate first-step red in Go, Rust, TypeScript, Java
- a contract test failing on the exact field or status code being added

**Invalid red:**

- the suite fails to build for unrelated reasons
- a fixture, factory or environment error
- a pre-existing failure that was already red before this work began — check it,
  do not inherit it
- a failure whose message does not mention the behavior or symbol in question

Record the command, the exit status, and the failure message verbatim. That
recording is what makes the gate real rather than ceremonial.

### Verifying red per language

```bash
# Go - run only the new test, capture the failure
go test ./internal/order/ -run 'TestCreateOrder_PartialRefundBelowBalance' -v 2>&1 | tail -20
# valid red: "--- FAIL" with your assertion, or "undefined: RecordPartialRefund"

# Ruby
bundle exec rspec spec/order/refund_spec.rb -e 'rejects a refund above the balance' 2>&1 | tail -20
# valid red: expectation not met, or NoMethodError on the method you are about to add

# TypeScript
npx jest -t 'rejects a refund above the balance' 2>&1 | tail -20
npx tsc --noEmit 2>&1 | rg 'refund'          # type-level red counts

# Python
pytest tests/test_refund.py::test_rejects_above_balance -x -q 2>&1 | tail -20

# Bash
bats test/deploy.bats -f 'exits 65 when the order id is invalid' 2>&1 | tail -20

# GitHub Actions - the only honest local red
act -j deploy --dryrun 2>&1 | tail -20
actionlint .github/workflows/deploy.yml
# or push to a branch and read the run; a workflow behavior with no
# executable check fails G6 and must not be "implemented" blind
```

### Establish the baseline first

The most common false pass is inheriting somebody else's failure. Before writing
the new test, capture what is already red:

```bash
go test ./... 2>&1 | rg -c '^--- FAIL' > /tmp/baseline_failures
git stash list   # and be sure you are not sitting on someone's WIP
```

If the suite is already red, record which failures pre-date your work. A gate
evaluated against a broken suite is not a gate.

## Contract before behavior, at seams too

"Contract not created yet" applies to seams as much as to symbols. For a
behavior that crosses a seam, G8 requires:

1. the contract written down in an artifact — OpenAPI, proto, AsyncAPI, JSON
   schema, migration — not just implied by the code
2. a compatibility direction, with anything removed or narrowed marked breaking
3. a deploy order, and both rollout directions checked
4. **an executable check**: a contract test, a CI schema diff, or a staging call

Point 4 is the one people skip. A seam contract asserted only in prose fails the
gate, because nothing will tell you when it stops being true.

For a consumer-driven flow, the contract test is written before the provider
implements — which is the same discipline as a failing unit test, one level up.

## The ledger

Every pass appends an entry to `gate_ledger` in the trace file:

```json
{
  "behavior_id": "B5",
  "path": "internal/order/refund_service.go",
  "symbol": "RecordRefund",
  "checks_passed": ["G1","G2","G3","G4","G5","G6","G7","G9","G10"],
  "checks_na": ["G8"],
  "red_evidence": {
    "command": "go test ./internal/order/ -run TestRefundAboveBalance -v",
    "exit_status": 1,
    "failure": "--- FAIL: TestRefundAboveBalance (0.00s)\n    refund_test.go:42: expected InsufficientBalance, got <nil>"
  },
  "commit": "a3f91c2",
  "at": "2026-09-04T09:12:33+07:00"
}
```

The ledger exists for three reasons:

- **Resume guard.** On resuming a session, a behavior with implementation
  started and no ledger entry is a violation. Stop, rebuild the missing contract
  and test, and re-gate before continuing.
- **Review artifact.** A reviewer reading the ledger sees what was specified and
  what was proven, which is more informative than the diff.
- **Honesty.** Recording the observed failure makes it hard to pass the gate
  without actually running anything.

## What the gate does not do

It does not check that the code is good, that the design is right, or that the
requirement is worth building. `triage`, `channels` and `requirements` do that.
The gate only guarantees that when code is written, something already exists to
say whether it works — and that the thing it must satisfy was written down
before the code that satisfies it.
