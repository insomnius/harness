# Translating a requirement into the domain

**Load for new-feature development only.** Model only the new capability's
needed terms, ownership and boundaries. Fixes, refactors, migrations,
infrastructure and documentation reuse existing terminology and ownership;
they do not require this DDD modeling exercise. Graph and TDD remain mandatory.

> **Illustrative, not normative.** Translating before searching, one term one
> meaning, invariants versus sequences, consistency boundaries and investment
> following subdomain are principles (`principles.md` 17-20, 17b). The greps and
> tables below are examples.


The `language` phase sits between a PM's prose and any searching. Its job is to
produce the vocabulary and the ownership assignments that everything downstream
depends on: `keyword` searches the glossary, `triage` routes behaviors by role,
`cross` reads the context map.

**Mine the model, do not invent it.** The domain model is already in the
codebase, in its table names, its test names and its module structure — usually
in an older dialect than the PM's. A model invented in isolation produces a
translation layer nobody asked for, and a glossary the code does not share is
just a second vocabulary to keep in sync.

## Classify the subdomain before modelling it

Do this first, because it decides how much of the rest of this file applies.

| Classification | What it means | Investment |
|---|---|---|
| **core** | the differentiator — the reason the product wins | model it properly; this is where the method earns out |
| **supporting** | needed, specific to you, not special | the minimum that works |
| **generic** | everyone has one: auth, billing, notifications, CSV | buy it, or use a library |

A generic subdomain modelled to core standards is the most expensive mistake
available here, and it looks like diligence while you make it. This is where
ponytail's question — *does this need to exist at all?* — is answered "no" most
often, and where the honest output of the `language` phase is sometimes "use a
library, close the ticket."

The inverse costs more. A core subdomain treated as generic is how a
differentiator ends up as `if status == "active"` scattered across four
controllers, and no library will give it back.

## Mining the ubiquitous language

```bash
# what the domain calls things: tables, columns, enums
rg -n 'CREATE TABLE|ALTER TABLE|CREATE TYPE' db/migrations/ | tail -40
psql -c '\dt' && psql -c '\dT+'

# what the code calls things: types and their fields
rg -n --type go '^type [A-Z][A-Za-z]* (struct|interface)' internal/
rg -n --type ruby '^\s*class [A-Z]|^\s*module [A-Z]' app/models app/services

# what behavior is called, in the codebase's own words
go test ./internal/... -list '.*' | rg -v '^ok|^---'
bundle exec rspec --dry-run --format doc | head -60

# event names already in use - the best evidence of domain vocabulary
rg -n --only-matching '"[a-z_]+\.[a-z_]+(ed|d)"' --type go --type ruby | sort -u

# the PM's vocabulary
# read the ticket, the product docs, and the support tickets it links to
```

Then build the glossary as a four-column mapping, because the interesting
information is in the disagreements:

| Domain term | Product says | Code says | Dead aliases |
|---|---|---|---|
| Refund | refund, money back | `Refund`, `refund_records` | `Reversal`, `chargeback_v1` |
| Ledger Entry | transaction | `LedgerEntry` | `journal_line` |
| Refund Policy | refund rules | *(nothing — implicit in `service.go`)* | — |

Three findings fall out, and each is worth reporting:

- **Drift** — product and code use different words for one concept. Every
  translation between them is a place bugs hide, and the trace must search both.
- **Dead aliases** — the code still carries an older name. This is the most
  common reason a keyword search misses the node that matters, so record them
  deliberately rather than cleaning them out of the glossary.
- **A concept with no name in code** — like `Refund Policy` above. An unnamed
  concept lives scattered across whatever files happened to need it, which is
  precisely how rules end up inside application services. Naming it is the actual
  work of the ticket.

Two failures to escalate rather than resolve alone:

- **One word, two meanings, one context.** `Order` meaning both a customer
  purchase and a work order will produce a bug. Two meanings in two *different*
  contexts is fine and normal.
