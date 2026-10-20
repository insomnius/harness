# Harness

Reusable skills that help coding agents understand a change before implementing
it and identify code that is becoming difficult to maintain. Use them with
Claude Code, Codex, Pi, OpenCode, or another agent that supports `SKILL.md`.

A skill is a set of instructions and supporting resources loaded by your agent.
These skills guide how the agent works in your project; they are not standalone
linters or applications.

## Choose a skill

| Skill | Use it when you want to… | What you get |
| --- | --- | --- |
| [design-thinking](#design-thinking) | Implement a feature, fix a bug, or trace the impact of a change before editing code. | A map of affected behavior and dependencies, recorded decisions, and test evidence for the implementation. |
| [code-smells](#code-smells) | Review maintainability or refactor code whose structure makes changes harder. | Prioritized findings with locations, evidence, consequences, and focused refactoring options. |

Each skill works independently. You can use `code-smells` to identify a cleanup
target, then `design-thinking` to trace and implement the resulting change.

## Install

### Detect and install automatically

Run this from the project where you want the skills. Requires Node.js 20+,
npm, and Git:

```sh
npx --yes github:insomnius/harness
```

The installer checks for `codex`, `claude`, and `pi` on PATH, plus Codex's
configuration directory (`CODEX_HOME` or `~/.codex`) and Pi's agent directory
(`PI_CODING_AGENT_DIR` or `~/.pi/agent`). It installs both skills for every
detected client:

- **Claude Code:** registers the Harness marketplace and installs its plugins
  through the `claude` CLI, including design-thinking's rendering hook. This
  requires access to the GitHub repository.
- **Codex and Pi:** copies the complete bundled skills into the current project's
  `.agents/skills/` directory, which both clients discover. If both are selected,
  they share a single copy.

```sh
# Preview detected clients and installation actions.
npx --yes github:insomnius/harness --dry-run

# Select a client explicitly, including a desktop-only Codex setup.
npx --yes github:insomnius/harness --agent codex
npx --yes github:insomnius/harness --agent claude-code
npx --yes github:insomnius/harness --agent pi

# Install across projects, or select just one skill.
npx --yes github:insomnius/harness --global
npx --yes github:insomnius/harness --skill code-smells

# Replace an older or modified shared Codex/Pi skill copy.
npx --yes github:insomnius/harness --agent codex --force
```

The default scope is the current project. `--global` uses `~/.agents/skills`
for Codex and Pi, and Claude's user plugin scope. Repeat `--agent` or `--skill`
to select multiple values. Identical skill copies are skipped; different existing
copies require `--force`. If detection finds no client, the installer explains
how to select one explicitly. Start a new agent session after installation.

The GitHub command uses the version pushed to this repository. To run an
unpublished checkout now, use its local path from the target project:

```sh
npx --yes --package=/absolute/path/to/harness harness-skills --dry-run
npx --yes --package=/absolute/path/to/harness harness-skills
```

The agent-specific commands below remain available for manual installation.

### Claude Code

Use the plugin marketplace to install the skills and design-thinking's optional
rendering hook. Run inside Claude Code:

```text
/plugin marketplace add insomnius/harness
/plugin install design-thinking@harness
/plugin install code-smells@harness
```

Install either plugin or both. See [plugin usage](#claude-code-plugin-usage)
below for invocation examples.

### Codex

Requires Node.js and npm. Run this from the project where you want the skills:

```sh
npx skills add insomnius/harness \
  --skill design-thinking code-smells --agent codex
```

This installs the complete skill folders for Codex. Add `-g` to make them
available across projects.

### Pi

```sh
npx --yes github:insomnius/harness --agent pi
```

Add `--global` to install across projects, or `--skill code-smells` to select
one skill. Manual setup also works: copy each complete skill folder from
`plugins/<name>/skills/<name>/` into `.agents/skills/` (project) or
`~/.agents/skills/` (user). These shared locations are supported by both Pi
and Codex; no separate copy is needed if already installed there.

Start a new Pi session or run `/reload`, then invoke either skill:

```text
/skill:design-thinking Implement partial refunds with tests.
/skill:code-smells Review the current diff for maintainability issues.
```

Pi installs standalone skills, not Claude's rendering hook. Design-thinking's
CLI still renders graphs when recording decisions. Review the skills before
granting project trust. See [Pi's skill documentation](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/skills.md).

### Other agents and installation options

To choose skills and agents interactively:

```sh
npx skills add insomnius/harness
```

Other useful options:

```sh
# Preview the available skills without installing.
npx skills add insomnius/harness --list

# Install only code-smells for OpenCode in the current project.
npx skills add insomnius/harness --skill code-smells --agent opencode

# Make both skills available to Codex across your projects.
npx skills add insomnius/harness \
  --skill design-thinking code-smells --agent codex -g
```

Installation includes each skill's supporting files. The default scope is the
current project; `-g` selects your user directory. See the
[Skills CLI documentation](https://skills.sh/docs/cli) for other supported agents
and installation options. Installation was tested with `skills@1.7.2`.

## Standalone frontend security checker

Harness also includes a deterministic script, separate from its agent skills. No agent, model or skill installation is required. It uses fixed rules and explicit project configuration to scan public builds for private files, known environment values, credential formats and source maps. No automatic fixes or deployment.

From this checkout, copy the example into your project and configure its actual public output paths:

```sh
cp tools/frontend-security/frontend-security.config.example.json /path/to/project/frontend-security.config.json
bun run security:check --config /path/to/project/frontend-security.config.json
```

Requires Bun 1.3+ for the checker; the skill installer remains Node.js-only. Normal checks are local/read-only. Add `--live` only with permission to probe the project's configured owned origins. Exit codes are `0` passed, `1` findings, `2` incomplete/error; both nonzero codes fail CI. Results depend on the supplied artifacts, configuration, environment and, in live mode, HTTP responses—not model judgment. A passed scoped scan is not an exhaustive security guarantee.

The executable is packaged as `frontend-security`. After these changes are pushed, it can also be invoked with `npx --yes --package=github:insomnius/harness frontend-security --config /path/to/project/frontend-security.config.json`. Until then use the local checkout command above.

```sh
bun run test:security
```

See [the tool README](tools/frontend-security/README.md) for the versioned configuration, redacted JSON reports, coverage limits and optional explicitly authorized Docker comparisons. Project-specific policies stay in their projects; Harness contains no production targets or real credentials.

## design-thinking

**Understand which behavior needs to change, where it belongs, and how to prove
the change works.** This is a software implementation workflow, not a visual
design or brainstorming skill.

Use it for features, bug fixes, refactors, migrations, and CI or infrastructure
changes—especially when a requirement describes an outcome without identifying
the code involved. It can also resume or revalidate an existing trace.

The skill directs your agent to:

1. Understand the requirement using existing terminology and ownership; for
   new features, model the needed domain vocabulary and boundaries.
2. Trace relevant callers, dependencies, and boundaries to determine which
   files and behaviors need to change and which can stay as they are.
3. Describe success paths, errors, and required dependencies, then record
   failing checks before implementing the behavior.
4. Make the change, revisit the trace, and run the checks needed to demonstrate
   that the requirement is satisfied.

This is an opinionated workflow: it requires recorded test evidence before
behavior changes and does not treat an unverified implementation as complete.
Graph reports and the state machine are mandatory alongside TDD; DDD modeling
is reserved for new features. The entry-point instructions load detailed guides
only when relevant, and the bundled CLI shows the current phase, blockers and
transitions. It can capture test execution directly, so agents do not need to
write scripts to manipulate workflow state. Expect more investigation and
bookkeeping than a quick edit.

### Example requests

In Codex, invoke the installed skill by name:

```text
$design-thinking Add partial refunds. Trace the existing payment flow,
identify the affected rules, and prove the new behavior with tests.
```

```text
$design-thinking Fix duplicate webhook processing. Find where idempotency
belongs and trace the callers before changing the implementation.
```

In other agents, select `design-thinking` through their skill interface and
provide the same task description.

### What it produces

The bundled Python CLI records decisions in the target project's `.design/`
directory. An append-only log is the source for derived requirement records,
domain models, call traces, rendered graphs, and an index for later recall.
Those artifacts make it possible to inspect why a component was changed or
left alone. Decide per project whether to commit the traces.

**Requirements:** Python 3, Git, and the tools needed to test your project.
Language guides cover Go, Rust, Java, TypeScript, JavaScript, Effect, Ruby,
Python, Bash, GitHub Actions, and Terraform. Optional companion skills
`ponytail` and `caveman` are not bundled; the workflow includes fallbacks.

Read the [full skill](plugins/design-thinking/skills/design-thinking/SKILL.md),
[principles](plugins/design-thinking/skills/design-thinking/principles.md), or
[installation details](plugins/design-thinking/skills/design-thinking/INSTALL.md).

## code-smells

**Find structural problems that make code harder to understand, change, or
test—and explain the cost with evidence.**

Use it to review a diff, audit a component, prioritize technical debt, or carry
out a requested cleanup. A review request produces findings. A refactoring
request directs the agent to make focused changes and verify that observable
behavior is preserved.

For each actionable finding, the skill asks for:

- A file location and symbol, plus the smell's name.
- Evidence from the implementation, callers, or tests.
- The concrete maintenance consequence and its priority.
- The smallest useful remedy and the behavior that needs protection.

It also checks whether the structure is intentional. A long function, switch
statement, data record, or comment is not automatically a problem. The agent
should explain the actual cost, acknowledge uncertainty, and report no
actionable findings when that is the supported conclusion.

### Example requests

```text
$code-smells Review my current diff. Report actionable maintainability
issues with file locations and evidence. Do not edit files.
```

```text
$code-smells Review src/billing for duplicated business rules and coupling.
Prioritize the findings by the cost of future changes.
```

```text
$code-smells Refactor the duplicated discount policy in these checkout
handlers. Preserve behavior and run the relevant tests.
```

### The 23 bundled smells

Every smell has a local guide containing its definition, example, evidence to
collect, refactoring options, false-positive cautions, and verification advice.
The skill needs no website access.

| Category | Smells |
| --- | --- |
| Bloaters | Long Method; Large Class; Primitive Obsession; Long Parameter List; Data Clumps |
| Object-Orientation Abusers | Switch Statements; Temporary Field; Refused Bequest; Alternative Classes with Different Interfaces |
| Change Preventers | Divergent Change; Shotgun Surgery; Parallel Inheritance Hierarchies |
| Dispensables | Comments; Duplicate Code; Lazy Class; Data Class; Dead Code; Speculative Generality |
| Couplers | Feature Envy; Inappropriate Intimacy; Message Chains; Middle Man |
| Other | Incomplete Library Class |

Read the [full skill](plugins/code-smells/skills/code-smells/SKILL.md) or browse
the [local catalog](plugins/code-smells/skills/code-smells/references/diagnostics.md).
There are no bundled scripts or runtime dependencies; an agent still needs
access to your code and, for refactoring, your project's test tools.

## Claude Code plugin usage

The marketplace route above installs the full plugins, including design-thinking's
PostToolUse hook, which redraws graphs after edits. The `npx` route installs
skills and their resources.

Plugin invocation uses namespaced commands:

```text
/design-thinking:design-thinking Implement partial refunds with tests.
/code-smells:code-smells Review the current diff for maintainability issues.
```

Choose one installation route per agent to avoid duplicate skill entries.
Without the hook, design-thinking still renders graphs when its CLI records
decisions. Codex manifests are included, but the documented Codex installation
routes here install standalone skills, through the bundled installer or
`npx skills`.

## Develop and verify locally

The installer is a Node.js executable with no runtime dependencies or build
step. Test its detection, destinations, existing-file handling, and Claude
commands with:

```sh
npm test
bun run test:security
node bin/harness.mjs --dry-run
```

`package.json` packages the executable and complete skill folders for `npx`.
Check the distributable contents with `npm pack --dry-run`; keep benchmarks,
Python bytecode, and other generated files out of the package. GitHub execution
uses this package directly and does not require publishing to the npm registry.

The shared skill folders live under `plugins/<name>/skills/<name>/`. Keep each
folder's scripts and references together when copying it to another harness.
To preview skills from a local checkout:

```sh
npx skills add /absolute/path/to/harness --list
```

From this repository, run design-thinking's behavioral checks:

```sh
python3 plugins/design-thinking/skills/design-thinking/scripts/test_design.py
```

When invoking its CLI manually, use the installed script's absolute path and
keep your working directory in the project being changed. That determines
where `.design/` state is written.

## Sources

- **design-thinking** was imported at version `2.1.4` and adapted for standalone
  skill installation. Upstream attribution, the exact source commit, and local
  changes are recorded in
  [UPSTREAM.md](plugins/design-thinking/UPSTREAM.md).
- **code-smells** uses [Refactoring.Guru's taxonomy](https://refactoring.guru/refactoring/smells),
  with locally authored explanations, examples, and review guidance. Source
  links in the guides provide attribution, not a dependency on the website.
