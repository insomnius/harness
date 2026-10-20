# Repository guidance

## Project overview

Harness distributes reusable agent skills and optional Claude Code plugins.
The shared skill folders are the installable units. The root Node.js package
provides an installer with no runtime dependencies or build step.

- `README.md`: user-facing overview, installation, and development commands.
- `package.json`, `bin/harness.mjs`: executable `npx` installer and package contents.
- `tests/install.test.mjs`: installer behavior and packaging checks.
- `bin/frontend-security.mjs`, `tools/frontend-security/`: standalone deterministic checker; not a skill/plugin. Project configurations stay in target projects. The launcher requires explicit `--config`, resolves it before switching to a trusted cwd, and does not build, modify, or deploy targets.
- `tests/security.test.mjs`: checker launcher and packaging contract; `bun run test:security` runs scanner/configuration tests using synthetic data and mocked Docker.
- `.claude-plugin/marketplace.json`: Claude Code marketplace entries.
- `plugins/<name>/.claude-plugin/plugin.json`: Claude Code plugin metadata.
- `plugins/<name>/.codex-plugin/plugin.json`: Codex plugin metadata.
- `plugins/<name>/skills/<name>/`: skill instructions and bundled resources.
- `plugins/design-thinking/hooks/hooks.json`: optional graph-rendering hook.
- `plugins/design-thinking/UPSTREAM.md`: source revision and local adaptations.

The bundled skills are `design-thinking` (implementation tracing and test
evidence) and `code-smells` (maintainability reviews and focused refactoring).
Read the relevant skill files when changing their content or behavior; their
consumer workflows do not need to be invoked for every repository edit.

## Installation and distribution

Lead user-facing instructions with `npx --yes github:insomnius/harness`, then
document manual routes per agent. Keep commands synchronized with
[README.md](README.md), the executable, and the manifests.

The executable detects `codex`, `claude`, and `pi` on PATH and Codex's and Pi's
configuration directories, then installs for every detected client. Default to
project scope; support `--global`, repeated `--agent` and `--skill` selections,
and `--dry-run`.
Copy bundled Codex/Pi skills into shared `.agents/skills` folders (one copy
when both clients are selected); use Claude's marketplace CLI for plugins.
Preserve different existing skills unless `--force` is given.
Resolve source files relative to the package and destinations from the target
project's working directory. A dry run must not write files or mutate plugins.

Use `npx --yes --package=/absolute/path/to/harness harness-skills --dry-run`
for an unpublished checkout.
The GitHub command becomes available when the package files are pushed; no npm
registry publication is required.

**Claude Code: prefer the plugin marketplace.** It distributes the skill and
its supporting resources together and includes design-thinking's optional
PostToolUse hook. Run inside Claude Code:

```text
/plugin marketplace add insomnius/harness
/plugin install design-thinking@harness
/plugin install code-smells@harness
```