- **A term the domain expert rejects.** If the code's word is not the domain's
  word and the domain expert has a strong preference, that is a renaming task,
  not something to paper over in a mapping table.

## Assigning behavior: which role owns it

Every behavior the requirement needs gets exactly one owner. The old form of
this rule offered two homes — aggregate or orchestrator — which left every rule
that fits no aggregate homeless, because an orchestrator owns no rules. Ask
instead what *kind* of thing the behavior is:

| The behavior… | Owner | Purpose reads as |
|---|---|---|
| enforces an invariant over one consistency boundary | **aggregate root** | the invariant it protects |
| is a rule belonging to no single aggregate | **domain service** | the rule, stated as a decision |
| sequences steps within one transaction, owning no rule | **application service** | the sequence it coordinates |
| drives a flow across more than one transaction, over time | **process manager** | the flow, and its compensations |
| loads or persists one aggregate, whole | **repository** | the aggregate it stores |
| answers a question without writing | **read model** | the question, and for whom |
| translates a foreign model into ours | **anti-corruption layer** | the foreign model it translates |
| translates a transport into a call | **handler** | the transport it adapts |
| makes an invalid state unrepresentable | **value object** | the concept it constrains |
| carries identity through state transitions | **entity** | the identity and its legal transitions |

```
"A refund may not exceed the order's remaining balance"
  → invariant, on the Order's own state → Order aggregate

"After a refund is recorded, write a ledger entry and email the customer"
  → sequence, one transaction, no rules → RefundService (application service)

"A refund over 10,000 requires manager approval"
  → a rule, but not on Order's balance
  → RefundPolicy, a domain service. Not "the orchestrator decides."

"Refund the card, then reverse the ledger entry if the card refund fails"
  → two transactions and a compensation → RefundProcess (process manager)

"Show finance every refund issued this quarter"
  → a question, no writes → RefundLedgerView (read model)
```

**A behavior that fits no role means a concept has no name yet.** That is the
finding, and naming it is usually the real work of the ticket. The two illegal
moves are widening an existing purpose to absorb it — a human's decision, never
the agent's — and parking it in whatever service the trace reached first.

**Application service discipline.** Its purpose statement must read as a
sequence: *"coordinates refund approval, ledger entry and customer
notification."* If it reads as a rule — *"decides whether a refund is
permitted"* — a rule has migrated in, and that is a `MISPLACED` behavior with a
known destination.

```bash
# rules that migrated into services, handlers and controllers
rg -n --type go -B2 'if .*(> |< |>=|<=|== 0|!= nil && )' \
  internal/*/service*.go internal/*/process*.go internal/http/
rg -n --type ruby 'if .*(>|<|==)' app/services/ app/controllers/
```

Numeric comparisons, threshold constants and status checks inside an
application service, a process manager, a handler or a controller are almost
always displaced invariants.

## The four rules of aggregate design

1. **Model true invariants in consistency boundaries.** What must hold at every
   commit is what defines the aggregate. Nothing else belongs inside it.
2. **Design small aggregates.** A large one is a lock queue with a domain name.
3. **Reference other aggregates by identity**, never by object. A field holding
   another aggregate is a transaction boundary you did not mean to draw.
4. **Use eventual consistency outside the boundary**, with a named compensation.

The decision test, when it is not obvious: **whose job is it to make this data
consistent?** If it is the job of the user executing the command, do it in the
same transaction. If it is another user's or another system's job, use eventual
consistency — emit the event, handle it later, and name what undoes the first
step when the second fails. That question resolves most aggregate-boundary
arguments faster than any diagram.

## Process managers and eventual consistency

A process manager owns a flow, not a rule. It has explicit states, is advanced
by domain events, and carries a compensation for every completed step that a
later failure can invalidate. Three things must be written down or it is not
one:

