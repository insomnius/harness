# Lazy Class

Category: dispensables.

## Meaning

An abstraction adds navigation or lifecycle overhead without enough responsibility to justify it.

## Evidence to collect

Identify what the type contributes beyond relaying data and whether that contribution is used.

## Example

A private PriceHolder only wraps one value and has no validation, contract, or semantic distinction.

## Refactoring options

Inline it into its owner when doing so simplifies the design and preserves meaningful boundaries.

## When not to flag it

Small value types can prevent identifier or unit confusion; stable interfaces can justify small implementations.

## Verification

Check callers, equality, serialization, and lifecycle changes caused by inlining.

Source attribution: [Refactoring.Guru — Lazy Class](https://refactoring.guru/smells/lazy-class).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
