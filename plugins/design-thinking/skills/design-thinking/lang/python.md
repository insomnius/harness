# Python

> **Illustrative, not normative.** See `TEMPLATE.md` for the six questions.

No compile step, so the strongest routinely available evidence is a **coverage
run** — tier 2. Reach for it before grep on anything contract-changing.

## 1. Walk up — who calls this?

```bash
rg -n --type py '\bcreate_order\('                     # tier: text
pytest --collect-only -q | rg order                    # what tests exist
pytest --cov=mypackage --cov-report=term-missing        # tier: coverage
mypy --strict mypackage/ 2>&1 | rg 'error'             # tier: compiler (only under --strict)
```

Where the repo has type hints and `mypy --strict`, breaking a signature and
reading the error list is a real exhaustive trace. Where it does not, say so and
record `evidence: coverage` or `text` — not `compiler`.

```bash
rg -n 'getattr\(|globals\(\)\[|importlib|__import__' mypackage/   # dispatch by string
```

## 2. Walk down — what does it call?

```bash
pydeps mypackage --show-deps --no-output
rg -n '^\s*(from|import) ' mypackage/order/service.py
python -c "import ast,sys; [print(n.module) for n in ast.walk(ast.parse(open(sys.argv[1]).read())) if isinstance(n, ast.ImportFrom)]" mypackage/order/service.py
```

Import-time side effects are real downstream edges: a module that connects to a
database at import is a node whose R is discharged before any function runs.

## 3. Prove R

Python proves R only through parameters and constructor arguments. The ambient
ones it invites:

```bash
rg -n --type py 'datetime\.(now|utcnow)\(|time\.time\(\)|random\.' mypackage/
rg -n --type py 'os\.environ|os\.getenv' mypackage/     # anywhere but the edge
rg -n --type py '^[a-z_]+ = [A-Z][A-Za-z]*\(' mypackage/  # module-level instances
rg -n --type py '@(lru_cache|cache)' mypackage/         # hidden time_bounded cardinality
```

`@lru_cache` on a function that reaches a database changes cardinality to
`time_bounded` with an unstated TTL and no cache key discipline. That is a
decision (principle: cardinality is stated, not defaulted), not a decorator.

Inject with defaults so tests substitute R alone:

```python
from datetime import datetime, timezone          # timezone is needed below

def __init__(
    self,
    orders: OrderRepository,
    # tz-aware: a naive local-time clock is a hidden dependency on the host's
    # timezone, which is the bug this injection exists to prevent
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
):
```

## 4. Render A / E / R

- **A** — the function body with no `try` in the reading of it.
- **E** — one named exception class per break point, one policy each. `except
  Exception` is the absence of a policy. Each layer catches what it received and
  raises its own vocabulary.
- **R** — parameters and `__init__` arguments. A module-level constant is not R;
  it is a hidden dependency.

**Make illegal states unrepresentable** (principle 14b) — the tools are here and
routinely unused:

```python
@dataclass(frozen=True)          # a value object, not a dict
class RefundAmount:
    cents: int
    def __post_init__(self) -> None:
        if self.cents <= 0:
            raise ValueError("refund amount must be positive")

class RefundStatus(enum.Enum):   # not a str
    PENDING = "pending"
    SETTLED = "settled"
```

`dict[str, Any]` crossing a module boundary is the single most common way a
Python codebase loses its contract. **Parse once, at the edge** (principle 14):
one Pydantic model or `TypeAdapter`, at the boundary, serving as type, validator
and transformer.

Cardinality: a generator is `many` and obliges ordering, backpressure and
mid-stream failure answers — and a generator that holds an open connection
across a `yield` has scope that an early `break` can skip (principle 15). Use
`contextlib.contextmanager` so cleanup is structural.

## 5. Detect drift

```bash
git diff --name-only <traced_at_commit>...HEAD -- mypackage/order/
mypy mypackage/ && ruff check mypackage/
pytest mypackage/order/ -q
```

Contract hash inputs: the public function signatures with annotations, the
exception types raised, and the constructor arguments. In an untyped repo there
is less to hash, which is itself worth recording as a finding.

## 6. What defeats static tracing

- Decorators that register by side effect: Flask/FastAPI routes, Celery tasks,
  Click commands, pytest fixtures. The route or task name is the keyword, not
  the function name.
- DI containers and framework hooks resolved from configuration strings.
- `__getattr__`, `__init_subclass__`, metaclasses, monkey-patching in
  `conftest.py`.
- Entry points declared in `pyproject.toml` — a caller that lives in another
  package entirely.
