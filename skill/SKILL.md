---
name: scrub
description: Scan a repo for identity/company residue, cross-project leakage, and AI-authorship tells before publishing or sharing it. Invoke when Owen says "scrub this repo", "check for residue/AI tells", or before making a repo public/portfolio-visible. Args - path to the repo (defaults to cwd).
---

# Scrub — residue detection before publishing

Generalized from `ultra-csm/scripts/hygiene_scan.py` (same detect+baseline design,
proven there) into a portable, config-driven tool at
`~/.config/clean-docs/scrub.py` — stdlib-only Python, no dependencies, runs
against any repo regardless of its own language/stack.

## What it checks (three categories)

1. **identity-residue** — Owen's own name/company/project markers (universal
   across his repos, built into the engine, not per-repo config).
2. **wrong-domain** — terms that belong to a *different* one of Owen's projects
   leaking into this one (e.g. `sku`/`fulfillment` terms leaking into a repo
   that isn't sku-resolution-engine). Repo-specific — comes from
   `<repo>/.clean-docs/scrub-config.json`, `wrong_domain_terms: [...]`. Empty/no
   config just means this category returns nothing, never an error.
3. **meta-residue** — AI-authorship / hiring-prep tells (universal, built in):
   "load-bearing", "killer scenario", "portfolio", "the trap", etc.

## Usage

```
python3 ~/.config/clean-docs/scrub.py <repo_root>              # scan, exit 1 if findings
python3 ~/.config/clean-docs/scrub.py <repo_root> --no-baseline # ignore baseline, show everything
python3 ~/.config/clean-docs/scrub.py <repo_root> --refresh-baseline  # grandfather current findings
```

## Baseline (don't silently delete pre-existing stuff)

Findings are fingerprinted (path:line:kind:line-hash) into
`<repo>/.clean-docs/scrub-baseline.txt`. A finding already in the baseline doesn't
block — this is how the tool honors "mention pre-existing issues, don't
silently fix or delete them": review what `--refresh-baseline` would grandfather
before running it, so genuine pre-existing residue isn't accidentally excused,
only deliberately deferred.

## Detection only

This finds residue; it does not rewrite files. Once findings are reported,
fix them by hand (or hand the list to an agent) — auto-rewriting file content
across an unfamiliar repo is a bigger blast radius than this tool is scoped
for. Config and baseline files under `.clean-docs/` are excluded from their own
scan by construction — confirmed by test, not assumed.

## Extending per repo

Add `<repo>/.clean-docs/scrub-config.json`:
```json
{
  "wrong_domain_terms": ["sku", "fulfillment"],
  "scan_roots": ["README.md", "docs", "src"],
  "extra_ignored_paths": ["vendor"]
}
```
Only `wrong_domain_terms` and structural overrides belong here — identity and
meta-residue patterns are universal and live in the engine so a fix in one
never needs to be repeated per repo (the failure mode this replaces: the
same entity-migration list hardcoded in three separate command files).

## Companion: doc-surface hygiene (run before publishing)

Residue is one axis; document sprawl is another. As part of the pre-publish
sweep, also run the doc-hygiene linter — it enforces the corpus-level rules in
the canonical writing standard that neither this residue scan nor the per-write
quality gate can see:

```
python3 ~/scripts/doc-hygiene.py <repo_root>   # exit 1 if findings, --json for machine output
```

It flags process artifacts on the reader surface (reports, handoffs, status
logs), reference docs whose audience reads as a future agent, provenance and
receipts stored as canon, over-length docs and sections, and near-duplicate
paragraphs across docs (one-canonical-home violations). Detect-only, same as
scrub: it reports, you fix by hand. The two are complementary — scrub asks
"does this leak identity or cross-project residue?", doc-hygiene asks "does each
doc earn its place on a reader-facing surface?"
