# Message Chains

Category: couplers.

## Meaning

A caller navigates through multiple owners to reach behavior and becomes coupled to their arrangement.

## Evidence to collect

Show which intermediate representations the caller must know and what changes when one moves.

## Example

An invoice caller reaches customer.account.settings.billingPolicy to decide payment terms.

## Refactoring options

Expose the needed operation through a suitable owner or move the caller's operation closer to the data.

## When not to flag it

Fluent builders and pipelines can express one stable abstraction rather than leak an object graph.

## Verification

Check missing intermediate values, errors, and preservation of the final operation's behavior.

Source attribution: [Refactoring.Guru — Message Chains](https://refactoring.guru/smells/message-chains).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
