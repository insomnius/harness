# Crossing seams

> **Illustrative, not normative.** Seams as nodes, translation on crossing,
> compatibility over completeness, and bidirectional rollout are principles
> (`principles.md` 21-25). The tooling below is example mechanics.


`tracing.md` covers walking the graph inside one repo. This covers continuing it
past the process boundary: HTTP, RPC, queues, databases, and the infra layer.

The method is identical. What changes is that **the caller set stops being
provable**. In-process, the compiler enumerates every caller. Across a published
seam you get evidence, never proof — so the goal shifts from *finding all
consumers* to *not breaking the ones you cannot see*.

## The seam is a node

Give it an id and a contract like any other node:

```
seam:http:POST /v2/refunds
seam:rpc:refunds.RefundService/Create
seam:topic:refund.recorded
seam:table:orders
seam:config:REFUND_MAX_CENTS
```

A seam's contract has five parts, and only the first is usually written down:

| Part | What it covers | Where it hides |
|---|---|---|
| shape | request, response, payload, columns | OpenAPI, proto, migration |
| errors | status codes, RPC codes, DLQ conditions | usually nowhere |
| translation | how internal errors map outward, and back | usually nowhere |
| semantics | idempotency, ordering, delivery, timeouts | usually nowhere |
| auth | who may call, with what scope | gateway or mesh config |

The four undocumented ones cause the outages. A consumer that retries a
non-idempotent endpoint is not violating a written contract — it is violating
one nobody wrote.

## Which direction are you changing?

The whole decision hangs on this.

**Consumer-side change.** You call something and want more from it. Trace *down*
into the provider — schema artifact first, then its repo if you have it. Your
risk is that you depend on behavior the provider never promised. Check whether
what you rely on is in the artifact or merely observed.

**Provider-side change.** You serve something and want to change it. Tracing
*up* cannot be completed. Instead:

1. Establish whether the change is additive. Adding a field, an endpoint, an
   optional parameter, a new enum value that old clients ignore: safe.
2. Anything removed or narrowed is breaking. A field, a status code, an enum
   value the consumer switches on, a column, a permission, a looser timeout, a
   weaker ordering guarantee. Breaking regardless of how few consumers you found.
3. For breaking changes, expand-contract as three shippable steps: add the new
   shape → migrate consumers → remove the old. Each step is its own task, and
   the third often lands weeks later.

## Finding consumers

In rough order of strength:

```bash
# 1. Schema artifacts - the contract itself
fd -e yaml -e yml -e json . api/ openapi/ | xargs rg -l 'openapi:|swagger:'
fd -e proto . proto/ && rg -n 'service |rpc ' proto/
rg -n 'asyncapi:|"\$schema"' schemas/

# 2. Generated clients - every importer is a consumer
rg -n 'refunds-client|gen/refunds|RefundServiceClient' --hidden

# 3. Org-wide code search (needs gh auth, and read access to the org)
gh search code '"/v2/refunds"' --owner your-org --limit 50
gh search code '"refund.recorded"' --owner your-org --limit 50
gh api "search/code?q=orders+table+org:your-org+language:sql" --jq '.items[].repository.name'

# 4. Gateway / mesh / IaC - routes and permissions name their callers
rg -n '/v2/refunds' infra/ k8s/ terraform/ --hidden
rg -n 'refund' k8s/*/virtualservice*.yaml k8s/*/authorizationpolicy*.yaml

# 5. Telemetry - who is calling right now, not who compiled against it
#    (whatever you have: access logs, APM, mesh metrics)
#    This is the only source that reflects reality rather than intent.

# 6. Contract tests - consumers who already wrote their expectations down
fd -g '*pact*' -g '*contract*test*' .
```

Sources 1-4 find who *compiled* against the seam. Source 5 finds who is
*calling* it. They disagree more often than you would expect, and both matter:
a consumer in code but not in traffic may be dormant, not gone.

