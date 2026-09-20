# Switch Statements

Category: oo-abusers.

## Meaning

Branching logic becomes hard to maintain when it repeatedly encodes the same variation or mixes multiple responsibilities.

## Evidence to collect

Find repeated dispatch on the same type code and show what must change when a supported variant changes.

## Example

Pricing, export, and validation each repeat a growing customer-type switch.

## Refactoring options

First simplify or extract the decision. Use a dispatch table, strategy, or polymorphism only when it centralizes real variation.

## When not to flag it

A small exhaustive match over a closed enum is often ideal. A switch is not inherently a defect.

## Verification

Exercise every branch, unknown values, defaults, and fall-through behavior.

Source attribution: [Refactoring.Guru — Switch Statements](https://refactoring.guru/smells/switch-statements).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
