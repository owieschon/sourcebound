from __future__ import annotations

from clean_docs.write_gate import SECRET_RULES, redact_secrets


def _secret_pattern(rule_id: str):
    return next(pattern for name, pattern, _ in SECRET_RULES if name == rule_id)


def test_secret_rules_keep_minimum_lengths_and_word_boundary() -> None:
    openai = _secret_pattern("secret-openai-key")
    github = _secret_pattern("secret-github-token")

    assert openai.search("sk-" + "A" * 19) is None
    assert openai.search("prefixsk-" + "A" * 20) is None
    assert github.search("ghp_" + "A" * 19) is None


def test_redact_secrets_removes_raw_values_and_keeps_fail_closed_overmatch() -> None:
    openai_secret = "sk-" + "A" * 20
    github_secret = "ghp_" + "B" * 20
    long_kebab_slug = "sk-long-kebab-slug-with-many-characters"

    redacted, rules = redact_secrets(
        f"openai={openai_secret} github={github_secret} slug={long_kebab_slug}"
    )

    assert rules == (
        "secret-github-token",
        "secret-openai-key",
    )
    assert openai_secret not in redacted
    assert github_secret not in redacted
    # The broad sk- pattern intentionally over-redacts this non-secret slug.
    assert long_kebab_slug not in redacted
    assert redacted.count("[REDACTED]") == 3
