# Refused Bequest

Category: oo-abusers.

## Meaning

A subtype inherits capabilities it cannot meaningfully support, weakening the parent's promised contract.

## Evidence to collect

Inspect overridden methods that throw unsupported errors and callers that special-case the subtype.

## Example

ReadOnlyStore inherits MutableStore but rejects save and delete.

## Refactoring options

Narrow the shared interface, split capabilities, or replace implementation inheritance with composition.

## When not to flag it

Unused inherited methods alone do not establish a broken contract; inspect the documented guarantees.

## Verification

Run parent-contract tests against subtypes and verify callers of removed capabilities.

Source attribution: [Refactoring.Guru — Refused Bequest](https://refactoring.guru/smells/refused-bequest).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
