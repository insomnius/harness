# Long Method

Category: bloaters.

## Meaning

A routine combines enough operations or state that understanding one behavior requires following unrelated work.

## Evidence to collect

Look for separate responsibilities, deeply nested decisions, and values whose meaning changes midway.

## Example

A checkout routine validates a cart, computes tax, writes an invoice, and sends email in one block.

## Refactoring options

Extract cohesive operations with explicit inputs and outputs. Keep orchestration readable and avoid helpers that share hidden mutable state.

## When not to flag it

A long declarative table or straight-line algorithm can be clearer intact. Length alone is insufficient.

## Verification

Check result values, exception paths, and side-effect order.

Source attribution: [Refactoring.Guru — Long Method](https://refactoring.guru/smells/long-method).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
