# Register exemplars

These pairs anchor phrasing without granting a model authority over facts. The source supplies every
fact. The after side changes only altitude, rhythm, emphasis, or warmth.

## README hub: point, action, proof, route

Before:

> sourcebound is a source-bound documentation engine and CLI for maintainers whose code changes
> faster than its documentation. It identifies stale claims and provides a local, deterministic
> path from source change to repaired, verified docs.
>
> Start here for the product map, runnable drift tutorial, real-repository postmortem, and
> deterministic-boundary explanation.

After:

> sourcebound is a source-bound documentation engine and CLI for maintainers who need code and prose
> to change together. It turns selected source facts into checked documentation, so stale claims
> fail in local workflows and CI.
>
> Install sourcebound and catch your first stale claim. The final `sourcebound verify` command prints
> a receipt with `"ok": true`.

The after side defines the product, gives one first action, and names the proof. A routing table then
sends tutorials, command lookup, binding setup, and security questions to their canonical pages.
Mechanism and reference detail move deeper; they are not deleted.

## Outcome before mechanism

Before: The system performs repository documentation validation through deterministic extraction and
comparison mechanisms.

After: sourcebound fails the change when a bound claim no longer matches its source. Static extraction
and comparison produce that result.

## Concrete actors

Before: Documentation synchronization and projection regeneration provide consistency.

After: `repair` updates the bound region. `project` then refreshes every projection that includes it.

## Rhythm

Before: A stale sentence can remain plausible after its source changes, and reviewers can miss the
result during a busy change. A source binding records the relationship so the repository can check
it again. A failing gate then identifies the claim that needs repair.

After: A stale sentence can remain plausible after its source changes, and reviewers can miss it.
Bindings give that sentence a tripwire. The failing gate names the claim that needs repair.

## Assurance once

Before: Deterministic code owns the facts here. Deterministic code also owns the final gate result.

After: [The deterministic seam](../../../docs/learn/deep-dive-the-deterministic-seam.md) assigns fact,
phrasing, and gate authority once.

## Consequence instead of significance

Before: This demonstrates exactly the contract that makes the system trustworthy.

After: The receipt names the source, derived digest, and gate result, so a reviewer can inspect each
part.

## Honest qualification

Before: The command may run only when declared, unless the host blocks it, except when a plugin adds
another boundary.

After: The manifest must declare the command. Host isolation and plugin boundaries remain separate;
the security model owns those limits.

## Earned warmth

Before: Drift is detected reliably.

After: A stale README keeps a straight face. The binding gives it a tripwire.

## Depth instead of deletion

Before: The README includes the complete schema, every option, all precedence rules, and the install
path so the reader has one comprehensive page.

After: The README gives the first verified path. The reference keeps the schema and precedence rules
one click deeper.
