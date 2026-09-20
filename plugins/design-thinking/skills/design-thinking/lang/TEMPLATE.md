# <language>

> **Illustrative, not normative.** The six questions are fixed; the answers are
> this stack's. When a recipe here conflicts with `principles.md`, the principle
> wins.

Every file in `lang/` answers the same six questions in the same order. A new
language is a fill-in, not a redesign — and a stack with no compiler still has
an R, it just gets written down instead of proven.

## 1. Walk up — who calls this?

Strongest evidence first, and record the tier reached (`compiler` > `coverage` >
`references` > `text` > `reasoning`). A contract-changing symbol needs one of
the top two; anything weaker is `unsure` until resolved.

## 2. Walk down — what does it call?

## 3. Prove R — how are dependencies made explicit and substitutable?

Name the ambient ones this stack encourages: globals, singletons, the wall
clock, a random source, a mid-function env read. Those are the ones that make a
node untestable, and the greps that find them belong here.

## 4. Render A / E / R

What the three channels look like in this stack's syntax, and where the
language will *not* enforce them so they have to be written down.

## 5. Detect drift

How you tell that the code no longer matches the annotation.

## 6. What defeats static tracing

The edges no tool here will find. These are what make a verdict `unsure`
legitimately rather than lazily.
