"""intent — garbled natural language → ONE validated engine command.

The operator types with difficulty ("chek this japnse file for gotranscipt"), so the
`tt` wrapper lets him TALK to the engine instead of spelling flags. The law here is
the same law as everywhere else in this repo: a MODEL only ever PROPOSES; a human or
deterministic code owns every verdict. Concretely, the pipeline is a one-way street:

    utterance ──(a) small LOCAL LLM proposes a JSON config        (optional, lazy)
              ──(b) deterministic fuzzy-keyword proposer          (always available)
    proposal  ──validate(): EVERY field membership-checked against the LIVE
                registries; an invalid value moves to "unrecognized" — it is never
                guessed silently, and it never reaches an argv
    config    ──render_command(): the exact argv + the display line SHOWN to the
                human, who confirms with one raw keypress before anything runs

The vocabulary is built FROM the registries at call time (profiles._base.REGISTRY,
domains.DOMAIN_REGISTRY / SITE_REGISTRY, consensus.ROSTER) so a newly dropped
language/site/domain plugin appears in tt automatically — nothing here hardcodes
what exists, only what the ACTIONS are (that set mirrors the real entry points and
is closed on purpose).

LLM backends, tried in order, each optional (the feature must work with NONE):
  1. mlx_lm    (Apple Silicon) — mlx-community/Qwen2.5-1.5B-Instruct-4bit
  2. llama_cpp (any CPU box)   — gguf path from $TT_INTENT_MODEL
  3. neither   — the keyword fallback carries the whole feature
"""
from __future__ import annotations

import difflib
import json
import os
import re

# ---------------------------------------------------------------------------
# The CLOSED action space. Arg KEYS are fixed here because they mirror the real
# entry points (cli.main flags, ./check wrapper positionals, earcheck.run); arg
# VALUES of registry kinds are read live in vocabulary() — the registry decides
# what exists, this table only decides what an action can carry.
# ---------------------------------------------------------------------------
ACTIONS = {
    "check":         {"file": "path", "profile": "profile", "site": "site",
                      "domain": "domain", "mode": "mode", "fix": "bool"},
    "ship":          {"file": "path", "audio": "path"},
    "earcheck":      {"draft": "path", "audio": "path"},
    "ears":          {"lang": "lang"},
    "translate":     {"audio": "path", "src": "lang", "tgt": "lang"},
    "coverage":      {},
    "list-profiles": {},
}

# Path slots tt refuses to run without (it ASKS instead — a placeholder argv must
# never execute). ears/coverage/list-profiles need nothing.
REQUIRED = {"check": ("file",), "ship": ("file",),
            "earcheck": ("draft", "audio"), "translate": ("audio",)}

# Slot fill order per action, shared by the utterance-token path scan and the
# explicit `tt "..." file...` argument list: audio-extension files feed the audio
# slot, everything else feeds the transcript/draft slot; position breaks ties.
_PATH_SLOTS = {"check": ("file",), "ship": ("file", "audio"),
               "earcheck": ("draft", "audio"), "translate": ("audio",)}

# The engine's two verbatim modes (types.Transcript) — a closed pair, not a
# registry. The cli's documented spellings resolve by TABLE (deterministic alias,
# not a guess): --full and "verbatim" mean full_verbatim everywhere in this repo.
_MODES = ("clean_verbatim", "full_verbatim")
_MODE_ALIASES = {"full": "full_verbatim", "full-verbatim": "full_verbatim",
                 "full_verbatim": "full_verbatim", "verbatim": "full_verbatim",
                 "clean": "clean_verbatim", "clean-verbatim": "clean_verbatim",
                 "clean_verbatim": "clean_verbatim"}

# Human names for language codes — an ALIAS table, not the registry: vocabulary()
# keeps only names whose CODE is actually in consensus.ROSTER, so a new language
# plugin without an alias here still works by its code, and a name whose plugin
# was removed stops matching automatically.
_LANG_NAMES = {
    "japanese": "ja", "english": "en", "spanish": "es", "russian": "ru",
    "french": "fr", "german": "de", "portuguese": "pt", "turkish": "tr",
    "korean": "ko", "vietnamese": "vi", "arabic": "ar", "hindi": "hi",
    "urdu": "ur", "ukrainian": "uk",
}

