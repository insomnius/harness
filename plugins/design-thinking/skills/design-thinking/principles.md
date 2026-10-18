# Principles

The method, with no tools in it. Everything in the other reference files is an
illustration of one of these in some stack; when an illustration conflicts with
a principle, the principle wins. Phase applicability in `graph.json` determines
when a principle is exercised: DDD modeling (the Meaning section's aggregate,
context and subdomain work) applies to new features only. Other changes reuse
existing vocabulary and ownership. Graph reports, A/E/R contracts, state-machine
transitions and both TDD gates apply to every implementation task.

## Work

**1. Work is a loop.** Natural language in, a graph delta in the middle, a green
automated check out. Then the next requirement, against a warmer glossary.

**2. Closure is observed, not asserted.** A requirement is done when a check
that was red before any code went green on its own. An agent deciding that
something looks finished is the weakest available evidence.

**3. Stop when a turn stops teaching you something.** Not after a fixed number
of attempts — after the first turn that ends red having produced no new failure,
no new node, no new behaviour and no falsified assumption. A repeated identical
failure is evidence about the requirement, not about the code.

## The graph

**4. The graph already exists.** Discover it; do not invent it. The code, its
tests, its table names and its commit history hold the model already, usually in
an older dialect than the ticket's.

**5. Nodes and edges.** A node is a file with one purpose; a symbol within it; a
behavior within that. An edge is a call, an import, an invocation, a request, a
publish, shared state, or a provisioning relationship. The graph does not stop
at the process boundary — it continues over the wire, through the database, into
infrastructure.

**6. Trace both directions.** Up to what calls it, down to what it calls. Keep
expanding while the change's effect reaches the neighbour. Stop at the node that
absorbs it, or at a structural end — the flow's entrypoint above, a leaf or an
opaque seam below. A hop count is not a stop condition, and a delta still
propagating at the entrypoint is a finding rather than a limit.

**6b. Count decides nothing; compatibility does.** Many callers cost nothing
when the change is additive, and one caller costs a migration when it is
breaking. Where the caller set must be known, enumerate it — with a compiler, or
by running the tests. Where it cannot be known, do not break the contract in
place.

**6c. Evidence has tiers.** Compiler, then a coverage run, then references, then
text, then reasoning. Record which one you reached. A contract change needs one
of the top two; anything weaker is unresolved rather than decided.

**7. Reachable is not the same as belongs.** Every node has one purpose. A
change that reaches a node whose purpose does not cover it is misplaced — it
belongs where the purpose fits, or in a node that does not exist yet. Those are
the only two options available without a human: widening a purpose is a
decision, not a workaround. A purpose generic enough to accept anything is not a
purpose, and that node will accrete everything.

**7b. Deletion is a delta.** Removing a node, a dead alias, a displaced rule or a
pass-through chain is a legitimate entry in a change set, not housekeeping deferred
to later. A change set that only adds, in a codebase whose glossary tracks dead
aliases, has not finished.

**8. Behavior is the unit.** You do not change a file; you change a behavior.
Requirements are satisfied by behaviors; behaviors are proven by tests. That
chain is the only accepted evidence of done.

**8b. The behavior statement and the test name are the same sentence.** Written once,
in the domain's words, and copied rather than paraphrased. That is what makes the
chain from requirement to behavior to test greppable instead of known only to a state
file — and a test whose name does not state a behavior is not proving one.

**9. The code is the graph.** If the code does not match the annotated graph,
the implementation is wrong — not the graph. Resolve the divergence in one
direction deliberately; never leave it silent.

## Every node

**9b. A belongs to a flow.** The success path is a property of the end-to-end
path, not of any node on it. Annotate the flow first; a node's A is its slice of
it. Every node can conform individually while the path through them is wrong.

**10. Three channels.** What flows through on success, where it can break and
what happens then, and what it needs to exist. Annotate all three before writing
the node, in that order.

**11. The success path reads alone.** If following it means stepping over
retries and catches, the two are tangled. Cross-cutting behavior wraps a node
without changing its graph.

**12. Errors are named values with one policy each.** Retry with a bound, fall
back with a stated loss, propagate in this layer's vocabulary, or die. A failure
handled by accident is the same as unhandled. Each layer maps what it received
into its own words and leaks nothing from three layers down.

**13. Dependencies are explicit.** Complete the sentence "we cannot do this
without that" for each one. A dependency reached ambiently — a global, a
singleton, the wall clock, a random source — is invisible in the signature and
is why a node cannot be tested.

**13b. Dependencies point inward.** The domain depends on nothing; adapters depend on
the domain. Explicitness says a dependency is visible in the signature; direction says
which way it is allowed to run. An aggregate importing an HTTP client is explicit and
still wrong.