- **the states**, and which event moves it between them
- **the compensation** per undoable step — "reverse the ledger entry" is a
  compensation; "log an error" is not
- **the timeout**, and what happens when it fires. A process with no timeout is
  a leak with a domain name.

Its counterpart is the **read model**: a projection that answers one question
and writes nothing. Give it an explicit staleness budget. A read model whose
allowed lag is unstated will be treated as transactional by the first caller
who needs it to be, and that is a bug nobody can reproduce.

## Entities and value objects

| | Entity | Value object |
|---|---|---|
| identity | has one, persists through change | none, equal by content |
| mutability | state transitions over time | replace, never mutate |
| id type | branded and constrained, never a bare string | n/a |
| test focus | legal and illegal transitions | construction validity |

The practical payoff is at the boundary: a value object is where you make
invalid states unrepresentable, so validation happens once at construction
rather than at every use. `Money`, `EmailAddress`, `RefundAmount` are value
objects; if they are `int64` and `string` in your code, every caller is
revalidating and some caller is forgetting.

## Domain events

Past tense, in the domain's words, describing a fact rather than an intent:
`RefundRecorded`, not `RecordRefund` or `RefundRequestProcessed`. Emitted by the
aggregate whose invariant just held. Payload carries facts, not commands.

Event names are the best keywords in the whole method — a single event name
appears in the publisher, every subscriber, the schema artifact, the tests, and
often the topic name and the migration too. When `keyword` has an event name to
search, `locate` rarely misses.

## The context map

Do this before crossing any seam. For each foreign bounded context, name the
relationship, because it predicts the blast radius:

| Relationship | Their change reaches | Trace behavior |
|---|---|---|
| anti-corruption layer | the ACL node only | trace to the ACL and stop — it absorbs |
| published language | the artifact, then your adapter | diff the artifact |
| conformist | your whole domain | keep tracing; widest blast radius |
| shared kernel | both domains, bidirectionally | the only legitimate lockstep |
| customer-supplier | negotiated, on their schedule | task-tier blocking edge |
| separate ways | nothing, by design | a trace crossing here means a mistake |

This is what `CROSSING` needs in order to be actionable. A seam to a foreign
context with **no ACL and no published language** is the highest-risk shape
there is: you have taken on their model without a translation point, so every
change of theirs is an unbounded change of yours. Worth raising as a finding
even when it is not what the ticket asked about.

## What this phase produces

Captured in `.design/<ref>.<task-slug>.model.json` — the domain as understood
while doing *this* task, at a commit:

- `subdomains[]` — classification, and the investment that follows
- `contexts[]` — relationship, ACL node, predicted propagation depth
- `glossary[]` — canonical term, definition, product terms, code terms, dead
  aliases, drift flag, provenance
- `aggregates[]` — root, identity type, members, invariants
- `domain_services[]` — the rule each one decides
- `application_services[]` — coordinated steps, compensations, `owns_rules: false`
- `process_managers[]` — states, triggering events, compensations, timeout
- `repositories[]` — one aggregate root each
- `read_models[]` — the question, the projection source, the staleness budget
- `domain_events[]` — past-tense names and payloads
- `requirement_restatements[]` — each requirement in the ubiquitous language,
  with its owning role

Record glossary terms through `design.py term` and ownership through
`design.py own`. Use `note --phase language --json '...'` for richer phase
outputs such as context findings; these remain supplemental phase notes,
not automatically populated model fields. All commands append to the log.
See [cli.md](cli.md); never write a script to populate the model JSON.

**It is a record, not a document.** A later task never edits it — it captures
its own. Recall across tasks is `index.md`, derived from every snapshot on every
write, which is why it cannot go stale. When two tasks define one term
differently the index reports a **divergence**, and that is the highest-value
output this phase produces: one term with two meanings is a bug waiting
(principle 18), and it surfaces the moment the second task writes rather than
whenever someone next reads the glossary.
