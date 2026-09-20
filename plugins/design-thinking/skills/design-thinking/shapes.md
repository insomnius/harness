# Shapes and channels

> **Illustrative, not normative.** The channels and the disciplines around them
> are principles (`principles.md` 10-16). The per-language renderings below are
> examples. A language that cannot prove a dependency at compile time still has
> one — it just gets written down instead of enforced.


Every node carries three channels:

```
X  →  Y  →  Z
      │
      ├─ A   what flows through on success
      ├─ E   where it breaks, and what happens then
      └─ R   what it needs to exist
```

Annotate all three before writing the node. The order matters and it is not
arbitrary: **shapes → A → cardinality → E → R → boundary → layers → scope →
test → code.** Each step depends on the one before, and doing E before A is how
the happy path ends up unreadable.

The concepts are language-neutral. Some languages check them for you and some
do not, which changes the mechanics but not the discipline — a language that
cannot prove R at compile time still has an R, it is just written down instead
of enforced.

## Where the per-language rendering lives

The ten sections below are the channels themselves — the same in every stack.
How each one is *written* is per-language, and that lives in `lang/<name>.md`
under "Render A / E / R": Go, TypeScript, Effect, Ruby, Python, Bash, GitHub
Actions, Terraform. Read the one in play.

Effect (`lang/effect-ts.md`) is worth reading even on another stack: it is the
one place where A, E and R are in the type rather than in a comment, which makes
it the clearest worked example of what these sections are asking for.

## 1. Shapes

You cannot draw the graph until you know what flows through it.

| Shape | What it is | Why bother |
|---|---|---|
| **Record** | an entity that flows through nodes | names the thing, in the ubiquitous language |
| **Id** | identity, branded or constrained | a bare string accepts every other string |
| **Variant** | the closed set of legal states | makes illegal states unrepresentable |
| **Error** | a named value carrying context | a string error cannot be handled, only logged |

Per language:

```go
// Go
type OrderID string                     // weak: any string is an OrderID
type OrderID struct{ v string }         // better: constructor validates, no bare conversion
func NewOrderID(s string) (OrderID, error)

type RefundStatus int                   // variant, closed by convention
const (StatusPending RefundStatus = iota; StatusApproved; StatusRejected)

type InsufficientBalance struct{ OrderID OrderID; Short int64 }  // error with context
func (e InsufficientBalance) Error() string { ... }
// callers use errors.As, never string matching
```

```ruby
# Ruby
class OrderId
  def initialize(v) = (@v = v.to_s.tap { raise ArgumentError unless v.match?(/\A\d+\z/) })
  def ==(other) = other.is_a?(OrderId) && to_s == other.to_s
end

module RefundStatus
  ALL = [PENDING = :pending, APPROVED = :approved, REJECTED = :rejected].freeze
end

class InsufficientBalance < StandardError
  attr_reader :order_id, :short
  def initialize(order_id:, short:) = (@order_id, @short = order_id, short; super("..."))
end
```

```typescript
// TypeScript
type OrderId = string & { readonly __brand: 'OrderId' };
type RefundStatus = 'pending' | 'approved' | 'rejected';
type RefundError =
  | { _tag: 'InsufficientBalance'; orderId: OrderId; short: number }
  | { _tag: 'OrderNotFound'; orderId: OrderId };
```

```python
# Python
NewType("OrderId", str)                      # weak but documents intent
@dataclass(frozen=True)
class OrderId: value: str                    # better, and hashable
class RefundStatus(StrEnum): PENDING = "pending"; APPROVED = "approved"
@dataclass
class InsufficientBalance(Exception): order_id: OrderId; short: int
```

```bash
# Bash: shapes are argument and env contracts, asserted at the top
: "${DATABASE_URL:?DATABASE_URL required}"     # R, enforced
readonly ORDER_ID="${1:?order id required}"    # id, validated
[[ "$ORDER_ID" =~ ^[0-9]+$ ]] || { echo "invalid order id" >&2; exit 64; }
readonly E_INSUFFICIENT=65                     # named error, as an exit code
```

```yaml
# GitHub Actions: shapes are declared inputs with types
on:
  workflow_call:
    inputs:
      order_id: { required: true, type: string }
      environment: { required: true, type: string }   # variant, validated in a guard step
    secrets:
      DATABASE_URL: { required: true }                # R, declared
```

## 2. A — think the happy path first

Map the success flow as an ordered call graph before writing anything:

```
loadOrder → checkPolicy → recordRefund → publishEvent
```

That graph *is* the program structure. The rule that gives it teeth: **A must
read top to bottom with no error handling interleaved.** If following the
success path means stepping over retries and catches, A and E are tangled and
the node will be unreadable within two tickets.

