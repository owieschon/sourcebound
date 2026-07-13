# clean-docs product specification

**This specification defines the final clean-docs product, the releases that build it, and the executable evidence required to ship each release.**

clean-docs audits a software repository, produces accurate and readable documentation from repository evidence, and keeps the documentation current as the repository changes. Humans and agents consume the same canonical documentation through different generated indexes and context bundles.

This file stays whole despite its length because it has one job: bind the product contract to the release claims, E2E tests, and definitions of done that prove it. Splitting the roadmap from the product contract would let implementation scope and acceptance drift apart.

The product combines two workflows over one evidence model:

1. `clean-docs init` brings an existing repository to a documented baseline.
2. `clean-docs check` protects that baseline on every change.

Generation is the setup path. Continuous verification is the compounding product value. Both paths must share the same evidence graph, bindings, extractors, and renderers. A generator and a checker with separate interpretations of the repository would reproduce the drift clean-docs exists to prevent.

## 1. Product outcome

A repository using clean-docs has a documentation surface that is:

| Property | Product behavior | Evidence |
| --- | --- | --- |
| Accurate | Bound facts are derived from code, commands, schemas, tests, and repository metadata. | `clean-docs check` re-evaluates each binding and fails on drift. |
| Current | Pull requests cannot merge while protected facts differ from their sources. | Required CI check and a deliberate source-change test. |
| Clean | Pages follow the writing standard and the corpus has a deliberate information architecture. | Deterministic style and corpus checks, plus reviewable advisory findings. |
| Human-readable | Pages define the subject first, explain constraints plainly, and use the medium that matches the reader's task. | Task-based human E2E tests and blind comprehension tests. |
| Agent-readable | The same pages are indexed and packaged for retrieval without maintaining a second copy. | Generated `llms.txt`, context bundles, and agent round-trip tests. |
| Honest | The product distinguishes proved facts, advisory judgments, and uncovered surfaces. | Every finding and generated claim reports its evidence class and provenance. |

### Product promise

clean-docs can guarantee that a bound fact does not silently drift. It can detect likely undocumented change outside the bound surface. It cannot guarantee that every concept in any repository has been documented, or that unbound judgment prose remains correct.

"Any repository" means the core can inspect files, run explicitly accepted commands, and apply bindings without depending on a repository's language. Rich discovery of framework concepts requires a first-party or third-party adapter. Unsupported ecosystems retain the generic binding path instead of receiving fabricated semantic coverage.

Use this public claim:

> clean-docs keeps the documented spine of a repository synchronized with its sources and flags changes that may require new documentation.

Do not claim that documentation can never become stale.

## 2. Users and jobs

### Maintainer

The maintainer wants to establish useful documentation without manually reconstructing the repository. They run `clean-docs init`, review the proposed information architecture and bindings, then commit the accepted result.

### Contributor

The contributor changes code and needs an exact answer about documentation impact. They run `clean-docs check --changed`, update or regenerate affected pages, and receive actionable failures tied to source and destination.

### Reviewer

The reviewer needs to know whether documentation changed with the code and whether the changes are grounded. A pull-request report shows changed sources, affected documentation, regenerated regions, failed claims, and uncovered changes.

### Human reader

The reader needs to understand, choose, and act without reading repository internals. They receive task-shaped pages, runnable examples, explicit limitations, and one canonical home for each fact.

### Agent reader

The agent needs compact, current context with stable identifiers and source links. It receives the same canonical pages through `llms.txt`, filtered context bundles, and machine-readable provenance.

## 3. Product principles

1. **Repository evidence outranks authored claims.** Generate factual content from evidence when a deterministic source exists.
2. **One evidence model serves every mode.** Audit, render, check, release notes, and agent packaging call the same extractor interface.
3. **The gate is deterministic.** Models may propose mappings and prose. They do not decide whether CI passes.
4. **One corpus serves humans and agents.** Agent projections index and package canonical pages. They do not fork the facts.
5. **Every failure carries a repair path.** Name the source, document, binding, observed value, expected value, and command that repairs or accepts the change.
6. **Coverage is explicit.** Report bound, unbound, ignored, and advisory surfaces separately.
7. **Generated regions stay bounded.** clean-docs owns marked factual regions. Authors own surrounding explanation.
8. **No executable source by default.** Static extractors parse source. Command extractors require explicit allowlisting and run with declared timeouts.
9. **The product dogfoods itself.** clean-docs generates and verifies its own CLI, configuration, and capability references.

## 4. Existing foundation

clean-docs starts from a working documentation-standard system. Version 0 preserves its evidence and shortcomings. The product work packages and extends this foundation instead of recreating it.

