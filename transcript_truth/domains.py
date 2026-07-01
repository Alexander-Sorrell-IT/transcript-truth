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


def register_domain(name, scanners=(), description="", per_language=None):
    """A domain is TWO parts so it composes with ANY language:
      • `scanners`     = the language-NEUTRAL core (dosage numbers, timestamps, ISMP abbrevs, dash
                         format) — safe and useful for every language.
      • `per_language` = {lang: (extra scanners,)} — that language's SPECIFIC rules (English RxNorm
                         drug names, English CVL spelling/case, etc.). Added only for that language.
    So `compose(lang, domain)` = base + core + per_language.get(lang). Every language gets the
    universal core; a language gets the specialized layer once we've built its content."""
    DOMAIN_REGISTRY[name] = {"name": name, "scanners": tuple(scanners),
                             "per_language": {k: tuple(v) for k, v in (per_language or {}).items()},
                             "description": description}
    return DOMAIN_REGISTRY[name]


def domain_names():
    return sorted(DOMAIN_REGISTRY)


def domain_languages(domain_name: str) -> list:
    """Languages that have a dedicated per-language layer (beyond the universal core)."""
    dom = DOMAIN_REGISTRY.get(domain_name)
    return sorted(dom["per_language"]) if dom else []


def compose(profile_name: str, domain_name: str) -> Profile:
    """Return a Profile running the language profile's scanners PLUS the domain's universal core PLUS
    that language's per-language domain layer (if any). The domain composes with EVERY language via
    its core; the language-specific rules attach only where they belong — so a French transcript gets
    universal dosage/timestamp checks under `medical`/`legal`, but English CVL/RxNorm never misfire on it."""
    base = get_profile(profile_name)
    if domain_name in (None, "", "general"):
        return base
    if domain_name not in DOMAIN_REGISTRY:
        avail = ", ".join(domain_names()) or "(none)"
        raise KeyError(f"unknown domain {domain_name!r}; available: {avail}")
    dom = DOMAIN_REGISTRY[domain_name]
    extra = dom["per_language"].get(profile_name, ())        # language-specific layer (if built)
    combined, seen, scanners = tuple(base.scanners) + dom["scanners"] + tuple(extra), set(), []
    for s in combined:                                       # dedup: a base profile may already carry
        if s not in seen:                                    # a core scanner (e.g. timestamps) — don't
            seen.add(s); scanners.append(s)                  # run it twice (was double-counting)
    return Profile(
        name=f"{profile_name}+{domain_name}",
        description=f"{base.description}  +  {dom['description']}",
        scanners=tuple(scanners),
        modes=base.modes, default_mode=base.default_mode,
        fixers=getattr(base, "fixers", ()),   # keep the language profile's redline fixers (was dropped)
    )


# --- built-in domains ---
register_domain("general", (), "no domain-specific rules")

from .medical_rules import dangerous_abbreviations, dosage_hygiene, drug_name_check  # noqa: E402
register_domain(
    "medical",
    # universal core (every language): dosage-number hygiene (trailing-zero/naked-decimal) is
    # locale-safe number safety, useful in any language.
    scanners=(dosage_hygiene,),
    # English/US-medical layer: ISMP abbreviations are English/Latin letter-abbrevs (u, cc, MS…) that
    # collide with native words in other languages; RxNorm drug-name check uses an English frequency gate.
    per_language={"en": (dangerous_abbreviations, drug_name_check)},
    description="Medical — dosage hygiene (all languages) + ISMP abbrevs & RxNorm drug names (en)",
)

# Legal (TranscribeMe CVL) as a composable DOMAIN — the structural/formatting half of the guide
# that generalizes across languages (titles, numbers, a.m./p.m., bracketed tags, non-verbals,
# label spacing, timestamps). The English-SPECIFIC half (CVL spelling/slang/contractions/grammar)
# stays in the full `legal` PROFILE; per-language legal style data is the "more resources" path.
from .legal_rules import (legal_titles, legal_numbers, legal_ampm, legal_tags,  # noqa: E402
                          legal_nonverbal, legal_spacing)
from .scanners import timestamps as _timestamps  # noqa: E402
from .legal_terms import legal_terms  # noqa: E402
from .tm_legal import tm_sound_tags, tm_lowercase_terms, tm_speaker_caps, tm_double_dash, tm_spoken_punct  # noqa: E402
register_domain(
    "legal",
    # universal core (every language): timestamp format is the one language-neutral legal convention.
    scanners=(_timestamps,),
    # English layer: American-English CVL — case (Colloquy caps), spelling, titles, accents, English
    # tag words/number words, Latin terms, and the double-dash-attach convention — all English CVL.
    per_language={"en": (tm_double_dash, legal_titles, legal_numbers, legal_ampm, legal_tags,
                         legal_nonverbal, legal_spacing, legal_terms, tm_sound_tags,
                         tm_lowercase_terms, tm_speaker_caps, tm_spoken_punct)},
    description="Legal — timestamp core (all languages) + TranscribeMe CVL (en)",
)
