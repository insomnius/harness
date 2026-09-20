# Incomplete Library Class

Category: other.

## Meaning

A dependency lacks a required capability and cannot practically be changed directly.

## Evidence to collect

Identify the missing operation and repeated workarounds in consumers; inspect the supported extension surface.

## Example

Several callers reconstruct the same date-range operation around a third-party date type.

## Refactoring options

Add a focused local helper or adapter; use a local extension for a coherent larger capability. Avoid modifying installed dependency files.

## When not to flag it

A one-off operation may not justify a wrapper; extensions can increase dependency-upgrade maintenance.

## Verification

Test boundary values, library-version assumptions, and behavior at the adapter seam.

Source attribution: [Refactoring.Guru — Incomplete Library Class](https://refactoring.guru/smells/incomplete-library-class).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
