# clean-docs product specification

<!-- clean-docs:purpose -->
Use this specification when deciding what clean-docs must ship or whether a release claim is earned. It keeps product scope, version order, functional tests, and definitions of done in one contract so implementation and acceptance cannot drift apart.
<!-- clean-docs:end purpose -->

<!-- clean-docs:allow doc-length reason="The release contract and inherited E2E requirements must remain one versioned reference" -->

The product combines two workflows over one evidence model:

1. `clean-docs init` brings an existing repository to the declared standard.
2. `clean-docs drive` regenerates and repairs documentation after repository changes.
3. `clean-docs check` enforces the standard and source bindings in CI.

Generation is the setup path. Continuous verification is the compounding product value. Both paths must share the same evidence graph, bindings, extractors, and renderers. A generator and a checker with separate interpretations of the repository would reproduce the drift clean-docs exists to prevent.

## 1. Product outcome

A repository using clean-docs has a documentation surface that is:

| Property | Product behavior | Evidence |
| --- | --- | --- |
| Accurate | Bound facts are derived from code, commands, schemas, tests, and repository metadata. | `clean-docs check` re-evaluates each binding and fails on drift. |
| Current | Pull requests cannot merge while protected facts differ from their sources. | Required CI check and a deliberate source-change test. |
| Clean | Pages follow the writing standard and the corpus has a deliberate information architecture. | Policy checks and standard-constrained generation. |
| Human-readable | Pages define the subject first, explain constraints plainly, and use the medium that matches the reader's task. | Task-based human E2E tests and blind comprehension tests. |
| Agent-readable | The same pages are indexed and packaged for retrieval without maintaining a second copy. | Generated `llms.txt`, context bundles, and agent round-trip tests. |
| Bounded | The product distinguishes derived facts, standard-constrained phrasing, and uncovered surfaces. | Every generated claim reports its evidence class and provenance. |

### Product promise

clean-docs can guarantee that a bound fact does not silently drift. It can detect likely undocumented change outside the bound surface. It cannot guarantee that every concept in any repository has been documented, or that unbound judgment prose remains correct.

"Any repository" means the core can inspect files, run explicitly accepted commands, and apply bindings without depending on a repository's language. Rich discovery of framework concepts requires a first-party or third-party adapter. Unsupported ecosystems retain the generic binding path instead of receiving fabricated semantic coverage.

Use this public claim:

> Write your documentation standard once. clean-docs drives every repository to it and keeps the result current for humans and agents.

Do not claim that documentation can never become stale.

## 2. Users and jobs

### Maintainer

The maintainer writes or selects a documentation standard. They run `clean-docs init`; the product audits the repository, builds the evidence graph and bindings, writes the documentation, and verifies the result against the standard.

### Contributor

The contributor changes code without manually tracing documentation impact. `clean-docs drive --changed` regenerates affected documentation, and `clean-docs check --changed` proves that the committed result matches the source and standard.

### Repository operator

The operator needs autonomous maintenance with inspectable evidence. A run report shows changed sources, affected documentation, regenerated facts and prose, standard checks, and uncovered surfaces. Inspection is available but is not a required change gate.

### Human reader

The reader needs to understand, choose, and act without reading repository internals. They receive task-shaped pages, runnable examples, explicit limitations, and one canonical home for each fact.

### Agent reader

The agent needs compact, current context with stable identifiers and source links. It receives the same canonical pages through `llms.txt`, filtered context bundles, and machine-readable provenance.

## 3. Product principles

1. **The standard is the human-authored input.** It captures the judgment clean-docs applies across repositories and changes.
2. **Repository evidence owns factual content.** Derive facts from deterministic sources when they exist.
3. **Models phrase; they do not decide.** A model may turn an evidence-backed content plan into readable prose under the standard. Deterministic code owns facts, scope, validation, and gate results.
4. **One evidence model serves every mode.** Audit, render, check, release notes, and agent packaging call the same extractor interface.
5. **One corpus serves humans and agents.** Agent projections index and package canonical pages. They do not fork the facts.
6. **Maintenance is autonomous.** Once a standard is configured, no per-change approval is required for bound facts or standard-constrained prose.
7. **Every failure carries an automatic repair path.** Name the source, document, observed value, expected value, and `drive` action.
8. **Coverage is explicit.** Report bound, unbound, ignored, and standard-gap surfaces separately.
9. **No executable source by default.** Static extractors parse source. Command extractors require explicit allowlisting and run with declared timeouts.
10. **The product dogfoods itself.** clean-docs generates and verifies its own CLI, configuration, and capability references.
11. **The repository contains product truth only.** Private planning, unrelated project context, and publication residue stay outside product code, docs, tests, issues, examples, and metadata.
12. **The product stays local-first.** The CLI, pre-commit hook, and CI action are the product. A static demonstration may explain recorded behavior, but clean-docs does not require a hosted service or outbound telemetry.

## 4. Starting foundation

clean-docs began with a working documentation-standard system. Version 0 preserves its evidence and shortcomings. The version plan records how the product packaged and extended this foundation instead of recreating it.

