# Java

> **Illustrative, not normative.** See `TEMPLATE.md` for the six questions.

A compiler and mature tooling, so the evidence tier is high — but the
frameworks that dominate real Java codebases wire themselves at *runtime*, and
that is where the graph goes dark. Expect `compiler` for the code and
`reasoning` for the wiring, in the same file, and record the difference rather
than averaging it.

The unit is the **package**, then the class. Sealed hierarchies and modules
(`module-info.java`) are real boundaries and genuine absorption points.

## 1. Walk up — who calls this?

```bash
mvn -q compile 2>&1 | rg 'ERROR|cannot find symbol'    # tier: compiler
# after deliberately changing the signature - then revert
rg -n --type java '\brecordRefund\s*\('                # tier: text
mvn dependency:analyze                                 # unused + undeclared deps
jdeps --print-module-deps target/classes               # bytecode-level edges
```

Break the signature and read the errors: that is the exhaustive upstream trace,
and with sealed interfaces a new permitted subtype makes every non-exhaustive
`switch` fail, so a domain change enumerates its own callers.

Interfaces and DI hide callers. Search the method name, the interface, and
every injection point:

```bash
rg -n --type java 'implements .*RefundPolicy|extends .*RefundPolicy'
rg -n --type java '@(Autowired|Inject|Bean|Component|Service|Repository)' src/
rg -n --type java '@Qualifier|@Primary'                # which impl actually binds
```

## 2. Walk down — what does it call?

```bash
rg -n --type java '^import ' src/main/java/com/x/order/RefundService.java
mvn dependency:tree -Dscope=compile
```

Beware the field-injected dependency: it appears in no constructor and no
import you would search for, only as an annotation.

## 3. Prove R

Java proves R only through the constructor. Everything the framework does
behind your back is a hidden R:

```bash
rg -n --type java '@Autowired' -A2 src/ | rg -B1 'private .* [a-z]'   # field injection
rg -n --type java 'static .* (getInstance|INSTANCE)' src/
rg -n --type java 'Instant\.now|LocalDate(Time)?\.now|new Random|System\.getenv' src/
rg -n --type java 'new [A-Z][A-Za-z]*Client\(|new RestTemplate\(' src/
```

**Constructor injection is the difference between a testable node and a mocked
world.** Field injection compiles, runs and hides every dependency from the
signature, which is principle 13's core failure with a framework's blessing:

```java
public RefundService(OrderRepository orders, LedgerClient ledger, Clock clock) {
    // Clock, not Instant.now() reached for inline - java.time.Clock exists for this
}
```

`java.time.Clock` is in the JDK precisely so the wall clock can be an R. Using
`Instant.now()` inside a domain method is choosing an untestable node.

## 4. Render A / E / R

- **A** — the method body, read with no `try` in it. If following the success
  path means stepping over catches, extract.
- **E** — one checked or domain exception per break point, one policy each.
  `catch (Exception e)` is the absence of a policy. Each layer catches what it
  received and throws its own vocabulary — `SQLException → RepositoryException
  → RefundRejected → 422`.
- **R** — constructor parameters. A `@Value` field read at runtime is not R,
  it is configuration reaching in sideways.

**Make illegal states unrepresentable** (principle 14b) — modern Java has the
tools and most codebases still pass `String`:

```java
record OrderId(UUID value) {}                       // not a bare UUID
record RefundAmount(long cents) {
    RefundAmount { if (cents <= 0) throw new IllegalArgumentException("positive"); }
}
sealed interface Refund permits Pending, Settled {} // not a status enum + nullable field
```

Records are shallowly immutable only: a `record` holding a `List` still hands
out a mutable reference, so wrap with `List.copyOf` in the compact constructor
if the value object is meant to be one.

- **Cardinality** — `one` is a return value; `many` is `Stream` or a reactive
  `Flux`, and both oblige ordering, backpressure and mid-stream failure
  decisions. A `Stream` is also single-use, which is a cardinality fact worth
  stating.
- **Scope** — try-with-resources makes cleanup structural (principle 15): the
  close is tied to the declaration, so it cannot be forgotten at a new exit
  point. `finally` is *also* guaranteed here — unlike a plain block in some
  languages, it runs on an early `return` and on the exceptional path, and only
  a JVM exit skips it. Its two real hazards are different ones: a `return`
  inside `finally` silently discards the exception that was propagating, and a
  resource closed in `@PreDestroy` is scoped to the container rather than to
  the call.
- **Boundary** — one parse point: Jackson with
  `FAIL_ON_UNKNOWN_PROPERTIES` plus Bean Validation on the DTO, converted once
  into the domain type. Validation annotations on a domain entity mean the
  boundary is not doing its job.

## 5. Detect drift

```bash
mvn verify                                   # compile + test in one gate
japicmp / revapi                             # binary + source compatibility diff
mvn versions:display-dependency-updates
git diff --name-only <traced_at_commit>...HEAD -- src/main/java
```

`japicmp` or `revapi` is the contract check: it reports source *and binary*
incompatibility, and binary compatibility is a distinction Java has that most
of this directory does not — a change can compile for a rebuilt caller and
break one that was not rebuilt.

Contract hash inputs: the public signature, its checked exceptions, its
generics, and the annotations that carry behavior (`@Transactional`,
`@Cacheable`). **Changing `@Transactional` propagation changes behavior with no
signature diff at all.**

## 6. What defeats static tracing

- Spring wiring: component scan, `@Bean` factories, profiles, conditional
  beans. The bean *name* is the keyword, not the class name.
- Reflection, `Class.forName`, and the `ServiceLoader`/`META-INF/services`
  registry.
- AOP proxies: `@Transactional`, `@Cacheable`, `@Async` are behavior applied by
  a proxy at run time, invisible in the method body — and a self-invocation
  bypasses the proxy entirely, which is a bug no static tool will find.
- Annotation processors (Lombok, MapStruct) generating code the source lacks.
  `mvn compile` then read `target/generated-sources`.
- `@Value("${...}")` and profile-specific YAML: configuration is a `provisions`
  edge, and it changes behavior with no code diff.