| Existing artifact | Proven behavior | Product destination |
| --- | --- | --- |
| `STANDARD.md` | Defines sentence voice, medium choice, page shape, corpus structure, and the boundary between checks and judgment. | Becomes the default `clean-docs` policy profile and the canonical authoring standard. |
| `quality-gate.py` | Blocks high-confidence language, engineering-claim, code, and secret patterns before Claude Code writes a file. | Its portable rules move into `policy`; the Claude Code hook remains one adapter. |
| `doc-hygiene.py` | Checks process artifacts, agent-addressed docs, provenance, length, duplication, and restatement across tracked Markdown. | Its tested rules move into `policy` with stable finding identifiers, configuration, and regression fixtures. |
| `skill/SKILL.md` | Runs residue and corpus checks during one agent's pre-publish workflow. | Remains a distribution adapter. Equivalent CLI, CI, Codex, Claude Code, editor, and hosting adapters call the same core. |
| `DECISION_LOG.md` | Records why archive handling and several noisy patterns were changed after real-repo triage. | Seeds regression cases and architecture decisions. |
| `ultra-csm-findings.json` and `ultra-csm-before-after.md` | Preserve the 280-finding baseline and the docs-only cleanup evidence. | Seed corpus-policy fixtures and the first dogfood case. |
| `README_ACCESSIBILITY_TEST.md` | Establishes separate mechanical and blind-task gates, then exposes that accessible prose can still be factually incomplete. | Seeds human and agent task-evaluation formats. |
| Prior product brief | Defines ref-aware extraction, region/claim/symbol bindings, derive/check symmetry, and a no-model CI gate. | Supplies the binding engine contract in this specification under the final `clean-docs` name. |

### What the existing proof establishes

- The deterministic policies find real corpus failures.
- Tuning against a real repository exposes false positives that synthetic examples miss.
- A lower finding count proves cleaner structure, not clearer or more accurate prose.
- Blind comprehension testing finds defects that a writer's self-review misses.
- Prose rewriting alone can preserve a stale capability description.
- Repository-derived factual regions and continuous verification are required, not optional extensions.

### What remains unbuilt

- The existing scripts do not share a package, configuration schema, finding model, or CLI.
- The write gate is coupled to Claude Code.
- The hygiene linter detects but does not propose or apply a reviewed baseline.
- No source binding, generated region, claim assertion, coverage model, or ref-aware evidence graph exists in code.
- No `llms.txt`, context bundle, release delta, or task-evaluation runner exists.
- The ultra-csm cleanup improved navigation but left justified findings and did not prove documentation accuracy.

These are the starting conditions for the version plan. Existing artifacts remain executable until their replacements pass parity tests.

## 5. Scope and non-goals

### In scope for the final product

- Repository discovery across common languages and build systems.
- Documentation inventory and information-architecture analysis.
- Evidence extraction from source, schemas, CLI output, tests, and repository metadata.
- Initial documentation generation and existing-document repair proposals.
- Continuous drift checks on bound facts.
- Change-impact detection for new or removed public surface.
- Human-readable Markdown rendering.
- Agent projections, including `llms.txt` and scoped context bundles.
- Deterministic style and corpus hygiene checks.
- Advisory language and structure review.
- Grounded release-note skeletons from evidence deltas.
- Local CLI, pre-commit integration, and GitHub Actions integration.
- A documented extractor and renderer extension API.

### Not in scope

- Replacing a documentation site generator or hosting platform.
- Treating an LLM judgment as a merge gate.
- Executing arbitrary repository code during discovery.
- Rewriting all author-owned prose on each change.
- Inferring product intent that the repository does not encode.
- Promising complete documentation coverage without an accepted coverage policy.
- Maintaining separate human and agent copies of the same facts.

## 6. System model

The system has one pipeline with two enforcement classes.

```text
repository at git ref
        |
        v
  discovery adapters ------> uncovered-surface report (advisory)
        |
        v
  normalized evidence graph
        |
        +------> bindings ------> renderers ------> canonical docs
        |             |                              |
        |             +------> deterministic check --+
        |
        +------> projections --> llms.txt / context bundles / release deltas
        |
        +------> evaluators ---> hygiene / human tasks / agent round trips
```

The deterministic enforcement class includes schema validation, extraction, rendering, binding comparison, claim assertions, symbol checks, link checks, and approved command checks. The advisory class includes proposed coverage, prose rewrites, information-architecture suggestions, and semantic change review.

### 6.1 Core packages

| Package | One job |
| --- | --- |
| `core` | Load configuration, resolve git refs, build the execution plan, and aggregate results. |
| `evidence` | Store normalized evidence values and provenance. |
| `discover` | Inventory code and docs, identify public surfaces, and propose evidence candidates. |
| `extractors` | Convert one source at one git ref into a typed evidence value. |
| `bindings` | Map evidence to a generated region, claim, symbol reference, or coverage expectation. |
| `renderers` | Convert typed evidence into stable Markdown or machine-readable output. |
| `docs` | Parse marked regions, apply patches, and preserve author-owned prose. |
| `policy` | Run deterministic style, corpus, link, and coverage rules. |
| `projections` | Produce `llms.txt`, context bundles, and release deltas from canonical evidence and docs. |
| `reporters` | Present terminal, JSON, SARIF, and GitHub pull-request output. |

### 6.2 Extractor contract

