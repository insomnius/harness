# Effect (TypeScript)

> **Illustrative, not normative.** See `TEMPLATE.md` for the six questions, and
> `typescript.md` for everything that applies to TypeScript generally.

Effect is where this method came from, and it is the one stack where the three
channels are **compiler-enforced rather than written down**: `Effect<A, E, R>`
puts the success value, the error set and the requirement set in the type. That
makes it the best worked example of `shapes.md`, not a special case — everywhere
else, R is a discipline; here it is a type error.

```
Effect<A, E, R>
        │  │  └─ R: what it needs to exist        (§5 / principle 13)
        │  └──── E: how it can fail               (§4 / principle 12)
        └─────── A: what flows through on success (§2 / principle 10)
```

## 1. Walk up — who calls this?

As `typescript.md`, and the type is far more informative: widening `E` or `R`
breaks every caller at compile time, so the exhaustive upstream trace is free.

```bash
npx tsc --noEmit 2>&1 | rg 'src/'
rg -n --type ts 'Effect\.provide|Layer\.provide' src/     # where R is satisfied
rg -n --type ts 'yield\* .*refund' src/                   # composition sites
```

Adding a requirement to `R` is a **breaking change to every caller that has
already discharged its R** — principle 6b in its most literal form, and the
compiler enumerates it for you.

## 2. Walk down — what does it call?

Read the `Effect.gen` body: every `yield*` is one downstream edge, in order.
The success path *is* the call graph, which is the property the whole method is
built on.

## 3. Prove R

This is the payoff. `R` is a type, so a hidden dependency is a compile error
rather than a code review comment:

```ts
class Clock extends Context.Tag('Clock')<Clock, { now: () => DateTime }>() {}

const recordRefund = (id: OrderId) => Effect.gen(function* () {
  const clock  = yield* Clock                 // R, in the type
  const orders = yield* OrderRepository
  ...
})   // Effect<Refund, InsufficientBalance, Clock | OrderRepository>
```

`R = never` means the program can run. Anything else names exactly what is
missing. Test by swapping the layer behind R with the graph shape unchanged —
principle 16, mechanically.

```bash
rg -n --type ts 'Effect\.runSync|Effect\.runPromise' src/   # R must be never here
rg -n --type ts 'Effect\.die|Effect\.orDie'                 # defects, not domain errors
```

## 4. Render A / E / R

**`gen` is A; `pipe` is E.** Not a style preference — it is the structural
separation principle 11 asks for:

```ts
const handler = recordRefund(id).pipe(
  Effect.retry({ times: 3, schedule: Schedule.exponential('100 millis') }),
  Effect.catchTag('InsufficientBalance', e => Effect.fail(new Rejected(e))),
  Effect.catchTag('LedgerUnavailable', () => Effect.succeed(Deferred)),  // loss stated
  Effect.withSpan('refund.record'),
)
```

Before writing the pipe, read the actual `E` of every yielded effect and
enumerate all of them. Each layer's pipe covers what *it* received, not what
originated three layers down:

```
Repository        Service          Handler
E=SqlError   →    E=DatabaseError  →  E=RefundRejected  →  422
```

- **Cardinality** — `Effect` is `one`, `Stream` is `many`. `many` obliges
  ordering, backpressure and mid-stream failure decisions; `Stream` gives you
  the operators, not the decisions.
- **Scope** — `Effect.acquireRelease` and `Scope` make cleanup structural
  (principle 15). A `finally` that an interrupt can skip is not scoped;
  `Scope` cannot be skipped.
- **Boundary** — `Schema.decodeUnknown` is the single parse point, one
  definition serving as type, validator and transformer (principle 14).
- **Divergent strategies** — when two effects in one `gen` need different
  failure semantics, handle each inline. It is the one exception to "no error
  handling in `gen`", it exists because the graph forked, and it should be rare
  enough to comment.

## 5. Detect drift

The `Effect<A, E, R>` type *is* the contract hash. Diff it:

```bash
npx tsc --declaration --emitDeclarationOnly --outDir /tmp/dts && \
  git diff --no-index /tmp/dts.prev /tmp/dts
```

A changed `E` or `R` in an emitted declaration is contract drift with no
judgement required — the only stack in this directory where drift detection is
exact.

## 6. What defeats static tracing

- `Effect.provideService` deep inside a call chain: R discharged somewhere the
  signature no longer shows.
- `Effect.orDie` / `Effect.catchAll` collapsing a distinguishable error set
  into one — principle 12's *collapsing* failure, and the type stops warning
  you the moment it happens.
- `Layer` graphs assembled dynamically.
- Everything in `typescript.md` §6 still applies at the edges, where Effect
  code meets a framework that does not use it.
