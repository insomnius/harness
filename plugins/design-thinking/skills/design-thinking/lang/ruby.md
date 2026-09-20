# Ruby

> **Illustrative, not normative.** See `TEMPLATE.md` for the six questions.

No compiler, and metaprogramming defeats static analysis. That does not mean
guessing — it means **the test suite is the call graph**, and a coverage run is
tier-2 evidence available in any Ruby repo. A dynamic language is not condemned
to guessing; it is condemned to running its tests.

## 1. Walk up — who calls this?

```bash
rg -n --type ruby '\bcreate_order\b'                       # tier: text
rg -n --type ruby "send\(:create_order|:create_order"      # dynamic dispatch
bundle exec rspec --dry-run 2>/dev/null | rg -i order      # tier: references
COVERAGE=1 bundle exec rspec spec/orders_spec.rb           # tier: coverage
```

The coverage run is the move that matters: run the suite, read which specs
touched the file, and you have an empirical caller set. Where a symbol is
contract-changing and coverage does not reach it, the verdict is `unsure` — and
that is a finding about the test suite as much as about the trace.

## 2. Walk down — what does it call?

```bash
rg -n --type ruby "^\s*(require|require_relative|autoload)" app lib
rg -n --type ruby 'define_method|method_missing|const_get|public_send'
```

Every hit in the second command is a node that hides its own edges. Record it
and mark the edges `evidence: reasoning`.

## 3. Prove R

Ruby proves nothing at compile time, so R is written down or it does not exist.
The ambient dependencies Rails actively encourages:

```bash
rg -n --type ruby '\b[A-Z][A-Za-z]+\.(instance|current|config)\b' app/
rg -n --type ruby 'Time\.(now|current)|SecureRandom|ENV\[' app/
rg -n --type ruby 'Rails\.(cache|logger|application)' app/
```

Inject through the initialiser and default at the call site:

```ruby
def initialize(orders:, ledger:, clock: -> { Time.current })
```

That keeps the graph shape identical between production and test, which is the
whole point of principle 16.

## 4. Render A / E / R

- **A** — the method body. Guard clauses that `return` early on a *domain*
  condition are A; `rescue` is E.
- **E** — a named exception class per break point, one policy each. `rescue
  StandardError` is not a policy, it is the absence of one. Each layer rescues
  what it received and raises its own vocabulary.
- **R** — keyword arguments on the initialiser. Nothing reached through a
  constant counts.

Value objects are where Ruby earns the most: `Money`, `RefundAmount` and a
`Refund::Status` enum move validation from every caller into one constructor
(principle 14b). If they are `BigDecimal` and `String`, every caller is
revalidating and one of them has forgotten.

## 5. Detect drift

```bash
git diff --name-only <traced_at_commit>...HEAD -- app/services/
bundle exec rubocop --only Lint app/services/refund_service.rb
bundle exec rspec spec/services/refund_service_spec.rb    # the real drift check
```

There is no signature to hash, so the contract hash is over the **public
method names, their keyword argument names, and the exception classes raised**.
Extract them explicitly; nothing computes them for you.

## 6. What defeats static tracing

- Rails callbacks, concerns and `included do` blocks — edges by convention.
- STI, polymorphic associations, and anything resolved from a string
  (`"#{type}Service".constantize`).
- `ActiveSupport` monkey-patches changing core behavior with no local diff.
- Sidekiq and ActiveJob: the enqueue and the perform are two nodes joined by a
  queue, which is a `reads_writes` seam, not a call.
- Default to `unsure` more often here than in Go. That is calibration, not
  timidity.
