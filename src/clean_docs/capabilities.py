"""Public capability registry rendered into the clean-docs README."""

PRODUCT_OVERVIEW = (
    "A stale sentence does not fail loudly. It keeps a straight face after the code has moved on, "
    "and reviewers have no mechanical way to identify the false claim. clean-docs gives each "
    "protected fact a source, then checks that relationship again in CI.\n\n"
    "Declared sources own the protected facts. A packaged policy enforces the deterministic form "
    "floor; authored judgment still owns motivation, pedagogy, and voice. Static adapters read "
    "common code and schema formats, while declared commands run under explicit process controls. "
    "The engine can repair bound regions, rank static count and column candidates, enforce accepted "
    "source-claim relationships, and publish context such as `llms.txt` with local receipts."
)

ASSURANCE_BOUNDARIES = (
    {
        "surface": "Generated region",
        "clean-docs proves": "Rendered region bytes match configured source evidence",
        "clean-docs does not prove": "Authored prose outside the region is accurate or complete",
    },
    {
        "surface": "Legacy command pin (`type: claim`)",
        "clean-docs proves": "Allowlisted command output matches the configured expected value and the document anchor exists",
        "clean-docs does not prove": "The prose under that anchor states the command result",
    },
    {
        "surface": "Symbol reference",
        "clean-docs proves": "The configured source path or Python symbol exists",
        "clean-docs does not prove": "The surrounding prose describes that symbol accurately",
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
        "surface": "Binding sensitivity receipt",
        "clean-docs proves": "One static check becomes stale after one independently frozen source fact changes",
        "clean-docs does not prove": "The document and source describe the same concept or that the relationship should be accepted",
    },
    {
        "surface": "Declared review contract",
        "clean-docs proves": "At two immutable refs, repository-declared source locators changed without every declared target locator changing",
        "clean-docs does not prove": "The target is stale, a co-change is semantically correct, or the locators describe the same concept",
    },
    {
        "surface": "Pull-request verdict",
        "clean-docs proves": "Static configured checks and changed-surface evidence produce the reported state at one pinned commit",
        "clean-docs does not prove": "Unbound prose, skipped processes, semantic relationships, or authored judgment are correct",
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
    {
        "surface": "Opt-in feedback loop",
        "clean-docs proves": "Validated operational envelopes and improvement-state receipts satisfy their closed schemas",
        "clean-docs does not prove": "Observed behavior establishes causality, authorizes purpose, or makes a candidate change correct",
    },
)

SUPPORTED_BINDINGS = {
    "command-pin": {
        "binding": "command pin (`type: claim`)",
        "source": "Allowlisted JSON command",
        "output": "Configured assertion plus an existing document anchor",
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
    {"command": "binding", "job": "Inspect one proposed source relationship", "writes": "no", "example": "clean-docs binding --help"},
    {
        "command": "binding sensitivity",
        "job": "Test whether one static check depends on a frozen source fact",
        "writes": "no",
        "example": "clean-docs binding sensitivity --help",
    },
    {"command": "context", "job": "Compile provider-neutral evidence packets", "writes": "no", "example": "clean-docs context --help"},
    {"command": "context compile", "job": "Compile a bounded source-addressed context bundle", "writes": "no", "example": "clean-docs context compile --request context-request.json"},
    {"command": "init", "job": "Write a source-bound documentation baseline", "writes": "yes", "example": "clean-docs init --no-model"},
    {"command": "explain", "job": "Explain a finding or coverage state", "writes": "no", "example": "clean-docs explain purpose-contract --format json"},
    {"command": "doctor", "job": "Check repository and integration readiness", "writes": "with --bundle", "example": "clean-docs doctor --bundle doctor.json"},
    {"command": "verify", "job": "Write a local deterministic outcome receipt", "writes": "with --out", "example": "clean-docs verify --out outcome.json"},
    {"command": "benchmark", "job": "Measure changed-check time and memory budgets", "writes": "with --out", "example": "clean-docs benchmark --base HEAD~1 --head HEAD"},
    {"command": "derive", "job": "Preview or write generated region changes", "writes": "with --write", "example": "clean-docs derive --check"},
    {"command": "drive", "job": "Repair bound regions after deterministic policy checks", "writes": "yes", "example": "clean-docs drive"},
    {"command": "plan", "job": "Build an immutable read-only documentation impact plan", "writes": "no", "example": "clean-docs plan --base origin/main --head HEAD --format json"},
    {
        "command": "verdict",
        "job": "Compose one coverage-stating static PR verdict",
        "writes": "no",
        "example": "clean-docs verdict --base origin/main --head HEAD --format json",
    },
    {"command": "check", "job": "Fail on binding drift or uncovered changed surface", "writes": "no", "example": "clean-docs check --changed --base origin/main --head HEAD"},
    {"command": "project", "job": "Regenerate configured documentation projections", "writes": "unless --check", "example": "clean-docs project --check"},
    {"command": "eval", "job": "Score human tasks and replayable agent round trips", "writes": "with --history or live recording", "example": "clean-docs eval --fixtures .clean-docs/eval.yml"},
    {"command": "release", "job": "Render typed release facts between immutable refs", "writes": "no", "example": "clean-docs release --from v0.9.0 --to HEAD"},
    {"command": "migrate", "job": "Upgrade a prior manifest with rollback backup", "writes": "with --write or --rollback", "example": "clean-docs migrate --write"},
    {"command": "feedback", "job": "Manage opt-in operational feedback", "writes": "yes", "example": "clean-docs feedback status"},
    {"command": "feedback enable", "job": "Consent to a named feedback sink", "writes": "yes", "example": "clean-docs feedback enable --sink local"},
    {"command": "feedback status", "job": "Show feedback consent and pending counts", "writes": "no", "example": "clean-docs feedback status"},
    {"command": "feedback preview", "job": "Print exact pending envelope bytes", "writes": "no", "example": "clean-docs feedback preview"},
    {"command": "feedback flush", "job": "Deliver pending feedback envelopes", "writes": "yes", "example": "clean-docs feedback flush"},
    {"command": "feedback disable", "job": "Remove feedback delivery authority", "writes": "yes", "example": "clean-docs feedback disable"},
    {"command": "feedback rotate", "job": "Replace the feedback installation identifier", "writes": "yes", "example": "clean-docs feedback rotate"},
    {"command": "feedback purge", "job": "Delete local feedback state", "writes": "yes", "example": "clean-docs feedback purge"},
    {"command": "feedback signal", "job": "Validate or ingest aggregate behavior signals", "writes": "varies", "example": "clean-docs feedback signal validate --input signal.json"},
    {"command": "feedback signal prepare", "job": "Add a canonical content-derived signal ID", "writes": "no", "example": "clean-docs feedback signal prepare --input signal-body.json"},
    {"command": "feedback signal validate", "job": "Validate one aggregate behavior signal", "writes": "no", "example": "clean-docs feedback signal validate --input signal.json"},
    {"command": "feedback signal ingest", "job": "Create an observed improvement case", "writes": "yes", "example": "clean-docs feedback signal ingest --input signal.json"},
    {"command": "feedback case", "job": "Advance a verified improvement case", "writes": "yes", "example": "clean-docs feedback case transition --case ID --to reproduced --receipt receipt.json"},
    {"command": "feedback case transition", "job": "Apply one adjacent evidence-backed state transition", "writes": "yes", "example": "clean-docs feedback case transition --case ID --to reproduced --receipt receipt.json"},
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
    {
        "scorer": "mutation-red",
        "input": "Provider proposal, frozen fact, and disposable static repository",
        "passes when": "The sensitivity state matches without authorizing the relationship",
    },
)