# Codes that double as garbled English ("ar"=are, "hi"=hello, "ur"=your, and the
# "me" profile = me). They are CLAIMED wherever seen (so they never spill into
# "couldn't place" noise) but ASSIGNED only with positional evidence: last token
# of the utterance, or right after a to/from/language marker. Anything softer
# turned "hi chek this" into --profile=hi during design.
_RISKY_SHORT = {"ar", "hi", "ur", "me"}
_LANG_MARKERS = {"to", "into", "in", "from", "ot", "2", "lang", "language",
                 "langauge", "profile", "profil"}

# ---------------------------------------------------------------------------
# Keyword fallback vocabulary: action trigger words INCLUDING his real typo
# forms. Fuzzy matching (difflib) covers the rest — the typo forms just anchor
# the shapes we've actually seen so the cutoff can stay strict.
# ---------------------------------------------------------------------------
_ACTION_TRIGGERS = {
    # NOTE: no "audit"/"lint" here — "audio" fuzzes to "audit" at 0.80 and would
    # cast a phantom check-vote on every earcheck/translate utterance. Same for
    # "listen" under earcheck: "list" fuzzes to it at 0.80.
    "check":         {"check", "chek", "cheq", "chk", "checkit", "qa", "grade"},
    "ship":          {"ship", "shp", "shipit", "submit", "finish", "send"},
    "earcheck":      {"earcheck", "ear-check", "earchek"},
    "ears":          {"ears", "ers", "preflight", "roster", "witnesses",
                      "liveness", "witness"},
    "translate":     {"translate", "translat", "traslate", "tranlate",
                      "translation", "translsate"},
    "coverage":      {"coverage", "coverge", "covrage", "covarge"},
    "list-profiles": {"profiles", "profils", "list-profiles", "profiless"},
}
# "er check" / "ears chek …": the ear-word alone is ambiguous (ears-preflight vs
# earcheck), so earcheck needs the bigram — an ear-ish token DIRECTLY followed by
# a check-ish token. "against …audio" in an ear sentence means the same thing.
_EARISH = {"ear", "er", "ers", "ears", "eear", "eras"}

# When several actions match, the most SPECIFIC wins (ship is check--ship, so
# check is last; earcheck's bigram evidence beats everything).
_PRIORITY = ("earcheck", "ship", "translate", "ears", "coverage",
             "list-profiles", "check")

_MODE_WORDS = {"full", "verbatim", "clean", "fv"}
_FIX_WORDS = {"fix", "fixit", "fixes", "fixed", "fx", "thoth", "autofix"}

# Filler that must never be echoed back as "couldn't place" — includes the
# garbled forms his hands actually produce. Checked AFTER every arg pass, so a
# stopword can never shadow a real registry value.
_STOPWORDS = {
    "a", "an", "and", "the", "this", "that", "these", "those", "it", "its",
    "is", "are", "was", "be", "been", "i", "im", "me", "my", "we", "you", "u",
    "to", "for", "of", "on", "at", "by", "as", "or", "so", "then", "now",
    "please", "pls", "plz", "do", "does", "did", "can", "could", "would",
    "should", "will", "just", "go", "make", "take", "get", "got", "have",
    "has", "had", "want", "need", "lets", "let", "us", "up", "out", "again",
    "against", "from", "into", "onto", "over", "about", "with", "run",
    "file", "files", "transcript", "transcripts", "draft", "drafts", "audio",
    "job", "jobs", "one", "all", "every", "alive", "dead", "ok", "okay",
    "yes", "no", "what", "whats", "how", "list", "show", "see", "look",
    "give", "in", "if", "there", "ther", "here",
    # garbled forms seen in his real typing
    "teh", "hte", "eth", "tis", "ths", "thsi", "ar", "aer", "adn", "nad",
    "fo", "ot", "si", "agianst", "aginst", "agains", "abut", "abot", "wiht",
    "wtih", "fro", "eht", "whcih", "taht",
}

_AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".mp4", ".flac", ".ogg", ".aac",
               ".opus", ".aiff", ".wma", ".webm", ".mkv", ".mov", ".mpga"}
_TEXTY_EXTS = {".txt", ".md", ".srt", ".vtt", ".doc", ".docx", ".rtf", ".json"}

_MLX_MODEL = "mlx-community/Qwen2.5-1.5B-Instruct-4bit"


# ---------------------------------------------------------------------------
# vocabulary — the LIVE registry snapshot
# ---------------------------------------------------------------------------

def vocabulary():
    """What values EXIST right now, read from the registries at call time.

    Imported lazily so `import intent` stays light and a broken heavy dep in a
    registry module degrades this one call, not the whole module. A new plugin
    dropped into profiles/ or registered in domains.py appears here with zero
    changes to this file — that is the whole point."""
    from .profiles import names as profile_names
    from .domains import domain_names, site_names
    from .consensus import ROSTER
    langs = sorted(ROSTER)
    return {
        "profiles": list(profile_names()),
        "sites": list(site_names()),
        "domains": list(domain_names()),
        "langs": langs,
        "modes": list(_MODES),
        # only names whose code is really in the roster survive the filter
        "lang_names": {n: c for n, c in _LANG_NAMES.items() if c in langs},
    }


# ---------------------------------------------------------------------------
# validate — the wall. Membership checks ONLY; fuzz belongs to the proposers.
# ---------------------------------------------------------------------------

def _check_value(kind, value, vocab):
    """-> (ok, normalized). Exact registry membership or a FIXED alias table —
    the validator never fuzzy-matches: a proposer's guess that missed the
    registry is evidence of a hallucination and must surface, not be repaired."""
    if kind == "path":
        # A flag-shaped "path" (--update, --list-profiles) would be re-parsed DOWNSTREAM as a
        # flag and run a different action than the displayed one (verifier-found 2026-07-24:
        # file='--update' reached update.run under a 'check' display line). Same guard the
        # wrappers use: a path never starts with '-'.
        ok = (isinstance(value, str) and bool(value.strip())
              and not value.strip().startswith("-"))
        return ok, value.strip() if ok else value
    if kind == "bool":
        if isinstance(value, bool):
            return True, value
        s = str(value).strip().lower()
        if s in ("true", "yes", "1"):
            return True, True
        if s in ("false", "no", "0"):
            return True, False
        return False, None
    if not isinstance(value, str):
        return False, None
    s = value.strip().lower()
    if kind == "mode":
        s = _MODE_ALIASES.get(s, s)
        return s in vocab["modes"], s
    if kind == "lang":
        s = vocab["lang_names"].get(s, s)          # "japanese" -> "ja" (alias table)
        return s in vocab["langs"], s
    if kind == "profile":
        s = vocab["lang_names"].get(s, s)          # a language name IS its profile
        return s in vocab["profiles"], s
    if kind == "site":
        return s in vocab["sites"], s
    if kind == "domain":
        return s in vocab["domains"], s
    return False, None


def validate(proposal, vocab=None):
    """Proposal (from EITHER proposer) -> final config. Every field is checked
    against the action space + live registries; anything invalid lands in
    "unrecognized" verbatim — never dropped silently, never passed through.
    Deterministic: same proposal + same registry state -> same config."""
    vocab = vocab or vocabulary()
    unrecognized = [str(u) for u in (proposal.get("unrecognized") or [])]
    action = proposal.get("action")
    raw_args = dict(proposal.get("args") or {})

    if action not in ACTIONS:
        if action:                                  # a made-up action must surface
            unrecognized.append(f"action={action}")
        return {"action": None, "args": {}, "unrecognized": unrecognized}

    # small models sometimes flatten args to the top level — recover KNOWN keys
    # rather than lose them (graceful degradation, still membership-checked below)
    for k, v in proposal.items():
        if k in ACTIONS[action] and k not in raw_args:
            raw_args[k] = v

    args = {}
    for k, v in raw_args.items():
        kind = ACTIONS[action].get(k)
        if kind is None:                            # hallucinated FIELD
            unrecognized.append(f"{k}={v}")
            continue
        ok, norm = _check_value(kind, v, vocab)
        if ok:
            args[k] = norm
        else:                                       # hallucinated VALUE
            unrecognized.append(f"{k}={v}")
    return {"action": action, "args": args, "unrecognized": unrecognized}


