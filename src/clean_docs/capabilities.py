"""Public capability registry rendered into the clean-docs README."""

PRODUCT_OVERVIEW = (
    "Version 1.0rc3 protects Python and TypeScript repository documentation through local, "
    "pre-commit, and pull-request workflows. It compares normalized evidence across immutable "
    "refs and renders "
    "provenance-backed release facts. Optional narrative drafts cannot change, omit, or "
    "uncite those facts. Versioned plugins add extractors, discoverers, renderers, and policy "
    "checks in disposable snapshots; manifest migration includes a byte-exact rollback. It "
    "projects one verified documentation graph into llms.txt, named context bundles, and an "
    "accessible static demonstration. It scores human commands and recorded agent responses, "
    "reports changed binding drift and coverage gaps, and bootstraps source-bound baselines. "
    "Mature repositories can commit an exact existing-debt baseline that fails on new and "
    "resolved findings until explicitly refreshed. "
    "Static adapters cover Python, TypeScript, OpenAPI, JSON Schema, package metadata, and MCP "
    "tools without importing repository code. Declared processes run in disposable copies with "
    "bounded I/O and minimal environments. Local outcome, performance, and diagnostic receipts "
    "make checks inspectable without telemetry. `derive` previews changes unless you pass "
    "`--write`; `audit`, `check`, `verify`, and `release` never change documentation."
)

SUPPORTED_BINDINGS = {
    "claim": {
        "binding": "claim",
        "source": "Allowlisted JSON command",
        "output": "Assertion at a document anchor",
        "check": "Compare typed expected and observed values",
    },
    "region": {
        "binding": "region",
        "source": "Static Python, structured data, text, or paths",
        "output": "Table, list, scalar, or fenced text",
        "check": "Re-render and compare",
    },
    "symbol": {
        "binding": "symbol",
        "source": "Static path or Python symbol",
        "output": "Reference at a document anchor",
        "check": "Resolve the cited locator",
    },
}

CLI_REFERENCE = (
    {
        "command": "audit",
        "job": "Inventory and check repository documentation",
        "writes": "with --update-baseline",
    },
    {"command": "inventory", "job": "List detected repository surfaces and coverage", "writes": "no"},
    {"command": "init", "job": "Write a source-bound documentation baseline", "writes": "yes"},
    {"command": "explain", "job": "Explain a finding or coverage state", "writes": "no"},
    {"command": "doctor", "job": "Check repository and integration readiness", "writes": "no"},
    {"command": "verify", "job": "Write a local deterministic outcome receipt", "writes": "with --out"},
    {"command": "benchmark", "job": "Measure changed-check time and memory budgets", "writes": "with --out"},
    {"command": "derive", "job": "Preview generated region changes", "writes": "with --write"},
    {"command": "drive", "job": "Repair bound regions and enforce policy", "writes": "yes"},
    {"command": "check", "job": "Fail on binding drift or uncovered changed surface", "writes": "no"},
    {"command": "project", "job": "Regenerate configured documentation projections", "writes": "yes"},
    {"command": "eval", "job": "Score human tasks and replayable agent round trips", "writes": "with --history or live recording"},
    {"command": "release", "job": "Render typed release facts between immutable refs", "writes": "no"},
    {"command": "migrate", "job": "Upgrade a prior manifest with rollback backup", "writes": "with --write or --rollback"},
    {"command": "emit", "job": "Project the manifest into another format", "writes": "yes"},
    {
        "command": "emit stepwise-skill",
        "job": "Write a manifest-derived stepwise skill package",
        "writes": "yes",
    },
    {
        "command": "emit llms-txt",
        "job": "Write an index of source-bound documents",
        "writes": "yes",
    },
    {"command": "standard", "job": "Build or verify the bundled policy pack", "writes": "varies"},
    {"command": "standard build", "job": "Compile the canonical standard", "writes": "yes"},
    {"command": "standard check", "job": "Fail when the policy pack is stale", "writes": "no"},
)

EVALUATION_SCORERS = (
    {
        "scorer": "command",
        "input": "Allowlisted command and documented excerpt",
        "passes when": "Exit code and required output match",
    },
    {
        "scorer": "configuration",
        "input": "Recorded manifest and fixture repository",
        "passes when": "Schema validation and check pass",
    },
    {
        "scorer": "structured-output",
        "input": "Recorded JSON and expected value",
        "passes when": "Parsed values match exactly",
    },
    {
        "scorer": "cited-limit",
        "input": "Recorded answer, canonical citation, and forbidden inferences",
        "passes when": "The answer cites the declared limit without inferring support",
    },
)
