"""Public capability registry rendered into the clean-docs README."""

PRODUCT_OVERVIEW = (
    "A stale sentence does not fail loudly. It keeps a straight face after the code has moved on, "
    "and reviewers have no mechanical way to identify the false claim. clean-docs gives each "
    "protected fact a source, then checks that relationship again in CI.\n\n"
    "Declared sources own the protected facts. A packaged policy enforces the deterministic form "
    "floor; authored judgment still owns motivation, pedagogy, and voice. Static adapters read "
    "common code and schema formats, while declared commands run under explicit process controls. "
    "The engine can repair bound regions, rank static count and column candidates, enforce accepted "
    "claim relationships, and publish context such as `llms.txt` with local receipts."
)

ASSURANCE_BOUNDARIES = (
    {
        "surface": "Bound region, claim, or symbol",
        "clean-docs proves": "Configured evidence and documentation still agree",
        "clean-docs does not prove": "Unbound prose is accurate or complete",
    },
    {
        "surface": "Repository catalog",
        "clean-docs proves": "Detected additions, removals, and replacements stay visible",
        "clean-docs does not prove": "Every cataloged item needs or has a reader-facing explanation",
    },
    {
        "surface": "Accepted static source claim",
        "clean-docs proves": "The documented count or identifier set matches its accepted source locator",
        "clean-docs does not prove": "A ranked candidate names the right semantic relationship",
    },
    {
        "surface": "Packaged writing policy",
        "clean-docs proves": "Implemented deterministic rules pass",
        "clean-docs does not prove": "Motivation, pedagogy, personality, or usefulness pass judgment",
    },
    {
        "surface": "Authored purpose and scope",
        "clean-docs proves": "Declared markers and configured relationships remain intact",
        "clean-docs does not prove": "The repository chose the right goals, audience, or priority",
    },
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
        "job": "Assess documentation and enforce adopted scopes",
        "writes": "with --update-baseline",
        "example": "clean-docs audit --format json",
    },
    {"command": "inventory", "job": "List detected repository surfaces and coverage", "writes": "no", "example": "clean-docs inventory --format json"},
    {"command": "claims", "job": "Rank and verify static count and column claims", "writes": "no", "example": "clean-docs claims --format json"},
    {"command": "init", "job": "Write a source-bound documentation baseline", "writes": "yes", "example": "clean-docs init --no-model"},
    {"command": "explain", "job": "Explain a finding or coverage state", "writes": "no", "example": "clean-docs explain purpose-contract --format json"},
    {"command": "doctor", "job": "Check repository and integration readiness", "writes": "with --bundle", "example": "clean-docs doctor --bundle doctor.json"},
    {"command": "verify", "job": "Write a local deterministic outcome receipt", "writes": "with --out", "example": "clean-docs verify --out outcome.json"},
    {"command": "benchmark", "job": "Measure changed-check time and memory budgets", "writes": "with --out", "example": "clean-docs benchmark --base HEAD~1 --head HEAD"},
    {"command": "derive", "job": "Preview or write generated region changes", "writes": "with --write", "example": "clean-docs derive --check"},
    {"command": "drive", "job": "Repair bound regions after deterministic policy checks", "writes": "yes", "example": "clean-docs drive"},
    {"command": "check", "job": "Fail on binding drift or uncovered changed surface", "writes": "no", "example": "clean-docs check --changed --base origin/main --head HEAD"},
    {"command": "project", "job": "Regenerate configured documentation projections", "writes": "unless --check", "example": "clean-docs project --check"},
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