Every extractor is a pure function of a repository snapshot, parameters, and an execution policy:

```text
extract(snapshot, parameters, policy) -> EvidenceValue
```

`snapshot` identifies an immutable git ref and a temporary checkout. `EvidenceValue` contains:

```yaml
kind: table | scalar | text | symbol-set | command-result | schema
value: <typed payload>
provenance:
  ref: <commit SHA>
  sources:
    - path: <repo-relative path>
      locator: <symbol, JSON pointer, line, or command id>
  extractor: <name and version>
  digest: <stable SHA-256 over normalized value>
```

Ref-aware extraction is required from the first release. The same extractor must evaluate `HEAD`, a release tag, or a merge base without changing behavior.

### 6.3 Binding types

| Binding | Authoring behavior | Check behavior | Typical source |
| --- | --- | --- | --- |
| `region` | clean-docs renders a marked block. | Re-render and compare normalized output. | Registry, enum, schema, CLI, routes, MCP tools. |
| `claim` | An author writes prose and declares a machine-checkable assertion. | Evaluate the assertion and compare the typed result. | Test count, coverage floor, package count, compatibility range. |
| `symbol` | An author cites a path, symbol, endpoint, or anchor. | Resolve it at the target ref. | Source files, functions, routes, config keys. |
| `coverage` | A policy declares which public surfaces require documentation. | Compare discovered public surface with accepted bindings or ignores. | Packages, exported symbols, CLI commands, endpoints. |

Generated regions are preferred because the document cannot misstate a value that it does not own. Claims and symbol references cover facts that read better in prose. Coverage bindings expose the product's honest seam: new surface is reported even when no existing binding could have drifted.

### 6.4 Manifest

This section keeps the complete example together because readers need to see how execution policy, bindings, coverage, and projections share one repository contract.

The canonical file is `.clean-docs.yml`. Paths are repository-relative. Unknown keys fail schema validation.

```yaml
version: 1

docs:
  roots: [README.md, docs]
  exclude: [docs/archive]

execution:
  commands: deny
  allowed_commands:
    test-summary:
      argv: [python, -m, pytest, --collect-only, -q]
      timeout_seconds: 30
      network: false

bindings:
  - id: csm-actions
    type: region
    doc: README.md
    region: capabilities
    extractor: python-literal
    source:
      path: src/ultra_csm/governance/csm_actions.py
      symbol: CSM_ACTION_SPECS
    renderer: markdown-table
    columns: [action, autonomy_tier, customer_affecting, release_condition]

  - id: test-count
    type: claim
    doc: README.md
    anchor: testing
    extractor: command
    command: test-summary
    assertion:
      json_path: $.collected
      operator: equals
      expected: 340

  - id: sweep-symbol
    type: symbol
    doc: README.md
    anchor: architecture
    source:
      path: src/ultra_csm/agent1/sweep.py

coverage:
  - id: cli-commands-documented
    discoverer: python-argparse
    include: [public]
    require_binding_type: region
    ignores:
      - match: internal-debug
        reason: Internal command excluded from user documentation.

projections:
  llms_txt:
    output: llms.txt
  bundles:
    - id: contributor
      output: .clean-docs/context/contributor.md
      include: [README.md, docs/CONTRIBUTING.md, docs/ARCHITECTURE.md]
```

### 6.5 Generated-region markers

Markers carry a stable binding identifier. Generated content never nests.

```markdown
<!-- clean-docs:begin csm-actions -->
...generated Markdown...
<!-- clean-docs:end csm-actions -->
```

`derive` refuses malformed, missing, duplicate, or nested markers. It writes through a temporary file and an atomic replace. It changes no text outside the selected regions.

## 7. Command-line experience

| Command | Reader's task | Gate class |
| --- | --- | --- |
| `clean-docs init` | Audit a repository and create a reviewable baseline proposal. | Advisory until accepted. |
| `clean-docs inventory` | List docs, public surfaces, evidence candidates, and coverage. | Deterministic inventory with advisory classifications. |
| `clean-docs derive [--binding ID] [--check]` | Render bound documentation or show the diff without writing. | Deterministic. |
| `clean-docs check [--changed]` | Verify bindings, policy, links, projections, and declared coverage. | Deterministic failures plus separated advisory findings. |
| `clean-docs explain ID` | Show why a finding exists and how to repair it. | Deterministic. |
| `clean-docs project` | Regenerate `llms.txt` and context bundles. | Deterministic. |
| `clean-docs eval` | Run human-task fixtures and agent round-trip evaluations. | Deterministic scoring over recorded outputs; model execution is opt-in. |
| `clean-docs release --from REF --to REF` | Produce a grounded factual change skeleton. | Deterministic facts; narrative remains author-owned. |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | All required checks passed. Advisory findings may exist. |
| `1` | Documentation drift or policy failure. |
| `2` | Invalid configuration or usage. |
| `3` | Extractor or allowed-command execution failed. |
| `4` | The repository state is unsupported or unsafe to inspect. |

JSON and SARIF output must carry the same result identifiers and evidence as terminal output.

