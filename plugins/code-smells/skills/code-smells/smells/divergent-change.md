# Divergent Change

Category: change-preventers.

## Meaning

One owner must change for several unrelated reasons because distinct responsibilities are combined.

## Evidence to collect

Show independent change drivers and the methods or dependencies associated with each.

## Example

A report class changes when tax rules change and also when printer layouts change.

## Refactoring options

Separate responsibilities along actual reasons for change, keeping each rule with its data.

## When not to flag it

A coordinated feature can legitimately affect several methods in a cohesive class.

## Verification

Verify each extracted responsibility and the integration that combines them.

Source attribution: [Refactoring.Guru — Divergent Change](https://refactoring.guru/smells/divergent-change).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
