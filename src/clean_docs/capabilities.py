"""Public capability registry rendered into the sourcebound README."""

PRODUCT_OVERVIEW = (
    "A stale sentence does not fail loudly. It keeps a straight face after the code has moved on, "
    "and reviewers have no mechanical way to identify the false claim. Sourcebound gives each "
    "protected fact a source, then checks that relationship again in CI.\n\n"
    "Declared sources own the protected facts. A packaged policy enforces the deterministic form "
    "floor; authored judgment still owns motivation, pedagogy, and voice. Static adapters read "
    "common code and schema formats, while declared commands run under explicit process controls. "
    "The engine can repair bound regions, rank static count and column candidates, enforce accepted "
    "source-claim relationships, and project canonical text and visual records into purpose-built "
    "human and agent surfaces with local receipts."
)

ASSURANCE_BOUNDARIES = (
    {
        "surface": "Generated region",
        "sourcebound proves": "Rendered region bytes match configured source evidence",
        "sourcebound does not prove": "Authored prose outside the region is accurate or complete",
    },
    {
        "surface": "Legacy command pin (`type: claim`)",
        "sourcebound proves": "Allowlisted command output matches the configured expected value and the document anchor exists",
        "sourcebound does not prove": "The prose under that anchor states the command result",
    },
    {
        "surface": "Symbol reference",
        "sourcebound proves": "The configured source path or Python symbol exists",
        "sourcebound does not prove": "The surrounding prose describes that symbol accurately",
    },
    {
        "surface": "Repository catalog",
        "sourcebound proves": "Detected additions, removals, and replacements stay visible",
        "sourcebound does not prove": "Every cataloged item needs or has a reader-facing explanation",
    },
    {
        "surface": "Accepted static source claim",
        "sourcebound proves": "The documented count or identifier set matches its accepted source locator",
        "sourcebound does not prove": "A ranked candidate names the right semantic relationship",
    },
    {
        "surface": "Binding sensitivity receipt",
        "sourcebound proves": "One static check becomes stale after one independently frozen source fact changes",
        "sourcebound does not prove": "The document and source describe the same concept or that the relationship should be accepted",
    },
    {
        "surface": "Declared review contract",
        "sourcebound proves": "At two immutable refs, repository-declared source locators changed without every declared target locator changing",
        "sourcebound does not prove": "The target is stale, a co-change is semantically correct, or the locators describe the same concept",
    },
    {
        "surface": "Pull-request verdict",
        "sourcebound proves": "Static configured checks and changed-surface evidence produce the reported state at one pinned commit",
        "sourcebound does not prove": "Unbound prose, skipped processes, semantic relationships, or authored judgment are correct",
    },
    {
        "surface": "Packaged writing policy",
        "sourcebound proves": "Implemented deterministic rules pass",
        "sourcebound does not prove": "Motivation, pedagogy, personality, or usefulness pass judgment",
    },
    {
        "surface": "Authored purpose and scope",
        "sourcebound proves": "Declared markers and configured relationships remain intact",
        "sourcebound does not prove": "The repository chose the right goals, audience, or priority",
    },
    {
        "surface": "Opt-in feedback loop",
        "sourcebound proves": "Validated operational envelopes and improvement-state receipts satisfy their closed schemas",
        "sourcebound does not prove": "Observed behavior establishes causality, authorizes purpose, or makes a candidate change correct",
    },
)

