"""SHIP GATE — the mechanical stop between a draft and a submission (pure, no model).

Born from T4791286: an unverified draft carrying ⚠ ear-flags, ?speaker labels and a
"# … DRAFT (verify by ear …)" header went to GoTranscript anyway — 1/5 "way too many
mishears", Japanese channel lost. Every uncertainty marker was VISIBLE on the page, but
nothing mechanically refused to ship them. This module is that refusal. Law: nothing
ships until zero flags — ship_check() returns ok=False with a line-addressed blocker
list while ANY marker is unresolved, and the ./check wrapper turns ok=False into exit 3
with no grade printed (a grade on an unshippable file reads as permission, which is
exactly what got misread).

Draft conventions this gate understands (see T4791286_draft.md):
  ⚠            engine-uncertain span — must be judged by ear        -> unverified_span
  **?Name:** / ?Name:   unconfirmed speaker label (line start ONLY) -> unconfirmed_speaker
  "# … DRAFT/verify …"  leftover editorial header                   -> draft_header

Ear ledger (<file>.ear.json — written by the human DURING the listen-through, the proof
the ear pass actually happened): maps line number -> decision. Accepted shapes:
    {"24": "k", "30": "e", "56": "u"}                       (terse dict)
    [{"line": 24, "decision": "k", "note": "..."}, ...]     (list of entries)
    {"resolved": [{"line_no": 24, "decision": "keep"}, ...], "total_flagged": N}
                                            (what ./earcheck actually writes)
Decisions: k = kept as written (heard it, draft is right), e = edited after listening,
u = listened but still unresolved. k/e clear that line's ⚠ blocker; u is itself a
blocker (unresolved_ear) — an honest "couldn't tell" must still stop the ship.
?speaker labels are NOT ear-clearable: confirming a speaker means editing the label.
"""
import json
import os
import re

# The draft's speaker-uncertainty convention: "**?Bose:**" (bold GT-editor label) or the
# plain "?Bose:" form. Anchored to the label position at line start because Japanese text
# is FULL of question marks (いかがでしょう？ / ですか?) — a "?" anywhere else must NEVER
# block. ASCII "?" only (the marker the draft convention uses; sentence punctuation in JA
# is typically full-width ？ anyway), name capped at 40 chars and barred from ":"/"*" so a
# question-opening sentence with a stray colon downstream can't masquerade as a label.
_Q_SPEAKER = re.compile(r"^(?:\*\*\?[^:*\n]{1,40}:\*\*|\?[^:*\n]{1,40}:)")


def _norm_ear(ear):
    """Normalize either accepted ear-ledger shape to {line:int -> decision-initial:str}.
    Entries that can't be read (non-numeric line, missing decision) are DROPPED, not
    guessed — an unreadable entry can never count as proof that a line was ear-verified."""
    out = {}
    if not ear:
        return out
    if isinstance(ear, dict) and isinstance(ear.get("resolved"), list):
        ear = ear["resolved"]                   # ./earcheck's wrapper — the ledger is inside
    items = (ear.items() if isinstance(ear, dict)
             else ((e.get("line", e.get("line_no")) if isinstance(e, dict) else None, e)
                   for e in ear))
    for ln, v in items:
        if isinstance(v, dict):
            v = v.get("decision", "")
        try:
            ln = int(ln)
        except (TypeError, ValueError):
            continue
        d = str(v).strip().lower()[:1]          # "k"/"kept", "e"/"edited", "u"/"unresolved"
        if d:
            out[ln] = d
    return out


def _ev(s, limit=70):
    s = s.strip()
    return s if len(s) <= limit else s[:limit - 1] + "…"


def ship_check(text, ear_resolutions=None):
    """-> {"ok": bool, "blockers": [{"line", "kind", "evidence"}]}. Deterministic; the
    ONLY way to ok=True is a text with zero markers and a ledger with zero "u" entries.
    Blockers are line-sorted so the refusal print reads top-to-bottom like the file."""
    ear = _norm_ear(ear_resolutions)
    lines = text.split("\n")
    blockers = []
    for n, raw in enumerate(lines, 1):
        s = raw.lstrip()                        # an accidentally indented marker still blocks
        if s.startswith("# ") and ("DRAFT" in s.upper() or "VERIFY" in s.upper()):
            blockers.append({"line": n, "kind": "draft_header", "evidence": _ev(s)})
        m = _Q_SPEAKER.match(s)
        if m:
            blockers.append({"line": n, "kind": "unconfirmed_speaker", "evidence": m.group(0)})
        if "⚠" in raw and ear.get(n) not in ("k", "e"):
            # evidence = from the ⚠ onward — that's where the draft puts its judge-by-ear note
            blockers.append({"line": n, "kind": "unverified_span",
                             "evidence": _ev(raw[raw.index("⚠"):])})
    for ln in sorted(ear):
        if ear[ln] == "u":
            ev = lines[ln - 1] if 1 <= ln <= len(lines) else "(entry beyond end of file)"
            blockers.append({"line": ln, "kind": "unresolved_ear", "evidence": _ev(ev)})
    blockers.sort(key=lambda b: b["line"])      # stable: within-line order preserved
    return {"ok": not blockers, "blockers": blockers}


def load_ear(path):
    """CLI-path sidecar loader: the ear ledger for transcript X lives at X.ear.json (or,
    thoth-style, X-with-ext-swapped .ear.json — both spellings occur in the wild, first
    hit wins). Missing -> None (no ear pass claimed). Unreadable JSON -> None too: a
    corrupt ledger must never silently unlock the gate — the ⚠ blockers simply stand."""
    base, _ext = os.path.splitext(path)
    for p in (path + ".ear.json", base + ".ear.json"):
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, ValueError):
                return None
    return None


def ship_check_file(path):
    """The whole CLI path in one call: read the transcript, auto-load its ear sidecar
    when present, gate. This is what ./check --ship runs FIRST, before any QA/grade."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return ship_check(text, load_ear(path))
