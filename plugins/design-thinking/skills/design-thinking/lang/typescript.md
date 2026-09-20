# TypeScript

> **Illustrative, not normative.** See `TEMPLATE.md` for the six questions.
> Effect-based codebases: read `effect-ts.md` after this one — it is a dialect
> where A/E/R is compiler-enforced rather than written down.

## 1. Walk up — who calls this?

```bash
npx tsc --noEmit 2>&1 | rg 'src/'                    # tier: compiler
# after deliberately breaking the type - then revert
rg -n --type ts '\bcreateOrder\('                    # tier: text
```

`tsc --noEmit` after a deliberate break is the exhaustive upstream trace, the
same move as Go's. It is worth more than any grep here because structural
typing means a caller need not name your type to depend on its shape.

Two things blunt it and both must be checked:

```bash
rg -n 'as any|as unknown|@ts-ignore|@ts-expect-error' src/   # holes in the proof
rg -n '"strict"\s*:\s*false|"noImplicitAny"\s*:\s*false' tsconfig*.json
```

A repo with `strict: false` gives compiler evidence that is weaker than it
looks. Record the tier honestly.

## 2. Walk down — what does it call?

```bash
npx madge --json src/order/service.ts
npx madge --circular src/                            # cycles, which are never followed
rg -n "^import .* from '" src/order/service.ts
```

**Barrel files (`index.ts`) hide real edges.** Resolve through to the defining
file and mark the barrel as a pass-through to collapse — a chain of three hops
that transforms nothing is exactly what principle 3 says to collapse.

## 3. Prove R

TypeScript proves R when dependencies arrive as constructor or function
parameters, and proves nothing about what a module does at import time.

```bash
rg -n --type ts 'new Date\(\)|Date\.now\(\)|Math\.random\(\)' src/
rg -n --type ts 'process\.env\.' src/                # not at the edge = hidden R
rg -n --type ts '^export const [a-z][A-Za-z]* = new ' src/   # module singletons
```

A module-level `export const db = new Client()` is a singleton with import-time
side effects: invisible in every signature, and the reason the module cannot be
imported in a test without a live connection.

## 4. Render A / E / R

- **A** — an `async` function read top to bottom with no `try` in it.
- **E** — a discriminated union of named errors, or typed rejections. `throw`
  of a bare `Error` with a message string is not a named error value; the
  caller cannot distinguish two failures by matching on prose.
- **R** — the parameter list. `import` is not R; it is a static edge.

```ts
type RefundError =
  | { readonly _tag: 'InsufficientBalance'; readonly shortfall: Money }
  | { readonly _tag: 'OrderCancelled' }
```

**Make illegal states unrepresentable** (principle 14b) — this is where
TypeScript is strongest and where it is most often left on the table. Branded
ids, discriminated unions over boolean pairs, `readonly` by default:

```ts
type OrderId = string & { readonly __brand: 'OrderId' }
// not: { loading: boolean; error?: string; data?: Order }  - four illegal combinations
type Fetch<A> = { _tag: 'idle' } | { _tag: 'loading' } |
                { _tag: 'failed'; error: RefundError } | { _tag: 'loaded'; data: A }
```

**Parse once, at the edge** (principle 14): one Zod or Valibot schema serving as
type, validator and transformer. `as` at a boundary is an assertion, not a
parse, and it is a lie the compiler agreed to.

## 5. Detect drift

```bash
git diff --name-only <traced_at_commit>...HEAD -- src/order/
npx tsc --noEmit
npx tsc --declaration --emitDeclarationOnly --outDir /tmp/dts   # diff the .d.ts
```

Diffing emitted declarations is the cheapest real contract check TypeScript
offers: it changes exactly when the public shape does, and not when a body does.

## 6. What defeats static tracing

- Decorators and DI containers (NestJS, InversifyJS, TypeORM): registration by
  metadata, resolved at runtime.
- Dynamic `import()` and anything keyed by a string.
- Framework file-system routing (Next.js, Remix): the route is an entrypoint
  with no importer at all. Grep the URL, not the symbol.
- `any` propagating silently — an edge through `any` is `evidence: reasoning`,
  whatever the compiler says.
