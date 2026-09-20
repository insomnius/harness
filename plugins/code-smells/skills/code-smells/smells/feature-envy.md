# Feature Envy

Category: couplers.

## Meaning

An operation is primarily concerned with another owner's data, suggesting behavior is misplaced.

## Evidence to collect

Inspect which data determines the operation and whether moving it would reduce exposed internals.

## Example

A billing service repeatedly reads shipment dimensions and computes shipment-specific volume rules.

## Refactoring options

Move the cohesive behavior toward the data or extract the shared domain concept.

## When not to flag it

A mapper, serializer, or pure transformation may intentionally operate on external data.

## Verification

Test the moved rule and ensure callers no longer require unnecessary internal access.

Source attribution: [Refactoring.Guru — Feature Envy](https://refactoring.guru/smells/feature-envy).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
