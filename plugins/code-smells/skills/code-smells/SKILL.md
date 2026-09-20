---
name: code-smells
description: Identify and prioritize code smells using Refactoring.Guru's taxonomy, with concrete evidence and behavior-preserving refactoring options. Use for code-smell reviews, maintainability audits, or targeted cleanup of existing code.
---

# Code smells

Treat a smell as a reason to investigate design, not proof of a bug. Explain
which maintenance task becomes harder and why fixing it is worth the added
abstraction or migration cost.

This workflow uses [Refactoring.Guru's code-smell taxonomy](https://refactoring.guru/refactoring/smells).
The evidence requirements, prioritization, and language-specific cautions below
are this skill's review guidance, not quotations or universal rules from the site.

## Scope and evidence

Follow the user's requested mode: a review produces findings; an authorized
cleanup implements the relevant fixes. Loading this skill does not itself
authorize edits. For a change review, inspect the diff and nearby callers;
for a broader audit, state the directories or components actually examined.
Treat vendored and generated code as context unless explicitly in scope.

Use [the local catalog](references/diagnostics.md) to locate the relevant guides
in `smells/` when classifying a candidate. All 23 smells are documented locally
with definitions, evidence, examples, remedies, exceptions, and verification.
Read the guides relevant to the code under review; external source links are
attribution only, not required reading. Disclose unresolved uncertainty.

For each candidate:

1. Read the implementation, its callers, and relevant tests. Search results,
   line counts, and linter warnings locate candidates; they do not establish one.
2. Identify the concrete cost: a rule duplicated across owners, unrelated
   reasons to edit one module, a dependency on another object's internals, or
   difficulty isolating a behavior for tests. Use history when available to
   substantiate repeated co-changes; do not invent historical evidence.
3. Look for a reason the structure is intentional. Consider framework
   contracts, public compatibility, serialization, performance, and language
   idioms. Distinguish an observed problem from a hypothetical future extension.
4. Select the smallest change that addresses that cost and name the behavior
   and callers that need protection. Combine overlapping labels into one finding
   when they share the same cause and remedy.

## Avoid mechanical diagnoses

- Do not enforce universal limits on function length or parameter count. Show
  mixed responsibilities, tangled state, or error-prone call sites.
- Do not prescribe class hierarchies for functional or data-oriented code.
  A small exhaustive match, a transport record, or a pure transformation can
  be appropriate even if its shape resembles an object-oriented smell.
- Preserve comments explaining intent, constraints, compatibility, or subtle
  behavior. When comments compensate for confusing code, improve that code.
- Similar text is insufficient evidence for a shared abstraction. Establish
  that the fragments express the same rule and should change together.
- Before claiming code is dead, check exports, registries, reflection,
  configuration, framework callbacks, and external consumers. If reachability
  cannot be established, report uncertainty rather than recommending deletion.
- A forwarding layer may enforce a boundary, policy, or stable public API.
  Count that value before recommending removal.

## Findings

Lead with actionable findings, ordered by demonstrated impact. For each, give
the location (`path:line` and symbol), smell name, observed evidence, concrete
maintenance consequence, and smallest useful remedy. Use the relevant local
guide when explaining a smell. Separate confidence from priority:
missing context lowers confidence, while widespread impact raises priority.

Prioritize changes that repeatedly force coordinated edits or endanger an
existing contract over local readability improvements. Label optional polish
as such. Do not describe a smell as an urgent correctness defect without
evidence of incorrect behavior. Report no actionable findings when warranted,
and state coverage limits rather than claiming the whole codebase is clean.

## Refactor when requested

Establish the relevant test baseline. Where coverage is missing, add focused
characterization checks for the behavior being moved before restructuring it.
Preserve externally observable outputs, errors, side effects, ordering, and
public contracts. Make small changes and run the checks that exercise affected
callers; include type checking or linting where the project uses them.

A pure refactor should keep behavior checks green. If the task also fixes a
bug, distinguish that behavior change and its regression test from structural
cleanup. Report pre-existing failures and any checks that could not run.
Finish by explaining the reduced maintenance cost, verification performed,
and any remaining tradeoff. Do not add an abstraction solely to remove a label.
