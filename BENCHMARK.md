# Design-thinking benchmark

Measure whether design-thinking makes correct changes cheaper and makes code
easier to recall across fresh sessions with minimal documentation. Keep
benchmark instrumentation outside the skill's ordinary workflow. The initial
Rails adapter lives in [`benchmark/rails/`](benchmark/rails/); this protocol
does not itself claim a measured improvement.

## Metrics

| Metric | Definition |
| --- | --- |
| Token usage | Sum model-reported input and output tokens across every request, including retries and any delegated work. Report cached input and reasoning tokens separately when available; do not add them again if they are already included in input/output totals. Record unavailable fields as unknown, not zero. |
| Skill usage | Record which skill and version was activated, explicit or automatic activation, and supporting resources loaded. Distinguish activation from rereading a file. Record observed workflow actions such as tracing, gate evidence, and recall; a file read alone does not prove the instructions were followed. |
| Tool usage | Count calls by tool and purpose: discovery/read, state/recall, edit, verification, and other. Include failures, retries, duration, and output size. Count actual nested calls separately from orchestration wrappers; record commands within batched calls when observable. |
| Mean time to achieve a goal | Wall-clock time from task delivery to the first independently verified successful result, including investigation, skill loading, state writes, and repairs. Report mean, median, and p90 for successful runs alongside success rate, timeout count, and failed-run duration. Record human waiting separately. |
| Behavior accuracy | Report whole-task pass rate and the hidden-verifier test-case pass rate (passed cases divided by non-skipped cases). Also report assertion pass rate when the verifier completed without runtime errors. Keep case-level and assertion-level accuracy separate because a case can contain many assertions and tests are not equally weighted. |
| Recall clarity | Accuracy and evidence quality when a fresh session locates relevant code, explains an invariant and its reason, traces affected callers, and proposes the correct change location. Report time, tokens, tool calls, and documentation consumed to reach that answer. |

Also report total tokens and total elapsed time across all attempts divided by
successful goals. Include failed attempts in those numerators; if no goal
succeeds, report the ratio as undefined. Wall-clock time is not the sum of tool
durations when tools run concurrently.

Correctness is a prerequisite for efficiency claims: score independent
acceptance checks and regressions against earlier behavior. A cheaper run that
does not meet the goal is a failure. Skill and tool counts explain cost; fewer
calls or more skill activations are not inherently better.

## Controlled comparison

Use the same model/version, reasoning settings, tools, starting code, task
sequence, per-task budget, and fixed repository instructions in three conditions:

1. Baseline: no design-thinking skill or `.design/` history.
2. Design-thinking with previous `.design/` history removed between tasks.
3. Design-thinking with `.design/` history retained between tasks.

Each condition keeps its own evolving code. Start a fresh conversation for every
task; clear cross-session agent memory other than the explicitly retained files.
Hold companion-skill availability constant between the skill conditions and log
actual usage. Apply the same important-reason-only code comment policy in every
condition to isolate the workflow and memory effects.

Use related tasks that revisit earlier decisions, plus unrelated tasks to expose
overhead. Repeat sequences, vary condition execution order, and retain unseen
sequences for evaluating later skill revisions. Freeze task expectations and
scoring checks before running; keep scoring checks outside the agent's editable
workspace. Count timeouts and incomplete tasks rather than silently dropping
them. Predefine whether a failed step stops its sequence or is repaired; record
any repair and its cost.

At selected checkpoints, clone the same code snapshot into paired recall runs
with and without the accumulated `.design/` history. Use the skill in both.
This separates memory's contribution from differences in earlier generated code.
Include a checkpoint where code has changed since the recorded decision to test
whether the agent revalidates old context.

## Recall with minimal documentation

Give a fresh agent the repository and a bounded question, for example:

> Where is the rule that prevents over-refunding enforced, why is it there,
> and which callers and tests would need attention if that rule changed?

Use a prepared rubric checked against current code and test behavior. Score each
dimension from 0 to 2: 0 incorrect/missing, 1 partly correct, 2 correct and
supported by concrete code or test references.

- Location of the owning rule.
- Explanation of the invariant and important reason; acknowledge when historical
  intent cannot be established instead of inventing it.
- Relevant callers and boundaries affected by the proposed change.
- Proposed change location and verification needed to preserve other behavior.

Report the four scores separately, plus unsupported claims and the resources
read. Set the time/token budget and acceptable score before comparing runs.
Use a reviewer blinded to the condition where practical; agent self-ratings are
not the score. Check acceptable alternative implementations rather than matching
one exact patch.

Hold existing documentation constant in paired runs. Track newly created prose,
code comments/docstrings, and `.design/` state separately by size; also measure
how much is read. Generated state is part of the documentation cost. Review new
comments for an important, non-obvious reason; zero comments is not a goal in
itself. Keep evaluation questions and answers out of retained history.

## Compounding context

Compare retained-history and fresh-history results at the same task position:
correctness, recall score, tokens, tool calls, and time. Include the cost of
creating, reading, and updating history. Report cumulative costs as well as
individual-task costs; easier later tasks alone do not establish improvement.

Claim a benefit only when history improves verified outcomes or reduces their
cost at comparable correctness and recall quality. Report variability across
repeats and sequences; a small pilot supplies direction, not proof of a general
improvement. Preserve raw run metadata, model usage, tool events, code revisions,
skill revisions, and evaluator results so the comparison can be reproduced.

The Rails adapter records machine-readable task results and raw Codex JSONL
events. Recall scoring remains reviewer-scored because invariant explanations
and evidence quality require a rubric: capture the answer, resources read, and
0–2 scores for each dimension, with condition hidden from the reviewer when
practical. See [`benchmark/rails/README.md`](benchmark/rails/README.md) for
installation, the task sequence, command, measured fields, and known protocol
differences from the public Rails leaderboard. A separate Lemans adapter runs
matched baseline and design-thinking Fizzy tasks with Lemans' Miniswen agent;
see [`benchmark/rails/lemans/README.md`](benchmark/rails/lemans/README.md) for
its setup and scope limits.
