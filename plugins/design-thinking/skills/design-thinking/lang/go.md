# Go

> **Illustrative, not normative.** See `TEMPLATE.md` for the six questions.

The real boundary is the **package**, not the file — files in a package share
privates, so a change inside one can reach every file beside it. Record
`package` on every node or the blast radius is understated by default.

## 1. Walk up — who calls this?

```bash
gopls references ./internal/order/service.go:42:6      # tier: references
go build ./... 2>&1 | rg 'cannot use|arguments|undefined'   # tier: compiler
rg -n --type go '\bCreateOrder\('                      # tier: text
```

**Break the signature deliberately, read the error list, revert.** That is the
fastest exhaustive upstream trace Go offers and it is the only one that finds
interface-dispatched callers. Revert immediately — never leave the break.

Interfaces hide callers. Search the *method name* as well as the concrete type,
and check wherever the type is bound into a struct field or a provider.

```bash
rg -n --type go 'interface \{[^}]*CreateOrder'         # who declares it
rg -n --type go 'OrderService(\s|\)|,|\{)'             # who holds it
```

## 2. Walk down — what does it call?

```bash
go list -deps ./internal/order
go list -f '{{.ImportPath}} -> {{join .Imports " "}}' ./...
```

## 3. Prove R

Go proves R at compile time only when dependencies arrive as struct fields or
parameters. The ambient ones it encourages:

```bash
rg -n --type go 'func init\(' internal/                # package-level side effects
rg -n --type go '^var [A-Z][A-Za-z]* = ' internal/     # mutable package globals
rg -n --type go 'time\.Now\(\)|rand\.|os\.Getenv'      # unsignatured dependencies
rg -n --type go 'http\.DefaultClient|sql\.Open'        # ambient transports
```

`context.Context` is not an R channel. A dependency smuggled through
`context.Value` is invisible in the signature and fails principle 13 exactly as
a global does.

## 4. Render A / E / R

- **A** — the function body, top to bottom, with no `if err != nil` in the
  reading of it. If following the success path means stepping over error
  returns, A and E are tangled; extract.
- **E** — one named error per break point, one policy each. `errors.Is` and
  `errors.As` are the layer's vocabulary check; a sentinel returned from three
  layers down and matched at the top is a leak.
- **R** — the struct fields of the receiver plus explicit parameters. Nothing
  else counts.

```go
type RefundService struct {          // R, provable
    orders  OrderRepository
    ledger  LedgerClient
    now     func() time.Time         // the clock as R, not as time.Now()
}
```

Cardinality: `one` is a return value, `many` is a channel or an iterator — and
`many` obliges an answer on ordering, backpressure and what a mid-stream
failure means. An unbuffered channel with no context cancellation is an
unbounded wait.

## 5. Detect drift

```bash
git diff --name-only <traced_at_commit>...HEAD -- internal/order/
gofmt -l . && go vet ./...
go test ./... -run TestNothing 2>&1 | rg -i 'undefined|cannot'   # does it still build
```

Contract hash inputs: the exported signature, the error set it can return, and
its struct-field dependencies. A body-only change is not drift.

## 6. What defeats static tracing

- Reflection, `encoding/json` tags driving behavior, `plugin` loading.
- `go:generate` output — the generated file is a node; the directive is an edge.
- Build tags: a caller that only exists under `//go:build linux` is invisible
  to a default build. Trace with the tags the deploy actually uses.
- Struct embedding promoting a method you did not look for.
