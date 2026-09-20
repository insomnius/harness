# Tracing up and down, per language

> **Illustrative, not normative.** Tracing up and down, stopping at absorption,
> and reading purpose from what exists are principles (`principles.md` 4-7).
> The commands below are examples for a few stacks. In an uncovered stack, ask
> the same questions and find that stack's way of answering them.


The method never changes. Only the mechanics of two questions change:

- **Up:** who calls this symbol?
- **Down:** what does it call, and what does it depend on?

Record the strongest evidence available on each edge. An LSP or compiler
understands interfaces, generics and shadowing; grep does not. Mark grep-only
edges as `evidence: text` so triage can see where the map is soft.

## Order of preference

This is `graph.json`'s `evidence_tiers.ladder`, in its order, and the names are
the values `design.py --evidence` records. Reach for the highest tier the stack
allows, and record the one you actually reached.

1. **`compiler`** — break the contract deliberately, read the error list,
   revert. The fastest *exhaustive* upstream trace that exists, and the only
   one that finds interface- and generic-dispatched callers. Go, Rust,
   TypeScript, Java. Revert immediately.
2. **`coverage`** — run the suite with coverage and read which tests executed
   the symbol. An empirical caller set, and **the strongest tier available with
   no compiler** — which makes it the one that matters in Ruby, Python and
   JavaScript rather than an afterthought.
3. **`references`** — LSP find-references or call hierarchy. Static, so it
   misses dynamic dispatch.
4. **`text`** — ripgrep. No type understanding, but the only tier that finds
   strings, routes, config keys, migrations and framework registrations.
5. **`reasoning`** — DI, reflection, metaprogramming and convention-based
   wiring, worked out by reading. Always the weakest, never sufficient alone
   for a contract change.

**A contract-changing symbol needs tier 1 or 2** (principle 6c). Anything
weaker is `unsure`, and resolving that `unsure` is what actually forces the
coverage run to happen.

## Per-language recipes

One file per language in `lang/`, each answering the same six questions: walk
up, walk down, prove R, render A/E/R, detect drift, and what defeats static
tracing here.

| Stack | File | Strongest evidence available |
|---|---|---|
| Go | `lang/go.md` | compiler — break the signature, read the errors, revert |
| TypeScript | `lang/typescript.md` | compiler — `tsc --noEmit`, weaker under `strict: false` |
| Effect (TS) | `lang/effect-ts.md` | compiler — A/E/R is in the type, so drift is exact |
| Ruby | `lang/ruby.md` | coverage run — the suite is the call graph |
| Python | `lang/python.md` | coverage; compiler under `mypy --strict`, otherwise not available |
| Bash | `lang/bash.md` | text only — no exhaustive upstream trace exists |
| GitHub Actions | `lang/github-actions.md` | `actionlint`; callers across repos are unprovable |
| Terraform | `lang/terraform.md` | `terraform graph`, and `plan -detailed-exitcode` for drift |
| Rust | `lang/rust.md` | compiler — exhaustive `match` makes a domain change enumerate its own callers |
| Java | `lang/java.md` | compiler for the code, `reasoning` for the framework wiring |
| JavaScript | `lang/javascript.md` | coverage run — no compiler tier, so the suite is the caller set |

Read only the file for the language in play. `lang/TEMPLATE.md` is the question
set — an uncovered stack is a fill-in, not a redesign.

## Cross-language edges

This is what makes one graph out of many stacks. Record the edge kind:

| From | To | Kind | How to find it |
|---|---|---|---|
| workflow | script | `invokes` | `run:` step, script path |
| workflow | workflow | `invokes` | `needs:`, `uses: ./`, `workflow_run` |
| script | binary | `invokes` | command name in the script body |
| script | script | `invokes` / `imports` | path, or `source` |
| service | service | `invokes` | HTTP client, queue publish |
| anything | anything | `reads_writes` | shared table, topic, bucket, env var |

