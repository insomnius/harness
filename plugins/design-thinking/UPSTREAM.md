# Upstream provenance

- Source: https://github.com/getboon/boon-plugins/tree/main/plugins/design-thinking
- Commit: `66a61fb6723d7a72a1fc414be643e6fe8879c2e3`
- Plugin version: `2.1.4`
- Imported: 2026-09-20, from the clean local upstream checkout.

The initial import preserved all upstream files. Local version `2.1.5` makes
the skill independently installable: scripts now live inside the skill folder,
template and test paths resolve there, and installation instructions describe
the local layout. A plugin-root `scripts` symlink preserves existing CLI and
Claude hook paths. Local documentation uses Harness installation paths and
descriptive refs instead of issue-tracker IDs. Upstream source attribution is
kept in this record outside the installable skill folder. Local additions
include this record and `.codex-plugin/plugin.json`.

Further local adaptations retain the pinned upstream revision and attribution:

- Shorten `SKILL.md` to a progressive-disclosure entry point; retain graph
  output, red-first TDD and the existing 18-phase state machine.
- Scope DDD modeling to new features; other changes reuse existing ownership.
- Add `cli.md` and `reporting.md`, plus CLI status guidance, spec-driven phase
  transitions, behavior contracts, supplemental notes and captured check runs.
- Keep the append-only log as the source; invalidate stale contracts/gates,
  require green behaviors at closure, and disallow `--force` evidence waivers.
- Add behavioral and gate-audit coverage. Existing logs remain readable; old
  gates without contract snapshots need a contract and fresh red to resume.

No LICENSE, COPYING, or NOTICE file was present in the source checkout.
This import does not assign a new license to upstream material.

For an update, compare this pinned source directory with the new upstream
revision, preserve local additions, run `python3 scripts/test_design.py` from
this plugin directory, and update this record and the Codex manifest version.
