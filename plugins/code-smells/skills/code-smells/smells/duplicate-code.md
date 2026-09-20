# Duplicate Code

Category: dispensables.

## Meaning

Multiple implementations repeat the same knowledge and should change together.

## Evidence to collect

Compare semantics and callers, not just text; identify the shared rule and any drifting copies.

## Example

Three checkout paths implement the same discount eligibility policy with slight differences.

## Refactoring options

Consolidate the shared rule at its natural owner. Keep context-specific orchestration separate.

## When not to flag it

Similar code from unrelated domains may need to evolve independently; test setup can benefit from explicit repetition.

## Verification

Capture meaningful differences before extraction and test every former caller.

Source attribution: [Refactoring.Guru — Duplicate Code](https://refactoring.guru/smells/duplicate-code).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
