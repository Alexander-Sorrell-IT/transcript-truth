"""Domain axis — orthogonal to language. A domain (medical, legal, …) is a set of
LANGUAGE-AGNOSTIC scanners that COMPOSE with any language profile: a transcript is audited with
`language × domain` = both scanner sets combined. This separates "what field is this" from
"what language is this" so any domain works with any language.

    audit_transcript(text, profile="en", domain="medical")  # English + medical
    audit_transcript(text, profile="fr", domain="medical")  # French + medical (same domain rules)

Domains self-register here; `compose(lang_profile, domain)` returns a merged Profile.
"""
from __future__ import annotations
from .profiles._base import Profile, get as get_profile

DOMAIN_REGISTRY = {}


def register_domain(name, scanners, description=""):
    DOMAIN_REGISTRY[name] = {"name": name, "scanners": tuple(scanners), "description": description}
    return DOMAIN_REGISTRY[name]


def domain_names():
    return sorted(DOMAIN_REGISTRY)


def compose(profile_name: str, domain_name: str) -> Profile:
    """Return a Profile that runs the language profile's scanners PLUS the domain's scanners."""
    base = get_profile(profile_name)
    if domain_name in (None, "", "general"):
        return base
    if domain_name not in DOMAIN_REGISTRY:
        avail = ", ".join(domain_names()) or "(none)"
        raise KeyError(f"unknown domain {domain_name!r}; available: {avail}")
    dom = DOMAIN_REGISTRY[domain_name]
    return Profile(
        name=f"{profile_name}+{domain_name}",
        description=f"{base.description}  +  {dom['description']}",
        scanners=tuple(base.scanners) + dom["scanners"],
        modes=base.modes, default_mode=base.default_mode,
    )


# --- built-in domains ---
register_domain("general", (), "no domain-specific rules")

from .medical_rules import dangerous_abbreviations, dosage_hygiene, drug_name_check  # noqa: E402
register_domain(
    "medical", (dangerous_abbreviations, dosage_hygiene, drug_name_check),
    "Medical — ISMP dangerous-abbreviation + dosage hygiene + RxNorm drug-name check (language-agnostic)",
)

# Legal (TranscribeMe CVL) as a composable DOMAIN — the structural/formatting half of the guide
# that generalizes across languages (titles, numbers, a.m./p.m., bracketed tags, non-verbals,
# label spacing, timestamps). The English-SPECIFIC half (CVL spelling/slang/contractions/grammar)
# stays in the full `legal` PROFILE; per-language legal style data is the "more resources" path.
from .legal_rules import (legal_titles, legal_numbers, legal_ampm, legal_tags,  # noqa: E402
                          legal_nonverbal, legal_spacing)
from .scanners import timestamps as _timestamps  # noqa: E402
from .legal_terms import legal_terms  # noqa: E402
from .tm_legal import tm_sound_tags, tm_lowercase_terms, tm_speaker_caps, tm_double_dash  # noqa: E402
register_domain(
    "legal", (_timestamps, legal_titles, legal_numbers, legal_ampm, legal_tags,
              legal_nonverbal, legal_spacing, legal_terms, tm_sound_tags, tm_lowercase_terms,
              tm_speaker_caps, tm_double_dash),
    "Legal (TranscribeMe CVL) — formatting + terminology + TranscribeMe rules (sound-tags, Bates, Colloquy caps, dashes)",
)