# ---------------------------------------------------------------------------
# render — what the human SEES before anything runs
# ---------------------------------------------------------------------------

def render_command(config):
    """config -> (argv, display). argv is EXACTLY what the dispatcher hands to
    the entry point (cli.main flags / ./check wrapper positionals / earcheck.run
    args); display is the one line shown before the y/n. A missing required path
    renders as an angle-bracket placeholder so the display never pretends to
    know something it doesn't — tt refuses to execute a placeholder."""
    a, g = config["action"], config.get("args", {})
    if a == "check":
        argv = [g.get("file") or "<file>"]
        for flag, key in (("--profile", "profile"), ("--site", "site"),
                          ("--domain", "domain"), ("--mode", "mode")):
            if g.get(key):
                argv.append(f"{flag}={g[key]}")
        if g.get("fix"):
            argv.append("--fix")
        return argv, "check " + " ".join(argv)
    if a == "ship":
        argv = [g.get("file") or "<file>", "--ship"]
        if g.get("audio"):
            argv.append(g["audio"])
        return argv, "check " + " ".join(argv)
    if a == "earcheck":
        argv = [g.get("draft") or "<draft>", g.get("audio") or "<audio>"]
        return argv, "earcheck " + " ".join(argv)
    if a == "ears":
        argv = [f"--ears={g.get('lang') or 'ja'}"]
        return argv, "check " + " ".join(argv)
    if a == "translate":
        tgt = g.get("tgt") or "en"
        argv = [g.get("audio") or "<audio>", f"--translate={tgt}"]
        if g.get("src"):
            argv.append(f"--src={g['src']}")
        display = (f"translate {argv[0]} --src={g.get('src') or 'auto'}"
                   f" --to={tgt}")
        return argv, display
    if a == "coverage":
        return ["--coverage"], "coverage"
    if a == "list-profiles":
        return ["--list-profiles"], "list-profiles"
    raise ValueError(f"unknown action: {a!r}")


# ---------------------------------------------------------------------------
# proposer (b): deterministic fuzzy-keyword fallback — always available
# ---------------------------------------------------------------------------

def _fuzz(tok, cands, cutoff):
    """Exact hit or best difflib match above cutoff. Candidates are sorted so a
    set's iteration order can never change the answer (determinism law)."""
    if tok in cands:
        return tok
    m = difflib.get_close_matches(tok, sorted(cands), n=1, cutoff=cutoff)
    return m[0] if m else None


def _is_pathish(tok):
    """Path evidence = a slash, or an extension that is either a known
    transcript/audio type or belongs to a file that really exists. A bare word
    is NEVER a path even when a same-named file exists — the repo root itself
    has files called `check` and `tt`, and eating the action word as a path was
    a real bug during design ("er check …" parsed as ears because "check" got
    claimed). Extensionless real files still reach the engine through the
    explicit files list (`tt "…" <file>`), where no guessing is involved."""
    if "/" in tok:
        return True
    root, ext = os.path.splitext(tok)
    if not root or not ext:
        return False
    return ext.lower() in (_AUDIO_EXTS | _TEXTY_EXTS) or os.path.isfile(tok)


def _lang_hit(norm, vocab):
    """Token -> language code, or None. Codes match EXACTLY (2-letter fuzzing is
    how 'ers' becomes Spanish); full names may fuzz because they're long enough
    to be unambiguous ('japnse' -> japanese at .857)."""
    if norm in vocab["langs"]:
        return norm
    if len(norm) >= 4:
        name = _fuzz(norm, set(vocab["lang_names"]), 0.75)
        if name:
            return vocab["lang_names"][name]
    return None


def _risky_ok(toks, i):
    """Positional evidence gate for _RISKY_SHORT codes — see the table comment."""
    if toks[i]["norm"] not in _RISKY_SHORT:
        return True
    if i == len(toks) - 1:                          # last word: "ears alive hi"
        return True
    return i > 0 and toks[i - 1]["norm"] in _LANG_MARKERS


