# Dependencies

> **Both gates outrank both skills.** ponytail governs *how much code* gets
> written, never *what must be specified*. caveman governs *narration*, never a
> gate verdict. Where either conflicts with a gate, the gate wins and the
> conflict is said out loud.

Two third-party skills, declared in `graph.json` under `dependencies.required`.
The method stands without either; `preflight` reports absence and continues.

| Skill | Source | Does |
|---|---|---|
| ponytail | `DietrichGebert/ponytail` | lazy-senior-dev minimality: shortest solution that works, YAGNI, stdlib before dependencies, shortcut rationale and upgrade paths recorded as accepted debt in `.design/` |
| caveman | `JuliusBrussee/caveman` | strips articles, filler and hedging from prose; code blocks and error messages quoted exactly |

---

## ponytail

Its question — *does something already do this?* — is the same question
`locate` asks as prior art, and the same one greenfield asks before creating a
node. Which makes it a genuine fit rather than a bolt-on.

**Where it hands off**

| Phase | Handoff |
|---|---|
| `language` | the earliest and highest-leverage one: a context classified **generic** is where "does this need to exist at all?" is answered *no* most often. Investment follows subdomain (principle 17b), so the honest output here is sometimes "use a library, close the ticket" |
| `locate` | before seeding a new node, ask whether the platform, stdlib or framework already covers it. A capability that exists needs no node |
| greenfield | the same question, harder — the cheapest new node is the one never created |
| `triage` | among valid change sets, prefer the one touching fewest nodes and adding no abstraction |
| `implement:A` | write the smallest happy path that turns the behavior green |
| `retrace` | run `ponytail-review` over the diff; check its deletions against the behavior list |

The `language` handoff is worth stating separately because it is the only one
that can end the ticket. The others shrink a change set; this one can delete the
premise. It is also the one place ponytail's judgement outranks thoroughness by
design — a method this detailed applied to a generic subdomain looks like
diligence the whole time it is being wasted.

**Two reconciliations**

*Shortcuts are accepted debt.* Record their rationale and upgrade paths in
`.design/` at `implement:finalize`. Existing relevant `ponytail:` comments can
supply that evidence, but do not create shortcut comments by default. The code
comment policy in `SKILL.md` takes precedence: add an inline comment only to
explain an important, non-obvious reason, never just to label a shortcut.

*Deletion is bounded by behaviors.* `ponytail-review` may propose deleting
anything no behavior claims — that is its value, and unclaimed code is a real
finding worth acting on. It may **not** delete an error policy, a boundary
parse, a scoped release or a test. Those exist because a behavior or a gate
check demanded them, and "no behavior asked for this error handling" means the
E annotation is missing, not that the handling is surplus.

**Where they pull against each other.** ponytail wants the shortest thing that
works; the behavior gate wants an annotated contract, one policy per break
point, a single parse point and a structural release. Those look opposed and are
not, once the line is drawn in the right place: **minimality applies to the
implementation, specification is not negotiable.** The smallest code that
satisfies every annotated behavior is precisely what both want. What ponytail
cannot do is argue that a behavior needs no test, or that an error needs no
policy, because it is faster without one.

## caveman

Compression on the narration only. This is safe here for a structural reason:
caveman leaves code blocks and error messages exactly as written, and the status
tree, the red evidence and the check output are all blocks.

**Never compressed:**

- the status tree — it is the report, not commentary on it
- gate verdicts and which check failed; a compressed refusal is an unclear one
- red evidence: command, exit status, failure message, verbatim
- the expected-versus-observed line on a red check, which is what the next
  decision turns on
- a falsified assumption reported back to you — the loop's highest-value output,
  and the thing most damaged by terseness
- anything escalated for a human decision

**One honest note.** In ponytail's own agentic benchmark, caveman measured
slightly *above* the no-skill baseline on tokens, cost and time, because
agentic cost is dominated by file reading and tool calls rather than by prose.
Install it because the padding annoys you, not as a cost strategy. The
compression is real; the saving is not where the marketing suggests.

---

## Install

```bash
# ponytail
/plugin marketplace add DietrichGebert/ponytail
/plugin install ponytail@ponytail        # two separate prompts

# caveman
/plugin marketplace add JuliusBrussee/caveman
/plugin install caveman@caveman
```

Both install independently from their upstream marketplaces. Harness keeps
`ponytail` and `caveman` optional and separate from `design-thinking`; see
`INSTALL.md`. A fully atomic package would vendor all three. If you vendor them
elsewhere, keep the upstream source recorded in `graph.json` so updates are
traceable, and re-check the pinned copies periodically; both projects move.

## Verify the integration

Ask for a change in a real repo and look for four things:

1. **preflight** names which of the two are present.
2. At `locate`, a note on whether anything native already covers the
   requirement — that is ponytail's question being asked.
3. A gate refusal stays **fully worded** even with caveman active.
4. `ponytail-review` at `retrace` proposes deletions, and each one is checked
   against the behavior list rather than accepted wholesale.

If a gate verdict comes back terse, or a proposed deletion removes an error
policy, precedence is not being applied — that is the thing to catch early.
