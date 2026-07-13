"""Public capability registry rendered into the clean-docs README."""

SUPPORTED_BINDINGS = {
    "claim": {
        "binding": "claim",
        "source": "Allowlisted JSON command",
        "output": "Assertion at a document anchor",
        "check": "Compare typed expected and observed values",
    },
    "region": {
        "binding": "region",
        "source": "Static Python assignment or JSON Pointer",
        "output": "Markdown table",
        "check": "Re-render and compare",
    },
    "symbol": {
        "binding": "symbol",
        "source": "Static path or Python symbol",
        "output": "Reference at a document anchor",
        "check": "Resolve the cited locator",
    },
}