## 8. Repository onboarding workflow

`clean-docs init` produces a proposal, not an unreviewed rewrite.

1. Inventory languages, build systems, public surfaces, docs, links, and current claims.
2. Run deterministic hygiene and duplication checks.
3. Build an evidence-candidate graph from static adapters and explicitly allowed commands.
4. Propose the reader-facing information architecture and one canonical home for each fact.
5. Propose bindings for facts with deterministic evidence.
6. Draft or repair author-owned prose with evidence citations. If a model is enabled, label every model-produced change as advisory.
7. Generate a patch, manifest, coverage report, and acceptance checklist.
8. Require a human to accept bindings and prose before `check` treats them as baseline truth.

The no-model path must still inventory, lint, propose deterministic bindings, and render bound regions. A model improves classification and prose drafting. It is not required for the freshness gate.

## 9. Continuous freshness workflow

`clean-docs check --changed` runs in a pull request:

1. Resolve the merge base and head ref.
2. Map changed files and symbols to extractors and bindings.
3. Re-evaluate affected evidence at head.
4. Re-render affected regions and compare them with committed docs.
5. Evaluate claims and symbol references.
6. Compare discovered public surfaces at base and head.
7. Regenerate affected projections.
8. Run hygiene, link, and configured coverage policies.
9. Emit required failures and advisory findings in separate sections.

A failed binding report must answer five questions in one screen:

- What source changed?
- Which documentation is affected?
- What value was committed?
- What value exists now?
- Which command repairs or accepts the result?

## 10. Human and agent accessibility

Canonical documentation follows the existing clean-docs standard:

- Start with a plain definition and the governing constraint.
- Use prose for cause and reasoning.
- Use code for actions the reader should execute.
- Use tables for lookup and comparison.
- Use diagrams for flow, state, or branching.
- Keep one canonical home for each fact.
- Remove process artifacts from the reader-facing surface.
- Carry limitations beside the claim they constrain.

Agent access is a projection problem, not a second-authoring problem.

### `llms.txt`

The generated index contains stable page titles, one-line jobs, canonical URLs or paths, and optional topic tags. Its entries preserve the human information architecture.

### Context bundles

A bundle selects canonical pages and resolved generated regions for one task. Each bundle includes the source ref, creation time, content digest, and links back to full pages. A bundle never introduces facts absent from the canonical corpus.

### Round-trip evaluation

A round-trip test gives a reader or agent only the declared documentation bundle and asks it to complete a concrete task. The evaluator scores observable outputs, not writing style impressions. Examples include invoking a CLI command, identifying a safety limit, constructing a valid configuration, or listing an API surface.

## 11. Security and trust model

Repository content is untrusted input.

- Static parsing is the default.
- Discovery never imports repository Python or JavaScript modules.
- Command extractors run only named `argv` arrays from the accepted manifest.
- Shell interpolation is unsupported.
- Network access is denied unless an accepted command explicitly enables it.
- Commands have time, output, and process-count limits.
- Temporary checkouts are isolated from the user's working tree.
- Secrets are redacted from logs and generated output.
- Symlinks that escape the repository are rejected.
- Generated paths must remain under declared documentation roots.
- Model prompts exclude ignored paths, detected secrets, and files beyond configured size limits.
- CI pins clean-docs and third-party extractor versions.

The initial local implementation may rely on operating-system process controls. The public v1.0 claim requires a documented isolation model and adversarial tests for repository-controlled configuration and content.

## 12. Quality model and metrics

No single score represents documentation quality. clean-docs reports separate measures so one improvement cannot hide another failure.

| Measure | Definition |
| --- | --- |
| Binding freshness | Passing bindings divided by evaluated bindings. Required target: 100%. |
| Surface coverage | Required public surfaces with accepted bindings or explicit ignores. |
| Projection freshness | Generated projections matching the canonical corpus. Required target: 100%. |
| Hygiene findings | Deterministic sentence and corpus findings, by rule. |
| Human task success | Completed human E2E tasks divided by attempted tasks. |
| Agent round-trip success | Correct observable task outputs divided by attempted tasks. |
| False-positive rate | Dismissed required findings divided by required findings. |
| Time to repair | Median time from failed check to passing rerun in dogfood repositories. |

The product must never describe a reduction in hygiene findings as proof that prose became clearer. The ultra-csm pass established that distinction: moving process artifacts improved navigation but did not rewrite reader-facing prose.

## 13. Versioned build plan

Each release proves one product claim before the next release broadens it. A later release may refine schemas, but it cannot weaken a prior E2E test without a recorded compatibility decision.

### Version 0: Proven local foundation, complete

**Claim:** the existing standard, write gate, and corpus linter mechanize part of documentation quality and expose where human judgment remains necessary.

Existing receipts:

- `STANDARD.md` is live as the canonical local writing standard and has been checked against its own rules.
- `quality-gate.py` is registered as a Claude Code pre-write hook.
- `doc-hygiene.py` runs as a standalone detect-only corpus linter with JSON output and nonzero findings exit.
- ultra-csm triage reduced 280 findings to 73 justified findings through documentation-only changes and three evidence-driven false-positive fixes.
- The accessibility experiment demonstrated a real comprehension gain and then exposed a stale capability description, which caused the product to pivot from prose cleanup to source-grounded freshness.

Version 0 preservation work at the start of Version 0.1:

1. Capture golden outputs for the current scripts before refactoring.
2. Turn every decision-log false positive into a named regression fixture.
3. Capture the original and tuned ultra-csm finding sets as corpus-policy acceptance data.
4. Capture the README blind-test prompt, response schema, and known accuracy failure as an evaluation fixture.
5. Keep the standalone scripts runnable until the packaged policy engine proves parity or an intentional difference is recorded.

#### Definition of done

- The receipts above exist at the paths named in section 4 and remain readable.
- Current `quality-gate.py` and `doc-hygiene.py` execute with their documented exit behavior.
- The live `STANDARD.md` and workspace copy are byte-identical at the Version 0 baseline commit.
- Every known false-positive fix in `DECISION_LOG.md` has a regression-case specification.
- The Version 0 limitation is stated without qualification: it detects hygiene problems but does not keep documentation facts synchronized with code.

### Version 0.1: Deterministic binding engine

**Claim:** clean-docs packages the proven policy foundation, then derives and continuously verifies factual documentation on two dissimilar repositories without a model. The two initial dogfoods prove repository independence, not cross-language discovery.

#### Build

- Python package and `clean-docs` CLI.
- Packaged standard, write-gate rules, and corpus-hygiene rules behind a shared policy result model.
- Compatibility wrappers for the existing standalone scripts and Claude Code hook.
- Versioned `.clean-docs.yml` schema with strict validation.
- Immutable git snapshot abstraction.
- Evidence value and provenance model.
- `region`, `claim`, and `symbol` bindings.
- Language-neutral file, structured-data, allowlisted-command, and path extractors, plus a static Python literal/AST extractor.
- Markdown table, list, scalar, and fenced-text renderers.
- Marker-safe `derive` and read-only `derive --check`.
- `check`, terminal output, and JSON output.
- Pre-commit example and reusable GitHub Actions workflow.
- Dogfood manifests for ultra-csm and bank-mcp.

#### Functional E2E tests

1. **ultra-csm capability drift**
   - Given a fixture containing `CSM_ACTION_SPECS` and a matching README region.
   - When a tenth action is added without regenerating the README.
   - Then `clean-docs check` exits `1`, names the binding and changed action, and `clean-docs derive` adds the row without changing surrounding prose.
2. **bank-mcp command claim**
   - Given a README claim bound to an allowlisted deterministic fixture command.
   - When the command result changes from 340 to 341.
   - Then `check` exits `1`, reports committed and observed values, and changes no file.
3. **symbol removal**
   - Given a cited source path or Python symbol.
   - When the symbol is renamed at head.
   - Then `check` exits `1` with the missing locator and affected document anchor.
4. **author prose preservation**
   - Given text before and after two generated regions.
   - When both regions are derived.
   - Then byte comparison proves that all bytes outside the markers are unchanged.
5. **ref purity**
   - Given two refs with different evidence values.
   - When the same extractor runs at each ref in either order.
   - Then it returns the correct ref-specific value with no working-tree mutation.
6. **CI behavior**
   - Given a fixture pull request with drift.
   - When the published workflow runs.
   - Then the check fails and uploads JSON or SARIF evidence. A regenerated commit passes.
7. **Version 0 policy parity**
   - Given the frozen Version 0 fixture corpus and gate payloads.
   - When the packaged policy engine and existing scripts run.
   - Then normalized findings match, except for differences named in an accepted migration file.
8. **known false-positive regressions**
   - Given archived docs, `IF/THEN` decision records, and technical `byte-identical` claims from the prior triage.
   - When corpus policy runs.
   - Then the archived content is skipped in directory scans and the two technical phrases do not create the previous false positives.

#### Definition of done

- All eight E2E scenarios run in CI from temporary git repositories.
- The packaged policy engine passes Version 0 parity before the binding engine replaces any live script.
- Unit and integration tests cover schema rejection, marker corruption, extractor failure, and exit-code contracts.
- `clean-docs check` invokes no model and performs no network request.
- Both dogfood repositories pass at pinned commits with different binding types.
- A deliberate drift commit fails in each dogfood repository.
- The generic file, structured-data, command, and path bindings require no Python project metadata.
- Installation from a clean environment and `clean-docs --help` succeed on supported Python versions.
- The README CLI and manifest reference are generated and verified by clean-docs itself.
- The standalone scripts remain available as compatibility entry points or print an exact migration command.
- The repository carries an OSI-approved license, security policy, and reproducible release artifact.

### Version 0.2: Repository audit and baseline generation

**Claim:** clean-docs can bring an unfamiliar repository to a reviewable documentation baseline without turning model output into accepted truth.

#### Build

