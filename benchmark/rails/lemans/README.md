# Rails tasks on Lemans

This adapter packages two Rails Foundation Fizzy tasks for the official Lemans
harness. Each task has a matched `baseline` and `design-thinking` variant with
the same pinned source, initial application state, task requirements, and
hidden verifier. The skill variant includes the current design-thinking skill
and asks Miniswen to read it. Both variants preserve the Rails repository's
existing guidance and append the same rule to add code comments only for
important reasons.

This is a skill-versus-baseline accuracy and effort comparison. The trials are
independent: each starts from the same seed, and `.design/` history starts
empty. It does not measure retained-history compounding or fresh-session code
recall; the Codex runner documented in [`../README.md`](../README.md) covers
those conditions.

## Prepare

Keep the pinned `rails/ai-evals` checkout and all generated tasks/results
outside this repository. The setup below expects the clean app snapshot and
Python-enabled base image produced by the Rails adapter's `--prepare-only`
mode:

```sh
python3 benchmark/rails/runner.py \
  --corpus /tmp/rails-ai-evals-sparse \
  --results /tmp/harness-rails-lemans-prereq \
  --tasks ft-card-stalled-quiet-clock,ft-card-drop-settled-landing \
  --prepare-only
```

Build a small Lemans image layer so setup commands start in the Rails app
directory. Lemans runs those commands from the image's default directory, while
the shared Rails adapter image defaults to `/workspace`:

```sh
docker build \
  -t harness-fizzy-lemans:rails-ai-evals-168d25f \
  --build-arg BASE_IMAGE=harness-fizzy-codex:rails-ai-evals-168d25f \
  -f benchmark/rails/lemans/Dockerfile \
  benchmark/rails/lemans
```

Lemans needs Ruby 3.4 or newer. This adapter was validated with Lemans 1.4.0
on Ruby 4.0.1. Install that version in the Ruby environment used for the
commands below, then generate the two design-thinking task definitions:

```sh
gem install lemans -v 1.4.0
```

```sh
python3 benchmark/rails/lemans/prepare.py \
  --corpus /tmp/rails-ai-evals-sparse \
  --base-app /tmp/harness-rails-lemans-prereq/cache/fizzy-base \
  --output /tmp/harness-rails-lemans-skill-only \
  --variants design-thinking
```

The corpus revision is pinned to
`168d25fae0b9a1df857e9db90440998011fbb350`. The generated `prepared.json`
records the task list, model, image, and SHA-256 of the skill files so results
can be tied to the exact inputs.

## Run

The generated bench config uses Lemans `miniswen`, Docker with no sandbox
network, and `openai/gpt-6-luna#max`. Miniswen makes model requests from the
host and operates on the isolated task container. Set the provider credential
expected by RubyLLM in the environment before running; `codex login` credentials
are not an OpenAI API key and are not consumed by this Lemans agent.

```sh
lemans run \
  --bench /tmp/harness-rails-lemans-skill-only \
  --attempts=3 \
  --concurrency=1 \
  --backend=docker \
  --runs-dir=/tmp/harness-rails-lemans-skill-only/runs

lemans report \
  --runs-dir=/tmp/harness-rails-lemans-skill-only/runs \
  --format=csv

python3 benchmark/rails/lemans/analyze.py \
  --runs-dir /tmp/harness-rails-lemans-skill-only/runs \
  --output-dir /tmp/harness-rails-lemans-skill-only/analysis
```

This runs only the two design-thinking tasks, with three attempts each. It does
not rerun baseline. Join the results to the saved baseline by `source_task`;
the analyzer keeps per-task results separate.

```sh
lemans report --runs-dir=/tmp/harness-rails-lemans-skill-only/runs \
  --metadata=condition:design-thinking --aggregate=task
```

Lemans records hidden-verifier reward, model tokens, model steps, cost,
elapsed duration, per-test checks, and an ATIF trajectory with tool calls and
observations. `analyze.py` compares task accuracy and hidden-test case accuracy
by condition, plus tokens, duration, tool counts, and observed skill-file or
design-CLI references. A reward of `1` means the hidden verifier passed. Treat
reading the skill as exposure, not proof that its workflow was followed;
inspect trajectory evidence of tracing and verification. Recall clarity still
needs a separate blinded rubric as described in [`../../../BENCHMARK.md`](../../../BENCHMARK.md).

Before a model run, validate the environment and golden solutions with the
oracle agent. This only tests packaging and grading; its perfect score is not
a model or skill result:

```sh
lemans run \
  --bench /tmp/harness-rails-lemans-skill-only \
  --agent=oracle \
  --attempts=1 \
  --concurrency=1 \
  --backend=docker \
  --runs-dir=/tmp/harness-rails-lemans-skill-only/oracle-smoke
```

## Scope and limits

The underlying Rails task instructions and hidden verification tests are kept
from the pinned public benchmark. Lemans' table report grades task-level
reward; `analyze.py` also reads its saved per-test checks to calculate case
accuracy.
This adapter also uses Lemans' `miniswen` agent, not the authenticated Codex CLI
used by the adjacent runner. It therefore measures the effect of making the
skill available to Miniswen under the configured model, not native Codex skill
activation. Do not compare its scores directly with Rails leaderboard numbers
or with the separate Codex run as if only the skill changed.
