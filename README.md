# Harness

My reusable coding skills and plugins for Claude Code, Codex, and other agents.
Each plugin lives in `plugins/<name>/`, with shared skill instructions and
resources alongside agent-specific packaging.

## Install with npx

Requires Node.js/npm. Run from the project that should receive the skills:

```sh
# List skills without installing.
npx skills add /absolute/path/to/harness --list

# Install both skills for your chosen agents.
npx skills add /absolute/path/to/harness --skill design-thinking code-smells --agent codex claude-code
```

`npx` runs the published Skills CLI, which installs SKILL.md folders and their
contents. This repository needs no npm package. `--skill` selects skills;
`--agent` selects harnesses. Add `-g` for personal installation across projects.
Omit selectors for interactive choices. OpenCode uses `--agent opencode`.
`--copy` creates independent copies instead of links to a shared installed copy.
See the [Skills CLI documentation](https://skills.sh/docs/cli).

After pushing this repository to a Git host, replace the local path with its
URL or GitHub `OWNER/REPO`. No remote is configured here yet. Private sources
need Git authentication. The tested installer version is `npx skills@1.7.0`.

This installs skills and bundled resources, not plugin hooks. Use the full
Claude plugin route below for its rendering hook. Choose one route per agent
to avoid duplicate entries.

## Design thinking

[design-thinking](plugins/design-thinking/skills/design-thinking/SKILL.md)
combines domain modeling, call-graph tracing, and test-driven implementation.
Imported from `getboon/boon-plugins` at version `2.1.4`; the exact source commit
and local additions are recorded in [UPSTREAM.md](plugins/design-thinking/UPSTREAM.md).

Local version `2.1.5` bundles the CLI inside the skill folder so copying the
complete skill preserves its resources. A plugin-root `scripts` symlink keeps
existing CLI and hook paths working.
The runtime uses Python 3 and Git. Optional companion skills
`ponytail` and `caveman` are not bundled; the upstream workflow reports their
absence and continues.

## Code smells

[code-smells](plugins/code-smells/skills/code-smells/SKILL.md) provides
evidence-based maintainability reviews and behavior-preserving cleanup using
[Refactoring.Guru's taxonomy](https://refactoring.guru/refactoring/smells).
It includes [23 local smell guides](plugins/code-smells/skills/code-smells/references/diagnostics.md)
with definitions, examples, refactoring options, verification, and guidance for
avoiding false positives. External links provide attribution; the skill needs
no website access. Reviews report findings; cleanup requests authorize
focused refactoring. This skill has no scripts, hooks, or external dependencies.

For Claude Code, add the marketplace as described below, then install and invoke:

```text
/plugin install code-smells@harness
/code-smells:code-smells Review the current changes for code smells.
```

For Codex, copy or symlink `plugins/code-smells/skills/code-smells` into your
project's `.agents/skills/code-smells`, then invoke `$code-smells`. For example,
from the target project, with this checkout at the specified absolute path:

```sh
mkdir -p .agents/skills
ln -s /absolute/path/to/harness/plugins/code-smells/skills/code-smells .agents/skills/code-smells
```

Other harnesses that support `SKILL.md` can install the entire `code-smells`
skill folder in their discovery directory; keep both `references/` and `smells/`.
Both Claude and Codex plugin manifests are included. Codex currently uses the
skill-discovery route documented here; no Codex marketplace is configured.

## Claude Code

From your project directory, start a session with the full plugin path:

```sh
claude --plugin-dir /absolute/path/to/harness/plugins/design-thinking
```

Invoke `/design-thinking:design-thinking`. For a persistent installation, run
these commands inside Claude Code:

```text
/plugin marketplace add /absolute/path/to/harness
/plugin install design-thinking@harness
```

The Claude plugin includes a PostToolUse hook to redraw graphs after edits.
See the [Claude plugin documentation](https://code.claude.com/docs/en/plugins).

## Codex

Link the shared skill into a project's discovery directory, keeping this
checkout in place:

```sh
mkdir -p /absolute/path/to/project/.agents/skills
ln -s /absolute/path/to/harness/plugins/design-thinking/skills/design-thinking \
  /absolute/path/to/project/.agents/skills/design-thinking
```

Start a new Codex session and invoke `$design-thinking`. For personal use across
projects, use `~/.agents/skills` as the destination instead. These commands do
not replace an existing skill. See the [official skill documentation](https://learn.chatgpt.com/docs/build-skills).

The plugin also includes `.codex-plugin/plugin.json` for Codex packaging.
The skill-link route does not install the Claude hook; graphs still render
when the Python CLI records decisions.

## Other agents and CLI usage

Point the agent at the shared `SKILL.md` and its adjacent reference files.
Discovery and hook support vary by agent. Tell it where this checkout lives
and invoke the CLI by absolute path from the project being worked on:

```sh
python3 /absolute/path/to/harness/plugins/design-thinking/scripts/design.py --help
python3 /absolute/path/to/harness/plugins/design-thinking/scripts/design.py init \
  --ref TASK-1 --title "Describe the change"
```

The CLI writes `.design/` state in the target project. Examples in the imported
skill abbreviate this full invocation as `design.py`.

## Validation and maintenance

Run the upstream behavioral checks from this repository:

```sh
python3 plugins/design-thinking/scripts/test_design.py
```

For future imports, preserve supporting scripts and references, record source
provenance, and add agent manifests only where needed. Keep one shared copy of
each skill. Upstream documentation is retained as imported; this README covers
usage of the personal repository.