`reads_writes` edges are the ones that bite. A Go service and a Ruby worker
sharing a table have no static link at all, and a column rename in one breaks
the other silently. Enumerate them manually during `trace`; they are worth more
than half the import graph.

## Reading a node's purpose and behaviors

Both are read off the repository, never invented. The order matters: tests
first, because they are the only place behavior is stated as behavior.

```bash
# 1. Behaviors, as the codebase already documents them: test names
go test ./internal/order/ -list '.*'
rg -n --type go -g '*_test.go' '^func Test|t\.Run\(' internal/order/
bundle exec rspec spec/order --dry-run --format doc     # doc format IS the behavior list
npx jest --listTests && rg -n "describe\(|it\(" src/order/
rg -n 'name:' .github/workflows/deploy.yml              # step names, same idea

# 2. Exported surface: which symbols could own a behavior
rg -n --type go '^func [A-Z]|^func \([^)]+\) [A-Z]' internal/order/service.go
rg -n --type ruby '^\s*def (self\.)?[a-z]' app/services/order.rb

# 3. Untested behavior - the dangerous kind, present in code and documented nowhere
go test ./internal/order/ -coverprofile=/tmp/c.out && \
  go tool cover -func=/tmp/c.out | rg ' 0.0%'

# 4. Purpose, when the code will not say it plainly: why the node was created
git log --diff-filter=A --format='%h %s' -- internal/order/service.go
git log --format='%s' -20 -- internal/order/service.go   # what it keeps changing for
```

That last command is the most reliable purpose detector there is. A node whose
commit subjects all describe one capability has one purpose. A node whose
subjects wander across unrelated features has already lost it, and every new
behavior you add there compounds the problem — which is exactly what a
`MISPLACED` verdict is protecting against.

Three signals a purpose statement is wrong:

- it contains "and" joining unrelated capabilities → the node is two nodes
- it is a category rather than a capability ("helpers", "utils", "common") →
  no purpose, so nothing can ever be misplaced there, so everything lands there
- the test names do not all fit under it → either the statement is too narrow,
  or behaviors have already accreted that belong elsewhere

## Universal fallbacks

```bash
rg -n --word-regexp 'CreateOrder'
rg -n "'create_order'|\"create_order\"|create-order"     # string form

# co-change index: what historically ships with this node
git log --format='%h' -30 -- internal/order/service.go | \
  xargs -I{} git show --stat --format='' {} | \
  rg '\|' | awk '{print $1}' | sort | uniq -c | sort -rn | head -20
```

The co-change index finds nodes the static graph cannot: fixtures, generated
clients, workflow files, another service's contract. In a repo with DI or
name-based registration it is often better than the import graph.

## Drift detection

```bash
git rev-parse HEAD                      # record as traced_at_commit
git rev-parse HEAD:internal/order/service.go    # record as blob_sha

# later, or on resume:
git diff --name-only <traced_at_commit>...HEAD   # three-dot: compares to merge base
git log --follow --diff-filter=RD -- <path>      # find a rename or deletion
git log --oneline <traced_at_commit>..HEAD -- <path>   # who changed it, and why
```

Intersect the changed paths with your node set. For each hit: compare
`blob_sha` first; if it moved, re-read the symbol and recompute the contract
hash. A changed file with an intact contract hash is not drift — just update
the fingerprint and carry on.

## Things that defeat static tracing

Record as `evidence: reasoning` and verify by running something:

- interface / trait / duck-typed dispatch
- DI containers, service locators, Rails autoloading
- reflection, `send`, `getattr`, `const_get`, dynamic imports
- name-based framework registration: routes, event handlers, queue consumers, cron
- code generation and generated clients
- config-driven behavior and feature flags
- database triggers, views, materialized views
- shell string interpolation building a command at runtime
- workflow `if:` expressions and matrix expansion
- cross-service calls — the trace does not stop at the wire, it becomes a seam
  node and continues on the far side. See `crossing.md`.
