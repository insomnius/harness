# Long Parameter List

Category: bloaters.

## Meaning

A call requires many independent arguments, making correct combinations difficult to understand.

## Evidence to collect

Inspect actual call sites for swapped values, boolean combinations, repeated groups, and parameters irrelevant in some modes.

## Example

sendReport(user, start, end, format, includeDrafts, compress, destination) obscures which choices belong together.

## Refactoring options

Group a real domain concept, separate distinct operations, or derive redundant arguments from an existing input.

## When not to flag it

A language with named arguments or a stable low-level interface may make a larger signature clear.

## Verification

Check defaults, positional callers, optional combinations, and public compatibility.

Source attribution: [Refactoring.Guru — Long Parameter List](https://refactoring.guru/smells/long-parameter-list).
This local guide uses original explanations and examples; the diagnostic cautions
and verification steps are repository guidance. No web access is required.
