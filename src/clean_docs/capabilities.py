"""Public capability registry rendered into the clean-docs README."""

PRODUCT_OVERVIEW = (
    "Source owns the facts; the packaged standard owns their form. clean-docs audits tracked "
    "Markdown, binds claims to source evidence, repairs declared regions, and fails CI when "
    "either the facts or the documentation contract drift.\n\n"
    "Static adapters cover Python, TypeScript, OpenAPI, JSON Schema, package metadata, and MCP "
    "tools without importing repository code. Declared commands and versioned plugins run in "
    "disposable copies with bounded I/O and minimal environments.\n\n"
    "The same verified graph produces `llms.txt`, named context bundles, grounded release facts, "
    "and task evaluations for people and agents. Local receipts make those checks inspectable "
    "without telemetry.\n\n"
    "`derive` previews changes unless you pass `--write`. `audit`, `check`, `verify`, and "
    "`release` never change documentation."
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
        "example": "clean-docs audit --format json",
    },
    {"command": "inventory", "job": "List detected repository surfaces and coverage", "writes": "no", "example": "clean-docs inventory --format json"},
    {"command": "init", "job": "Write a source-bound documentation baseline", "writes": "yes", "example": "clean-docs init --no-model"},
    {"command": "explain", "job": "Explain a finding or coverage state", "writes": "no", "example": "clean-docs explain purpose-contract --format json"},
    {"command": "doctor", "job": "Check repository and integration readiness", "writes": "with --bundle", "example": "clean-docs doctor --bundle doctor.json"},
    {"command": "verify", "job": "Write a local deterministic outcome receipt", "writes": "with --out", "example": "clean-docs verify --out outcome.json"},
    {"command": "benchmark", "job": "Measure changed-check time and memory budgets", "writes": "with --out", "example": "clean-docs benchmark --base HEAD~1 --head HEAD"},
    {"command": "derive", "job": "Preview generated region changes", "writes": "with --write", "example": "clean-docs derive --write"},
    {"command": "drive", "job": "Repair bound regions and enforce policy", "writes": "yes", "example": "clean-docs drive"},
    {"command": "check", "job": "Fail on binding drift or uncovered changed surface", "writes": "no", "example": "clean-docs check --base origin/main --head HEAD"},
    {"command": "project", "job": "Regenerate configured documentation projections", "writes": "yes", "example": "clean-docs project --check"},
    {"command": "eval", "job": "Score human tasks and replayable agent round trips", "writes": "with --history or live recording", "example": "clean-docs eval --fixtures .clean-docs/eval.yml"},
    {"command": "release", "job": "Render typed release facts between immutable refs", "writes": "no", "example": "clean-docs release --from v0.9.0 --to HEAD"},
    {"command": "migrate", "job": "Upgrade a prior manifest with rollback backup", "writes": "with --write or --rollback", "example": "clean-docs migrate --write"},
    {"command": "emit", "job": "Project the manifest into another format", "writes": "yes", "example": "clean-docs emit --help"},
    {
        "command": "emit stepwise-skill",
        "job": "Write a manifest-derived stepwise skill package",
        "writes": "yes",
        "example": "clean-docs emit stepwise-skill --out skill",
    },
    {
        "command": "emit llms-txt",
        "job": "Write an index of source-bound documents",
        "writes": "yes",
        "example": "clean-docs emit llms-txt --out llms.txt",
    },
    {"command": "standard", "job": "Build or verify the bundled policy pack", "writes": "varies", "example": "clean-docs standard --help"},
    {"command": "standard build", "job": "Compile the canonical standard", "writes": "yes", "example": "clean-docs standard build"},
    {"command": "standard check", "job": "Fail when the policy pack is stale", "writes": "no", "example": "clean-docs standard check"},
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
