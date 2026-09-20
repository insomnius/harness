# Local code-smell catalog

All 23 smells have complete local guides in `../smells/`. Read the relevant
guide for its meaning, evidence, example, refactoring options, exceptions, and
verification. No external lookup is needed. Source links are attribution only.

The taxonomy follows [Refactoring.Guru](https://refactoring.guru/refactoring/smells)
(consulted 2026-09-20). Explanations and examples are authored for this repository.

## Bloaters

- [Long Method](../smells/long-method.md)
- [Large Class](../smells/large-class.md)
- [Primitive Obsession](../smells/primitive-obsession.md)
- [Long Parameter List](../smells/long-parameter-list.md)
- [Data Clumps](../smells/data-clumps.md)

## Object-Orientation Abusers

- [Switch Statements](../smells/switch-statements.md)
- [Temporary Field](../smells/temporary-field.md)
- [Refused Bequest](../smells/refused-bequest.md)
- [Alternative Classes with Different Interfaces](../smells/alternative-classes-with-different-interfaces.md)

## Change Preventers

- [Divergent Change](../smells/divergent-change.md)
- [Shotgun Surgery](../smells/shotgun-surgery.md)
- [Parallel Inheritance Hierarchies](../smells/parallel-inheritance-hierarchies.md)

## Dispensables

- [Comments](../smells/comments.md)
- [Duplicate Code](../smells/duplicate-code.md)
- [Lazy Class](../smells/lazy-class.md)
- [Data Class](../smells/data-class.md)
- [Dead Code](../smells/dead-code.md)
- [Speculative Generality](../smells/speculative-generality.md)

## Couplers

- [Feature Envy](../smells/feature-envy.md)
- [Inappropriate Intimacy](../smells/inappropriate-intimacy.md)
- [Message Chains](../smells/message-chains.md)
- [Middle Man](../smells/middle-man.md)

## Other

- [Incomplete Library Class](../smells/incomplete-library-class.md)

Incomplete Library Class appears among Couplers on the source overview and
under Other Smells in its navigation; it is included once here under Other.
