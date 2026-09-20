# Inappropriate Intimacy

Category: couplers.

## Meaning

Components rely on each other's internal representation, allowing local changes to spread across boundaries.

## Evidence to collect

Find private-field access, mutual state mutation, or duplicated assumptions about internal layout.

## Example

An importer mutates a cache's internal dictionary and manually maintains its eviction counters.

## Refactoring options

Expose a purposeful operation, move behavior to the owner, or reconsider whether the split is meaningful.

## When not to flag it

Closely cooperating implementation parts can share internals intentionally; assess the actual boundary.

## Verification

Verify invariants, mutation order, and behavior when the internal representation changes.

Source attribution: [Refactoring.Guru — Inappropriate Intimacy](https://refactoring.guru/smells/inappropriate-intimacy).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