Record how each consumer was found on the seam node. A consumer found via
telemetry with no code you can read is a real constraint and an `unsure` you
cannot resolve locally — say so rather than assuming it away.

## Continuing into the far side

If the far side is reachable, keep tracing. Address its nodes as
`<service>:<path>` so one trace file can hold both:

```
payments:internal/refund/service.go
orders:internal/http/refund_handler.go
```

Reachable means: same monorepo, a sibling checkout, a vendored client, or a
committed schema artifact detailed enough to trace against. When it is only
partially reachable — you have the artifact but not the code — trace to the
artifact and stop there, marking the seam's far side `OPAQUE` with the contract
recorded. That is a legitimate stop; pretending you traced further is not.

## Error translation

This is where layers meet, and the thing most worth writing down because no tool
will check it.

```
domain error          seam (HTTP)        consumer domain
──────────────────────────────────────────────────────────
InsufficientBalance → 422 + code=BAL  → RefundRejected      (expected, handled)
OrderNotFound       → 404             → RefundRejected      (collapsed! see below)
DatabaseTimeout     → 503             → retry, then fail    (retryable)
InvalidRefundAmount → 400             → programmer error    (die)
```

Two failure patterns to look for at every seam:

- **Collapsing.** Two distinct domain errors mapping to the same code, so the
  consumer cannot tell them apart and handles both the same way. Above, a
  missing order and an over-balance refund both become `RefundRejected`, which
  is fine only if the consumer genuinely should treat them alike.
- **Leaking.** An implementation error crossing outward unchanged — a SQL error
  or stack trace reaching a consumer, which then couples to your internals.
  Each layer should map what it received into its own vocabulary before passing
  it on, and the seam is the last chance to do that.

Changing this mapping is a behavior change with a test, not a refactor.

## Deploy order

| Change | Order | Why |
|---|---|---|
| additive provider (new field, new endpoint) | provider first | consumers cannot use what is not there |
| removal (field, endpoint, column) | consumer first | provider cannot remove what is still called |
| in-place shape change | **do not** | split into additive + removal |
| new required request field | provider accepts optional first | otherwise old consumers break instantly |
| stricter validation | provider last, after consumers comply | it is a removal of tolerance |
| DB column add | migration first, code second | code must not read what does not exist |
| DB column drop | code first, migration later | and later means a separate release |

The rollout window is the part people skip. Both must hold: **old consumer
against new provider**, and **new consumer against old provider**. The second is
what breaks during a canary or a partial rollout, and during a rollback.

## Seam drift

A seam can drift with no commit in your repo at all — the provider deployed and
nothing here changed. A git-only drift check misses this entirely, which is why
it needs its own procedure:

```bash
# pin what you can, and diff on fetch
git diff HEAD -- api/openapi.yaml proto/
buf breaking proto/ --against '.git#branch=main'     # proto compatibility
oasdiff breaking api/openapi-old.yaml api/openapi.yaml

# contract tests: a red one is drift, not flakiness
go test ./contract/... -run Refund

# what is actually deployed on the far side
kubectl get deploy payments -o jsonpath='{.spec.template.spec.containers[0].image}'
gh release view --repo your-org/payments

# database seam: re-read the schema
psql -c '\d+ orders'
rg -n 'ALTER TABLE orders' db/migrations/ | tail -5
```

Record the provider version on the seam at trace time. That single field is what
makes seam drift detectable later.

## What is genuinely OPAQUE

Not much, and it is worth being strict, because `OPAQUE` is where analysis stops:

- third-party APIs you do not control (Stripe, a bank, a government service)
- another company's system
- a vendored binary with no source
- a service whose repo you have no access to *and* whose artifact is not published

For each, you still record the seam contract and the compatibility requirement,
because that is the entire leverage you have. Everything else — another team's
service in your org, a different language, a different repo — is `CROSSING`, and
the trace continues.
