# The loop

> **Illustrative, not normative.** The loop and its closure rule are principles
> (`principles.md` 1-3, 26-27). The harnesses, commands and flags below are
> examples from stacks that happened to be written down. Adapt them; if your
> stack is not here, ask the principle's question and find its local answer.


Work is a loop, not a pipeline. One turn takes one natural-language requirement
and ends when an automated check says it is satisfied.

```
        natural language requirement
                    │
      ┌─────────────▼──────────────┐
      │  DECIPHER                  │  requirements → language → keyword →
      │  prose → graph delta       │  locate → trace → cross → triage → order
      └─────────────┬──────────────┘
                    │  which nodes, symbols, behaviors change, in what order
      ┌─────────────▼──────────────┐
      │  SPECIFY                   │  acceptance (red, requirement altitude)
      │  done, made executable     │  channels + test (red, behavior altitude)
      └─────────────┬──────────────┘
      ┌─────────────▼──────────────┐
      │  GATE                      │  ten checks, per behavior, blocking
      └─────────────┬──────────────┘
      ┌─────────────▼──────────────┐
      │  CHANGE                    │  implement in passes → retrace
      └─────────────┬──────────────┘
      ┌─────────────▼──────────────┐
      │  CLOSE                     │  run unit → contract → acceptance
      │  green closes it, not you  │  red routes back with the reason
      └─────────────┬──────────────┘
                    │
        next requirement, warmer glossary
```

**The closure rule.** A requirement is closed by an automated check going from
red to green — never by an agent judging that the work looks done. That
judgment is the weakest link available, and replacing it is the point of this
whole file. If a requirement genuinely cannot be expressed as an automated
check, say so, name who closes it manually and on what evidence, and do not
close it yourself.

## Two gates, two altitudes

| | Requirement gate (`acceptance`) | Behavior gate (`gate`) |
|---|---|---|
| altitude | where the user observes it | one symbol |
| artifact | acceptance spec | unit test |
| written | before any work on the requirement | before any code for the behavior |
| must be | red for the intended reason | red for the intended reason |
| closes | the loop turn | the behavior |

Same discipline twice. The behavior gate stops you writing unspecified code; the
requirement gate stops you writing code toward an undefined outcome.

## Choosing the harness

By where the requirement is observable, not by preference. Two altitudes for one
requirement means it is two requirements.

| Requirement is about | Harness | Assert on |
|---|---|---|
| a user-visible flow | Playwright, Cypress, Selenium | what the user sees and can do |
| an HTTP or RPC contract | API test, or a contract test | status, shape, headers, errors |
| a command or script | bats, shunit2, plain script | exit code, stdout shape, side effects |
| an event or queue | publish, then assert the consumer's effect | the observable effect, never the handler call |
| a pipeline or workflow | a real run: branch push, `act`, `workflow_dispatch` | run conclusion and produced artifacts |
| a migration or data shape | migrate a seeded DB, then assert | shape, plus that the down path restores it |

```bash
# browser
npx playwright test tests/acceptance/partial-refund.spec.ts

# http
go test ./test/acceptance -run TestPartialRefundEndpoint
npx vitest run test/acceptance/refund.api.test.ts

# cli
bats test/acceptance/deploy.bats

# event
go test ./test/acceptance -run TestRefundRecordedConsumer

# workflow — the only honest check is a run
gh workflow run deploy.yml -f environment=staging && gh run watch

# migration
psql -f db/seed.sql && migrate up && psql -f test/assert_schema.sql
```

## Playwright specifics

If the requirement is user-visible, this is the harness most people reach for,
and it is also the easiest to make flaky. Non-negotiables:

```ts
// stable selectors — never CSS classes or nth-child
await page.getByTestId('refund-amount').fill('25.00');
await page.getByRole('button', { name: 'Request refund' }).click();

// assert on the outcome, and let auto-waiting do the waiting
await expect(page.getByTestId('refund-status')).toHaveText('Approved');

// NEVER
await page.waitForTimeout(2000);   // a sleep is a flake with a delay
```

- **Pin time and identity.** Freeze the clock and seed ids, or a
  "created today" assertion fails at midnight and a snapshot fails every run.
- **Seed data per test, tear it down after.** A test depending on data another
  test left behind will pass alone and fail in CI, and then get deleted.
- **Assert the outcome, not the layout.** Copy, ordering and pixel positions
  make the check fail on unrelated work. One assertion on the observable result
  beats twenty on the page.
- **Trace on failure** (`trace: 'on-first-retry'`) so a red check tells you why
  without a re-run.
- **Retries mask flakiness.** A check that passes on retry is not green; treat
  it as a determinism bug in the check.

## The check manifest