def _fill_path_slots(args, action, paths):
    """Assign path strings to the action's slots: audio extensions feed the audio
    slot, everything else feeds the text slot, position breaks ties. Not a silent
    guess — the human sees exactly where each file landed and confirms."""
    slots = _PATH_SLOTS.get(action, ())
    if not slots or not paths:
        return
    taken = set(v for v in args.values() if isinstance(v, str))
    audio = [p for p in paths if os.path.splitext(p)[1].lower() in _AUDIO_EXTS]
    other = [p for p in paths if p not in audio]
    for slot in slots:
        if args.get(slot):
            continue
        pool = audio if slot == "audio" else other
        pick = next((p for p in pool if p not in taken), None)
        if pick is None and slot == "audio":
            # positional fallback for the AUDIO slot only: a recording without a known audio
            # extension is still plausibly audio. A TEXT slot never steals an audio-classified
            # file (verifier-found 2026-07-24: 'ship … interview.mp3' fed the mp3 to check's
            # UTF-8 read) — leaving it empty prints an honest 'need: <file>' instead.
            pick = next((p for p in paths if p not in taken), None)
        if pick is not None:
            args[slot] = pick
            taken.add(pick)


def _keyword_propose(utterance, files=None, vocab=None):
    """The always-on deterministic parser: fuzzy token matching over the live
    registry vocabulary + the trigger tables above. Same utterance + same
    registry state -> same proposal, every time (tested)."""
    vocab = vocab or vocabulary()
    toks = []
    for raw in utterance.split():
        stripped = raw.strip("\"'`,;:!?()[]{}")
        # trailing sentence dot: strip only when it doesn't form a known extension
        norm = stripped if _is_pathish(stripped) else stripped.strip(".").lower()
        if norm or stripped:
            toks.append({"raw": raw, "norm": norm, "claimed": False})

    args, paths, hits = {}, [], {}

    # pass 1 — paths (before anything can fuzzy-eat "draft.md")
    for t in toks:
        s = t["raw"].strip("\"'`,;:!?()[]{}")
        if _is_pathish(s):
            t["claimed"] = True
            paths.append(s)

    # pass 2 — actions: earcheck bigram first (ear-ish + check-ish), then single
    # trigger words; every hit is recorded, priority picks the winner
    i = 0
    while i < len(toks):
        t = toks[i]
        if not t["claimed"]:
            nxt = toks[i + 1] if i + 1 < len(toks) else None
            if (t["norm"] in _EARISH and nxt and not nxt["claimed"]
                    and _fuzz(nxt["norm"], _ACTION_TRIGGERS["check"], 0.8)):
                t["claimed"] = nxt["claimed"] = True
                hits.setdefault("earcheck", i)
                i += 2
                continue
            for action, trig in _ACTION_TRIGGERS.items():
                if len(t["norm"]) >= 2 and _fuzz(t["norm"], trig, 0.8):
                    t["claimed"] = True
                    hits.setdefault(action, i)
                    break
        i += 1
    action = next((a for a in _PRIORITY if a in hits), None)

    # pass 3 — mode words (before profile fuzzing can see "full" in "ja:full")
    mode_hit = clean_hit = False
    for t in toks:
        if not t["claimed"]:
            w = _fuzz(t["norm"], _MODE_WORDS, 0.75)
            if w:
                t["claimed"] = True
                mode_hit = mode_hit or w in ("full", "verbatim", "fv")
                clean_hit = clean_hit or w == "clean"
    # pass 4 — fix words
    fix_hit = False
    for t in toks:
        if not t["claimed"] and _fuzz(t["norm"], _FIX_WORDS, 0.8):
            t["claimed"] = fix_hit = True
    # mode/fix with no action word means "check this" — the only action they fit
    if action is None and (mode_hit or clean_hit or fix_hit):
        action = "check"
    if action == "check":
        if mode_hit:
            args["mode"] = "clean_verbatim" if clean_hit else "full_verbatim"
        elif clean_hit:
            args["mode"] = "clean_verbatim"
        if fix_hit:
            args["fix"] = True

    trigger_pos = hits.get(action, -1)

    if action == "check":
        # exact profile tokens first ("legal", "dt", "en") — an exact profile
        # name beats the same word's domain reading (profile=legal is the CVL
        # study profile he actually runs; domain legal remains reachable as
        # "legal domain" via the LLM path or --domain by hand)
        for i, t in enumerate(toks):
            if (not t["claimed"] and t["norm"] in vocab["profiles"]
                    and _risky_ok(toks, i)):
                t["claimed"] = True
                args.setdefault("profile", t["norm"])
        for t in toks:
            if not t["claimed"]:
                d = t["norm"] if t["norm"] in vocab["domains"] else (
                    _fuzz(t["norm"], set(vocab["domains"]), 0.75)
                    if len(t["norm"]) >= 4 else None)
                if d:
                    t["claimed"] = True
                    args.setdefault("domain", d)
        for t in toks:
            if not t["claimed"]:
                s = t["norm"] if t["norm"] in vocab["sites"] else (
                    _fuzz(t["norm"], set(vocab["sites"]), 0.75)
                    if len(t["norm"]) >= 4 else None)
                if s:
                    t["claimed"] = True
                    args.setdefault("site", s)
        # long-word fuzzy against profile names ("legl" -> legal); short codes
        # already handled exactly above
        for t in toks:
            if not t["claimed"] and len(t["norm"]) >= 4:
                p = _fuzz(t["norm"], {p for p in vocab["profiles"]
                                      if len(p) >= 4 and ":" not in p}, 0.75)
                if p:
                    t["claimed"] = True
                    args.setdefault("profile", p)
        # a language word IS the profile choice for check ("japnse" -> ja)
        for i, t in enumerate(toks):
            if not t["claimed"]:
                code = _lang_hit(t["norm"], vocab)
                if code:
                    t["claimed"] = True             # claim even when not assigned
                    if _risky_ok(toks, i):
                        args.setdefault("profile", code)

    elif action == "ears":
        # lang AFTER the trigger wins ("ar eth ears alive ja" -> ja, not the
        # garbled "ar"); pre-trigger hits are claimed so they don't echo as noise
        for i, t in enumerate(toks):
            if not t["claimed"]:
                code = _lang_hit(t["norm"], vocab)
                if code:
                    t["claimed"] = True
                    if i > trigger_pos and _risky_ok(toks, i):
                        args["lang"] = code         # last post-trigger hit wins

    elif action == "translate":
        # "to X" marks the TARGET; any other language mention is the source
        for i, t in enumerate(toks):
            if not t["claimed"]:
                code = _lang_hit(t["norm"], vocab)
                if code and _risky_ok(toks, i):
                    t["claimed"] = True
                    prev = toks[i - 1]["norm"] if i else ""
                    if prev in ("to", "into", "in", "ot", "2"):
                        args["tgt"] = code
                    elif prev == "from" or "src" not in args:
                        args["src"] = code
                elif code:
                    t["claimed"] = True

    # residual language-code claim for every other action so a stray "ja" in
    # "ship it ja" degrades to claimed-but-unused instead of "couldn't place"
    for t in toks:
        if not t["claimed"] and _lang_hit(t["norm"], vocab):
            t["claimed"] = True

    if action in _PATH_SLOTS:
        _fill_path_slots(args, action, paths)

    # stopwords LAST — filler can never shadow a registry value this way
    for t in toks:
        if not t["claimed"] and (t["norm"] in _STOPWORDS
                                 or _fuzz(t["norm"], _STOPWORDS, 0.85)):
            t["claimed"] = True

    unrecognized = [t["raw"] for t in toks if not t["claimed"] and t["norm"]]
    return {"action": action, "args": args, "unrecognized": unrecognized}


