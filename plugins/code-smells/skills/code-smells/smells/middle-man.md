# Middle Man

Category: couplers.

## Meaning

A layer largely forwards requests without providing a useful boundary or policy.

## Evidence to collect

Identify its callers and determine whether it adds translation, authorization, stability, or ownership.

## Example

A private service mirrors every repository method with unchanged arguments and results.

## Refactoring options

Remove unnecessary forwarding or give the boundary a meaningful contract if one is required.

## When not to flag it

Proxies, adapters, facades, authorization gates, and public compatibility layers can justify delegation.

## Verification

Verify removed indirection did not own lifecycle, interception, access control, or error translation.

Source attribution: [Refactoring.Guru — Middle Man](https://refactoring.guru/smells/middle-man).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
