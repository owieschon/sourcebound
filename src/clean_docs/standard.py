from __future__ import annotations

import hashlib
import json
import re
from importlib import resources
from pathlib import Path
from typing import Any

from clean_docs.errors import ConfigurationError

PACK_VERSION = 1
DEFAULT_PROFILE = "clean-docs-default"
HEADING_RE = re.compile(r"^(#{2,4})\s+(.+?)\s*$")
CHECK_RE = re.compile(r"^- \[ \]\s+(.+)$")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pack_digest(pack: dict[str, Any]) -> str:
    content = {key: value for key, value in pack.items() if key != "pack_sha256"}
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _digest(canonical)


def _exemplar_asset(standard: Path) -> tuple[str, str]:
    local = standard.parent / "src/clean_docs/standards/exemplars.md"
    if local.exists():
        text = local.read_text(encoding="utf-8")
    else:
        resource = resources.files("clean_docs").joinpath("standards/exemplars.md")
        with resources.as_file(resource) as path:
            text = path.read_text(encoding="utf-8")
    return text, _digest(text)


def _headings(lines: list[str]) -> list[dict[str, Any]]:
    result = []
    for line_number, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if match:
            result.append({
                "level": len(match.group(1)),
                "title": match.group(2),
                "line": line_number,
            })
    return result


def _checklist(lines: list[str]) -> list[str]:
    start = next(
        (index for index, line in enumerate(lines) if line.startswith("## 8. Pre-publish checklist")),
        None,
    )
    if start is None:
        raise ConfigurationError("standard is missing the pre-publish checklist")
    checks: list[str] = []
    current: list[str] = []
    for line in lines[start + 1:]:
        match = CHECK_RE.match(line)
        if match:
            if current:
                checks.append(" ".join(current))
            current = [match.group(1).strip()]
        elif current and line.startswith("      "):
            current.append(line.strip())
        elif current and not line.strip():
            checks.append(" ".join(current))
            current = []
    if current:
        checks.append(" ".join(current))
    if not checks:
        raise ConfigurationError("standard pre-publish checklist is empty")
    return checks


def _mechanical_policy(text: str, checks: list[str]) -> dict[str, Any]:
    length = re.search(
        r"README pages over (?P<readme>\d+) lines and guides over (?P<guide>\d+) lines",
        text,
    )
    section = re.search(r"A section over (?P<section>\d+) lines", text)
    preamble = re.search(r"first (?P<preamble>\d+) lines", text)
    nominalizations = re.search(
        r"sentence with (?P<nominalizations>\w+) or more abstraction-suffix", text
    )
    qualifiers = re.search(r"gets at most (?P<qualifiers>\w+) `may`", text)
    if not all((length, section, preamble, nominalizations, qualifiers)):
        raise ConfigurationError(
            "standard is missing page budgets, preamble window, or register thresholds"
        )
    number_words = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
    }
    assert length is not None
    assert section is not None
    assert preamble is not None
    assert nominalizations is not None
    assert qualifiers is not None
    booster_check = next((check for check in checks if "booster adjectives" in check), None)
    if booster_check is None:
        raise ConfigurationError("standard is missing the booster-adjective check")
    boosters = re.findall(r"`([^`]+)`", booster_check)
    if len(boosters) < 3:
        raise ConfigurationError("standard booster-adjective check has no usable registry")
    return {
        "readme_max_lines": int(length.group("readme")),
        "guide_max_lines": int(length.group("guide")),
        "section_max_lines": int(section.group("section")),
        "preamble_window_lines": int(preamble.group("preamble")),
        "nominalization_threshold": number_words[nominalizations.group("nominalizations")],
        "nominalization_allowlist": [
            "documentation",
            "application",
            "section",
            "configuration",
        ],
        "sentence_variance_min_words": 15,
        "sentence_variance_max_words": 35,
        "qualifier_threshold": number_words[qualifiers.group("qualifiers")],
        "significance_phrases": [
            "exactly the",
            "the very",
            "this demonstrates",
            "deliberately",
            "is itself",
            "which is precisely",
        ],
        "prohibited_boosters": boosters,
        "require_grounded_facts": any("factual claim" in check for check in checks),
        "require_definition_first": any("first screen defines" in check for check in checks),
        "require_one_job": any("one job" in check for check in checks),
        "require_purpose_contract": any("BLUF purpose contract" in check for check in checks),
        "require_preamble_contract": any(
            "first 15 lines contain the purpose" in check for check in checks
        ),
        "require_readme_routes": any("README routes decisions" in check for check in checks),
        "require_depth_links": any(
            "explanatory section over 80 words" in check for check in checks
        ),
    }