- `inventory` and `init` commands.
- Language, package, CLI, API, schema, test, and documentation inventory interfaces.
- Initial adapters for Python packaging, argparse, MCP tools, OpenAPI, JSON Schema, Markdown links, and common test runners.
- Additional policy configuration and finding explanations beyond the Version 0 rules packaged in Version 0.1.
- Evidence-candidate graph and accepted/ignored/unresolved states.
- Patch-plan output with proposed information architecture, bindings, moves, deletions, and prose changes.
- Optional model provider for classification and prose drafts.
- Human acceptance workflow that writes the manifest and baseline.
- `--no-model` mode.

#### Functional E2E tests

1. **unfamiliar Python repository audit**
   - Given a fixture with a package, argparse CLI, tests, stale README command list, duplicate docs, and a process handoff under `docs/`.
   - When `clean-docs init --no-model` runs.
   - Then the proposal inventories the public CLI, detects the stale list, identifies the duplicate and process artifact, and proposes deterministic bindings without editing files.
2. **reviewed bootstrap**
   - Given an accepted subset of the proposal.
   - When `clean-docs init --apply acceptance.yml` runs.
   - Then it writes only accepted docs, markers, ignores, and bindings. A following `check` passes.
3. **model boundary**
   - Given a model response containing an unsupported capability claim.
   - When the proposal is built.
   - Then the claim is marked unsupported and cannot enter an accepted generated region without evidence or explicit author-owned classification.
4. **no-model completeness**
   - Given model credentials are absent.
   - When `init --no-model` runs.
   - Then deterministic inventory, hygiene, binding proposals, and patch output still complete.
5. **idempotent rerun**
   - Given an accepted baseline with no repository changes.
   - When `init` reruns.
   - Then it proposes no factual change and preserves stable binding identifiers.
6. **multi-language fixture**
   - Given a small TypeScript service with `package.json`, CLI help, OpenAPI, and Markdown docs.
   - When inventory runs.
   - Then adapters produce normalized evidence without executing project modules.

#### Definition of done

- All six E2E scenarios pass in CI with recorded proposal artifacts.
- `init` is dry-run by default and requires an acceptance file or interactive confirmation to write.
- Every proposed factual statement links to evidence or carries an `author-owned` label.
- Model-off tests pass with network disabled.
- Secret fixtures prove that detected credentials never enter prompts, logs, or output.
- Re-running the accepted baseline produces an empty patch.
- Audit results distinguish required failures, advisory findings, and unresolved coverage.
- The bootstrap succeeds on one Python and one TypeScript dogfood repository.

### Version 0.3: Change-impact and pull-request gate

**Claim:** clean-docs catches both drift in documented facts and likely new undocumented public surface on every repository change.

#### Build

- `check --changed --base REF --head REF`.
- Dependency map from files and symbols to evidence, bindings, documents, and projections.
- `coverage` bindings and accepted ignore records.
- Base-to-head public-surface diff.
- Required GitHub check with annotations and summary.
- SARIF output and stable finding identifiers.
- Cache keyed by ref, extractor version, parameters, and source digest.
- Repair commands and acceptance workflow for new coverage.
- Monorepo project selection.

#### Functional E2E tests

1. **bound change blocks merge**
   - Given a pull request changes evidence behind a generated region.
   - When the GitHub workflow runs.
   - Then the required check fails with an annotation on the document and a repair command.
2. **new public surface is flagged**
   - Given a pull request adds a public CLI command not present at base.
   - When changed-surface discovery runs.
   - Then the check reports an unresolved coverage item even though no old binding drifted.
3. **private refactor stays quiet**
   - Given a pull request changes private implementation without changing normalized evidence or public surface.
   - When `check --changed` runs.
   - Then required checks pass and no documentation update is requested.
4. **accepted ignore remains explicit**
   - Given a new internal command matches an accepted ignore with a reason.
   - When coverage runs.
   - Then the result passes, reports the ignore, and fails if the ignore no longer matches any surface.
5. **cache correctness**
   - Given repeated checks at one ref and then a source change.
   - When checks run.
   - Then the second unchanged run uses cache, while the changed source invalidates only dependent entries.
6. **monorepo isolation**
   - Given two projects in one repository.
   - When a pull request changes one project.
   - Then only its bindings, policies, and projections run unless a shared source changed.

#### Definition of done

- All six E2E scenarios pass against a local GitHub workflow fixture or equivalent action harness.
- Required and advisory results appear in separate report sections and machine-readable fields.
- A new public surface cannot disappear through a baseline update without an accepted binding, accepted ignore, or recorded removal.
- Stable finding identifiers preserve review state across reruns.
- Cached and uncached runs return byte-identical normalized results.
- Median changed-file check time meets the published budget on dogfood repositories.
- The GitHub Action pins dependencies and requires read-only repository permissions unless posting a report is enabled.

### Version 0.4: Human and agent projections with task evaluation

**Claim:** one canonical documentation corpus supports human tasks and agent tasks without factual forks.

#### Build

