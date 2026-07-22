# Reader guide

<!-- sourcebound:purpose -->
Use this fixture when verifying that source-bound and editorial checks remain independent. It gives maintainers one deliberate drift case that shows which tool should fail and which should abstain.
<!-- sourcebound:end purpose -->

Run the fixture from the Sourcebound repository root:

```bash
python3 tests/contracts/run_toolchain_fixture.py \
  --tree HEAD \
  --receipt /tmp/sourcebound-toolchain-receipt.json
```

The baseline Sourcebound and Vale checks must both exit zero. The runner then adds `publish` to
`src/actions.py`: Sourcebound must reject the stale action table, while Vale must remain green
because it owns wording rather than source truth. Inspect the receipt at the path passed to
`--receipt` for the four exit codes and their output digests.

The runner downloads the checksum-pinned Vale binary and requires macOS `sandbox-exec`. Use the
repository's contract tests when either prerequisite is unavailable.