def _style_contract(text: str, checks: list[str]) -> dict[str, Any]:
    normalized = " ".join(text.split())
    required_phrases = {
        "second_person": "Second person + imperative",
        "system_actor": "Name the system as an actor",
        "informative_clauses": "Every clause adds information",
        "concrete_verbs": "Plain, concrete verbs",
        "direct_facts": "State facts without hedging",
        "senior_colleague": "helpful senior colleague",
        "bounded_personality": "Personality has a budget",
        "bluf": "BLUF purpose contract",
    }
    missing = [name for name, phrase in required_phrases.items() if phrase not in normalized]
    if missing:
        raise ConfigurationError(
            "standard is missing required style trait(s): " + ", ".join(missing)
        )
    if not any("BLUF purpose contract" in check for check in checks):
        raise ConfigurationError("standard checklist is missing the BLUF purpose contract")
    if not any("subject-derived memorable element" in check for check in checks):
        raise ConfigurationError("standard checklist is missing bounded personality review")
    return {
        "precedence": [
            "truth and honesty",
            "grounding",
            "reader budget",
            "register",
            "warmth",
        ],
        "voice": {
            "register": "helpful senior colleague",
            "reader_actions": "second person and imperative",
            "system_behavior": "name the system as an actor and state behavior as fact",
            "sentence_shape": "split claims that need separate evidence or differ in scope",
            "verbs": "plain and concrete",
            "certainty": "direct facts; mark genuine uncertainty explicitly",
            "contractions": "allowed",
        },
        "purpose_contract": {
            "begin_marker": "<!-- clean-docs:purpose -->",
            "end_marker": "<!-- clean-docs:end purpose -->",
            "position": "first meaningful block after the H1",
            "mechanical": [
                "exactly one marked purpose block",
                "purpose block precedes body content",
                "purpose prose does not restate the H1",
            ],
            "judgment": [
                "defines the project-specific subject and intended operator",
                "names the consequential failure or decision the page addresses",
                "states the authority boundary and a falsifiable resulting capability",
                "uses authored language grounded in the implementation and cited sources",
            ],
        },
    }


def compile_standard(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"cannot read standard {path}: {exc}") from exc
    lines = text.splitlines()
    headings = _headings(lines)
    titles = [heading["title"] for heading in headings]
    required = {
        "voice": "2. Voice at the sentence level",
        "document": "3. How to explain something technical simply (the actual techniques)",
        "corpus": "6. Beyond the single doc: does it earn its existence?",
        "grounding": "7. Grounding: the doc must be true to the code (and stay true)",
    }
    missing = [title for title in required.values() if title not in titles]
    if missing:
        raise ConfigurationError(f"standard is missing required tier heading(s): {', '.join(missing)}")
    checks = _checklist(lines)
    style = _style_contract(text, checks)
    exemplars, exemplar_sha256 = _exemplar_asset(path)
    pack: dict[str, Any] = {
        "pack_version": PACK_VERSION,
        "profile": DEFAULT_PROFILE,
        "source": {
            "name": path.name,
            "sha256": _digest(text),
        },
        "tiers": required,
        "headings": headings,
        "checklist": checks,
        "policy": _mechanical_policy(text, checks),
        "style": style,
        "generation": {
            "instructions": text,
            "constraint": "Phrase only the supplied evidence and preserve its scope.",
            "voice": style["voice"],
            "purpose_contract": style["purpose_contract"],
            "precedence": style["precedence"],
            "exemplars": exemplars,
            "exemplars_sha256": exemplar_sha256,
        },
    }
    pack["pack_sha256"] = _pack_digest(pack)
    return pack


def write_pack(pack: dict[str, Any], path: Path) -> None:
    from clean_docs.regions import atomic_write

    atomic_write(path, json.dumps(pack, indent=2, ensure_ascii=False) + "\n")


def load_pack(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(f"cannot read policy pack {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"invalid policy pack {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("pack_version") != PACK_VERSION:
        raise ConfigurationError(f"unsupported policy pack: {path}")
    if raw.get("pack_sha256") != _pack_digest(raw):
        raise ConfigurationError(f"policy pack integrity check failed: {path}")
    return raw


def load_default_pack() -> dict[str, Any]:
    resource = resources.files("clean_docs").joinpath("standards/default.json")
    with resources.as_file(resource) as path:
        return load_pack(path)


def pack_matches_standard(standard: Path, pack_path: Path) -> bool:
    return compile_standard(standard) == load_pack(pack_path)
