# Large Class

Category: bloaters.

## Meaning

One class accumulates responsibilities that could evolve independently.

## Evidence to collect

Identify clusters of methods using different fields, unrelated dependencies, and changes driven by different business concerns.

## Example

CustomerManager owns authentication, invoice calculation, and CSV formatting.

## Refactoring options

Extract a cohesive responsibility and give it a clear contract. Move its data and behavior together.

## When not to flag it

A generated schema or cohesive facade may legitimately have many members.

## Verification

Exercise public callers and verify initialization and state ownership.

Source attribution: [Refactoring.Guru — Large Class](https://refactoring.guru/smells/large-class).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
