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

DOMAIN_REGISTRY = {}   # FIELD plugins (what SUBJECT is this): legal, medical …
SITE_REGISTRY = {}     # SITE/format plugins (what OUTPUT FORMAT / platform): transcribeme …


def _register(registry, name, scanners=(), description="", per_language=None, per_language_fixers=None):
    """Register a composable LAYER (field or site). A layer is THREE parts so it composes with ANY
    language:
      • `scanners`     = the language-NEUTRAL core — safe/useful for every language.
      • `per_language` = {lang: (extra scanners,)} — that language's SPECIFIC rules. Added only there.
      • `per_language_fixers` = {lang: (extra Redline autofixers,)} — that language's deterministic
                         auto-fixes, so a composed plug autofixes exactly like a standalone profile.
    `compose(lang, field, site)` merges base + each layer's core + per_language.get(lang)."""
    registry[name] = {"name": name, "scanners": tuple(scanners),
                      "per_language": {k: tuple(v) for k, v in (per_language or {}).items()},
                      "per_language_fixers": {k: tuple(v) for k, v in (per_language_fixers or {}).items()},
                      "description": description}
    return registry[name]


def register_domain(name, scanners=(), description="", per_language=None, per_language_fixers=None):
    """Register a FIELD plugin (subject: legal, medical). Composes on the DOMAIN axis."""
    return _register(DOMAIN_REGISTRY, name, scanners, description, per_language, per_language_fixers)


def register_site(name, scanners=(), description="", per_language=None, per_language_fixers=None):
    """Register a SITE/format plugin (per-website output format: transcribeme, rev, …). Same layer
    shape as a domain — it just composes on the SITE axis: language × field × site."""
    return _register(SITE_REGISTRY, name, scanners, description, per_language, per_language_fixers)


def domain_names():
    return sorted(DOMAIN_REGISTRY)


def site_names():
    return sorted(SITE_REGISTRY)


def domain_languages(domain_name: str) -> list:
    """Languages that have a dedicated per-language layer (beyond the universal core)."""
    dom = DOMAIN_REGISTRY.get(domain_name)
    return sorted(dom["per_language"]) if dom else []


# --- Part 1: multi-language auto-extend — coverage map + scaffolder ---
# Meta/style profiles that are NOT reusable language plugs. (Japanese currently rides `default`.)
_NON_LANGUAGE_PROFILES = {"default", "legal", "ccsl", "me", "agent"}


def language_profiles() -> list:
    """The registered LANGUAGE plugs (excludes meta/style profiles and `:full` variants)."""
    from .profiles import names as _names
    return [n for n in _names() if ":" not in n and n not in _NON_LANGUAGE_PROFILES]


def coverage_report() -> list:
    """For every language × layer (FIELD + SITE): 'full' (has a per-language layer) or 'core'
    (universal core only). The LIVING cross-language scan — a NEW language auto-appears ('core' for
    free, 'full' once its layer is written). Covers both the field axis (legal/medical) and the site
    axis (transcribeme/…). Each row: {language, layer, kind: field|site, coverage}."""
    rows = []
    for lang in language_profiles():
        for kind, reg in (("field", DOMAIN_REGISTRY), ("site", SITE_REGISTRY)):
            for nm in sorted(reg):
                if nm == "general":
                    continue
                has = lang in reg[nm]["per_language"]
                rows.append({"language": lang, "layer": nm, "kind": kind,
                             "coverage": "full" if has else "core"})
    return rows


_STUB_TEMPLATE = '''"""{domain} domain — {lang} per-language layer (SCAFFOLD — fill me in).

Clone the English layer's intent, adapted to {lang}'s conventions. DO NOT copy English rules blindly:
some (e.g. accent-stripping) would CORRUPT correct {lang} text. Every flag = a deterministic rule hit
cited at its line, with a fix. No model in the verdict path.
"""
from __future__ import annotations
import re  # noqa: F401
from .types import Flag, Transcript  # noqa: F401


def {domain}_{lang}_example(t: Transcript) -> list:
    """TODO: replace with real {lang} {domain} rules."""
    return []


{LANG}_{DOMAIN}_SCANNERS = ({domain}_{lang}_example,)
'''


