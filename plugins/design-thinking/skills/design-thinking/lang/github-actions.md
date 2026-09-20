# GitHub Actions

> **Illustrative, not normative.** See `TEMPLATE.md` for the six questions.

Workflow YAML is a node like any other, and `needs:` makes CI a graph with the
same shape as the task tier. It is also where the **`invokes`** edge kind earns
its place: workflow runs script, script runs binary, and no single language's
tooling spans that chain.

## 1. Walk up — what triggers or reuses this workflow?

```bash
rg -n 'workflow_call|workflow_dispatch|workflow_run' .github/workflows/
rg -n 'deploy\.yml' .github/ . --hidden -g '!.git'
rg -n 'uses: .*/\.github/workflows/deploy\.yml@' --hidden      # cross-repo reuse
```

A reusable workflow called from **another repository** has an unprovable caller
set — principle 23 exactly. Its `inputs:`, `secrets:` and `outputs:` are a
published contract, so anything removed or narrowed is breaking however few
callers you found.

## 2. Walk down — what does it invoke?

```bash
rg -n 'uses:|run:' .github/workflows/deploy.yml
rg -n 'needs:' .github/workflows/                     # job dependency edges
rg -n 'uses: \./' .github/workflows/                  # local composite actions
rg -n 'run:' -A 3 .github/workflows/deploy.yml | rg '\.sh|make |go run|bundle exec'
```

That last command is the cross-language edge that matters most. Follow it into
`bash.md` and keep tracing — the script is a node, and its args and env are
this workflow's downstream contract.

## 3. Prove R

A workflow's R is unusually large and entirely invisible to static analysis:

```bash
rg -n 'secrets\.|vars\.' .github/workflows/deploy.yml       # secrets and variables
rg -n 'permissions:' -A 6 .github/workflows/deploy.yml      # token scopes
rg -n 'runs-on:|container:|services:' .github/workflows/    # the runner itself
rg -n 'environment:' -A 3 .github/workflows/                # approvals and env secrets
rg -n 'uses: [a-z].*@' .github/workflows/ | rg -v '@[0-9a-f]{40}'   # unpinned actions
```

An action pinned by tag rather than SHA is a dependency that can change under
you with no diff in your repo — the same class of invisibility as a seam whose
provider deployed.

## 4. Render A / E / R

- **A** — the job sequence implied by `needs:`, read as a DAG. A job with no
  `needs:` runs immediately; that is the entrypoint.
- **E** — `continue-on-error`, `if: failure()`, and the retry pattern. Each is
  a policy and each needs a stated loss: `continue-on-error: true` on a test job
  means the pipeline is green while tests fail, which is a fallback with a very
  large loss.
- **R** — secrets, variables, permissions, runner labels, container images,
  service containers, and the environment's approval gate.

```yaml
concurrency:                    # cardinality: without this, two runs race
  group: deploy-${{ github.ref }}
  cancel-in-progress: false     # a deploy is not safe to cancel mid-flight
timeout-minutes: 15             # an unbounded job is an outage amplifier
```

A workflow with no `timeout-minutes` and no `concurrency` group has defaulted
two decisions that must be stated:

- **`concurrency` is the cardinality decision.** Cardinality is stated, not
  defaulted: what does a second run of this workflow, while the first is still
  going, mean? For a deploy, usually "queue, do not cancel".
- **`timeout-minutes` bounds the failure.** Principle 12 requires every retry to
  carry a bound for the same reason a job needs one: unbounded waiting turns a
  stuck step into a held runner and a blocked queue.

## 5. Detect drift

```bash
actionlint                                            # the closest thing to a compiler
gh workflow view deploy.yml
gh run list --workflow=deploy.yml --limit 5
git diff --name-only <traced_at_commit>...HEAD -- .github/
```

Contract hash inputs: `on:` triggers, `inputs:`, `secrets:`, `permissions:`,
`outputs:`, and the `needs:` graph. **Changing `permissions:` or a secret name
propagates to every caller exactly as a signature change does, and nothing will
type-check it** — these are the highest-value `unsure` verdicts in the method.

## 6. What defeats static tracing

- Expressions computed at run time: `uses: ${{ matrix.action }}`.
- `matrix:` fan-out — one job definition, N runtime nodes, and a failure in one
  shard only.
- Repository, organisation and environment settings that live in the GitHub UI
  and not in the repo at all: required checks, branch protection, environment
  approvers, org-level secrets. These change behavior with no commit.
- `GITHUB_TOKEN` default permissions, which are an org setting.
- Anything a composite action does internally, in another repo, at another SHA.