# ---------------------------------------------------------------------------
# proposer (a): small LOCAL LLM — optional, lazy, never trusted
# ---------------------------------------------------------------------------

_GEN = None            # cached generate(prompt)->str; False = probed, unavailable


def _load_backend():
    """Best available LOCAL backend, loaded once. mlx_lm first (Apple Silicon,
    model already in the HF cache), llama_cpp second ($TT_INTENT_MODEL gguf —
    the HP path), else False. Import errors and load errors both mean 'no
    model', never a crash: the keyword proposer is always behind us."""
    import importlib.util as _ilu
    if _ilu.find_spec("mlx_lm") is not None:
        try:
            from mlx_lm import load, generate
            model, tok = load(_MLX_MODEL)
            def _gen(prompt):
                p = tok.apply_chat_template(
                    [{"role": "user", "content": prompt}],
                    add_generation_prompt=True, tokenize=False)
                return generate(model, tok, prompt=p, max_tokens=160,
                                verbose=False)
            return _gen
        except Exception:
            pass
    gguf = os.environ.get("TT_INTENT_MODEL", "")
    if gguf and os.path.exists(gguf) and _ilu.find_spec("llama_cpp") is not None:
        try:
            from llama_cpp import Llama
            llm = Llama(model_path=gguf, n_ctx=2048, verbose=False)
            def _gen(prompt):
                out = llm.create_chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=160, temperature=0.0)
                return out["choices"][0]["message"]["content"]
            return _gen
        except Exception:
            pass
    return False