Install either plugin or both. For a shared project, use `--scope project` on
the install commands; each teammate still needs to install the plugin locally.
See [Claude Code's installation docs](https://code.claude.com/docs/en/discover-plugins).

**Pi: install complete standalone skills into the shared Agent Skills locations.**
Use `npx --yes github:insomnius/harness --agent pi`; default project scope uses
`.agents/skills`, and `--global` uses `~/.agents/skills`. Detect `pi` on PATH or
its agent directory (`PI_CODING_AGENT_DIR` or `~/.pi/agent`). Explicit selection
works before Pi is installed. Invoke `/skill:design-thinking` or
`/skill:code-smells`; use `/reload` after installation in an active session.
Do not install a second copy if Codex already uses the same shared location.
Claude plugin hooks are not installed for Pi.

**Codex: install complete standalone skills for this repository.** The bundled
installer copies them directly. The external Skills CLI remains an alternative;
from the project receiving the skills, with Node.js/npm installed:

```sh
npx skills add insomnius/harness --skill design-thinking code-smells --agent codex
```

The default scope is the current project; add `-g` for personal installation
across projects. Codex discovers local skills under `.agents/skills` and personal
skills under `~/.agents/skills`. Copy or symlink the complete skill folder for
manual setup. `$skill-installer` can also install skills from repository paths.
See [Codex skill discovery](https://learn.chatgpt.com/docs/build-skills) and the
[Skills CLI options](https://github.com/vercel-labs/skills#readme).

Codex also supports native plugins and marketplaces through `/plugins` and
`codex plugin`. Do not describe plugins as unsupported. Before recommending a
Harness-specific native plugin command, verify its catalog and installation in
the target client; `.codex-plugin/plugin.json` alone does not prove that route
works. See the [Codex CLI reference](https://learn.chatgpt.com/docs/cli/reference).

Established projects illustrate these installation patterns (reviewed 2026-10-13):

| Project | Installation pattern |
| --- | --- |
| [Anthropic skills](https://github.com/anthropics/skills#readme) | Register `anthropics/skills`, then install a skill bundle such as `document-skills@anthropic-agent-skills` in Claude Code. |
| [Superpowers](https://github.com/obra/superpowers#readme) | Native plugin marketplaces for Claude Code and Codex, with separate instructions per agent. |
| [Vercel agent-skills](https://github.com/vercel-labs/agent-skills#readme) | One-command installation with `npx skills add vercel-labs/agent-skills`; the Skills CLI supports agent and skill selection. |

Preserve both marketplace packaging and independently installable skill folders.
The Skills CLI installs skill resources; it does not install Claude plugin hooks.
Use one installation route per skill per agent to avoid duplicate entries. Test
discovery and copied resources in a temporary project when changing packaging;
use a local checkout path in place of `insomnius/harness` to test unpublished work.

## Editing conventions

- Keep changes focused and preserve existing working-tree changes.
- Keep instructions concrete, internally consistent, and usable across the
  supported agents. Document agent-specific behavior explicitly.
- Keep scripts, templates, and references inside their skill folder so that
  installing a skill independently includes everything it needs.
- Use relative links within documentation and portable paths in scripts. Avoid
  hard-coded checkout paths in committed files.
- Preserve the plugin-root `scripts` symlink for design-thinking: existing CLI
  and Claude hook paths rely on it.
- Keep plugin names, paths, descriptions, and versions consistent across the
  relevant manifests, marketplace entries, and installation documentation.
- Preserve upstream attribution. For design-thinking upstream updates, follow
  `UPSTREAM.md`, retain local adaptations, and record the new source revision.

## Design-thinking toolchain

Python scripts live in
`plugins/design-thinking/skills/design-thinking/scripts/`. They use Python 3
and the standard library; Git is also used by the CLI.

- `design.py`: CLI for recording decisions.
- `design_state.py`: state discovery and persistence.
- `fold.py`: derives current state from recorded decisions.
- `render_graph.py`: renders trace views.
- `audit_gates.py`: audits workflow gates.
- `workflow.py`: reads canonical phase transitions and gate validity from the spec.
- `test_design.py`: standalone behavioral checks.

Preserve the append-only decision log as the source of derived `.design/`
state. Keep CLI vocabulary and behavior synchronized with `graph.json`, JSON
templates, workflow documentation, and language guides. The tests check several
of these relationships.

When trying the CLI manually, invoke the script by absolute path from the
target project's working directory, which determines where `.design/` state
is written. Use a temporary project for experiments.

## Verification

For installer or package changes, run `npm test` and `npm pack --dry-run`.
Exercise the packed executable through `npx` in a temporary project. Keep agent
configuration isolated for integration tests; tests must not install plugins
into the developer's active configuration. Include complete skill resources
and provenance in the package, and exclude benchmarks and generated bytecode.

For changes to the design-thinking scripts, specifications, templates, or
workflow instructions, run from the repository root:

```sh
python3 plugins/design-thinking/skills/design-thinking/scripts/test_design.py
```

Add focused behavioral checks to the existing runner when changing toolchain
behavior. Keep `SKILL.md` short and load detailed guides by current phase.
Graph output, both TDD gates and the state machine are mandatory; DDD modeling
is conditional on new-feature work. Use the bundled CLI as the only supported
state writer, not generated scripts or hand-edited JSON. `status` reads phase
guidance from `graph.json`; `contract`, `note` and `check` record annotations,
supplemental findings and captured execution evidence. For documentation-only changes, check affected paths, links, and
examples; do not add tests that merely duplicate prose.

For manifest changes, check JSON syntax and confirm referenced directories and
hook targets exist. For skill discovery or packaging changes, the optional
preview command is:

```sh
npx skills add /absolute/path/to/harness --list
```

This preview requires Node.js/npm and may access the network. Code-smells has
no bundled runtime or test runner; check its catalog links and guide consistency.

Before finishing, review `git diff --check` and the changed files. Report what
changed, which checks ran, and any verification that could not be completed.