How each language keeps them separable:

- **Go** — the happy path as sequential steps with `if err != nil { return ... }`
  as the only interruption; no retry loops or fallback logic inline. Retry and
  timeout go in a wrapper function or middleware.
- **Ruby** — the method body is A; `rescue` blocks at the method boundary, not
  sprinkled through it. Retry via a wrapper or `around` hook.
- **TypeScript** — A in the function body, error mapping in a `.catch` at the
  edge or a wrapper. With Effect: `Effect.gen` body is A, `.pipe()` is E.
- **Python** — A in the body, `try/except` at the boundary, retry via decorator.
- **Bash** — A as the sequence of commands; `set -euo pipefail` plus a
  `trap`-based handler keeps error handling out of the flow.
- **Actions** — A as the ordered steps; `continue-on-error`, `if: failure()` and
  retry actions are separate steps rather than logic inside the main one.

## 3. Cardinality

Does the node produce one value, many over time, or a result valid for a window?

| Cardinality | Also decide | The bug when it is wrong |
|---|---|---|
| **one** | nothing further | — |
| **many** | ordering, backpressure, completion, mid-stream failure | only the first page is ever processed |
| **time_bounded** | cache key, TTL, dedupe of concurrent identical lookups | thundering herd on expiry |

Mark it on the node. `many` renders as an iterator, channel, stream, generator,
paginated loop, or a subscription — and every one of those needs the mid-stream
failure question answered, because "the tenth item failed after nine were
already committed" has no single right answer to default to.

## 4. E — where it breaks

Each break point gets exactly **one** policy:

| Policy | When | Must also record |
|---|---|---|
| **retry** | transient: timeout, rate limit, reset, lock conflict | the bound — attempts, backoff, total budget |
| **fallback** | recoverable: default, cache, degraded answer | what the caller loses |
| **propagate** | the caller's problem | the vocabulary it maps into |
| **die** | invariant violated, programmer error | nothing — do not catch it |

An unbounded retry is an outage amplifier, not resilience. `die` is not a domain
error; failing loudly beats continuing on violated assumptions.

**Errors are values, not control flow.** They flow through the graph like data,
and at each node you choose: retry, fall back, map onward, or let it kill the
process. Go returns them, Rust returns `Result`, TypeScript can use a tagged
union, Ruby and Python raise — but even where the mechanism is an exception, the
*error* should be a structured value carrying context, not a message string.

### Per-layer E scoping

Each layer enumerates the errors **it** receives and maps them into its own
vocabulary. Callers never see the vocabulary of a layer three below.

```
repository        service           handler          transport
SqlError      →   DatabaseError  →  RefundRejected →  422 + code
SqlTimeout    →   DatabaseError  →  Unavailable    →  503
                  PolicyDenied   →  RefundRejected →  422 + code
                  (unmapped)     →  die            →  500 + alert
```

Two failure patterns to look for at every layer, exactly as at a network seam:

- **Leaking** — a driver error reaching a caller unchanged, so the caller
  couples to your storage engine.
- **Collapsing** — two errors the caller must distinguish arriving as one, so it
  cannot behave differently.

### Divergent strategies

When two steps in one flow need different policies — one falls back, one fails
hard — handle those two inline rather than in a single outer wrapper, because an
outer wrapper cannot tell which step produced which error. Mark it in the
annotation. It should be rare; more than one or two in a node usually means the
node has two responsibilities.

## 5. R — what the node needs

Complete this sentence for every dependency: **"We cannot do X if we do not have
Y."** Each Y is an entry in R.

```go
// Go: R is the constructor's parameters. Nothing ambient.
type RefundService struct {
    orders  OrderRepository   // R
    ledger  LedgerClient      // R
    clock   func() time.Time  // R — time is a dependency
    ids     IDGenerator       // R — so is identity
}
func NewRefundService(o OrderRepository, l LedgerClient, c func() time.Time, i IDGenerator) *RefundService
```

```ruby
def initialize(orders:, ledger:, clock: Time.method(:now), ids: SecureRandom)
```

```python
def __init__(self, orders: OrderRepository, ledger: LedgerClient,
             clock: Callable[[], datetime], ids: IdGenerator) -> None
```

```bash
: "${DATABASE_URL:?}" "${LEDGER_URL:?}"   # R declared and enforced at the top
```

```yaml
secrets: { DATABASE_URL: { required: true } }   # R declared
permissions: { contents: read, id-token: write } # R, and easy to forget
```

