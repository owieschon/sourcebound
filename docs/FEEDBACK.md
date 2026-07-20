# Feedback loop

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Operators can use this page to turn run outcomes into product improvements without giving telemetry
control over documentation gates, project purpose, or policy.
<!-- sourcebound:end purpose -->

**[Preview the exact envelope bytes before enabling delivery](#enable-and-inspect-feedback)**.

Feedback is a separate observation plane. sourcebound records bounded outcomes from opted-in runs
and delivers them to a named sink. Delivery never participates in a documentation gate. Aggregate
results return through the separately governed [behavior-signal path](BEHAVIOR_SIGNALS.md).

## Consent boundary

Feedback is off by default in local runs and CI. While it is off, a run creates no installation
identifier, envelope, outbox file, or network request.

Enabling feedback writes `.sourcebound/feedback.json`. That visible file names the sink, a
pseudonymous installation identifier, retention, and queue limits. It never stores a credential.
Delivery remains explicit: enabled runs add local envelopes, and only `feedback flush` contacts a
connected sink.

## Enable and inspect feedback

Use a repository-local sink to inspect the complete lifecycle without a network request:

```bash
sourcebound feedback enable --sink local
sourcebound check
sourcebound feedback status
sourcebound feedback preview
sourcebound feedback flush
```

`preview` writes the exact pending `sourcebound.feedback.v1` envelope bytes in delivery order.
Local delivery preserves those bytes. A connected adapter wraps the same envelope in its transport
format and reads its credential only during `flush`.

To stop delivery authority immediately while retaining the local queue:

```bash
sourcebound feedback disable
```

To remove the identifier and every local envelope, signal, case, and delivery record:

```bash
sourcebound feedback purge
```

`feedback rotate` replaces the pseudonymous installation identifier. It does not rewrite queued
envelopes.

## What fires, and when

Each opted-in non-feedback command writes one local envelope after it exits. Feedback commands
manage the queue and do not create another envelope. Nothing fires while feedback is off.

| Exit code | `result_class` | Meaning |
| --- | --- | --- |
| `0` | `success` | The command completed its configured contract. |
| `1` | `drift` | A declared check found documentation drift. |
| `2` | `invalid` | Input, configuration, or a bounded provider response was invalid. |
| `3` | `extraction-failed` | Static extraction could not produce required evidence. |
| Any other code | `failure` | The command stopped outside the defined classes. |

The envelope records the command and exit class, not its arguments, source, prose, prompt, or
provider response. A capture failure leaves the original command result unchanged.

## Outgoing envelope

`sourcebound.feedback.v1` contains only bounded operational fields:

| Field | Meaning |
| --- | --- |
| `event_id` | Stable SHA-256 used for transport deduplication |
| `run_id` | Pseudorandom SHA-256 created once for an opted-in invocation |
| `outcome_id` | SHA-256 binding that run to its command result and repository revision |
| `occurred_at` | UTC observation time |
| `product_version` | sourcebound producer version |
| `installation_id` | Pseudonymous identifier created by explicit enable |
| `command` | Top-level sourcebound command, without arguments |
| `exit_code` and `result_class` | Bounded process result |
| `execution_policy` | `trusted` or `static-only` |
| `adapter` | Aggregate document adapter class |
| `repository_size_class` | Aggregate file-count band |

The envelope excludes source, prose, paths, remotes, arguments, prompts, model responses,
environment values, credentials, and unbounded errors. One run keeps the same IDs across delivery
retries; a new invocation receives new IDs. Connected delivery supplies the event ID as its
deduplication key.

The outbox is capped at 1,000 records and 5 MiB by default. Records expire after 30 days. Delivery
retries stop after three explicit flush attempts and move the envelope to the local dead-letter
directory. Capture and delivery failures never replace the original command's exit code.

The [security model](SECURITY_MODEL.md#feedback-transport) owns transport trust. The
[connected event adapter](adapters/connected-event.md) owns the reference sink setup, and the
[behavior-signal contract](BEHAVIOR_SIGNALS.md) owns the return path.
