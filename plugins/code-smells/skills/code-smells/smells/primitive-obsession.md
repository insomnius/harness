# Primitive Obsession

Category: bloaters.

## Meaning

Raw strings, numbers, or codes carry domain meaning that their types cannot express.

## Evidence to collect

Find repeated parsing or validation, mixed units, magic codes, and identifiers that callers can accidentally swap.

## Example

Functions accept amount, currency, and customer ID as unvalidated strings throughout the domain.

## Refactoring options

Introduce a focused value type, enum, or validated boundary representation. Centralize the specific invariant.

## When not to flag it

Primitives at serialization boundaries and simple local calculations are normal; wrapping every value adds noise.

## Verification

Cover invalid inputs, conversion, equality, units, and serialization compatibility.

Source attribution: [Refactoring.Guru — Primitive Obsession](https://refactoring.guru/smells/primitive-obsession).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