**A hidden R is the core failure.** A dependency reached through a global, a
singleton, an ambient import, `Time.now`, `SecureRandom`, an env read in the
middle of a function, or a module-level client is invisible in the signature —
and it is exactly why a node cannot be tested without mocking the world. The
`channels` phase hunts for these:

```bash
# hidden R: time, randomness, identity, env, global clients
rg -n --type go 'time\.Now\(\)|rand\.|uuid\.New\(\)|os\.Getenv' internal/ | rg -v '_test|/main.go|config'
rg -n --type ruby 'Time\.(now|current)|SecureRandom|ENV\[' app/ | rg -v spec/
rg -n --type py 'datetime\.now\(|uuid4\(|os\.environ' src/ | rg -v tests/
```

When R is fully satisfied, the node runs. Anything outstanding is precisely what
is missing — which is a better error than a nil dereference at 3am.

## 6. Boundary — unknown becomes trusted, once

Where does untrusted data enter? Transport payloads, queue messages, files, env
vars, third-party responses, CLI arguments.

**One definition serving as type, validator and transformer**, applied once at
the edge. After it, shapes are guaranteed and nothing inside revalidates.

| Stack | The one definition |
|---|---|
| Go | a DTO struct + explicit `Validate()` + conversion into the domain type |
| Ruby | `dry-schema` / `ActiveModel::Validations` at the controller or consumer |
| TypeScript | `zod` / `valibot` schema — infers the type and parses in one place |
| Python | `pydantic` model |
| Bash | argument and env assertions in the first ten lines |
| Actions | typed `workflow_call` inputs plus one guard step |

Trust nothing at the boundary; trust everything inside. Validation appearing in
a node's interior means either the boundary is not doing its job, or some caller
is bypassing it — and both are findings worth recording.

## 7. Layers — behavior that wraps without changing the graph

Retry, timeout, logging, tracing, metrics, caching, auth. These belong *outside*
the node so its graph stays readable. The graph says what happens; the layers
say how it behaves under pressure.

```go
svc = WithRetry(WithTimeout(WithTracing(svc)))   // decorator over an interface
```

- **Ruby** — `Module#prepend`, `around_action`, a middleware stack
- **TypeScript** — higher-order functions, or `.pipe()` in Effect
- **Python** — decorators, context managers
- **Bash** — a wrapper script or function around the real command
- **Actions** — a reusable workflow or composite action wrapping the job

The test: **could you delete the retry or the logging without touching the happy
path?** If not, it is entangled rather than wrapped.

## 8. Scope — cleanup as a structural guarantee

Every acquired resource — connection, file handle, lock, subscription, child
process, transaction — needs release guaranteed on *every* exit path, including
error, panic and cancellation.

| Stack | Mechanism |
|---|---|
| Go | `defer`, plus `context` for cancellation propagation |
| Ruby | block form (`File.open do ... end`), `ensure` |
| Python | `with` / `contextlib`, `async with` |
| Rust | `Drop` — the compiler does it |
| TypeScript | `try/finally`, `using` where available |
| Bash | `trap cleanup EXIT INT TERM` |
| Actions | `if: always()` cleanup step |

If a panic, early return or cancellation can skip the cleanup, it is not scoped
— it is a comment hoping someone remembers.

## 9. Test by substituting R

The production and test call graphs differ only in what sits behind R. Same
graph shape, same A, same E possible, different things behind the dependencies.

```
production                     test
handler                        handler
  → RefundService                → RefundService
    → PostgresOrderRepo            → InMemoryOrderRepo
    → HttpLedgerClient             → StubLedgerClient
    → time.Now                     → fixedClock
```

This is where the channel separation pays off, and it doubles as a design check:

> **If you have to mock the world to test one node, the node is doing too much.**

A test needing five fakes, a database, and monkey-patched time is reporting a
hidden R or a node with several responsibilities. Fix the design rather than
growing the fixture — and note that this is consistent with sociable testing
rather than opposed to it: real collaborators stay real, and only the
out-of-process and nondeterministic parts of R are substituted.

## 10. The code is the graph

```
PROBLEM
  → what are the shapes?          → the domain language
  → what is the happy path?       → the call graph (A)
  → one value or many?            → cardinality
  → where can it break?           → policies on the graph (E)
  → what does each node need?     → requirements (R)
  → where does untrusted enter?   → one parse point
  → what wraps without changing?  → layers
  → what needs cleanup?           → scope
  → can I swap R and still test?  → substitutability
  → CODE                          → the code IS the graph
```

**If the code does not match the graph, the implementation is wrong — not the
graph.** The `retrace` phase checks this explicitly: same A order, same E
enumeration, same R. A divergence gets resolved in one direction or the other,
never left as a silent mismatch, because a graph nobody can trust is worse than
no graph at all.