def scaffold_domain_layer(lang: str, domain: str, write: bool = True) -> dict:
    """Create a stub per-language layer file for (lang, domain) from the template, so filling a new
    language is fill-in-the-blank. Returns the path + the exact snippet to register it. SAFE: never
    edits domains.py itself, never overwrites an existing file."""
    import os
    if domain not in DOMAIN_REGISTRY or domain == "general":
        raise KeyError(f"unknown domain {domain!r}; available: {', '.join(domain_names())}")
    root = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(root, f"{domain}_{lang}_rules.py")
    created = False
    if write and not os.path.exists(path):
        body = _STUB_TEMPLATE.format(lang=lang, domain=domain, LANG=lang.upper(), DOMAIN=domain.upper())
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        created = True
    snippet = (f'from .{domain}_{lang}_rules import {lang.upper()}_{domain.upper()}_SCANNERS\n'
               f'DOMAIN_REGISTRY[{domain!r}]["per_language"][{lang!r}] = '
               f'{lang.upper()}_{domain.upper()}_SCANNERS')
    return {"path": path, "created": created, "register_snippet": snippet}


def autodiscover_domain_layers() -> list:
    """Auto-wire per-language FIELD or SITE layers BY CONVENTION, so a downloaded pack self-installs.
    A file `{layer}_{lang}_rules.py` exporting `{LANG}_{LAYER}_SCANNERS` (and optionally
    `{LANG}_{LAYER}_FIXERS`), where {layer} is a registered field (legal/medical) OR site
    (transcribeme/…), is picked up automatically — no editing this file. This is the 'download a new
    language/site → its legal/medical/format layers set themselves up' mechanism. Returns [(layer, lang)].
    Safe: the pattern needs TWO underscores (layer_lang_rules), so existing single-underscore files
    (legal_rules.py, medical_rules.py, es_rules.py…) never false-match; a bad module is skipped."""
    import os, importlib, re as _re
    root = os.path.dirname(os.path.abspath(__file__))
    pat = _re.compile(r"^([a-z]+)_([a-z]{2,3})_rules\.py$")
    found = []
    for fn in sorted(os.listdir(root)):
        m = pat.match(fn)
        if not m:
            continue
        layer, lang = m.group(1), m.group(2)
        reg = (DOMAIN_REGISTRY if layer in DOMAIN_REGISTRY else
               SITE_REGISTRY if layer in SITE_REGISTRY else None)
        if reg is None or layer == "general":
            continue
        try:
            mod = importlib.import_module(f".{layer}_{lang}_rules", __package__)
        except Exception:
            continue
        scanners = getattr(mod, f"{lang.upper()}_{layer.upper()}_SCANNERS", None)
        if not scanners:
            continue
        reg[layer]["per_language"][lang] = tuple(scanners)
        fixers = getattr(mod, f"{lang.upper()}_{layer.upper()}_FIXERS", None)
        if fixers:
            reg[layer]["per_language_fixers"][lang] = tuple(fixers)
        found.append((layer, lang))
    return found


def compose(profile_name: str, domain_name: str = None, site_name: str = None) -> Profile:
    """Compose a LANGUAGE plug with an optional FIELD (domain) and optional SITE (format) layer:
    `language × field × site`. Each layer contributes its universal core + that language's
    per-language scanners/fixers; everything is deduped. A layer composes with EVERY language via its
    core; per-language rules attach only where built. Back-compatible: `compose(lang, domain)` still works.

        compose("en", "legal", "transcribeme")  # English + legal field + TranscribeMe format = full CVL
        compose("en", "medical")                # English + medical, format-agnostic
        compose("es", None, "transcribeme")     # Spanish, TranscribeMe format, no field
    """
    base = get_profile(profile_name)
    layers = []
    for reg, nm, kind in ((DOMAIN_REGISTRY, domain_name, "domain"), (SITE_REGISTRY, site_name, "site")):
        if nm in (None, "", "general"):
            continue
        if nm not in reg:
            avail = ", ".join(sorted(reg)) or "(none)"
            raise KeyError(f"unknown {kind} {nm!r}; available: {avail}")
        layers.append(reg[nm])
    if not layers:
        return base
    seen, scanners = set(), []
    for s in base.scanners:                                  # base language scanners first
        if s not in seen:
            seen.add(s); scanners.append(s)
    fixers = list(getattr(base, "fixers", ()))
    descr = [base.description]
    for lay in layers:                                       # then each layer's core + per-language
        for s in tuple(lay["scanners"]) + lay["per_language"].get(profile_name, ()):
            if s not in seen:                                # dedup: never run a shared scanner twice
                seen.add(s); scanners.append(s)
        for fx in lay["per_language_fixers"].get(profile_name, ()):
            if fx not in fixers:                             # dedup fixers; keep the Redline path in the plug
                fixers.append(fx)
        descr.append(lay["description"])
    tag = "+".join([profile_name] + [lay["name"] for lay in layers])
    return Profile(name=tag, description="  +  ".join(descr),
                   scanners=tuple(scanners), modes=base.modes,
                   default_mode=base.default_mode, fixers=tuple(fixers))


