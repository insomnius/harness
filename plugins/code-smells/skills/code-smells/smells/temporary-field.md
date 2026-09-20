# Temporary Field

Category: oo-abusers.

## Meaning

An object contains fields meaningful only during certain operations, making valid state depend on its lifecycle.

## Evidence to collect

Trace writes and reads to identify setup requirements, stale values, and fields unused in most states.

## Example

A reusable invoice object stores workingTotal only between beginCalculation and finishCalculation.

## Refactoring options

Keep operation-local state local, introduce an operation object, or model distinct states explicitly.

## When not to flag it

Legitimate optional domain data and documented lazy caches need separate analysis.

## Verification

Check repeated calls, failures midway, concurrency where relevant, and state cleanup.

Source attribution: [Refactoring.Guru — Temporary Field](https://refactoring.guru/smells/temporary-field).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
