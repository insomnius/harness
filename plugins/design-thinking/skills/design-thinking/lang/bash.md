# Bash

> **Illustrative, not normative.** See `TEMPLATE.md` for the six questions.

Nodes are scripts. Edges are **invocations**, not imports — so the graph here
joins onto CI workflows above and binaries below, and it is usually the seam
between two languages that neither one's tooling can see.

## 1. Walk up — who calls this script?

```bash
rg -n 'deploy\.sh' --hidden -g '!.git'        # everywhere: YAML, Makefiles, other scripts, docs
rg -n 'deploy\.sh' .github/ ci/ Makefile* Dockerfile* 2>/dev/null
```

Grep the **path**, not a symbol, and search file types you would not think of —
a Dockerfile `RUN` and a cron entry are callers. Evidence tier is `text` at
best; there is no exhaustive upstream trace for a script, which is exactly why
its contract must not change in place (principle 6b).

## 2. Walk down — what does it call?

```bash
rg -n '^\s*(source|\.)\s' scripts/deploy.sh              # sourced files = true imports
rg -no '\./[a-zA-Z0-9_./-]+\.sh' scripts/deploy.sh       # other scripts
rg -n '\b(curl|jq|aws|kubectl|psql|make|go|bundle|terraform)\b' scripts/deploy.sh
```

A sourced file shares variable scope, so it is the bash equivalent of a Go
package — a change inside it reaches the sourcing script's whole body.

## 3. Prove R — and a script's R is its contract

A script's contract is its **arguments, environment variables, exit codes and
stdout shape**, and all four propagate to every caller:

```bash
rg -n '\$\{?[1-9@#]' scripts/deploy.sh                   # positional args = inputs
rg -n '\$\{?[A-Z_]{3,}' scripts/deploy.sh | sort -u      # env vars = R
rg -n 'exit [0-9]+' scripts/deploy.sh                    # exit codes = E
rg -n '\b(command -v|which)\b' scripts/deploy.sh         # required binaries = R
```

Every required binary and every env var is an R entry. "We cannot deploy
without `AWS_PROFILE`" is exactly the sentence principle 13 asks you to
complete, and nothing here will check it for you — so it gets written down and
asserted at the top:

```bash
set -euo pipefail
: "${AWS_PROFILE:?AWS_PROFILE is required}"
command -v jq >/dev/null || { echo "jq is required" >&2; exit 3; }
```

**Never reuse bash's special variable names**, and note they fail in two
different ways:

- `UID`, `EUID`, `PPID` are **readonly** — assignment errors out loudly under
  `set -e`, which is the good case.
- `GROUPS`, `PWD`, `SECONDS`, `RANDOM`, `LINENO`, `IFS`, `OSTYPE` accept the
  assignment but do not mean what you wrote: the shell either overwrites the
  value or reinterprets it. That failure is silent, and it surfaces as a logic
  bug in whatever consumes the value rather than at the assignment.

## 4. Render A / E / R

- **A** — the script top to bottom under `set -euo pipefail`. Without that
  line, A is a lie: a failing command in the middle continues to the next.
- **E** — a distinct exit code per failure mode, documented in a header
  comment. One code for everything is the absence of a policy. `|| true` is a
  fallback and the loss it accepts must be stated.
- **R** — args, env, binaries, and network reachability.

```bash
# scope: cleanup that an early exit cannot skip (principle 15)
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT INT TERM
```

`trap ... EXIT` is the only structural cleanup bash has. A `rm` on the last line
is skipped by every non-zero exit above it.

## 5. Detect drift

```bash
shellcheck scripts/deploy.sh                             # the closest thing to a compiler
git diff --name-only <traced_at_commit>...HEAD -- scripts/
bash -n scripts/deploy.sh                                # syntax only
```

Contract hash inputs: positional parameters used, env vars read, exit codes
emitted, and the stdout shape if anything parses it. A caller piping this
script into `jq` depends on that shape as hard as on any signature.

## 6. What defeats static tracing

- `eval`, and any command assembled from a variable.
- `$@` forwarded to another script — the real callee is chosen by the caller.
- `PATH` deciding which binary runs. A different `PATH` in CI than on a laptop
  is a different graph.
- Anything reached over the network: `curl | bash` is an edge to a node you do
  not control and cannot pin. Record it as `OPAQUE` and record the contract.
- Cron, systemd timers and CI schedules — callers with no file reference at all.
