# Mandatory graph reports

Graph output is mandatory for every task, regardless of size. Use the bundled
CLI's rendered tree; do not maintain a second hand-written graph or generate a
script to draw one. Prose explains the graph and never replaces it.

`graph.json`'s `reporting` section defines the canonical reporting rules.
`design.py show` renders the current tree; `status` adds phase guidance.
Mutations render automatically and regenerate the Mermaid artifacts.

```text
R1 Above-balance refunds are rejected              accept green
`-- T1 refund
    src/cli.py                                    unchanged: contract absorbed
      -> src/refund.py                            changed; gate passed
         refund                                   B1 green
         -> src/repository.py                     unchanged: regression passes
```

This ASCII example illustrates nesting, not an alternative status vocabulary.
The CLI uses its established glyphs and signed depth labels.

- Root the graph at the entrypoint-most traced node. Nest by caller/callee
  relationships, not by arbitrary lists of files.
- Show requirement, task, affected nodes, symbols and behaviors. Show gate state,
  acceptance result, blockers, drift and seam compatibility where applicable.
- Keep changed and uncertain nodes, their connecting paths, and the adjacent
  absorption frontier. Omit unrelated traced nodes with an expand instruction.
- Expand a shared node once; reference subsequent appearances. Mark cycles
  without following them. Order markers show the edit sequence.
- Keep small tasks small. A single behavior still gets a graph and red/green
  evidence; it does not need an invented multi-service diagram.
- Include graphs at phase transitions, before production edits, after behavior
  completion, at verification, on resume, and in the final report.
- Attach observed check results and remaining uncertainty. Never label a passed
  red gate as completed implementation. If acceptance is red, show expected
  versus observed and the next diagnosis or human question.

Use `show --level 4` for behavior detail and `show --full` for every traced node.
Only load [visualize.md](visualize.md) when specialized views or Mermaid examples
are needed; its full diagram catalog is not required for ordinary reports.