# --- built-in domains ---
register_domain("general", (), "no domain-specific rules")

from .medical_rules import dangerous_abbreviations, dosage_hygiene, drug_name_check  # noqa: E402
from .umls import umls_term_check  # noqa: E402
register_domain(
    "medical",
    # UNIVERSAL core (every language): dosage-number hygiene (locale-safe) + UMLS terminology.
    # umls_term_check is multilingual — UMLS resolves native terms in every language it covers, and
    # the check verifies in the transcript's OWN language (reusing that language plugin). Built ONCE,
    # works across languages — no per-language medical build. Graceful: no key/offline → no-ops.
    scanners=(dosage_hygiene, umls_term_check),
    # English/US-medical layer: ISMP abbreviations (u, cc, MS…) are the US list, and the RxNorm
    # drug-name check uses English drug data — genuinely US/English-specific, so English-only.
    per_language={"en": (dangerous_abbreviations, drug_name_check)},
    description="Medical — dosage + multilingual UMLS terminology (all languages) + ISMP & RxNorm (en)",
)

# Legal as a composable FIELD (subject). Now SITE-NEUTRAL: the TranscribeMe-specific FORMAT (the tm_*
# rules) was split out into the `transcribeme` SITE below, so `legal` holds legal-transcription content
# (Latin terms + CVL spelling/slang/grammar/titles/numbers/…) that a court transcript needs anywhere,
# and the site supplies the platform's output format. `compose("en","legal","transcribeme")` == the
# old full CVL (== the standalone `legal` profile). Other languages get the timestamp core today.
from .legal_rules import LEGAL_SCANNERS, LEGAL_FIXERS  # noqa: E402 — CVL scanners + Redline autofixers
from .scanners import timestamps as _timestamps  # noqa: E402
from .legal_terms import legal_terms  # noqa: E402
from .tm_legal import tm_sound_tags, tm_lowercase_terms, tm_speaker_caps, tm_double_dash, tm_spoken_punct  # noqa: E402
register_domain(
    "legal",
    scanners=(_timestamps,),                    # universal core: timestamp format
    per_language={"en": (*LEGAL_SCANNERS, legal_terms)},
    per_language_fixers={"en": LEGAL_FIXERS},   # the CVL Redline autofix set travels with the plug
    description="Legal — timestamp core (all languages) + American-English CVL content (en)",
)

# --- SITE axis: per-website OUTPUT FORMAT plugins (language × field × SITE) ---
# TranscribeMe's format (the tm_* rules: speaker caps, sound tags, dash-attach, spoken punctuation)
# was split OUT of the legal field so it can pair with ANY field, and so `legal` is site-neutral.
# `compose("en","legal","transcribeme")` reassembles the full TranscribeMe CVL.
register_site(
    "transcribeme",
    scanners=(),                                # (timestamp format could move here later; tm_* are en today)
    per_language={"en": (tm_double_dash, tm_sound_tags, tm_lowercase_terms, tm_speaker_caps, tm_spoken_punct)},
    description="TranscribeMe output format (speaker caps, sound tags, dash-attach, spoken punctuation)",
)

# GoTranscript's English rules (en_format + the model-gated en_rules corrections) have always
# ridden the default profile implicitly; registering the site makes the axis explicit so
# compose("en", None, "gotranscript") works like every other vendor.
from .en_format import en_format as _gt_en_format

register_site(
    "gotranscript",
    scanners=(),
    per_language={"en": (_gt_en_format,)},
    description="GoTranscript output format (Okay caps, yes-not-yeah, number style, bracket tags)",
)

# Vendor site plugins self-register on import (rev, scribie; dt registers via dt_rules).
from . import rev_rules as _rev      # noqa: F401
from . import scribie_rules as _scr  # noqa: F401
from . import quicktate_rules as _qt  # noqa: F401
from . import dt_rules as _dt        # noqa: F401

# Auto-wire any per-language field/site layers present by convention (download a language/site pack →
# its layers self-install). Runs AFTER the built-in field + site plugins are registered.
autodiscover_domain_layers()
