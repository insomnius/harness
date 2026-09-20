# Upstream provenance

- Source: https://github.com/getboon/boon-plugins/tree/main/plugins/design-thinking
- Commit: `66a61fb6723d7a72a1fc414be643e6fe8879c2e3`
- Plugin version: `2.1.4`
- Imported: 2026-09-20, from the clean local `../boon-plugins` checkout.

The initial import preserved all upstream files. Local version `2.1.5` makes
the skill independently installable: scripts now live inside the skill folder,
template and test paths resolve there, and installation instructions describe
the local layout. A plugin-root `scripts` symlink preserves existing CLI and
Claude hook paths. The method and reference content otherwise remain upstream.
Local additions include this record and `.codex-plugin/plugin.json`.

No LICENSE, COPYING, or NOTICE file was present in the source checkout.
This import does not assign a new license to upstream material.

For an update, compare this pinned source directory with the new upstream
revision, preserve local additions, run `python3 scripts/test_design.py` from
this plugin directory, and update this record and the Codex manifest version.