- `project` command.
- `llms.txt` generation from the accepted documentation graph.
- Named context bundles with provenance and content digests.
- Link and anchor verification across canonical docs and projections.
- Human task fixture format.
- Agent round-trip fixture format with provider adapters and recorded replay mode.
- Deterministic scorers for structured outputs, commands, configuration, and cited limits.
- Evaluation history that records corpus digest, model, prompt, scorer, and result.
- Accessibility advisory checks tied to the writing standard.

#### Functional E2E tests

1. **single-source projection**
   - Given a canonical page changes.
   - When `project` runs.
   - Then `llms.txt` and affected bundles change, all entries link back to canonical pages, and no independent factual prose is introduced.
2. **stale projection gate**
   - Given canonical docs are current but `llms.txt` is not regenerated.
   - When `check` runs.
   - Then the projection binding fails and `project` repairs it.
3. **human quickstart task**
   - Given a clean environment and only the quickstart docs.
   - When the scripted user follows documented commands.
   - Then installation, first command, and expected output succeed without repository knowledge.
4. **agent configuration round trip**
   - Given an agent receives only the contributor context bundle.
   - When asked to create a valid manifest binding for a fixture.
   - Then the produced file passes schema validation and `check` on that fixture.
5. **limitation retrieval**
   - Given a human or agent receives only the declared docs.
   - When asked whether an unsupported behavior is allowed.
   - Then the answer cites the canonical limitation and does not infer support.
6. **recorded replay**
   - Given a saved agent response and corpus digest.
   - When evaluation reruns without network.
   - Then the scorer reproduces the same result.

#### Definition of done

- All six E2E scenarios pass, with networked agent runs separated from replayable scoring.
- Projections contain canonical content or references only, plus generated metadata.
- Every bundle records a source ref and digest.
- Human and agent task scores are reported separately from hygiene findings.
- At least three task types use deterministic scorers.
- A projection drift test fails before repair and passes after repair.
- The public docs state which evaluation claims are model-specific and which are deterministic.

### Version 0.5: Grounded release workflow and extension API

**Claim:** clean-docs can compare evidence across refs, produce an accurate factual release skeleton, and support new ecosystems without changing the core.

#### Build

- `release --from REF --to REF`.
- Typed evidence diff for added, removed, and changed values.
- Release-note skeleton renderer with provenance links.
- Optional advisory narrative draft over the factual delta.
- Versioned extractor, discoverer, renderer, and policy plugin interfaces.
- Plugin isolation and compatibility checks.
- First-party adapters for CLI frameworks, OpenAPI, JSON Schema, environment/config schemas, package metadata, and MCP tools across Python and TypeScript.
- Migration tooling for manifest schema versions.

#### Functional E2E tests

1. **factual release delta**
   - Given two refs where a CLI command is added and an option is removed.
   - When `release` runs.
   - Then the skeleton reports both changes with source provenance and no unsupported explanation.
2. **narrative cannot alter facts**
   - Given an advisory model draft omits or contradicts a typed delta.
   - When the release artifact is assembled.
   - Then the factual section remains unchanged and the conflicting draft is flagged.
3. **third-party extractor**
   - Given a fixture plugin implementing the published interface.
   - When clean-docs loads it.
   - Then it returns typed evidence, participates in derive/check/release, and cannot write outside its output contract.
4. **incompatible plugin**
   - Given a plugin targeting a different API version.
   - When configuration loads.
   - Then clean-docs exits `2` with an exact compatibility message before extraction.
5. **schema migration**
   - Given a prior manifest version.
   - When migration runs.
   - Then the new manifest validates and produces the same normalized evidence and rendered docs.
6. **cross-ref isolation**
   - Given release extraction at two refs with different dependencies.
   - When adapters run.
   - Then each reads only its snapshot and results do not depend on the active working tree.

#### Definition of done

- All six E2E scenarios pass in CI.
- Release facts are reproducible from refs with no model or network.
- The plugin contract is documented, versioned, and exercised by an external fixture package.
- Schema migration has golden tests and a rollback path.
- First-party adapters share normalized evidence types and identical ref semantics.
- Advisory narrative is clearly separated from deterministic facts in every output format.

### Version 1.0: Supported product

**Claim:** clean-docs is safe and practical for continuous use across supported repository types.

#### Build

- Stable CLI, manifest v1, evidence schema, and plugin API.
- Supported Python and TypeScript adapters with documented compatibility.
- Local, pre-commit, and GitHub pull-request workflows.
- Isolation controls for allowlisted commands and plugins.
- Performance budgets, caching, telemetry opt-in, and diagnostic bundle.
- Upgrade and deprecation policy.
- Public documentation generated and checked by clean-docs.
- Signed release artifacts and software bill of materials.

#### Functional E2E tests

1. **empty-to-protected repository**
   - Given an undocumented supported repository.
   - When a maintainer inventories, reviews, accepts, derives, and enables CI.
   - Then the repo reaches a passing protected baseline without manual manifest editing for discovered standard surfaces.
