"""TranscribeMe — Clean Verbatim for Legal (CVL), English.

Deterministic scanners encoding the rules of the "CV for Legal Style Guide"
(TranscribeMe, updated 9-June-2025). No model, no network — every flag is a
regex/rule hit cited at its line, with a guideline-grounded fix and a page
reference. This is the *mechanical* half of the CVL guide; the semantic half
(is this the right word? does the comma reflect the real sentence boundary?)
is the human listener's job, exactly as in the rest of the engine.

CONFLICT NOTE — why this is a separate profile, not the default scanners:
CVL Legal disagrees with the GoTranscript English rules already in the engine.
  • GoTranscript wants "Okay" (capital). CVL wants "okay" (lowercase, p.5).
  • GoTranscript rewrites yeah -> yes. CVL keeps "yes or yeah" both (p.9).
  • GoTranscript drops "you know"/"I mean" as fillers. CVL KEEPS crutch words
    and only omits the hesitations uh/ah/um/er (p.10).
  • The default [inaudible] scanner REQUIRES a timestamp; CVL [inaudible] has
    none (p.13).
Running the wrong profile would flag correct CVL text, so they live apart.

USAGE BOUNDARY (from the Legal Prequalification Exam instructions): the exam is
no-AI and must be taken solo — using an AI to produce or check your *exam*
answers is grounds for a permanent block. The permitted, intended use of this
tool is to STUDY the guide and to check your OWN practice transcripts. The SG,
research, and spell-checkers are all explicitly allowed; this is a spell-check
for the style guide, not an exam autopilot.
"""
from __future__ import annotations
import re
import unicodedata
from .types import Flag, Transcript

# A leading speaker label so checks run on speech, not on "MR. SMITH" / "Q" / "A".
_LABEL = re.compile(r"^\s*(?:[A-Z][A-Z .'-]{0,38}|Q|A)\s{2,}|^\s*[^:]{1,40}?:\s")


def _body(text: str) -> str:
    m = _LABEL.match(text)
    return text[m.end():] if m else text


def _flag(rule, label, line, ev, fix, sev="moderate"):
    return Flag(rule=rule, label=label, line=line, severity=sev, evidence=ev, fix=fix)


# ---------------------------------------------------------------- spelling (p.5)
# wrong-surface -> (right-surface, page-grounded fix). Case handled per entry.
_SPELL = [
    # (regex, replacement, fix)
    (re.compile(r"\bO[Kk]\b"), "okay", "Write 'okay' (lowercase), never OK/Ok ('kay). [p.5]"),
    (re.compile(r"'kay\b", re.I), "okay", "Write 'okay', not ''kay'. [p.5]"),
    (re.compile(r"\balright\b", re.I), "all right", "Two words: 'all right', not 'alright'. [p.5]"),
    (re.compile(r"\balot\b", re.I), "a lot", "Two words: 'a lot', not 'alot'. [p.5]"),
    (re.compile(r"\betc\b\.?"), "et cetera", "Spell it out: 'et cetera', not 'etc.'. [p.5]"),
    (re.compile(r"\bU\.S\.A\.?"), "USA", "No periods: 'USA', not 'U.S.A'. [p.5]"),
    (re.compile(r"\bU\.S\.(?!A)"), "US", "No periods: 'US', not 'U.S.'. [p.5]"),
    (re.compile(r"\be-mail\b", re.I), "email", "One word, no hyphen: 'email'. [p.5]"),
    (re.compile(r"\bhealth care\b", re.I), "healthcare", "One word: 'healthcare'. [p.5]"),
    # 'internet' lowercase (p.5) is handled by the dedicated inline check below — don't duplicate here.
]


