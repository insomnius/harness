# Rails benchmark runner

This adapter runs the Rails Foundation's Agents on Rails **Fizzy** feature
tasks with the same Codex model in three conditions: no skill, design-thinking
with history cleared between tasks, and design-thinking with history retained.
Each ticket gets a new Codex conversation. Within a condition, code evolves
through the selected ticket sequence. The model and all its shell tools run in
the benchmark Docker container; hidden verifiers are copied in only after the
agent has finished that ticket.

Keep the upstream corpus and all trial output outside this repository. The
corpus includes a canary and hidden tests; do not publish it, add it to a
prompt, or commit trial output. The runner checks the upstream corpus revision
`168d25fae0b9a1df857e9db90440998011fbb350` by default.

## Prerequisites

- Docker with enough space to build the upstream Fizzy image (first build takes
  several minutes).
- Python 3.10 or newer on the host, Git, Node.js, Codex CLI, and an active
  `codex login` session.
- A local checkout of `rails/ai-evals`, kept outside the agent workspace. The
  runner needs the official task seed patches and hidden verifiers locally.

The runner builds the upstream image and a thin derived image. The derived
image adds Python 3 because design-thinking's bundled CLI uses it; both skill
conditions and baseline receive the same runtime. The container receives the
Codex login file needed for the model request, but no host workspace, Docker
socket, corpus checkout, or hidden verifier before grading. API access is
available to the model container so Codex can authenticate; this is broader
network access than the upstream leaderboard's allowlist and is held constant
across the A/B conditions.

## Run the pilot

Start with a short plan to confirm corpus and task IDs:

```sh
python3 benchmark/rails/runner.py \
  --corpus /tmp/rails-ai-evals-sparse \
  --tasks ft-card-stalled-quiet-clock,ft-card-drop-settled-landing \
  --plan
```

Run one paired sequence across all three conditions:

```sh
python3 benchmark/rails/runner.py \
  --corpus /tmp/rails-ai-evals-sparse \
  --results /tmp/harness-rails-pilot \
  --tasks ft-card-stalled-quiet-clock,ft-card-drop-settled-landing \
  --conditions baseline,skill-cold,skill-warm \
  --repeats 1 \
  --model gpt-6-luna \
  --reasoning-effort max \
  --timeout-minutes 90 \
  --keep-workspaces
```

The two card tickets form a related sequence. Baseline gets the same
repository guidance and code-comment rule as both skill conditions. The cold
condition removes `.design/` before each ticket. The warm condition retains it.
Each run starts from the same pinned Fizzy image and applies the official seed
patches in sequence. A seed patch conflict is recorded as a failed setup rather
than silently changing the task.

To add repetitions, use `--repeats 3`; the runner shuffles condition order with
a fixed seed and records it in `run-metadata.json`. For a first run, one repeat
is a pilot, not a performance claim. Do not compare the resulting figures
directly with published leaderboard numbers: this adapter uses Codex rather
than the benchmark's miniswen agent and allows network access for Codex login.

## What gets measured

`trials.jsonl` and each task's `result.json` capture task and corpus hashes,
model/effort, reported token usage (or input-plus-output totals when Codex
omits its total), Codex event/tool counts, tool failures,
observed tool durations and output size, documentation paths noticed in tool
commands, `.design/` bytes and log records, code-comment additions, agent time,
independent suite/verifier results, and end-to-end elapsed time. The summary
reports success rate among completed trials and separately counts interrupted
trials. It also reports hidden-verifier test-case accuracy and assertion
accuracy; assertion accuracy is left unknown when the verifier output reports
runtime errors. Successful-run mean, median, p90, token totals, tool failures,
and documentation-state size are grouped by condition. Missing token fields
stay unknown. If a run was interrupted after its logs were written, refresh
derived records and the summary without making model calls:

```sh
python3 benchmark/rails/runner.py \
  --corpus /tmp/rails-ai-evals-sparse \
  --results /tmp/harness-rails-pilot \
  --tasks ft-card-stalled-quiet-clock,ft-card-drop-settled-landing \
  --refresh-existing
```

The runner does not treat a skill file being present as proof it was followed.
It records skill availability and explicit activation separately from observed
skill-related events and `.design/` writes. The trial prompt asks skill
conditions to invoke `$design-thinking`; inspect `agent-final.md`, event logs,
and state records when interpreting usage.

For an independent Lemans run of matched baseline and design-thinking tasks,
see [`lemans/README.md`](lemans/README.md). That adapter uses Lemans' Miniswen
agent and is reported separately from this Codex-runner experiment.

After a skill-warm coding session completes, the runner automatically makes
two fresh recall runs from the same final code snapshot, even if the feature
verifier found a bug. The runs use and omit its accumulated `.design/` history.
It saves the answers under the warm run and
creates `recall-score-sheet.csv` with blind IDs. A reviewer scores the four
dimensions in `BENCHMARK.md` from 0–2 without opening the private
`private/recall-key-repeat-*.json` until scoring is complete. Token, time, tool,
and documentation measurements for each answer go to `recall.jsonl`. A zero
comment count is not a target; review added comments for important,
non-obvious rationale.

## Artifacts

Results are deliberately written outside the checkout. Preserve these files
for an evaluation: `summary.json`, `trials.jsonl`, per-task JSONL events,
agent output, patch, test logs, and the exact model, skill and corpus revisions.
Use the raw per-trial `elapsed_seconds` as wall time; do not add tool durations
to it. Completed verifier failures remain in the success-rate denominator.
Interrupted attempts remain in attempt counts and wall-time totals, while the
summary reports the success rate among completed trials separately.
