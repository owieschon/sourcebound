"""Public capability registry rendered into the clean-docs README."""

PRODUCT_OVERVIEW = (
    "The current alpha audits documentation without configuration and verifies region, claim, "
    "and symbol bindings from static Python, structured data, text files, path globs, and "
    "allowlisted JSON commands. It never imports repository code. `derive` previews changes "
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
