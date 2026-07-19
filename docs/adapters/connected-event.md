# PostHog feedback adapter

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Use this adapter when a PostHog project should receive explicitly flushed sourcebound feedback
envelopes for aggregate analysis and an external improvement controller.
<!-- sourcebound:end purpose -->

**[Preview the local envelope before the first flush](../FEEDBACK.md#enable-and-inspect-feedback)**.

This adapter is a transport for the vendor-neutral `sourcebound.feedback.v1` contract. It does not
run inside documentation gates, enable itself, or grant a remote system authority to change a
repository.

## Configure the sink

Choose the capture endpoint for your project region and keep the project token in an environment
variable:

```bash
export CLEAN_DOCS_FEEDBACK_TOKEN='<project-token>'
sourcebound feedback enable \
  --sink connected \
  --endpoint 'https://<region-host>/i/v0/e/' \
  --token-env CLEAN_DOCS_FEEDBACK_TOKEN
```

The configuration stores the environment-variable name, not its value. No request occurs during
enable or during a normal sourcebound command.

Inspect the envelope, then send it:

```bash
sourcebound check
sourcebound feedback preview
sourcebound feedback flush
```

The adapter sends the event name `clean_docs_feedback`, uses the installation identifier as
`distinct_id`, disables person-profile processing, and derives the capture request's stable
top-level `uuid` from the envelope's `event_id`. Retries therefore keep the same ingestion
identity. The project token is added only to the transport body during `flush`; it is never written
to the outbox.

## Failure behavior

A capture error leaves the envelope queued and makes `feedback flush` non-zero. It does not change
the earlier `check`, `audit`, or `verify` result. After three explicit failed flushes, sourcebound
moves the envelope to `.sourcebound/feedback/dead-letter/`.

Use `feedback disable` to remove delivery authority without deleting the queue. Use
`feedback purge` when the identifier and all local feedback state must be removed.

PostHog may aggregate and cluster these events, but its output returns as a
`sourcebound.behavior-signal.v1` hypothesis. The
[behavior-signal contract](../BEHAVIOR_SIGNALS.md) defines the steps required before any candidate
change reaches a normal pull request.
