# Install

This edition bundles scripts and templates inside the skill folder. Requires
Python 3 and Git. From the project receiving the skill, run:

```sh
npx skills add /absolute/path/to/harness --skill design-thinking --agent codex claude-code
```

Add `-g` for personal installation across projects. Other supported agents can
be selected with `--agent`. Keep the entire installed skill directory together.
Resolve scripts relative to the installed SKILL.md; run them from the project
being changed so .design/ state is created in that project:

```sh
python3 /absolute/path/to/installed/design-thinking/scripts/design.py --help
python3 /absolute/path/to/installed/design-thinking/scripts/test_design.py
```

For the full Claude plugin, including its optional PostToolUse rendering hook:

```text
/plugin marketplace add /absolute/path/to/harness
/plugin install design-thinking@harness
```

The npx skill route renders graphs through the CLI but does not install hooks.
Choose one installation route per agent to avoid duplicates. The plugin-root
scripts symlink preserves legacy CLI and hook paths. Optional ponytail and
caveman skills are not bundled; the method continues with its fallbacks.
Choose whether to commit .design/ traces in each target project.

Adapted from getboon/boon-plugins design-thinking 2.1.4; this repository's
UPSTREAM.md records the import and local packaging changes.
