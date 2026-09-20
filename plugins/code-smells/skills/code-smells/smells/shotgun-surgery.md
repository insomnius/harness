# Shotgun Surgery

Category: change-preventers.

## Meaning

One logical change requires small coordinated edits across many owners.

## Evidence to collect

Trace a concrete rule or change through all affected locations; history can confirm repeated co-changes.

## Example

Adding a billing status requires updating separate validation, mapping, and display rules scattered across services.

## Refactoring options

Consolidate the rule or define a shared contract at the right boundary. Preserve intentional deployment independence.

## When not to flag it

Cross-layer feature work is not automatically fragmentation; each layer may own a distinct responsibility.

## Verification

Test all affected consumers and check that one source now governs the shared decision.

Source attribution: [Refactoring.Guru — Shotgun Surgery](https://refactoring.guru/smells/shotgun-surgery).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