Prefer the bundled runner to capture command output and exit status directly:

```sh
design.py check --kind acceptance --id R1 --expect red --cmd '<check>' \
  --reason '<why the observed failure is the intended missing behavior>'
# After implementation, reuse the same command:
design.py check --kind acceptance --id R1 --expect green
```

Use `check --kind baseline --cmd '<suite>'` for inherited failures and
`note --phase preflight --json '{"baseline_failures": [...]}'` for their
reviewed classification (replace `...` with actual JSON values). The runner
stores baseline executions in `check_runs`; it does not infer failure causes.
See [cli.md](cli.md) for behavior contracts, green checks and state commands.
The raw observations below remain useful for externally executed checks.

Acceptance is recorded at `acceptance`, red first, because the requirement gate needs a check
that failed before any code:

```bash
design.py acceptance --id R1 --cmd '<command>' --red '<observed failure>'
```

`--red` or `--green` is required — the command alone records nothing, since a
manifest entry with no observation is exactly the assertion principle 2 refuses.
The command lands in the decision log and the fold surfaces it in the derived
`.design/<ref>.json`, so the loop re-runs the same thing every turn instead of
the agent improvising one. Never edit the fold — the next append rebuilds it:

```json
"checks": {
  "unit":       { "cmd": "go test ./internal/...", "expect_green_before_change": true },
  "contract":   { "cmd": "go test ./contract/...", "expect_green_before_change": true },
  "acceptance": { "cmd": "npx playwright test tests/acceptance/partial-refund.spec.ts",
                  "expect_green_before_change": false },
  "lint":       { "cmd": "golangci-lint run" },
  "baseline_failures": []
}
```

The manifest above illustrates the desired check layers, not fields to
hand-edit into a fold. The CLI populates acceptance commands through
`acceptance`/`check`; record other layer commands as supplemental phase outputs
with `note`, and baseline executions with `check --kind baseline`.

`baseline_failures` is what was already red before the work started. Without
it, an inherited failure reads as your own and a real failure hides in the
noise.

Run order is **unit → contract → acceptance**: cheapest and most localizing
first. A red unit test names the node. A red acceptance check only says the
requirement is unmet.

## Reading the close

| unit | contract | acceptance | Means |
|---|---|---|---|
| green | green | green | closed. Recorded with the red→green transition |
| green | green | **red** | behaviors right, requirement unmet. **The most informative failure in the method** |
| green | **red** | red | the seam is wrong — back to `cross` |
| **red** | — | red | a behavior is wrong — back to `implement` |
| green | green | green *on retry* | not green. Fix the check's determinism |

That second row is the one worth internalizing. Every unit test passing while
the acceptance check stays red means one of exactly two things, and they route
differently:

- **the graph delta missed a node** — something in the path was never traced.
  Back to `trace`, with the acceptance failure as the new seed.
- **the requirement was misunderstood** — the behaviors are correct and are the
  wrong behaviors. Back to `language`; no amount of implementation fixes this.

Read the expected-versus-observed diff before deciding which. Guessing here
produces the worst outcome available: correct code, wrong feature, all tests
green except the one that mattered.

## Ambiguities become assertions

Every ambiguity in the register with basis `assumed` gets an assertion in the
acceptance check. That is how the register stops being a list of good
intentions:

```
A3  "Does a partial refund reopen the order?"
    expectation: no, the order stays closed
    basis: assumed
    → assertion: after a partial refund, order status is still 'closed'
```

When it passes, the assumption is confirmed by machine. When it fails, the
assumption was wrong — and that is a **requirement finding to report**, not a
bug to quietly fix. Falsified assumptions go back to the user; that is the
single highest-value output of the loop, because it catches the
misunderstanding before it ships rather than after.

An ambiguity with no possible assertion is escalated at `acceptance`, not
carried silently to the end.

## The stop condition

When a turn through change → close leaves the acceptance check red without
producing new information, the loop **stops**. It reports:

`graph.json`'s `halt_condition.new_information_is` enumerates what counts as new
information; a materially different diagnosis counts, but relabeling the same
failure does not.

- the expected-versus-observed diff from the acceptance failure
- what was tried on each turn
- the most likely misunderstanding in the requirement itself

An agent grinding against an unchanged red check is the failure mode this rule
exists to prevent. A repeated identical failure is evidence about the
requirement, not about the code.

## What the loop carries forward

New-feature work updates its needed glossary, context map and vocabulary map;
other work reuses existing terminology and ownership. Each
of those makes the next turn's `keyword` phase land faster. That compounding is
the argument for running the loop rather than working ad hoc: the second
requirement in a ticket is cheaper than the first, and the tenth ticket in a
codebase is much cheaper than the first.