def _llm_generate(prompt):
    """Raw completion from the local model, or None when there is no model /
    it failed. Lazy + cached so a REPL pays the load once. Never raises — the
    deterministic fallback must always get its turn. TT_NO_LLM=1 skips outright
    (and the tests monkeypatch this function, so no model ever loads offline)."""
    global _GEN
    if os.environ.get("TT_NO_LLM"):
        return None
    if _GEN is False:
        return None
    try:
        if _GEN is None:
            _GEN = _load_backend()
        if not _GEN:
            _GEN = False
            return None
        return _GEN(prompt)
    except Exception:
        return None


def _build_prompt(utterance, vocab):
    """Registry vocabulary + few-shots in his REAL garbled style. The few-shots
    are the spec: garbled in, ONE strict-JSON proposal out. Values outside the
    lists are told to go to "unrecognized" — and validate() enforces it anyway."""
    return (
        "You convert ONE utterance from a transcription operator into ONE JSON "
        "command proposal. He types with difficulty, so words are garbled — map "
        "them to the closest allowed value. Output ONLY the JSON object.\n\n"
        "Actions (with their allowed args):\n"
        "  check(file, profile, site, domain, mode, fix) - QA a transcript\n"
        "  ship(file, audio)          - ship gate, then QA\n"
        "  earcheck(draft, audio)     - ear-verify draft flags against the audio\n"
        "  ears(lang)                 - witness liveness preflight\n"
        "  translate(audio, src, tgt) - translate an audio file\n"
        "  coverage()                 - language/layer coverage table\n"
        "  list-profiles()            - list available profiles\n"
        "Allowed values (anything else goes in \"unrecognized\"):\n"
        f"  profile: {', '.join(vocab['profiles'])}\n"
        f"  site: {', '.join(vocab['sites'])}\n"
        f"  domain: {', '.join(vocab['domains'])}\n"
        f"  lang/src/tgt: {', '.join(vocab['langs'])}\n"
        f"  mode: {', '.join(vocab['modes'])}\n"
        "Examples:\n"
        "utterance: chek this japnse file for gotranscipt\n"
        '{"action":"check","args":{"profile":"ja","site":"gotranscript"}}\n'
        "utterance: er check it agianst the audio\n"
        '{"action":"earcheck","args":{}}\n'
        "utterance: ship it\n"
        '{"action":"ship","args":{}}\n'
        "utterance: ar eth ears alive\n"
        '{"action":"ears","args":{"lang":"ja"}}\n'
        "utterance: ears alive ru\n"
        '{"action":"ears","args":{"lang":"ru"}}\n'
        "utterance: translat this japnse audio to englsh\n"
        '{"action":"translate","args":{"src":"ja","tgt":"en"}}\n'
        "utterance: full verbtim chek job.txt\n"
        '{"action":"check","args":{"file":"job.txt","mode":"full_verbatim"}}\n'
        "utterance: fix it\n"
        '{"action":"check","args":{"fix":true}}\n'
        "utterance: list profils\n"
        '{"action":"list-profiles","args":{}}\n'
        f"utterance: {utterance}\n"
    )