def legal_spelling(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        x = ln.text
        for rx, repl, fix in _SPELL:
            for m in rx.finditer(x):
                out.append(_flag("legal_spelling",
                                 f"'{m.group(0)}' should be '{repl}'", ln.n, m.group(0), fix))
        # "Internet" capitalized mid-sentence -> lowercase (p.5). Skip sentence-initial.
        for m in re.finditer(r"(?<=[a-z,;:\-]\s)Internet\b", x):
            out.append(_flag("legal_spelling", "'Internet' should be lowercase 'internet'",
                             ln.n, m.group(0), "'internet' is lowercase. [p.5]"))
    return out


# ----------------------------------------------------------------- slang (p.9)
# FLAG -> standard. KEEP (never flag): y'all, ain't, gotcha, alls, I'ma.
# "yeah" is allowed ("yes or yeah"); do NOT flag it.
_SLANG = {
    "sorta": "sort of", "kinda": "kind of", "wanna": "want to", "gonna": "going to",
    "gotta": "got to", "coulda": "could have", "shoulda": "should have",
    "woulda": "would have", "cuz": "because", "ya": "you",
    "yep": "yes (or yeah)", "yup": "yes (or yeah)",
}
_SLANG_RX = re.compile(r"\b(" + "|".join(_SLANG) + r")\b", re.I)
_GOIN = re.compile(r"\bgoin'", re.I)          # goin' -> going
_CAUSE = re.compile(r"'cause\b", re.I)         # 'cause -> because


def legal_slang(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        body = _body(ln.text)
        for m in _SLANG_RX.finditer(body):
            w = m.group(0).lower()
            out.append(_flag("legal_slang", f"'{m.group(0)}' should be '{_SLANG[w]}'",
                             ln.n, m.group(0),
                             f"CVL writes the standard form '{_SLANG[w]}' (keeps y'all/ain't/gotcha). [p.9]"))
        for m in _GOIN.finditer(body):
            out.append(_flag("legal_slang", "'goin'' should be 'going'", ln.n, m.group(0),
                             "Drop the dropped-g: 'going'. [p.9]"))
        for m in _CAUSE.finditer(body):
            out.append(_flag("legal_slang", "''cause' should be 'because'", ln.n, m.group(0),
                             "CVL writes 'because'. [p.9]"))
    return out


# ----------------------------------------------------- contractions (p.8)
# Keep all contractions as spoken EXCEPT these three.
_CONTRACT = {"could've": "could have", "should've": "should have", "would've": "would have"}
_CONTRACT_RX = re.compile(r"\b(could|should|would)'ve\b", re.I)


def legal_contractions(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _CONTRACT_RX.finditer(_body(ln.text)):
            std = _CONTRACT[m.group(0).lower()]
            out.append(_flag("legal_contraction", f"'{m.group(0)}' should be '{std}'",
                             ln.n, m.group(0),
                             f"CVL exception: write '{std}' (other contractions stay as spoken). [p.8]"))
    return out


# -------------------------------------------------- crutch/hesitation (p.10)
# OMIT hesitations uh/ah/um/er. KEEP crutch words (like, you know, I mean) and the
# nonverbals uh-huh / uh-uh / huh? (so the (?!-) guard protects "uh-huh").
_HESITATION = re.compile(r"\b(uh+|ah+|um+|er+|erm+)\b(?!-)", re.I)


def legal_fillers(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _HESITATION.finditer(_body(ln.text)):
            out.append(_flag(
                "legal_filler", f"Hesitation '{m.group(0)}' should be removed",
                ln.n, m.group(0),
                "CVL omits uh/ah/um/er (but KEEPS like, you know, I mean). [p.10]"))
    return out


# ------------------------------------------------- nonverbal responses (p.11)
# Only uh-huh, uh-uh, huh? are allowed. mm-hmm/mm-mm -> uh-huh/uh-uh.
_NONVERBAL = [
    (re.compile(r"\bmm+[-\s]?h+m+\b", re.I), "uh-huh", "yes"),
    (re.compile(r"\bm+h+m+\b", re.I), "uh-huh", "yes"),
    (re.compile(r"\bmm+[-\s]?mm+\b", re.I), "uh-uh", "no"),
]


def legal_nonverbal(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        body = _body(ln.text)
        for rx, repl, meaning in _NONVERBAL:
            for m in rx.finditer(body):
                out.append(_flag("legal_nonverbal",
                                 f"'{m.group(0)}' ({meaning}) should be '{repl}'", ln.n, m.group(0),
                                 f"Only uh-huh/uh-uh/huh? are allowed nonverbals; use '{repl}'. [p.11]"))
    return out


# ----------------------------------------------------------- titles (p.12)
# Do NOT use Mrs. or Miss with a name -> use Ms.
_MRS = re.compile(r"\b(Mrs\.?|Miss)\s+[A-Z][a-z]+")
# A professional title/rank used WITH a name is capitalized (p.12: "Doctor Jamison", "Sergeant
# Saunders", "Investigator Joe Bloggs"). Case-sensitive so only a LOWERCASE title before a
# Capitalized name flags. Skip capitalized non-names (days/months/pronoun) to avoid false positives.
_TITLE_WORDS = ("doctor|officer|detective|sergeant|lieutenant|captain|judge|justice|investigator|"
                "attorney|professor|nurse|deputy|marshal|colonel|major|general|admiral|reverend|"
                "senator|governor|mayor|president|director|chief|counselor|agent")
_TITLE_CAP = re.compile(r"\b(" + _TITLE_WORDS + r")\s+([A-Z][a-z]+)")
_TITLE_SKIP = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
               "January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December", "I"}


def legal_titles(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _MRS.finditer(ln.text):
            out.append(_flag("legal_title", f"'{m.group(0)}' — use 'Ms.' with a name",
                             ln.n, m.group(0),
                             "Never Mrs./Miss with a name, however it's spoken — use 'Ms.'. [p.12]"))
        for m in _TITLE_CAP.finditer(ln.text):
            title, name = m.group(1), m.group(2)
            if name in _TITLE_SKIP:
                continue
            out.append(_flag("legal_title_caps", f"'{title} {name}' — capitalize the title used with a name",
                             ln.n, f"{title} {name}",
                             f"A title used with a name is capitalized: '{title.capitalize()} {name}'. [p.12]"))
    return out


# --------------------------------------------------- numbers & symbols (p.14)
# % -> spell "percent". Spelled 11+ -> numerals (review: many exceptions).
_PERCENT = re.compile(r"\d[\d,.]*\s?%")
_SPELLED_BIG = re.compile(
    r"\b(eleven|twelve|thir|four|fif|six|seven|eigh|nine)teen\b"
    r"|\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\b", re.I)


def legal_numbers(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        body = _body(ln.text)
        for m in _PERCENT.finditer(body):
            out.append(_flag("legal_number", "Use the word 'percent', not the % symbol",
                             ln.n, m.group(0), "Spell out 'percent'; never the % symbol. [p.14]"))
        for m in _SPELLED_BIG.finditer(body):
            out.append(_flag("legal_number",
                             f"'{m.group(0)}' (11+) is usually written in numerals", ln.n, m.group(0),
                             "Spell zero-ten; use numerals for 11+ (exceptions: estimates, "
                             "start-of-sentence). [p.14-17]", "review"))
    return out


# ----------------------------------------------------- accented letters (p.24)
# No special/accented characters. Flag any non-ASCII LETTER + give the ASCII fold.
def _ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode() or s


def legal_accents(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in re.finditer(r"\b\w*[^\x00-\x7F]\w*\b", ln.text):
            tok = m.group(0)
            # only letters-with-diacritics, not emoji/symbols
            if not any(unicodedata.category(c).startswith("L") and ord(c) > 127 for c in tok):
                continue
            fold = _ascii_fold(tok)
            if fold and fold != tok:
                out.append(_flag("legal_accent",
                                 f"Accented/special letters in '{tok}' — use plain ASCII '{fold}'",
                                 ln.n, tok,
                                 f"No accented letters (system restriction): write '{fold}'. [p.24]"))
    return out


# --------------------------------------------------------------- AM/PM (p.16)
_AMPM = re.compile(r"\b([ap])\.m\.", re.I)


def legal_ampm(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _AMPM.finditer(_body(ln.text)):
            std = "AM" if m.group(1).lower() == "a" else "PM"
            out.append(_flag("legal_ampm", f"'{m.group(0)}' should be '{std}'",
                             ln.n, m.group(0), f"AM/PM in caps, no periods: '{std}'. [p.16]"))
    return out


# -------------------------------------------------- inaudible & tags (p.13)
# CVL [inaudible] is lowercase, square brackets, and needs NO timestamp.
_INAUD_WRONG_BRACKETS = re.compile(r"\((inaudible|unintelligible)\)", re.I)
_INAUD_CAPS = re.compile(r"\[(In|UN|Un)[a-z]*\]")
_INAUD_TYPO = re.compile(r"\[\s*(inaudable|unintelligable|unintellligible|inadible)\s*\]", re.I)
# sound-event / tag in round brackets -> square brackets
_SOUND_PARENS = re.compile(
    r"\((laughs?|laughter|crosstalk|applause|sighs?|coughs?|pause|silence|phonetic|sic)\)", re.I)


def legal_tags(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        x = ln.text
        for m in _INAUD_WRONG_BRACKETS.finditer(x):
            out.append(_flag("legal_tag", f"'{m.group(0)}' must use square brackets: [{m.group(1).lower()}]",
                             ln.n, m.group(0), "Tags go in square brackets [ ], never ( ). [p.13/24]"))
        for m in _INAUD_CAPS.finditer(x):
            out.append(_flag("legal_tag", f"Tag '{m.group(0)}' must be lowercase",
                             ln.n, m.group(0), "Tags are always lowercase, e.g. [inaudible]. [p.13/24]"))
        for m in _INAUD_TYPO.finditer(x):
            out.append(_flag("legal_tag", f"Misspelled tag '{m.group(0)}'",
                             ln.n, m.group(0), "Spell it exactly: [inaudible] or [unintelligible]. [p.13]"))
        for m in _SOUND_PARENS.finditer(x):
            out.append(_flag("legal_tag", f"'{m.group(0)}' must use square brackets",
                             ln.n, m.group(0), "Sound tags use square brackets, lowercase. [p.24]"))
    return out


# ------------------------------------------------------- spacing (p.3)
# One space between sentences; no space before punctuation. Label-aware: legal
# Q&A/Colloquy separates the speaker label from speech with a tab/gap
# ("MR. JONES    I'm Don Jones..."), so we check the speech BODY, not the gap.
def legal_spacing(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        body = _body(ln.text)
        if "  " in body.strip():
            out.append(_flag("legal_spacing", "Double space between words/sentences",
                             ln.n, "  ", "One space between sentences, never two. [p.3]", "minor"))
        m = re.search(r"\S +[,.;:?]", body)
        if m:
            out.append(_flag("legal_spacing", "Space before punctuation",
                             ln.n, m.group(0), "No space before punctuation. [p.3]", "minor"))
    return out


# ------------------------------------------------- grammar / homophones
# NOT all of this lives in the CVL SG — the exam itself says "DO research if
# uncertain" — so these cite [grammar], not a page. DELIBERATELY high-confidence
# patterns only: each fires on a mechanical adjacency that is wrong in ~every
# context (you're + a possessed noun, of-for-'ve), never on a judgment call about
# which homophone a sentence "means". The semantic half — is THIS the right
# homophone in a sentence that could legitimately go either way? — stays the
# human's job, the same boundary the rest of the engine keeps. The one
# context-dependent check (possessive 'their' + a finite verb) is 'review', not a
# hard flag, so the tool never pretends to have read the meaning.

# "could of / should of / would of / must of" -> "... have" (a misheard ''ve').
# NOTE: 'may of'/'might of' are excluded — "May of 2020" (date) and "might of course" are common
# legit uses; only could/should/would/must + of is unambiguously "…have".
_OF_FOR_HAVE = re.compile(r"\b(could|should|would|must)\s+of\b", re.I)

# A curated possessed-noun list: directly after you're/there/they're/it's, these
# are ~always the possessive homophone, not the contraction. Kept short on
# purpose — every entry is a near-zero-false-positive case.
_POSSD = (r"own|fault|turn|name|job|house|home|car|money|kids?|child(?:ren)?|"
          r"family|wife|husband|parents?|cabin|responsibility|problem|point|"
          r"choice|decision|opinion|order|seat|side|hands?|head")
_YOURE_NOUN = re.compile(rf"\byou're\s+(?:{_POSSD})\b", re.I)            # you're cabin -> your
_THERE_NOUN = re.compile(rf"\b(there|they're)\s+(?:{_POSSD})\b", re.I)  # there own -> their
_ITS_NOUN   = re.compile(rf"\bit's\s+(?:{_POSSD})\b", re.I)             # it's own -> its
# possessive 'their' immediately before a finite verb -> a verb wants there/they're.
# Genuinely context-dependent, so 'review' only.
_THEIR_VERB = re.compile(r"\btheir\s+(is|are|was|were)\b", re.I)


def legal_grammar(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        body = _body(ln.text)
        for m in _OF_FOR_HAVE.finditer(body):
            std = m.group(1).lower() + " have"
            out.append(_flag("legal_grammar", f"'{m.group(0)}' should be '{std}'", ln.n,
                             m.group(0), f"'of' here is a misheard ''ve' — write '{std}'. [grammar]"))
        for m in _YOURE_NOUN.finditer(body):
            out.append(_flag("legal_grammar",
                             f"'{m.group(0)}' — 'you're' means 'you are'; use possessive 'your'",
                             ln.n, m.group(0),
                             "Possessive before a noun is 'your', not 'you're'. [grammar]"))
        for m in _THERE_NOUN.finditer(body):
            out.append(_flag("legal_grammar",
                             f"'{m.group(0)}' — use possessive 'their'", ln.n, m.group(0),
                             "Possessive before a noun is 'their', not 'there'/'they're'. [grammar]"))
        for m in _ITS_NOUN.finditer(body):
            out.append(_flag("legal_grammar",
                             f"'{m.group(0)}' — possessive 'its' has no apostrophe", ln.n, m.group(0),
                             "Possessive 'its' has no apostrophe; 'it's' means 'it is'. [grammar]"))
        for m in _THEIR_VERB.finditer(body):
            out.append(_flag("legal_grammar",
                             f"'{m.group(0)}' — a verb wants 'there {m.group(1)}' or 'they're'",
                             ln.n, m.group(0),
                             "'their' is possessive; before a verb you usually want "
                             "'there' or 'they're'. [grammar]", "review"))
    return out


LEGAL_SCANNERS = [
    legal_spelling, legal_slang, legal_contractions, legal_fillers,
    legal_nonverbal, legal_titles, legal_numbers, legal_accents,
    legal_ampm, legal_tags, legal_spacing, legal_grammar,
]


# ===================================================================
# Redline — deterministic auto-fix.  Each fixer is (compiled_pattern, repl),
# reusing the SAME compiled patterns the scanners detect with, so detect and fix
# can never drift. repl is a str or a callable(match)->str. Applied via re.sub,
# so word boundaries are respected (no "him" -> "hI'm" substring bugs). NO model,
# same spine as the rest of the engine. Only deterministic, ~always-correct fixes
# live here; 'review'-tier judgment calls (their+verb, cant/wont, typo'd tags) are
# deliberately absent so they stay the human's call.
def _cased(src: str, repl: str) -> str:
    """Carry the source's leading capital onto the replacement. 'okay' is forced
    lowercase (SG p.5 mandates it, never 'Okay')."""
    if repl == "okay":
        return "okay"
    if src[:1].isupper() and repl[:1].islower():
        return repl[:1].upper() + repl[1:]
    return repl


_INTERNET = re.compile(r"(?<=[a-z,;:\-]\s)Internet\b")
# hesitation removal eats a trailing comma/space too, so deletion leaves no gap.
_HESITATION_FIX = re.compile(r"\b(?:uh+|ah+|um+|er+|erm+)\b(?!-)[,;]?\s*", re.I)
_ACCENT_TOK = re.compile(r"\b\w*[^\x00-\x7F]\w*\b")


def _mk(repl):
    return lambda m: _cased(m.group(0), repl)


LEGAL_FIXERS = [
    (_HESITATION_FIX, ""),                                              # p.10 remove uh/ah/um/er
    (_INAUD_WRONG_BRACKETS, lambda m: f"[{m.group(1).lower()}]"),       # (inaudible) -> [inaudible]
    (_INAUD_CAPS, lambda m: m.group(0).lower()),                        # [Inaudible] -> [inaudible]
    (_SOUND_PARENS, lambda m: f"[{m.group(1).lower()}]"),               # (laughs) -> [laughs]
    (_AMPM, lambda m: "AM" if m.group(1).lower() == "a" else "PM"),     # p.16
    *[(rx, _mk(repl)) for rx, repl, _ in _SPELL],                       # p.5 spelling table
    (_INTERNET, "internet"),                                            # p.5
    (_SLANG_RX, lambda m: (_cased(m.group(0), _SLANG[m.group(0).lower()])
                           if "(" not in _SLANG[m.group(0).lower()]     # skip yep/yup -> 'yes (or yeah)'
                           else m.group(0))),                           # p.9
    (_GOIN, _mk("going")),
    (_CAUSE, _mk("because")),
    (_CONTRACT_RX, lambda m: _cased(m.group(0), _CONTRACT[m.group(0).lower()])),  # p.8
    *[(rx, _mk(repl)) for rx, repl, _ in _NONVERBAL],                   # p.11 mm-hmm -> uh-huh
    (_MRS, lambda m: "Ms. " + m.group(0).split(None, 1)[1]),            # p.12 Mrs./Miss -> Ms.
    (_PERCENT, lambda m: re.sub(r"\s*%", "", m.group(0)) + " percent"), # p.14
    (_ACCENT_TOK, lambda m: _ascii_fold(m.group(0)) or m.group(0)),     # p.24 fold accents
    (_OF_FOR_HAVE, lambda m: _cased(m.group(1), m.group(1).lower() + " have")),   # could of -> could have
    (_YOURE_NOUN, lambda m: ("Your" if m.group(0)[:1].isupper() else "your") + m.group(0)[6:]),
    (_THERE_NOUN, lambda m: ("Their" if m.group(0)[:1].isupper() else "their") + m.group(0)[len(m.group(1)):]),
    (_ITS_NOUN, lambda m: ("Its" if m.group(0)[:1].isupper() else "its") + m.group(0)[4:]),
]