SUPPORTED_BINDINGS = {
    "command-pin": {
        "binding": "command pin (`type: claim`)",
        "source": "Allowlisted JSON command",
        "output": "Configured assertion, with optional declared prose at a document anchor",
        "check": "Compare typed expected and observed values; verify declared anchored prose",
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
        "example": "sourcebound audit --format json",
    },
    {"command": "residue", "job": "Manage private cross-project residue matching", "writes": "with init-local", "example": "sourcebound residue status"},
    {"command": "residue status", "job": "Report whether private residue matching is active", "writes": "no", "example": "sourcebound residue status"},
    {"command": "residue init-local", "job": "Create a permission-restricted private residue template", "writes": "yes", "example": "sourcebound residue init-local"},
    {"command": "inventory", "job": "List detected repository surfaces and coverage", "writes": "no", "example": "sourcebound inventory --format json"},
    {"command": "claims", "job": "Rank and verify static count and column claims", "writes": "no", "example": "sourcebound claims --format json"},
    {"command": "binding", "job": "Inspect one proposed source relationship", "writes": "no", "example": "sourcebound binding --help"},
    {
        "command": "binding sensitivity",
        "job": "Test whether one static check depends on a frozen source fact",
        "writes": "no",
        "example": "sourcebound binding sensitivity --help",
    },
    {"command": "context", "job": "Compile provider-neutral evidence packets", "writes": "no", "example": "sourcebound context --help"},
    {"command": "context compile", "job": "Compile a bounded source-addressed context bundle", "writes": "no", "example": "sourcebound context compile --request context-request.json"},
    {"command": "review", "job": "Turn review observations into testable improvement candidates", "writes": "with --out", "example": "sourcebound review --help"},
    {"command": "review candidates", "job": "Compile documentation and product test candidates from one review", "writes": "with --out", "example": "sourcebound review candidates --input review-observations.json"},
    {"command": "review lifecycle", "job": "Track assessment-only candidate status with typed evidence", "writes": "with init or transition", "example": "sourcebound review lifecycle --help"},
    {"command": "review lifecycle init", "job": "Initialize a lifecycle record for one candidate set", "writes": "yes", "example": "sourcebound review lifecycle init --input review.json --out lifecycle.json"},
    {"command": "review lifecycle transition", "job": "Apply one evidence-backed candidate transition", "writes": "yes", "example": "sourcebound review lifecycle transition --help"},
    {"command": "review lifecycle check", "job": "Check a lifecycle record against its candidate set", "writes": "no", "example": "sourcebound review lifecycle check --input review.json --state lifecycle.json"},
    {"command": "init", "job": "Write a source-bound documentation baseline", "writes": "yes", "example": "sourcebound init --no-model"},
    {"command": "explain", "job": "Explain a finding or coverage state", "writes": "no", "example": "sourcebound explain purpose-contract --format json"},
    {"command": "doctor", "job": "Check repository and integration readiness", "writes": "with --bundle", "example": "sourcebound doctor --bundle doctor.json"},
    {"command": "verify", "job": "Write a local deterministic outcome receipt", "writes": "with --out", "example": "sourcebound verify --out outcome.json"},
    {"command": "benchmark", "job": "Measure changed-check time and memory budgets", "writes": "with --out", "example": "sourcebound benchmark --base HEAD~1 --head HEAD"},
    {"command": "derive", "job": "Preview or write generated region changes", "writes": "with --write", "example": "sourcebound derive --check"},
    {"command": "drive", "job": "Repair bound regions after deterministic policy checks", "writes": "yes", "example": "sourcebound drive"},
    {"command": "plan", "job": "Build an immutable read-only documentation impact plan", "writes": "no", "example": "sourcebound plan --base origin/main --head HEAD --format json"},
    {
        "command": "verdict",
        "job": "Compose one coverage-stating static PR verdict",
        "writes": "no",
        "example": "sourcebound verdict --base origin/main --head HEAD --format json",
    },
    {"command": "check", "job": "Fail on binding drift or uncovered changed surface", "writes": "no", "example": "sourcebound check --changed --base origin/main --head HEAD"},
    {"command": "project", "job": "Regenerate configured documentation projections", "writes": "unless --check", "example": "sourcebound project --check"},
    {"command": "eval", "job": "Score human tasks and replayable agent round trips", "writes": "with --history or live recording", "example": "sourcebound eval --fixtures .sourcebound/eval.yml"},
    {"command": "release", "job": "Render typed release facts between immutable refs", "writes": "no", "example": "sourcebound release --from v0.9.0 --to HEAD"},
    {"command": "migrate", "job": "Upgrade a prior manifest with rollback backup", "writes": "with --write or --rollback", "example": "sourcebound migrate --write"},
    {"command": "feedback", "job": "Manage opt-in operational feedback", "writes": "yes", "example": "sourcebound feedback status"},
    {"command": "feedback enable", "job": "Consent to a named feedback sink", "writes": "yes", "example": "sourcebound feedback enable --sink local"},
    {"command": "feedback status", "job": "Show feedback consent and pending counts", "writes": "no", "example": "sourcebound feedback status"},
    {"command": "feedback preview", "job": "Print exact pending envelope bytes", "writes": "no", "example": "sourcebound feedback preview"},
    {"command": "feedback flush", "job": "Deliver pending feedback envelopes", "writes": "yes", "example": "sourcebound feedback flush"},
    {"command": "feedback disable", "job": "Remove feedback delivery authority", "writes": "yes", "example": "sourcebound feedback disable"},
    {"command": "feedback rotate", "job": "Replace the feedback installation identifier", "writes": "yes", "example": "sourcebound feedback rotate"},
    {"command": "feedback purge", "job": "Delete local feedback state", "writes": "yes", "example": "sourcebound feedback purge"},
    {"command": "feedback signal", "job": "Validate or ingest aggregate behavior signals", "writes": "varies", "example": "sourcebound feedback signal validate --input signal.json"},
    {"command": "feedback signal prepare", "job": "Add a canonical content-derived signal ID", "writes": "no", "example": "sourcebound feedback signal prepare --input signal-body.json"},
    {"command": "feedback signal validate", "job": "Validate one aggregate behavior signal", "writes": "no", "example": "sourcebound feedback signal validate --input signal.json"},
    {"command": "feedback signal ingest", "job": "Create an observed improvement case", "writes": "yes", "example": "sourcebound feedback signal ingest --input signal.json"},
    {"command": "feedback case", "job": "Advance a verified improvement case", "writes": "yes", "example": "sourcebound feedback case transition --case ID --to reproduced --receipt receipt.json"},
    {"command": "feedback case transition", "job": "Apply one adjacent evidence-backed state transition", "writes": "yes", "example": "sourcebound feedback case transition --case ID --to reproduced --receipt receipt.json"},
    {"command": "emit", "job": "Project the manifest into another format", "writes": "yes", "example": "sourcebound emit --help"},
    {
        "command": "emit stepwise-skill",
        "job": "Write a manifest-derived stepwise skill package",
        "writes": "yes",
        "example": "sourcebound emit stepwise-skill --out skill",
    },
    {
        "command": "emit llms-txt",
        "job": "Write an index of source-bound documents",
        "writes": "yes",
        "example": "sourcebound emit llms-txt --out llms.txt",
    },
    {"command": "standard", "job": "Build or verify the bundled policy pack", "writes": "varies", "example": "sourcebound standard --help"},
    {"command": "standard build", "job": "Compile the canonical standard", "writes": "yes", "example": "sourcebound standard build"},
    {"command": "standard check", "job": "Fail when the policy pack is stale", "writes": "no", "example": "sourcebound standard check"},
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
