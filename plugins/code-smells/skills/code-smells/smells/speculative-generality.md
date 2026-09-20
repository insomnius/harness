# Speculative Generality

Category: dispensables.

## Meaning

Extension machinery exists for hypothetical needs while increasing the cost of current behavior.

## Evidence to collect

Identify unused hooks, unused modes, empty implementations, or abstractions with no present contractual purpose.

## Example

A one-provider feature carries a factory hierarchy and configuration switches for providers that do not exist.

## Refactoring options

Remove unused variation and inline unnecessary indirection while preserving actual extension contracts.

## When not to flag it

A published plugin interface or committed near-term requirement can justify extensibility; establish evidence.

## Verification

Exercise current behavior and supported extensions after simplifying construction and configuration.

Source attribution: [Refactoring.Guru — Speculative Generality](https://refactoring.guru/smells/speculative-generality).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