**14. Parse once, at the edge.** Untrusted data becomes trusted at a single
point, with one definition serving as type, validator and transformer. Trust
nothing at the boundary and everything inside it.

**14b. Make illegal states unrepresentable.** Push validity into the type rather than
into a check at every use. Parsing at the edge decides *when* trust is established;
this decides what the type is allowed to express afterwards. A quantity that can be
negative, an id that can be any string, a status that can be a typo — each one moves
a guarantee out of the compiler and into somebody's memory.

**15. Cleanup is structural.** If an early return, a failure or a cancellation
can skip it, the resource is not scoped.

**16. Substitutability is a design property.** A node should be testable by
replacing its dependencies, with the graph shape unchanged. Needing to fake the
world to test one node means the node is doing too much.

## Meaning

**17. Translate before searching.** A product requirement becomes the domain's
own language first. Untranslated terms are the main source of misplaced
behavior, and the code usually speaks an older dialect than the ticket — so
search the dead names too.

**17b. Investment follows subdomain.** Core gets the model, supporting gets the
minimum that works, generic gets a library. Deciding which one a context is comes
before deciding how much design it deserves — and a method thorough enough to be
worth using is thorough enough to be wasted on a CSV parser.

**18. One term, one meaning, one context.** Two names for a concept is debt. One
name for two concepts is a bug waiting.

**19. Invariants and sequences live in different places.** A rule belongs where
its invariant is owned. A sequence belongs in whatever coordinates it, and that
coordinator owns no rules. A rule with nowhere to live means a concept has no
name yet, and naming it is often the actual work.

**20. Consistency has a boundary.** What must hold together at every commit
defines it. Needing two boundaries to change atomically means either the
boundary is wrong or it is a policy enforced eventually, with a compensation.

## Boundaries between systems

**21. A seam is a node.** An endpoint, a topic, a table, a config key — each has
a contract, and each can drift while the code on both sides stays still.

**22. Crossing translates.** Errors most of all. That mapping is part of the
contract, and it is where two systems' bugs live.

**23. Completeness is unavailable across a published seam.** In-process, the
caller set is provable. Across the wire it is not, so compatibility replaces
completeness: anything removed or narrowed is breaking, however few consumers
were found.

**23b. What cannot be enumerated can be observed.** Replace "who calls this?"
with "is anyone still calling this?" Instrument the old path, announce the
deprecation, wait out the slowest consumer's cadence, verify zero traffic across
the whole window, then remove. That converts a guess into evidence.

**24. Relationship predicts blast radius.** Whether a foreign change stops at a
translation layer or propagates into your domain is decided by how the two
systems relate — and that is knowable before tracing.

**25. Rollout is bidirectional.** Both directions must hold during the window:
old callers against the new provider, and new callers against the old one. The
second is what breaks during a partial rollout and a rollback.

## Discipline

**26. Specify before building, at both altitudes.** No work on a requirement
without a red check for it. No code for a behavior without its contract
annotated and its test red. These two gates, graph reporting and the
state-machine protocol are mandatory; architectural recipes are guidance.

**27. Red for the intended reason.** A check failing because the harness is
broken or the suite will not build proves nothing. Know what was already red
before you started.

**28. Discovery during implementation is information, not friction.** A behavior
found while writing code returns through annotation, test and gate before it
gets written. Reality contradicting the model means correcting the model.

**29. A trace is valid only at the commit it was taken against.** Others change
the code; providers deploy. Re-check before trusting it.

**29b. The trace is the memory; context is a cache.** A verdict, a purpose, a behavior
or a gate entry is written to state before it is acted on, because the context window
gets truncated and the file does not. Any turn can be the last, so the state must read
cold to someone — or something — with no memory of the session that produced it.

**29c. Log the decision, not the state.** State is a fold over decisions, so record
the decision and derive the state — never the reverse. What a reader needs is rarely
the current verdict; it is that the verdict was `no_change` until a compiler error
moved it, and why. Overwriting a record destroys exactly the part worth keeping, and
a reversal with no reason attached is the one gap the log cannot fill later.

**30. A failing test on a node you marked unaffected means the trace was
wrong.** Not the test. That inversion is what makes the test suite the validator
of the analysis.

**31. Report as a multi-level graph.** Status belongs in node form — what is
changing, what is done, what is blocked — nested so the caller/callee
dependencies are visible. A flat list of touched files hides the structure the
whole method is built on, and hides the edit order with it. Prose explains the
tree; it does not replace it.

**31b. One source of truth; every view is rendered.** The append-only decision log
is the source; state files, the tree, the diagram and the index are derived on every write and never
maintained by hand. A view somebody edits is a second source, and the moment the two
disagree the map is lying while the code stands still. This is also why recall across
tasks is an index that is regenerated rather than a document that is updated.
