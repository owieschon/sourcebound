# Example: repairing a JSON-backed scalar default inside prose

## What this shows

`renderer: inline-scalar` (`json` extractor) lets a single scalar value from a
JSON file be bound to same-line markers inside a Markdown sentence, so a
prose default claim like `(default: y)` can be checked and repaired without
turning the sentence into a table or block region.

## Source case

ryankanno/cookiecutter-py PR [#660](https://github.com/ryankanno/cookiecutter-py/pull/660)
corrected three stale README defaults (`should_upload_coverage_to_codecov`,
`should_publish_to_testpypi`, `should_publish_to_pypi`: `y` -> `n`) that had
drifted from `cookiecutter.json`. This case was picked after the fact, from a
public, merged PR, to exercise this feature against a real bug rather than a
synthetic one.

`fixtures/` holds the frozen inputs, immutable and MIT-licensed:
- `upstream-README.md` — README before the fix (SHA-256
  `89b21a210d40a532767f0aee4b8eb95134b8077f10ba79f76bc4ccddfc881442`)
- `upstream-README-fixed.md` — README after the fix, used only as the
  comparison target
- `cookiecutter.json` — the JSON source of truth (SHA-256
  `0dc48fe4682188e7a1feb9908a4ad886352cd08867c0fbe7a30c19a19a34adb8`)
- `LICENSE` — upstream's MIT license, carried with the vendored files

## Run it

```sh
python examples/cookiecutter-defaults-repair/replay.py
```

The script is a single, offline, one-command replay: no network access and no
subprocess/model execution. It copies the frozen fixtures into a temp
directory, inserts 13 declared same-line markers (one per README default
claim — this insertion is manual setup, not automatic discovery), then:

1. Runs a minimal regex+JSON assertion directly against the *unmarked*
   original inputs (the same kind of check PR660 itself added) and confirms
   it independently finds the same 3 wrong claims. Sourcebound does not claim
   better discovery here — the bug is trivially detectable either way.
2. Runs Sourcebound's audit over the 13 declared bindings and confirms
   exactly 3 are wrong and 10 are unchanged.
3. Drives the repair, so only the interior bytes of the 3 wrong markers
   change — no other byte in the document moves.
4. Strips the inserted markers and checks the result is byte-identical to
   the real upstream-fixed README.
5. Demonstrates two negative paths (a duplicate region marker, a JSON
   pointer that does not resolve) failing with a clear diagnostic and
   leaving the document untouched.

## Limits

This demonstrates a bounded repair mechanism on one historical case, not
general accuracy, discovery, or a production-readiness claim. It requires
declaring markers and a manifest binding per claim; it does not find
undeclared drift on its own. Scope is Markdown only — MDX documents are
explicitly rejected for `inline-scalar`.