2. **full change lifecycle**
   - Given a protected repo and a pull request that changes, adds, and removes public behavior.
   - When the contributor follows repair output.
   - Then docs, coverage, projections, and release delta become current and the check passes.
3. **offline deterministic operation**
   - Given no credentials and blocked network.
   - When derive, check, project, release, and replay evaluation run.
   - Then all deterministic capabilities work.
4. **malicious repository**
   - Given fixtures with prompt injection, escaping symlinks, shell metacharacters, secret files, oversized output, and hanging commands.
   - When inventory and check run.
   - Then the product does not execute undeclared code, leak secrets, escape the repo, or exceed declared limits.
5. **upgrade compatibility**
   - Given repositories pinned to the prior supported minor release.
   - When clean-docs upgrades to 1.0.
   - Then manifests migrate or fail with an exact action, and accepted evidence does not silently change.
6. **independent reader success**
   - Given new human and agent users with only published clean-docs docs.
   - When they install the tool, protect a fixture repo, repair deliberate drift, and explain one limitation.
   - Then every observable task passes the published rubric.

#### Definition of done

- All six 1.0 E2E scenarios pass on every supported platform.
- All earlier release E2E suites remain green.
- Two external pilot repositories run the required check for at least 30 days with recorded false-positive and repair-time metrics.
- No open critical security issue exists; threat-model review and adversarial fixtures are complete.
- P95 changed-file check time and memory use meet published budgets on small, medium, and monorepo fixtures.
- Install, upgrade, rollback, and uninstall paths are documented and tested.
- Signed artifacts, checksums, SBOM, license, support policy, and security reporting path are published.
- The docs site, `llms.txt`, context bundles, and CLI reference all pass clean-docs at the release commit.
- The public guarantee matches the boundary in section 1.

## 14. Test architecture

Functional E2E tests use real temporary git repositories, not mocks of git behavior. Each fixture declares:

- Initial files and commit.
- Manifest and accepted policy.
- User action or source change.
- Command under test.
- Expected exit code.
- Expected file diff.
- Expected finding identifiers and evidence.
- Forbidden side effects, including working-tree mutation, network, secret output, and author-prose changes.

Keep four fixture classes:

| Fixture class | Purpose |
| --- | --- |
| `micro` | One behavior with exact golden output. |
| `repo-python` | Cross-feature Python acceptance. |
| `repo-typescript` | Cross-language acceptance. |
| `adversarial` | Trust-boundary and malformed-input tests. |

Dogfood repositories are product demonstrations, not the only E2E fixtures. Tests must remain runnable without access to private repositories or mutable external state.

## 15. Delivery plan

Each version follows the same delivery sequence:

1. Freeze the release claim and its E2E scenarios.
2. Identify which existing artifact, rule, receipt, or failure the release extends.
3. Write parity tests for inherited behavior and failing fixture tests for new behavior.
4. Implement the smallest vertical slice through CLI, core, extractor, binding, renderer, and report.
5. Run the slice on micro fixtures.
6. Run it on the two dissimilar dogfood repositories.
7. Record false positives, false negatives, repair time, and unsafe behavior.
8. Fix the product when a finding is wrong. Do not weaken a fixture to make it green without a recorded product decision.
9. Dogfood the release on clean-docs itself.
10. Retire an old script only after its replacement passes parity and its callers have a migration path.
11. Publish only when the version DoD and every inherited E2E test pass.

## 16. Product decisions carried forward

- The product name is `clean-docs`. The CLI is `clean-docs`. The manifest is `.clean-docs.yml`.
- `STANDARD.md`, `quality-gate.py`, and `doc-hygiene.py` are inherited product inputs, not disposable prototypes.
- The deterministic freshness gate is the product center.
- The repository bootstrapper is part of the final product, but it does not delay the first gate release.
- Models may draft and classify during bootstrap. They do not run in required freshness checks.
- Claim grounding means evaluating a declared source. It does not mean asking a model whether prose sounds supported.
- Derive, check, release, and projections use ref-aware extractors.
- New undocumented surface is a coverage finding, not proof that existing bindings drifted.
- Human and agent documentation share canonical pages.
- Round-trip evaluation measures task completion, not stylistic resemblance.
- Skills for Codex, Claude Code hooks, editor extensions, and hosting integrations are distribution adapters. None defines the product architecture.

## 17. Open decisions before Version 0.1 implementation

Only decisions that change the core contract block implementation:

1. Choose the implementation language and minimum supported runtime. Python fits the proven code and dogfood repos; a compiled binary may reduce installation friction later.
2. Choose the initial static-parser strategy for Python. The contract requires no module import, regardless of parser library.
3. Decide whether `derive` writes by default or requires `--write`. The safer default is a printed diff, with `--write` explicit.
4. Set the Version 0.1 performance budget and supported platforms.
5. Define the normalized-table ordering contract so generated diffs remain stable.

These choices belong in architecture decision records when implementation begins. Product extensions, model providers, hosting, and additional ecosystems do not block Version 0.1.
