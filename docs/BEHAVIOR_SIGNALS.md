# Behavior signals

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
Aggregate run outcomes can expose a product defect or unsupported surface. This page shows an
external controller how to turn that signal into a verified change without taking control of
purpose, policy, or gates.
<!-- clean-docs:end purpose -->

**[Prepare and validate one aggregate signal](#prepare-a-signal)**.

A behavior signal is a bounded hypothesis, not a work order. clean-docs records the signal, then
requires each later claim to cite the receipt before it. A candidate reaches the repository only
after it reproduces the problem, adds a failing fixture, beats the baseline in shadow, and passes
an ordinary pull-request verdict.

## Signal contract

An external controller converts feedback envelopes into aggregates. clean-docs accepts only
`clean-docs.behavior-signal.v1`, which requires:

- a versioned metric and its improvement direction;
- a closed UTC observation window;
- numerator and non-zero denominator;
- installation, product version, adapter, execution policy, and repository-size cohorts;
- data-quality and aggregate-privacy classes;
- a source-receipt digest;
- contradictory-evidence digests; and
- an evidence class that distinguishes independent observation from internal regression.

A cross-installation signal needs at least two contributing installations. A product output scored
by the same product stays labeled `internal-regression`.

## Prepare a signal

Have clean-docs compute the content-derived signal ID, then validate or ingest the result:

```bash
clean-docs feedback signal prepare --input signal-body.json > signal.json
clean-docs feedback signal validate --input signal.json
clean-docs feedback signal ingest --input signal.json
```

Ingest creates an `observed` case. It does not approve the metric, infer a goal, or schedule work.

## Advance a case

Every case advances one adjacent state at a time:

```text
observed
  -> reproduced
  -> root-cause-classified
  -> evaluation-proposed
  -> regression-added
  -> shadow-measured
  -> candidate-change
  -> ordinary-verified-pr
```

Advance a case with a receipt whose schema matches the next state:

```bash
clean-docs feedback case transition \
  --case SIGNAL_ID \
  --to reproduced \
  --receipt reproduction.json
```

## Verify the receipt chain

The first receipt binds the signal, reproduced fixture, baseline outcome, and failure class. Each
later receipt names the SHA-256 of the receipt before it. Root-cause receipts add classified
evidence. Evaluation receipts pin the metric, scorer, threshold, and protected cohorts. Regression
receipts prove the fixture went red, while candidate receipts bind the change and complete test
suite. clean-docs stores every receipt and rejects a changed link in the chain. Repeating the same
transition with the same bytes is idempotent.

The shadow receipt binds one cohort and the baseline and candidate metric, scorer, and threshold
digests. A changed definition invalidates the comparison. A candidate advances only when the
aggregate gets better and no protected cohort gets worse. The final state accepts only a
digest-valid `clean-docs.pr-verdict.v1` whose state is `ready`.

## Keep authority outside the signal

Signals may identify a hypothesis, reproduce a problem, classify its cause, propose a test, or name
a failing fixture. They cannot authorize purpose or change a safety boundary. They also cannot
rewrite a deterministic scorer, modify a gold relationship, or open and merge a pull request. An
external controller may ask its own coding system to propose a change, but that change returns
through the ordinary clean-docs and repository CI gates.

The [feedback page](FEEDBACK.md) owns consent, envelope privacy, queues, and delivery. The
[security model](SECURITY_MODEL.md#feedback-transport) owns the transport boundary.
