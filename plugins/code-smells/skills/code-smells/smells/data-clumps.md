# Data Clumps

Category: bloaters.

## Meaning

The same set of values repeatedly appears together because it represents an unnamed concept.

## Evidence to collect

Confirm the fields travel together across multiple signatures or records and share validation or lifecycle.

## Example

startDate and endDate are repeatedly passed, validated, and compared together.

## Refactoring options

Introduce a cohesive value such as DateRange and move shared rules with it. Preserve clear access at boundaries.

## When not to flag it

Coincidental adjacency is not a shared concept; do not group values that change independently.

## Verification

Test grouped invariants, absent values, and conversion at existing interfaces.

Source attribution: [Refactoring.Guru — Data Clumps](https://refactoring.guru/smells/data-clumps).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
