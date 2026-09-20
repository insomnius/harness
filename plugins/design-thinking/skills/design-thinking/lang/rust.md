# Rust

> **Illustrative, not normative.** See `TEMPLATE.md` for the six questions.

The compiler is the strongest tracing instrument in this directory. Ownership,
exhaustive `match` and `#[must_use]` mean a contract change is usually a *build
failure* rather than a review comment — so the exhaustive upstream trace is
free, and the honest evidence tier is `compiler` far more often than elsewhere.

The unit is the **crate**, then the module. `pub(crate)` is a real boundary: a
change behind it cannot reach outside the crate, which is a genuine absorption
point and worth recording as one.

## 1. Walk up — who calls this?

```bash
cargo check --workspace --all-targets 2>&1 | rg '^error'   # tier: compiler
# after deliberately changing the signature - then revert
rust-analyzer analysis-stats .                             # tier: references
rg -n --type rust '\brecord_refund\s*\('                   # tier: text
cargo tree --invert <crate>                                # who depends on the crate
```

**Break it and read the errors.** Rust's exhaustiveness makes this sharper than
in Go or TypeScript: add a variant to an enum and every non-exhaustive `match`
in the workspace fails, so the caller set for a *domain* change enumerates
itself. Revert immediately.

Traits hide callers the way interfaces do. Search the method name, the trait
name, and every `impl Trait for` block:

```bash
rg -n --type rust 'impl .*RefundPolicy.* for'
rg -n --type rust 'dyn RefundPolicy|impl RefundPolicy'     # dynamic + static dispatch
```

## 2. Walk down — what does it call?

```bash
cargo tree -e normal --depth 2
rg -n --type rust '^\s*(use|pub use) ' src/order/service.rs
cargo modules generate tree --with-types                    # if cargo-modules is present
```

`pub use` re-exports are Rust's barrel files: resolve through to the defining
module and mark the re-export as a pass-through.

## 3. Prove R

Rust proves R at compile time whenever dependencies arrive as generic
parameters or trait objects held in the struct. The ambient ones it still
permits:

```bash
rg -n --type rust 'lazy_static!|once_cell|static [A-Z_]+:' src/
rg -n --type rust 'SystemTime::now|Instant::now|rand::|std::env::var' src/
rg -n --type rust 'unsafe ' src/                            # the R the compiler stopped checking
```

Generic over the dependency is the idiomatic form, and it is what makes the
test substitute R alone with the graph shape unchanged:

```rust
pub struct RefundService<R: OrderRepository, C: Clock> {
    orders: R,
    clock: C,          // not SystemTime::now() reached for inline
}
```

`unsafe` deserves a line in R of its own. It is the one place the compiler
stops proving what the rest of the file assumes, so the invariant it upholds
belongs written down beside it — that is exactly the *hidden R* the method is
looking for.

## 4. Render A / E / R

- **A** — the function body read through `?`. The operator is what keeps the
  happy path readable: every `?` is an E edge that does not interrupt A.
- **E** — one `enum` per layer, variants named for domain failures, mapped
  outward with `From`. `thiserror` for a library's own error type, `anyhow`
  only at the binary's edge; `anyhow` inside a domain layer collapses errors
  the caller needed to distinguish.
- **R** — generic parameters and struct fields. A `static` is not R.

```rust
#[derive(thiserror::Error, Debug)]
pub enum RefundError {
    #[error("refund of {attempted} exceeds remaining {remaining}")]
    InsufficientBalance { attempted: Money, remaining: Money },
    #[error("order already cancelled")]
    OrderCancelled,
}
```

**Make illegal states unrepresentable** (principle 14b) is where Rust is
strongest in this whole directory, and where the type system will actually
enforce what elsewhere is a convention:

```rust
pub struct OrderId(Uuid);                    // newtype, not a bare Uuid
pub struct RefundAmount(NonZeroU64);         // zero is unrepresentable
enum Refund { Pending { .. }, Settled { at: DateTime<Utc>, .. } }
// not: struct Refund { settled: bool, settled_at: Option<DateTime<Utc>> }
```

That last pair is the shape to look for: a `bool` beside an `Option` that must
agree is two illegal states waiting.

- **Cardinality** — `one` is a return value; `many` is `Iterator` or `Stream`.
  A `Stream` obliges ordering, backpressure and mid-stream failure decisions,
  and in async Rust cancellation is a *fourth*: a future dropped mid-poll stops
  where it is, so anything not cancel-safe must say so.
- **Scope** — `Drop` makes cleanup structural (principle 15), and unlike a
  `defer` it also runs on unwind. The exception is `std::mem::forget` and a
  process abort, which are worth naming when a resource matters.
- **Boundary** — `serde` with `#[serde(deny_unknown_fields)]` plus a
  `TryFrom<Dto>` for the domain type is the single parse point (principle 14).
  A `#[serde(default)]` on a field the domain requires is a boundary that is
  not doing its job.

## 5. Detect drift

```bash
cargo public-api diff                       # the exact public-surface diff
cargo semver-checks check-release           # names the breaking change
cargo check --workspace && cargo clippy -- -D warnings
git diff --name-only <traced_at_commit>...HEAD -- src/
```

`cargo public-api` is the closest thing to exact drift detection in this
directory outside Effect: it prints the public surface, so diffing it changes
exactly when a contract does and not when a body does.

Contract hash inputs: the public signature, its error enum's variants, its
trait bounds, and the lifetimes. **A lifetime is part of the contract** —
tightening one is breaking even when the shape is unchanged.

## 6. What defeats static tracing

- Macros. `macro_rules!` and proc-macros generate the code the compiler sees,
  so grep finds the invocation and not the call. `cargo expand` is the answer.
- `#[cfg(...)]`: a caller behind a feature flag does not exist in a default
  build. Trace with the features the release actually enables.
- Trait objects and `Any` downcasts resolved at run time.
- Build scripts (`build.rs`) generating source, and `include!`.
- FFI: `extern "C"` is a seam with no compiler on the far side. Record it as
  `CROSSING`, or `OPAQUE` if the other side is a vendored binary.
