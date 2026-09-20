# Dead Code

Category: dispensables.

## Meaning

A definition or branch no longer participates in supported behavior.

## Evidence to collect

Check callers, exports, configuration, dynamic registration, reflection, and deployment entry points before concluding it is unused.

## Example

An obsolete formatter has no callers after a migration and is not exported or registered.

## Refactoring options

Remove proven unreachable code and its exclusively unused support, preserving required compatibility surfaces.

## When not to flag it

No textual references is not proof for callbacks, plugins, public APIs, or dynamically loaded code.

## Verification

Run builds and relevant integration tests; verify registrations and supported entry points.

Source attribution: [Refactoring.Guru — Dead Code](https://refactoring.guru/smells/dead-code).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
