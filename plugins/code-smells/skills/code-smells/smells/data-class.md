# Data Class

Category: dispensables.

## Meaning

A passive domain object leaves rules concerning its own data scattered among other owners.

## Evidence to collect

Locate behavior and invariants repeatedly applied externally to the same fields.

## Example

Order exposes mutable lines while several services independently compute and enforce its total rules.

## Refactoring options

Move cohesive domain operations toward the data or provide invariant-preserving functions in a functional design.

## When not to flag it

DTOs, serialization records, database projections, and intentional immutable data models can be appropriate.

## Verification

Check invariants, mutation access, serialization, and consumers of moved operations.

Source attribution: [Refactoring.Guru — Data Class](https://refactoring.guru/smells/data-class).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
