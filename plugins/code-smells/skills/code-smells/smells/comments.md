# Comments

Category: dispensables.

## Meaning

Comments repeatedly compensate for implementation whose intent could be expressed more clearly in code.

## Evidence to collect

Locate explanations of confusing steps, misleading names, or tangled control flow; identify the underlying readability problem.

## Example

A block says calculate overdue penalty while manipulating vaguely named variables across several branches.

## Refactoring options

Name the concept, extract a coherent operation, or simplify the logic. Update stale comments as part of that change.

## When not to flag it

Keep rationale, legal notices, constraints, public API documentation, and explanations of subtle algorithms.

## Verification

Verify the executable behavior is unchanged and remaining comments still match it.

Source attribution: [Refactoring.Guru — Comments](https://refactoring.guru/smells/comments).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