def _extract_json(text):
    """First parseable {...} object anywhere in the model's output — models wrap
    JSON in prose and code fences, so raw_decode is tried from every brace, not
    just the first (a stray '{' in the chatter must not kill a good object)."""
    dec = json.JSONDecoder()
    for m in re.finditer(r"\{", text or ""):
        try:
            obj, _ = dec.raw_decode(text[m.start():])
            if isinstance(obj, dict):
                return obj
        except ValueError:
            continue
    return None


def _llm_propose(utterance, vocab):
    """LLM proposal dict, or None on ANY failure (no model, empty output, no
    parseable JSON). The caller treats None as 'fall to the keyword proposer'."""
    out = _llm_generate(_build_prompt(utterance, vocab))
    if not out:
        return None
    obj = _extract_json(out)
    return obj if isinstance(obj, dict) and obj else None


# ---------------------------------------------------------------------------
# parse_intent — the one front door
# ---------------------------------------------------------------------------

def _apply_files(config, files):
    """Explicit files from `tt "…" draft.md audio.mp3` fill the action's still-
    empty path slots (same audio/text classification as utterance tokens)."""
    if config["action"] and files:
        _fill_path_slots(config["args"], config["action"], list(files))


def parse_intent(utterance, files=None):
    """utterance (+ optional explicit files) -> validated config:
        {"action", "args": {...}, "unrecognized": [...], "confidence", "source"}

    The LLM (when a local one exists) proposes first; validate() strips anything
    the registry doesn't know. Even a CLEAN LLM proposal is backfilled from the
    deterministic keyword parse when the actions agree — the live 1.5B dropped
    "japnse"→profile entirely during the design smoke test, and a model must
    never silently LOSE what registry matching found. A partial/hallucinated
    proposal is MERGED the other way (validated model fields win, keyword fills
    gaps, the union of unrecognized survives so nothing invented disappears
    silently). With no model at all the keyword path carries everything.
    Confidence is a fixed ladder, not a model score: 0.9 clean-LLM / 0.6 merged
    / 0.5 keyword / 0.0 no action — deterministic on the fallback path by
    construction."""
    vocab = vocabulary()
    kw = validate(_keyword_propose(utterance, files, vocab), vocab)
    raw = _llm_propose(utterance, vocab)

    if raw is not None:
        # A real local 1.5B can emit VALID JSON with the wrong SHAPE (args as a list, action
        # non-hashable) — validate() then throws and, unguarded, that crashed tt instead of
        # degrading (verifier-found 2026-07-24). A malformed proposal is just a failed
        # proposal: the deterministic fallback must always get its turn.
        try:
            v = validate(raw, vocab)
        except Exception:
            raw = None
    if raw is None:
        config = dict(kw)
        conf, src = (0.5 if kw["action"] else 0.0), "keyword"
    else:
        if v["action"] and not v["unrecognized"]:
            config, conf, src = dict(v), 0.9, "llm"
            if kw["action"] == v["action"]:
                # both proposals validated; a field only the keyword pass found
                # is registry truth the model dropped, not a guess — restore it
                config["args"] = dict(config["args"])
                for k, val in kw["args"].items():
                    config["args"].setdefault(k, val)
        else:
            action = v["action"] or kw["action"]
            if action:
                # keyword args first (filtered to the winning action's spec),
                # validated model fields on top
                args = {k: val for k, val in kw["args"].items()
                        if k in ACTIONS[action]}
                args.update(v["args"])
            else:
                args = {}
            unrec = v["unrecognized"] + [u for u in kw["unrecognized"]
                                         if u not in v["unrecognized"]]
            config = {"action": action, "args": args, "unrecognized": unrec}
            conf, src = (0.6 if action else 0.0), "llm+keyword"

    config["args"] = dict(config.get("args") or {})
    _apply_files(config, files)
    config["confidence"] = conf
    config["source"] = src
    return config
