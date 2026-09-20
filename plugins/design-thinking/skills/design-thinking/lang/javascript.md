# JavaScript

> **Illustrative, not normative.** See `TEMPLATE.md` for the six questions.
> For a typed codebase read `lang/typescript.md` instead — the tracing is the
> same, but the evidence tier is not, and that difference is the whole point of
> this file.

The mechanics of walking the graph are TypeScript's. What changes is that
**there is no compiler tier**. `tsc --noEmit` after a deliberate break is
unavailable, so the exhaustive upstream trace that TypeScript gives away has to
be earned another way — by running the tests, exactly as in Ruby.

The honest consequence: on a contract-changing symbol, evidence tops out at a
coverage run, and anything weaker is `unsure` until resolved. That is
calibration, not pessimism. A dynamic language is not condemned to guessing; it
is condemned to running its tests.

## 1. Walk up — who calls this?

```bash
node --test --experimental-test-coverage 2>&1 | rg 'order'   # tier: coverage
npx vitest run --coverage                                    # tier: coverage
rg -n --type js '\bcreateOrder\s*\('                         # tier: text
npx madge --json src/ | jq 'to_entries[] | select(.value[]? | contains("order/service.js"))'
```

The coverage run is the move that matters. Run the suite, read which specs
touched the file, and you have an empirical caller set. Where coverage does not
reach a contract-changing symbol, the verdict is `unsure` — and that is a
finding about the suite as much as about the trace.

Grep alone misses everything reached by string:

```bash
rg -n --type js "\[[\"'](\w+)[\"']\]\s*\(" src/     # obj['method']() dispatch
rg -n --type js 'require\(.*\+|import\(' src/       # dynamic module resolution
```

## 2. Walk down — what does it call?

```bash
npx madge --json src/order/service.js
npx madge --circular src/                            # cycles, never followed
rg -n "^(import|const .* = require)" src/order/service.js
```

**Two module systems, two resolution rules.** CommonJS `require` is resolved at
call time and can be conditional; ESM `import` is static and hoisted. A file
that mixes them — or a package whose `exports` map differs from its `main` —
resolves differently under Node and under a bundler, so the graph can differ
between test and production. Check `type` in `package.json` and the `exports`
map before trusting any edge.

Barrel files (`index.js`) hide real edges: resolve through to the defining file
and mark the barrel as a pass-through.

## 3. Prove R

Nothing is proven; R is written down or it does not exist.

```bash
rg -n --type js 'new Date\(\)|Date\.now\(\)|Math\.random\(\)' src/
rg -n --type js 'process\.env\.' src/                 # anywhere but the edge
rg -n --type js '^(export )?const [a-z]\w* = new ' src/   # module singletons
rg -n --type js 'globalThis\.|global\.' src/
```

A module-level `export const db = new Client()` runs at import time: invisible
in every signature, and the reason the module cannot be required in a test
without a live connection.

Inject with defaults so a test substitutes R alone, graph shape unchanged:

```js
export function createRefundService({
  orders,
  ledger,
  now = () => new Date(),      // the clock as R, not reached for inline
}) { /* ... */ }
```

Prefer this to `jest.mock()` of the module graph. Module mocking fakes the
world to test one node — the design finding principle 16 asks you to record,
not a fixture to grow.

## 4. Render A / E / R

- **A** — an `async` function read top to bottom with no `try` in it.
- **E** — named error classes, one policy each. `throw new Error('failed')` is
  not a named error: the caller cannot distinguish two failures by matching on
  prose. Give each a `name` or a `code` and check that, never the message.
- **R** — the parameter list. `import` is a static edge, not R.

```js
export class InsufficientBalance extends Error {
  name = 'InsufficientBalance';
  constructor(shortfall) { super(`short by ${shortfall}`); this.shortfall = shortfall; }
}
```

**Make illegal states unrepresentable** (principle 14b) is the hardest rule to
honour here, because the language will not help. What is available:

- `Object.freeze` for value objects, and construct-time validation in a factory
  so an invalid instance cannot exist.
- A single `status` field with a closed set of strings rather than several
  booleans that must agree — `{ loading, error, data }` has four illegal
  combinations, `{ state: 'loading' | 'failed' | 'loaded' }` has none.
- `#private` fields to keep an invariant enforceable rather than conventional.

Since the type system cannot carry the constraint, **write it in the trace**:
the value object's invariant belongs in the node's channels, because that is
the only place it will be recorded at all.

**Parse once, at the edge** (principle 14): one Zod or Valibot schema at the
boundary, serving as validator and transformer. Ad-hoc `if (!body.amount)`
checks scattered through handlers mean there is no boundary.

- **Cardinality** — `one` is a promise; `many` is an async iterator or a
  stream, and obliges ordering, backpressure and mid-stream failure decisions.
  An unawaited promise is a mid-stream failure with nowhere to go: an
  `unhandledRejection` that terminates the process in modern Node.
- **Scope** — `try/finally` is the only structural cleanup, and an
  `AbortController` passed down is how cancellation reaches a leaf. A
  `setInterval` with no `clearInterval` on the error path is an unscoped
  resource.

## 5. Detect drift

```bash
npx vitest run                              # the real drift check
npx eslint . && npx prettier --check .
npx api-extractor run                       # if the package publishes types
node --test
git diff --name-only <traced_at_commit>...HEAD -- src/
```

There is no signature to hash, so the contract hash is over the **exported
names, their arity, the error `name`/`code` values thrown, and the shape of
what they return** — extracted deliberately, because nothing computes it. For a
published package, the `exports` map in `package.json` is part of the contract:
narrowing it is breaking even when every file is untouched.

## 6. What defeats static tracing

- Everything in `typescript.md` §6, plus:
- No types, so structural coupling is invisible: a caller depending on a field
  you are about to rename produces no error anywhere until it runs.
- Monkey-patching, `Object.defineProperty`, and prototype mutation.
- `eval`, `new Function`, and anything assembled from a template string.
- Framework file-system routing and convention-based registration — grep the
  URL or the filename, not the symbol.
- Bundler aliases and `paths` remapping: the edge in the source is not the edge
  at run time.
- Duplicated transitive dependencies: two copies of one package means
  `instanceof` fails across them, and no static tool will show you that.
