# Alternative Classes with Different Interfaces

Category: oo-abusers.

## Meaning

Equivalent capabilities use incompatible names or calling conventions, forcing needless caller adaptation.

## Evidence to collect

Establish equivalent semantics before treating different signatures as interchangeable.

## Example

Two storage adapters expose put(key, value) and save(value, name) for the same operation.

## Refactoring options

Align interfaces where owned, or introduce a small adapter that preserves error and lifecycle semantics.

## When not to flag it

Similar names or outputs can hide different consistency, ownership, or failure guarantees.

## Verification

Use shared contract checks for outputs, errors, resource handling, and side effects.

Source attribution: [Refactoring.Guru — Alternative Classes with Different Interfaces](https://refactoring.guru/smells/alternative-classes-with-different-interfaces).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
