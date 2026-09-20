# Parallel Inheritance Hierarchies

Category: change-preventers.

## Meaning

Extending one inheritance family obliges developers to add a corresponding subtype in another.

## Evidence to collect

Show the pairing convention and the places that fail when a pair is incomplete.

## Example

Each new Document subclass requires a matching DocumentRenderer subclass plus registration glue.

## Refactoring options

Consider composition or moving related behavior so the variation has one owner. Keep independently varying dimensions separate.

## When not to flag it

Separate hierarchies can be intentional when dimensions evolve independently.

## Verification

Check all supported pairings, registration, and compatibility for existing extensions.

Source attribution: [Refactoring.Guru — Parallel Inheritance Hierarchies](https://refactoring.guru/smells/parallel-inheritance-hierarchies).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
