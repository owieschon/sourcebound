"""Public capability registry rendered into the clean-docs README."""

PRODUCT_OVERVIEW = (
    "Version 0.2 alpha statically inventories package, CLI, API, schema, test, and documentation "
    "surfaces. It audits documentation without configuration and verifies region, claim, and "
    "symbol bindings from static Python, structured data, text files, path globs, and "
    "allowlisted JSON commands. It emits manifest-derived stepwise skill packages and llms.txt "
    "indexes, and it never imports repository code. `derive` previews changes "
    "unless you pass `--write`; `audit` and `check` never write."
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
    {"command": "audit", "job": "Inventory and check repository documentation", "writes": "no"},
    {"command": "inventory", "job": "List detected repository surfaces and coverage", "writes": "no"},
    {"command": "doctor", "job": "Check repository and integration readiness", "writes": "no"},
    {"command": "derive", "job": "Preview generated region changes", "writes": "with --write"},
    {"command": "drive", "job": "Repair bound regions and enforce policy", "writes": "yes"},
    {"command": "check", "job": "Fail when a binding has drifted", "writes": "no"},
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