| Existing artifact | Proven behavior | Product destination |
| --- | --- | --- |
| [`STANDARD.md`](STANDARD.md) | Defines sentence voice, medium choice, page shape, corpus structure, and the boundary between checks and judgment. | Becomes the default `clean-docs` policy profile and the canonical authoring standard. |
| [`quality-gate.py`](quality-gate.py) | Blocks high-confidence language, engineering-claim, code, and secret patterns before an agent writes a file. | Its portable rules move into `policy`; the pre-write hook remains one adapter. |
| [`doc-hygiene.py`](doc-hygiene.py) | Checks process artifacts, agent-addressed docs, provenance, length, duplication, and restatement across tracked Markdown. | Its tested rules move into `policy` with stable finding identifiers, configuration, and regression fixtures. |
| [`skill/SKILL.md`](skill/SKILL.md) | Runs residue and corpus checks during one agent's pre-publish workflow. | Remains a distribution adapter. Equivalent CLI, CI, agent, editor, and publishing adapters call the same core. |
| [`DECISION_LOG.md`](DECISION_LOG.md) | Records why archive handling and several noisy patterns were changed after real-repo triage. | Seeds regression cases and architecture decisions. |
| [`docs/archive/v0/ultra-csm-findings.json`](docs/archive/v0/ultra-csm-findings.json) and [`docs/archive/v0/ultra-csm-before-after.md`](docs/archive/v0/ultra-csm-before-after.md) | Preserve the 280-finding baseline and the docs-only cleanup evidence. | Seed corpus-policy fixtures and the first dogfood case. |
| Prior product brief | Defines ref-aware extraction, region/claim/symbol bindings, derive/check symmetry, and a no-model CI gate. | Supplies the binding engine contract in this specification under the final `clean-docs` name. |

### What the existing proof establishes

- The deterministic policies find real corpus failures.
- Tuning against a real repository exposes false positives that synthetic examples miss.
- A lower finding count proves cleaner structure, not clearer or more accurate prose.
- Blind comprehension testing finds defects that a writer's self-review misses.
- Prose rewriting alone can preserve a stale capability description.
- Repository-derived factual regions and continuous verification are required, not optional extensions.

### Starting gaps closed by the version plan

- The original scripts did not share a package, configuration schema, finding model, or CLI.
- The original write gate was coupled to one agent runtime.
- The original hygiene linter detected findings but did not generate or maintain a compliant baseline.
- Source bindings, generated regions, claim assertions, coverage state, and a ref-aware evidence graph did not exist.
- `llms.txt`, context bundles, release deltas, and task evaluation did not exist.
- The initial ultra-csm cleanup improved navigation but left justified findings and did not prove documentation accuracy.

These are the starting conditions for the version plan. Existing artifacts remain executable until their replacements pass parity tests.

## 5. Scope and non-goals

### In scope for the final product

- Repository discovery across common languages and build systems.
- Documentation inventory and information-architecture analysis.
- Evidence extraction from source, schemas, CLI output, tests, and repository metadata.
- Automatic initial documentation generation and existing-document repair.
- Continuous drift checks on bound facts.
- Change-impact detection for new or removed public surface.
- Human-readable Markdown rendering.
- Agent projections, including `llms.txt`, scoped context bundles, and stepwise skill packages.
- Deterministic style and corpus hygiene checks.
- Standard-constrained language and structure generation with deterministic validation.
- Grounded release-note skeletons from evidence deltas.
- Local CLI, pre-commit integration, and GitHub Actions integration.
- One static demonstration page generated from recorded fixture evidence.
- One governed learning corpus with a tutorial, a source-grounded postmortem, an explanation, and
  a short index that connects them.
- A documented extractor and renderer extension API.

### Not in scope

- Replacing a documentation site generator or hosting platform.
- Treating an LLM judgment as a merge gate.
- Executing arbitrary repository code during discovery.
- Rewriting unaffected prose on each change.
- Inferring product intent that the repository does not encode.
- Promising complete documentation coverage beyond the configured standard and adapters.
- Maintaining separate human and agent copies of the same facts.
- Requiring a hosted service, backend, database, account system, or runtime dashboard.
- Sending repository activity or CLI usage to an analytics service.
- Creating a second documentation site for the learning corpus.

## 6. System model

The system has one pipeline with two enforcement classes.

```text
repository at git ref
        |
        v
  discovery adapters ------> standard and adapter coverage-gap signal
        |
        v
  normalized evidence graph
        |
        +------> content plan --> standard-constrained phraser --> canonical docs
        |             |                              |
        |             +------> deterministic check --+
        |
        +------> projections --> llms.txt / context bundles / release deltas
        |
        +------> evaluators ---> hygiene / human tasks / agent round trips
```

The deterministic enforcement class includes schema validation, extraction, content planning, binding comparison, claim assertions, symbol checks, policy checks, link checks, and approved command checks. The model receives the standard and grounded content plan, then phrases documentation. Its output must preserve cited facts and pass deterministic validation before clean-docs writes it.

### 6.1 Core packages

| Package | One job |
| --- | --- |
| `core` | Load configuration, resolve git refs, build the execution plan, and aggregate results. |
| `evidence` | Store normalized evidence values and provenance. |
| `discover` | Inventory code and docs, identify public surfaces, and produce evidence candidates. |
| `extractors` | Convert one source at one git ref into a typed evidence value. |
| `bindings` | Map evidence to a generated region, claim, symbol reference, or coverage expectation. |
| `renderers` | Convert typed evidence into stable Markdown or machine-readable output. |
| `docs` | Parse pages and marked regions, apply targeted repairs, and preserve unaffected prose. |
| `policy` | Run deterministic style, corpus, link, and coverage rules. |
| `projections` | Produce `llms.txt`, context bundles, stepwise skill packages, and release deltas from canonical evidence and docs. |
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

| Binding | Documentation behavior | Check behavior | Typical source |
| --- | --- | --- | --- |
| `region` | clean-docs renders a marked block. | Re-render and compare normalized output. | Registry, enum, schema, CLI, routes, MCP tools. |
| `claim` | The content plan pairs phrased prose with a machine-checkable assertion. | Evaluate the assertion and compare the typed result. | Test count, coverage floor, package count, compatibility range. |
| `symbol` | Generated prose cites a path, symbol, endpoint, or anchor. | Resolve it at the target ref. | Source files, functions, routes, config keys. |
| `coverage` | The standard declares which public surfaces require documentation. | Compare discovered public surface with bindings or explicit ignores. | Packages, exported symbols, CLI commands, endpoints. |

