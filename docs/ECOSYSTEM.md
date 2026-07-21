# Ecosystem fit

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Choose a tool here when a documentation failure has a clear owner but the repository has more than one kind of check. This page separates prose rules, executable procedures, generated reference, selected source-derived facts, and editorial judgment so two gates do not pretend to prove the same thing.
<!-- sourcebound:end purpose -->

**[Configure a source-to-document relationship](REFERENCE.md)**.

| Problem | Owner | Failure it catches | Combined pipeline |
| --- | --- | --- | --- |
| Terminology, spelling, tone, and sentence mechanics | [Vale](https://vale.sh/docs/) | A disallowed term in an authored guide | Run Vale on authored prose before the source-binding gate. |
| A documented UI, API, or CLI procedure | [Doc Detective](https://docs.doc-detective.com/docs/get-started/introduction) | A procedure that no longer reaches its expected result | Run the procedure test beside Sourcebound's static check. |
| Entire API or schema reference | A generator owned by that interface | A missing or stale generated signature | Generate the reference from its defining schema, then link to it. |
| A selected source-derived fact inside authored explanation | Sourcebound | A bound table, count, locator, or region that no longer matches its source | Bind the fact, check drift, repair declared bytes, then refresh projections. |
| Usefulness, completeness, purpose, and strategy | Human review | A true fact that still teaches the wrong thing | Review the reader task and evidence. Do not make a mechanical receipt claim this judgment. |

Sourcebound covers a narrow failure mode. It does not replace a style linter, a procedure runner, a
reference generator, or editorial review. It adds value when a hand-written page needs one or more
specific facts to stay attached to the source that owns them.

If all relevant reference is generated and a procedure test or style rule already owns the remaining
failure, skip Sourcebound. Another gate without a distinct failure mode is noise.