Generated regions are preferred because the document cannot misstate a value that it does not own. Claims and symbol references cover facts that read better in prose. Coverage bindings expose the product's honest seam: new surface is reported even when no existing binding could have drifted.

### 6.4 Manifest

This section keeps the complete example together because readers need to see how execution policy, bindings, coverage, and projections share one repository contract.

#### Manifest contract

The canonical file is `.clean-docs.yml`. Paths are repository-relative. Unknown keys fail schema validation.

#### Complete example

<!-- clean-docs:allow section-length reason="The manifest example must show one coherent repository contract" -->

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
    include: [README.md, docs/CONTRIBUTING.md, docs/ARCHITECTURE.md]
  bundles:
    - id: contributor
      output: .clean-docs/context/contributor.md
      include: [README.md, docs/CONTRIBUTING.md, docs/ARCHITECTURE.md]
```

`llms_txt.include` declares canonical context that contains no generated binding. The projection labels those entries as declared context and labels source-bound entries with their binding IDs. Every entry carries a content digest. This distinction prevents an index of bound facts from claiming to be the complete documentation corpus.

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
| `clean-docs init` | Audit a repository, create bindings and information architecture, write the baseline, and verify it against the standard. | Self-driving; `--dry-run` previews without becoming a gate. |
| `clean-docs inventory` | List docs, public surfaces, evidence candidates, and coverage. | Deterministic inventory with standard and adapter gaps. |
| `clean-docs derive [--binding ID] [--check]` | Render bound documentation or show the diff without writing. | Deterministic. |
| `clean-docs drive [--changed]` | Regenerate facts and prose affected by repository changes, then run required checks. | Self-driving. |
| `clean-docs check [--changed]` | Verify bindings, policy, links, projections, and declared coverage. | Deterministic failures plus separated coverage gaps. |
| `clean-docs doctor` | Verify configuration, dependencies, isolation support, provider access, and required tool versions before a run. | Deterministic and fail closed for required checks. |
| `clean-docs explain ID` | Show why a finding exists and how to repair it. | Deterministic. |
| `clean-docs project` | Regenerate `llms.txt` and context bundles. | Deterministic. |
| `clean-docs emit llms-txt` | Emit a manifest-derived index of bound documents with content digests. | Deterministic. |
| `clean-docs emit stepwise-skill` | Project the manifest and maintenance workflow into an interoperable stepwise skill package. | Deterministic. |
| `clean-docs eval` | Run human-task fixtures and agent round-trip evaluations. | Deterministic scoring over recorded outputs; model execution is opt-in. |
| `clean-docs release --from REF --to REF` | Produce grounded release notes phrased to the standard. | Deterministic facts with standard-constrained phrasing. |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | All required checks passed. Non-blocking coverage gaps may exist. |
| `1` | Documentation drift or policy failure. |
| `2` | Invalid configuration or usage. |
| `3` | Extractor or allowed-command execution failed. |
| `4` | The repository state is unsupported or unsafe to inspect. |

JSON and SARIF output must carry the same result identifiers and evidence as terminal output.

## 8. Repository onboarding workflow

`clean-docs init` turns the configured standard and repository evidence into a verified documentation baseline.

1. Inventory languages, build systems, public surfaces, docs, links, and current claims.
2. Run deterministic hygiene and duplication checks.
3. Build an evidence-candidate graph from static adapters and explicitly allowed commands.
4. Build the reader-facing information architecture and one canonical home for each fact under the standard.
5. Create bindings for facts with deterministic evidence.
6. Build a grounded content plan whose facts and allowed claims are machine-readable.
7. Phrase or repair prose under the standard. The model may choose wording, not facts or scope.
8. Write the docs, manifest, projections, and coverage state, then run the required checks.

The no-model path still inventories, checks, creates deterministic bindings, and renders factual regions. A configured phrasing provider is required only for prose that cannot be rendered deterministically. The freshness gate never requires a model.

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
9. Apply safe repairs or fail with required findings and coverage gaps.

A failed binding report must answer five questions in one screen:

- What source changed?
- Which documentation is affected?
- What value was committed?
- What value exists now?
- Which `drive` action repairs the result?

## 10. Human and agent accessibility

Canonical documentation follows the existing clean-docs standard:

- Open every reader-facing page with one marked BLUF purpose contract immediately after its H1.
- Name who should read, the problem that makes the page necessary, and the capability the reader gains.
- Start with a plain definition and the governing constraint.
- State the value and problem before the procedure.
- Use prose for cause and reasoning.
- Use code for actions the reader should execute.
- Use tables for lookup and comparison.
- Use diagrams for flow, state, or branching.
- Keep one canonical home for each fact.
- Remove process artifacts from the reader-facing surface.
- Carry limitations beside the claim they constrain.
- Use progressive disclosure: summary, task path, reference, then optional depth.
- Keep examples executable and test them against the supported release.

The gate checks the contract's mechanical floor: one complete block exists, it precedes all body
content, it is plain prose, and it does not restate the title. Judgment checks whether the audience,
problem, and outcome are specific, falsifiable, and true to the implementation. A mechanical pass
cannot establish those claims. Bootstrap marks an existing author opener without rewriting it and
creates a deterministic fallback only when no usable opener exists.

The compiled standard carries the voice as structured generation data: second-person imperative
for reader actions, the system as actor for behavior, one claim per sentence, concrete verbs,
direct certainty, explicit genuine uncertainty, and the register of a helpful senior colleague.
The full authored standard remains in the pack as the generation instruction; the structure makes
the traits testable at the prompt boundary instead of depending on a model to infer them.

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
- Command extractors run only named `argv` arrays from the configured manifest.
- Shell interpolation is unsupported.
- Deterministic clean-docs paths make no network request, and manifests cannot grant network access to a declared command or plugin.
- The local process wrapper cannot revoke host network access or absolute host paths. The execution environment must enforce those boundaries before it runs untrusted declared code.
- Commands have time, output, and process-count limits.
- Temporary checkouts are isolated from the user's working tree.
- Secrets are redacted from logs and generated output.
- Symlinks that escape the repository are rejected.
- Generated paths must remain under declared documentation roots.
- Model prompts exclude ignored paths, detected secrets, and files beyond configured size limits.
- Model prompts are assembled deterministically from declared inputs and record content digests.
- Secret values resolve outside model context and never enter prompts or provider logs.
- Repository text is scanned for prompt-injection patterns before it enters a phrasing-model context.
- Provider health checks fail closed before model-assisted work starts.
- CI pins clean-docs and third-party extractor versions.
- A clean-docs candidate cannot be its own release authority. The last trusted commit
  checks the candidate tree independently, and trust-pin promotion is a separate release
  operation after candidate tests and dogfood proofs pass.

The initial local implementation may rely on operating-system process controls. The public v1.0 claim requires a documented isolation model and adversarial tests for repository-controlled configuration and content.

## 12. Quality model and metrics

No single score represents documentation quality. clean-docs reports separate measures so one improvement cannot hide another failure.

| Measure | Definition |
| --- | --- |
| Binding freshness | Passing bindings divided by evaluated bindings. Required target: 100%. |
| Surface coverage | Required public surfaces with bindings or explicit ignores. |
| Projection freshness | Generated projections matching the canonical corpus. Required target: 100%. |
| Hygiene findings | Deterministic sentence and corpus findings, by rule. |
| Human task success | Completed human E2E tasks divided by attempted tasks. |
| Agent round-trip success | Correct observable task outputs divided by attempted tasks. |
| False-positive rate | Dismissed required findings divided by required findings. |
| Time to repair | Median time from failed check to passing rerun in dogfood repositories. |
| Critical-path model calls | Model calls made by deterministic derive and check paths. Required target: zero. |
| Local outcome receipts | Machine-readable counts for completed baselines, caught drift, repaired checks, and evaluation task success. |

The product must never describe a reduction in hygiene findings as proof that prose became clearer. The ultra-csm pass established that distinction: moving process artifacts improved navigation but did not rewrite reader-facing prose.

## 13. Versioned build plan

Each release proves one product claim before the next release broadens it. A later release may refine schemas, but it cannot weaken a prior E2E test without a recorded compatibility decision.

| Release | Commit | Required CI | Wheel SHA-256 |
| --- | --- | --- | --- |
| [`v0.1.0`](https://github.com/owieschon/clean-docs/releases/tag/v0.1.0) | `de5cdc5458d319043da31f2d874b3186c9840224` | [29226615998](https://github.com/owieschon/clean-docs/actions/runs/29226615998) | `5b8f53dfe3ee546e7efd9656414385099ef9a2f9eae00d3ffc0b04f286315497` |
| [`v0.2.0`](https://github.com/owieschon/clean-docs/releases/tag/v0.2.0) | `cea7c10b52c2fb4e7f836a92836a210bbc7557a7` | [29228125889](https://github.com/owieschon/clean-docs/actions/runs/29228125889) | `02b742a95d2676453e1ca14129978297e496f2a441c27c80f91f8c75f4d59b46` |
| [`v0.3.0`](https://github.com/owieschon/clean-docs/releases/tag/v0.3.0) | `f7c036198c7f2cbff59247d1307218133502b724` | [29228926772](https://github.com/owieschon/clean-docs/actions/runs/29228926772) | `0430ab14d02b643aab6990caed1094d1b89f6dfcd08d414d7968b39ff8ba21ac` |
| [`v0.4.0`](https://github.com/owieschon/clean-docs/releases/tag/v0.4.0) | `715b91f01f67d519993f5aa23640867b76178e1a` | [29231093305](https://github.com/owieschon/clean-docs/actions/runs/29231093305) | `7599cdfc191089b2b7cead7798512ed4814a85e5fb73d40b806be60b9eb5eff9` |
| [`v0.5.0`](https://github.com/owieschon/clean-docs/releases/tag/v0.5.0) | `17cd5461214e456d9f1925280627d7ec9ec0f0cb` | [29232645262](https://github.com/owieschon/clean-docs/actions/runs/29232645262) | `ed31005ab2160267701d7e16e1dacc8b0fa28935fcc321c3826f1973e8540f6d` |
| [`v1.0.0rc5`](https://github.com/owieschon/clean-docs/releases/tag/v1.0.0rc5) | `a7c37ee90c9c6f73af1d73e685be9690d6856b92` | [29238892016](https://github.com/owieschon/clean-docs/actions/runs/29238892016) | `0ddb43c5a848e4243466bb6222f090cf8cbc0d9a414c07b98cc53e519a1ffc83` |
| [`v1.0.0rc6`](https://github.com/owieschon/clean-docs/releases/tag/v1.0.0rc6) | `7f204ad38ac4c0668786c7cf7989b49fe435bb2e` | [29241466531](https://github.com/owieschon/clean-docs/actions/runs/29241466531) | `8d74fe28ab5c24d13899c7535c24286ec7795cb7c4b962ffab79bad53d8968c8` |

### Version 0: Proven local foundation, complete

**Claim:** the existing standard captures the human judgment; the write gate and corpus linter prove that part of it can already execute as policy.

Existing receipts:

- `STANDARD.md` is live as the canonical local writing standard and has been checked against its own rules.
- `quality-gate.py` is registered as a pre-write hook in the original runtime.
- `doc-hygiene.py` runs as a standalone detect-only corpus linter with JSON output and nonzero findings exit.
- ultra-csm triage reduced 280 findings to 73 justified findings through documentation-only changes and three evidence-driven false-positive fixes.
- The accessibility experiment demonstrated a real comprehension gain and then exposed a stale capability description, which caused the product to pivot from prose cleanup to source-grounded freshness.

Version 0 preservation work at the start of Version 0.1:

1. Capture golden outputs for the current scripts before refactoring.
2. Turn every decision-log false positive into a named regression fixture.
3. Capture the original and tuned ultra-csm finding sets as corpus-policy acceptance data.
4. Keep the standalone scripts runnable until the packaged policy engine proves parity or an intentional difference is recorded.

#### Definition of done

- The receipts above exist at the paths named in section 4 and remain readable.
- Current `quality-gate.py` and `doc-hygiene.py` execute with their documented exit behavior.
- The project `STANDARD.md` preserves the four-tier baseline while using product-neutral provenance and examples.
- Every known false-positive fix in `DECISION_LOG.md` has a regression-case specification.
- The Version 0 limitation is stated without qualification: it detects hygiene problems but does not keep documentation facts synchronized with code.

### Version 0.1: Deterministic binding engine, complete

**Claim:** clean-docs packages the proven policy foundation, then derives and continuously verifies factual documentation on two dissimilar repositories without a model. The two initial dogfoods prove repository independence, not cross-language discovery.

#### Build

- Python package and `clean-docs` CLI.
- Packaged standard, write-gate rules, and corpus-hygiene rules behind a shared policy result model.
- Packaged residue and cross-project leakage rules with neutral defaults and repository-owned configuration.
- Compatibility wrappers for the existing standalone scripts and pre-write hook.
- Versioned `.clean-docs.yml` schema with strict validation.
- Immutable git snapshot abstraction.
- Evidence value and provenance model.
- `region`, `claim`, and `symbol` bindings.
- Language-neutral file, structured-data, allowlisted-command, and path extractors, plus a static Python literal/AST extractor.
- Markdown table, list, scalar, and fenced-text renderers.
- Marker-safe `derive` and read-only `derive --check`.
- `check`, terminal output, and JSON output.
- Pre-commit example and reusable GitHub Actions workflow.
- `doctor` command for configuration, dependency, and isolation readiness.
- Pinned dogfood manifests for ultra-csm and agent-governance-lab.
- A dual self-hosting gate that runs both the candidate and a verifier extracted from a
  pinned trusted ancestor without importing candidate clean-docs code.

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
4. **unrelated prose preservation**
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
   - Then normalized findings match, except for differences named in a declared migration file.
8. **known false-positive regressions**
   - Given archived docs, `IF/THEN` decision records, and technical `byte-identical` claims from the prior triage.
   - When corpus policy runs.
   - Then the archived content is skipped in directory scans and the two technical phrases do not create the previous false positives.
9. **self-hosting checker tampering**
   - Given stale generated documentation and a candidate checker changed to always pass.
   - When the dual self-hosting gate runs.
   - Then the candidate result passes, the pinned trusted verifier fails on the stale binding, and the combined gate exits nonzero.

#### Definition of done

- All nine E2E scenarios run in CI from temporary git repositories.
- The packaged policy engine passes Version 0 parity before the binding engine replaces any live script.
- Unit and integration tests cover schema rejection, marker corruption, extractor failure, and exit-code contracts.
- `clean-docs check` invokes no model and performs no network request.
- Both dogfood repositories pass at pinned commits with different binding types.
- A deliberate drift commit fails in each dogfood repository.
- A candidate checker cannot override a trusted-verifier failure, and CI fetches the
  pinned ancestor required to run that verifier.
- The generic file, structured-data, command, and path bindings require no Python project metadata.
- Installation from a clean environment and `clean-docs --help` succeed on supported Python versions.
- The README CLI and manifest reference are generated and verified by clean-docs itself.
- The standalone scripts remain available as compatibility entry points or print an exact migration command.
- The repository carries an OSI-approved license, security policy, and reproducible release artifact.
- A repository-residue scan passes across code, docs, tests, examples, issue templates, and package metadata.

### Version 0.2: Repository audit and baseline generation, complete

**Claim:** clean-docs can drive an unfamiliar repository to the configured documentation standard without turning model output into factual authority.

#### Build

- `inventory` and `init` commands.
- Language, package, CLI, API, schema, test, and documentation inventory interfaces.
- Initial adapters for Python packaging, argparse, MCP tools, OpenAPI, JSON Schema, Markdown links, and common test runners.
- Additional policy configuration and finding explanations beyond the Version 0 rules packaged in Version 0.1.
- Evidence graph and bound/ignored/standard-gap states.
- Automatic information architecture, bindings, moves, deletions, and prose repairs, with `--dry-run` diff output.
- Optional model provider for classification and prose drafts.
- Deterministic prompt builder, provider interface, recorded response fixtures, and mock provider.
- Prompt-injection scan over repository content selected for model context.
- Deterministic acceptance rules that reject unsupported claims and invalid mappings before writing.
- `--no-model` mode.

#### Functional E2E tests

1. **unfamiliar Python repository baseline**
   - Given a fixture with a package, argparse CLI, tests, stale README command list, duplicate docs, and a process handoff under `docs/`.
   - When `clean-docs init --no-model` runs.
   - Then clean-docs inventories the public CLI, repairs the stale list, removes the duplicate and process artifact from the reader surface, creates deterministic bindings, and passes `check`.
2. **standard-once bootstrap**
   - Given a repository and a configured documentation standard.
   - When `clean-docs init` runs without interactive input.
   - Then it writes the baseline, manifest, and projections; every generated fact has evidence; and a following `check` passes.
3. **model boundary**
   - Given a model response containing an unsupported capability claim.
   - When the content plan is built.
   - Then the unsupported claim is rejected and cannot enter generated documentation.
4. **no-model completeness**
   - Given model credentials are absent.
   - When `init --no-model` runs.
   - Then deterministic inventory, hygiene, bindings, and factual-region generation still complete.
5. **idempotent rerun**
   - Given a generated baseline with no repository changes.
   - When `init` reruns.
   - Then it produces no factual change and preserves stable binding identifiers.
6. **multi-language fixture**
   - Given a small TypeScript service with `package.json`, CLI help, OpenAPI, and Markdown docs.
   - When inventory runs.
   - Then adapters produce normalized evidence without executing project modules.
7. **hostile phrasing context**
   - Given repository prose containing instructions to override the system, disclose secrets, or modify required findings.
   - When model-assisted classification runs against a mock provider.
   - Then the scan marks the input, secrets remain absent, deterministic findings stay unchanged, and the response cannot alter gate results.

#### Definition of done

- All seven E2E scenarios pass in CI with recorded content plans and evidence.
- `init` writes and verifies by default; `--dry-run` provides optional inspection without changing the autonomous contract.
- Every generated factual statement links to evidence. Unsupported claims fail before writing.
- Model-off tests pass with network disabled.
- Model-on E2E tests use the mock provider in required CI; optional live-provider tests never gate a release.
- Secret fixtures prove that detected credentials never enter prompts, logs, or output.
- Re-running the generated baseline produces an empty patch.
- Audit results distinguish required failures and standard or adapter coverage gaps.
- The bootstrap succeeds on one Python and one TypeScript dogfood repository.

### Version 0.3: Change-impact and pull-request gate, complete

**Claim:** clean-docs catches both drift in documented facts and likely new undocumented public surface on every repository change.

#### Build

- `check --changed --base REF --head REF`.
- Dependency map from files and symbols to evidence, bindings, documents, and projections.
- `coverage` bindings and explicit ignore records.
- Base-to-head public-surface diff.
- Required GitHub check with annotations and summary.
- SARIF output and stable finding identifiers.
- Cache keyed by ref, extractor version, parameters, and source digest.
- Automatic repair actions for recognized new coverage and exact gap reports for unsupported surfaces.
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
4. **declared ignore remains explicit**
   - Given a new internal command matches a declared ignore with a reason.
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
- Required results and standard or adapter gaps appear in separate report sections and machine-readable fields.
- A new public surface cannot disappear through a baseline update without an automatic binding, declared ignore, or recorded removal.
- Stable finding identifiers preserve finding identity across reruns.
- Cached and uncached runs return byte-identical normalized results.
- Median changed-file check time meets the published budget on dogfood repositories.
- The GitHub Action requires a full clean-docs commit, uses read-only repository permissions, and publishes a content-addressed receipt that binds the installed candidate, source commit, workflow run, and raw evidence files.

### Version 0.4: Human and agent projections with task evaluation, complete

**Claim:** one canonical documentation corpus supports human tasks and agent tasks without factual forks.

#### Build

- `project` command.
- `llms.txt` generation from the verified documentation graph.
- Named context bundles with provenance and content digests.
- Link and anchor verification across canonical docs and projections.
- Human task fixture format.
- Agent round-trip fixture format with provider adapters and recorded replay mode.
- Deterministic scorers for structured outputs, commands, configuration, and cited limits.
- Evaluation history that records corpus digest, model, prompt, scorer, and result.
- Standard-constrained accessibility generation and deterministic structural checks.
- Task-first documentation templates with intended-reader, value, prerequisites, procedure, limits, and next-step slots.
- Manifest-derived stepwise skill projection with strict configuration, ordered reference files,
  explicit navigation, and skill or command CLI roles.
- A static demonstration generated from recorded before, drift, and repaired fixture states.

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
7. **stepwise skill projection**
   - Given a manifest with bound documents and the recorded stepwise package schema.
   - When `emit stepwise-skill` runs twice.
   - Then the output is byte-stable, names the real bound documents, validates against the schema,
     chains every reference through `next_step`, and its audit, drive, and check commands pass in a
     temporary repository.
8. **static demonstration**
   - Given recorded fixture evidence for current, drifted, and repaired states.
   - When the demonstration is generated twice.
   - Then the output is byte-stable, shows the exact check and repair evidence, and requires no backend, database, credentials, or runtime network request.

#### Definition of done

- All eight E2E scenarios pass, with networked agent runs separated from replayable scoring.
- Projections contain canonical content or references only, plus generated metadata.
- Every bundle records a source ref and digest.
- Human and agent task scores are reported separately from hygiene findings.
- At least three task types use deterministic scorers.
- A projection drift test fails before repair and passes after repair.
- The public docs state which evaluation claims are model-specific and which are deterministic.
- The stepwise package is a projection of the manifest and canonical workflow; it carries no
  independent factual copy of repository documentation.

### Version 0.5: Grounded release workflow and extension API, complete

**Claim:** clean-docs can compare evidence across refs, produce an accurate factual release skeleton, and support new ecosystems without changing the core.

#### Build

- `release --from REF --to REF`.
- Typed evidence diff for added, removed, and changed values.
- Release-note skeleton renderer with provenance links.
- Standard-constrained narrative phrasing over the factual delta.
- Versioned extractor, discoverer, renderer, and policy plugin interfaces.
- Plugin isolation and compatibility checks.
- First-party adapters for CLI frameworks, OpenAPI, JSON Schema, environment/config schemas, package metadata, and MCP tools across Python and TypeScript.
- Migration tooling for manifest schema versions.

#### Functional E2E tests

1. **factual release delta**
   - Given two refs where a CLI command is added and an option is removed.
   - When `release` runs.
   - Then the skeleton reports both changes with source provenance and no unsupported explanation.
2. **phrasing cannot alter facts**
   - Given a model response omits or contradicts a typed delta.
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
- Narrative phrasing preserves and cites deterministic facts in every output format.

### Version 1.0: Supported product

**Claim:** clean-docs is safe and practical for continuous use across supported repository types.

#### Build

- Stable CLI, manifest v1, evidence schema, and plugin API.
- Supported Python and TypeScript adapters with documented compatibility.
- Local, pre-commit, and GitHub pull-request workflows.
- Isolation controls for allowlisted commands and plugins.
- Performance budgets, caching, local outcome receipts, and a diagnostic bundle.
- Upgrade and deprecation policy.
- Exact, reviewable hygiene baselines for adopting repositories with existing documentation debt.
- Compact bootstrap summaries that preserve a deterministic digest of the full detected catalog.
- Nested workspace and package discovery, including package manifests outside the root workspace glob.
- Conservative onboarding that leaves weak purpose openings unresolved instead of certifying metadata or boilerplate.
- Bounded canonical-document selection for `llms.txt`, with bound facts distinguished from declared context.
- Public documentation generated and checked by clean-docs.
- A compiled voice and BLUF purpose contract used by bootstrap, audit, and phrasing prompts.
- Public source repository under the MIT license from the first supported release.
- Signed release artifacts and software bill of materials.

#### Functional E2E tests

1. **empty-to-protected repository**
   - Given an undocumented supported repository.
   - When a maintainer supplies the standard and runs `clean-docs init`.
   - Then the repo reaches a passing protected baseline without manual document or manifest editing for discovered standard surfaces.
   - Every active Markdown page opens with a purpose contract; existing author prose remains byte-for-byte inside its markers, and a second init has no patch.
   - Given an existing corpus with hygiene debt, the explicit adoption mode records exact findings, fails on new findings, and requires baseline pruning when debt is resolved.
   - Given metadata, a status line, or a feature fragment where purpose prose should be, deterministic init leaves the page unchanged and names the authored-judgment gap.
   - Given a mature monorepo, the plan discovers nested packages and registered tools, excludes explicit Markdown fixtures, keeps ambiguous operational documents active, caps serialized facts and diffs, and proposes no more than eight canonical documents.
   - A source-bound registered-tool count changes when the registration source changes; a repository catalog never reports unrelated prose as directly bound.
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
   - Then manifests migrate or fail with an exact action, and bound evidence does not silently change.
6. **independent reader success**
   - Given fresh sessions for Anthropic Opus 4.8, Anthropic Sonnet 5, Codex GPT 5.5 High, and Codex GPT 5.6 Sol High with only published clean-docs docs.
   - When each model independently installs the tool, protects a fixture repo, repairs deliberate drift, and explains one limitation.
   - Then every model passes every observable task in the published rubric without shared history or prior outputs.
   - A reader can identify the README's applicability, problem, and resulting capability without reading past its first body block.
   - Required release evidence binds the candidate commit and artifact, rubric, supplied documents, participant independence attestations, and per-task receipts by SHA-256. Internal command rehearsal and recorded responses test the harness but do not substitute for the independent trial.

#### Definition of done

- All six 1.0 E2E scenarios pass on every supported platform.
- The stable release build rejects a missing, duplicate, substituted, incomplete, stale, or tampered receipt for any required model profile.
- All earlier release E2E suites remain green.
- Two external pilot repositories continue a 30-day evaluation window that records false-positive and repair-time metrics; this observation window does not block the stable release.
- No open critical security issue exists; threat-model review and adversarial fixtures are complete.
- P95 changed-file check time and memory use meet published budgets on small, medium, and monorepo fixtures.
- Install, upgrade, rollback, and uninstall paths are documented and tested.
- Signed artifacts, checksums, SBOM, license, support policy, and security reporting path are published.
- Machine-readable run summaries report product outcomes locally and make no outbound request.
- The static docs and demonstration site, `llms.txt`, context bundles, and CLI reference all pass clean-docs at the release commit.
- Audit fails on a missing, misplaced, malformed, or title-restating purpose contract, and generated stepwise docs pass the same rule.
- Functional tests prove that the phrasing prompt carries the structured voice and purpose rubrics while release-note fragments are not misclassified as complete documents.
- The public guarantee matches the boundary in section 1.

### Version 1.1: Governed learning layer

**Start condition:** the Version 1.0 stable release is published and its release DoD is green. The
non-blocking pilot observation window may continue in parallel; it does not delay this version.

**Claim:** the repository teaches why source-bound documentation matters, how to use it, and where
its deterministic boundary sits. clean-docs keeps the checkable spine of that teaching corpus
current in the same repository.

#### Build

- Set the public repository description to a one-sentence category and purpose contract.
- Add the topics `documentation`, `docs-as-code`, `developer-experience`, `context-engineering`,
  `llm`, `ai`, `cli`, `python`, `pre-commit`, and `technical-writing`.
- Render `docs/assets/clean-docs-social.png` from the system-map source at the repository social
  preview aspect ratio, then set it as the repository preview image.
- Keep the README purpose contract as its first body block. Add a compact status, license, and
  package badge row plus a **Start here** link to `docs/learn/index.md` before the product detail.
- Add `docs/learn/index.md` with the thesis that documentation drift is a source-derivation problem,
  then route readers through the product overview and three lessons.
- Add `docs/learn/tutorial-catch-a-lying-doc.md`, a runnable tutorial that binds one fact, creates
  deliberate drift, observes the failed check, repairs the region, and verifies the result.
- Add `docs/learn/postmortem-the-readme-that-lied.md`, a source-grounded case study built from the
  archived ultra-csm before-and-after evidence without exposing process artifacts as current docs.
- Add `docs/learn/deep-dive-the-deterministic-seam.md`, an explanation of why models may phrase
  supplied evidence but never select facts, widen scope, or decide whether the gate passes.
- Add the four learning pages to the canonical `llms.txt` projection. Link to existing reference
  facts instead of copying the CLI, supported-binding, security, or compatibility registries.
- Bind tutorial output to a deterministic fixture, render postmortem measurements from a typed
  historical evidence record, and bind deep-dive implementation claims to stable source locators.

#### Phase order

1. **Repository legibility:** description, topics, verified badges, README entry point, and social
   preview. Ship this as one reversible metadata and documentation change.
2. **Case study:** convert the archived before-and-after material into typed evidence and the
   postmortem, then prove that changing the evidence makes the bound prose fail.
3. **Tutorial:** build the clean-room fixture and execute every published command against the
   installed stable wheel.
4. **Explanation:** write and source-bind the deterministic-seam argument after the runnable path
   and concrete case establish its vocabulary.
5. **Learning spine:** publish the index, wire the README and `llms.txt`, then run the corpus and
   independent-reader checks. Do not add a fourth lesson.

#### Functional E2E tests

1. **public repository legibility**
   - Given the public repository and a fresh browser request.
   - When its metadata and README first screen are inspected.
   - Then the description and topics match the declared contract, every badge resolves, the social
     preview uses the generated PNG, and **Start here** reaches the learning index.
2. **tutorial from a clean room**
   - Given only the stable wheel, its offline dependencies, the tutorial, and an empty temporary git
     repository.
   - When every command is run in order with network blocked.
   - Then the baseline passes, deliberate source drift fails with the named binding, repair changes
     only the declared region, projection refresh succeeds, and final check and verify exit `0`.
3. **postmortem facts cannot drift**
   - Given the typed historical evidence and its rendered measurement and example regions.
   - When one recorded value or cited locator changes in a fixture.
   - Then check fails before repair, drive regenerates the bound passage, and unbound analysis stays
     byte-for-byte unchanged.
4. **deterministic-seam boundary**
   - Given the deep dive and the implementation sources it cites.
   - When a command, source locator, or authority boundary changes.
   - Then a source binding or link check fails; no copied registry can remain plausibly stale.
5. **additive learning corpus**
   - Given the complete `docs/learn/` directory.
   - When audit and project checks run.
   - Then all four pages have first-position purpose contracts, stay within the standard length
     ceilings, add no near-duplicate fact, resolve every link, and appear in `llms.txt`.
6. **fresh-reader learning path**
   - Given fresh sessions from two model families with only the README first screen, learning index,
     and linked published pages.
   - When each reader chooses a lesson for an orientation, hands-on, and mechanism question, then
     completes the tutorial and explains who owns facts and gate results.
   - Then both choose the matching page, produce the observed tutorial outcomes, and preserve the
     deterministic authority boundary. Receipts bind the corpus digest and task outputs.

#### Definition of done

- The Version 1.0 start condition is satisfied before any Version 1.1 implementation commit lands.
- Public repository description, topics, badges, and social preview pass the legibility E2E test.
- `docs/learn/` contains exactly the index and three named lessons; no separate learning site or
  fourth piece exists.
- The tutorial, postmortem, and deep dive are respectively a learning procedure, a case study, and
  an explanation. Each states its learning outcome in its first body block.
- Every tutorial command runs from the published stable artifact without network, hidden context,
  or repository-local installation.
- Tutorial outputs, historical measurements, and implementation-boundary claims are source-bound;
  changing their defining evidence makes check fail before repair.
- Existing canonical reference tables and version facts are linked, never copied into the lessons.
- `clean-docs audit`, `check`, `project --check`, and `verify` pass with zero new or baselined finding
  for the learning corpus, and all inherited release E2E suites remain green.
- The README links the learning index above product detail, the index links every lesson in the
  declared reading order, and `llms.txt` contains all four pages with current digests.
- Two independent fresh-reader receipts pass all routing, tutorial, and authority-boundary tasks;
  judgment evidence remains distinct from the deterministic merge gates.
- The work stops at the bounded learning corpus. It does not add a backend, a second site, a fourth
  lesson, multi-SDK reference volume, or unrelated subject-matter tutorials.

## 14. Test architecture

Functional E2E tests use real temporary git repositories, not mocks of git behavior. Each fixture declares:

- Initial files and commit.
- Manifest and configured standard.
- User action or source change.
- Command under test.
- Expected exit code.
- Expected file diff.
- Expected finding identifiers and evidence.
- Forbidden side effects, including undeclared working-tree mutation, network requests by deterministic clean-docs paths, secret output, and unrelated prose changes. Declared child-process network isolation remains an execution-environment responsibility.

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
- The repository bootstrapper is the self-driving setup path, but it does not delay the first gate release.
- Models may classify and phrase grounded content. They do not select facts, expand scope, or decide required checks.
- Claim grounding means evaluating a declared source. It does not mean asking a model whether prose sounds supported.
- Derive, check, release, and projections use ref-aware extractors.
- Recognized new surface is documented automatically. Unsupported new surface is a standard or adapter coverage gap that names the missing capability.
- Human and agent documentation share canonical pages.
- Round-trip evaluation measures task completion, not stylistic resemblance.
- Agent skills, pre-write hooks, editor extensions, and static publishing integrations are distribution adapters. None defines the product architecture.

## 17. Version 0.1 architecture decisions

1. The package targets CPython 3.10 through 3.14 on Linux and macOS. The required CI matrix runs every supported runtime and operating system pair.
2. Static Python evidence uses the standard-library abstract syntax tree and never imports repository modules.
3. `derive` prints a diff by default. `derive --write` and `drive` are the explicit write paths.
4. A static micro-repository check must complete within five seconds. Explicit command runtime is governed separately by each allowlisted timeout.
5. Tables and lists preserve source evidence order. Path evidence sorts lexicographically. clean-docs does not reorder semantic arrays to manufacture stable output.

Product extensions, model providers, static publishing, and additional ecosystems do not alter these Version 0.1 contracts.
