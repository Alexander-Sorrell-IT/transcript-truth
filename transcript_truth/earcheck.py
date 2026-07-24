"""earcheck — the 3AM ear-verification loop a draft MUST pass through before FINISH.

The failure this exists to prevent: an engine draft full of ⚠ (engine-uncertain) spans
was submitted unheard, rated 1/5 "way too many mishears", channel lost. The draft
convention already marks every span that needs a human ear:
    ⚠            = engine-uncertain span, judge by ear (note follows the mark)
    **?Name:**    = speaker attribution unconfirmed, judge by ear
    **[MM:SS]**   = timestamp marker every ~2 min (also [HH:MM:SS], bold or plain)
Nothing mechanically walked those spans against the audio. This does: it steps through
every flagged span, ffmpeg-cuts just those seconds, plays them, and records a
one-keypress verdict. Single-key on purpose — the operator types with difficulty, so
the only typing is an *optional* dictated correction after choosing (e)dit.

Deterministic and stdlib-only: no model anywhere near a verdict — the human ear IS the
verdict here; the code only routes audio to it and writes down what it said.

Verdict file <draft>.ear.json is rewritten after EVERY keypress, so a 3AM bail-out
(q, Ctrl-C, sleep-crash) never loses work; re-running skips decided lines. An
(u)nresolved span is deliberately NOT skipped on resume — "u" means "come back to
this", so it re-queues until it gets a real keep/edit.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

# One regex for every stamp shape the drafts use: **[00:02:00]**, **[02:00]**, [02:00].
# Bold is optional because the convention says "bold in the GT editor" but plain-text
# drafts (and hand edits) drop the **. Bracketed only — (1:02:30) inline-time mentions
# in dialogue must NOT anchor the map.
_STAMP = re.compile(r"(?:\*\*)?\[(\d{1,2}):(\d{2})(?::(\d{2}))?\](?:\*\*)?")
# Unconfirmed-speaker label: **?Name:** at line start. The ? is the flag.
_UNSURE_SPEAKER = re.compile(r"^\*\*\?")
_FLAG = "⚠"


def _stamp_seconds(m):
    # 2 groups = [MM:SS], 3 = [HH:MM:SS]. Same regex, so group 3 disambiguates.
    if m.group(3) is not None:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    return int(m.group(1)) * 60 + int(m.group(2))


def parse_draft(text):
    """-> ordered [{line_no, text, flagged, approx_seconds}] for every content line.

    approx_seconds: markers give exact anchors on their own line; everything between
    two anchors is LINEARLY interpolated by line position (speech rate ~constant over
    2-min windows, and ±6s of playback padding absorbs the error). Before the first
    marker the draft starts at 00:00, so the first content line is an implicit 0.0
    anchor. After the last marker we extrapolate at the last segment's rate — better
    than clamping, which would stack every tail line onto the same clip.
    """
    lines = text.split("\n")

    # Anchors from ALL lines (a stamp on a header/comment line still anchors time).
    anchors = []
    for i, line in enumerate(lines, 1):
        m = _STAMP.search(line)
        if m:
            secs = _stamp_seconds(m)
            # A typo'd stamp that goes BACKWARD would un-order the whole map; drop it
            # rather than emit non-monotonic times (determinism > completeness).
            if not anchors or secs >= anchors[-1][1]:
                anchors.append((i, float(secs)))

    entries = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):   # blanks + header comments
            continue
        entries.append({
            "line_no": i,
            "text": stripped,
            "flagged": _FLAG in stripped or bool(_UNSURE_SPEAKER.match(stripped)),
            "approx_seconds": 0.0,   # filled below once the anchor map is complete
        })
    if not entries:
        return entries

    # Implicit start-of-draft anchor: first content line = 00:00 (unless a real stamp
    # already anchors at/before it).
    if not anchors or anchors[0][0] > entries[0]["line_no"]:
        anchors.insert(0, (entries[0]["line_no"], 0.0))

    for e in entries:
        e["approx_seconds"] = round(_interp(anchors, e["line_no"]), 1)
    return entries


def _interp(anchors, line_no):
    """Piecewise-linear line_no -> seconds over the anchor map. Monotonic by
    construction: anchors are (increasing line, non-decreasing seconds)."""
    if line_no <= anchors[0][0]:
        return anchors[0][1]
    for (l0, s0), (l1, s1) in zip(anchors, anchors[1:]):
        if line_no <= l1:
            return s0 + (s1 - s0) * (line_no - l0) / (l1 - l0)
    # Past the last anchor: extend at the last segment's seconds-per-line rate.
    if len(anchors) >= 2:
        (l0, s0), (l1, s1) = anchors[-2], anchors[-1]
        rate = (s1 - s0) / (l1 - l0)
    else:
        rate = 0.0   # single anchor = no rate info; flat beats a made-up slope
    return anchors[-1][1] + rate * (line_no - anchors[-1][0])


def cut_and_play(audio_path, center_s, before=6, after=6):
    """ffmpeg-cut [center-before, center+after] to a temp wav and afplay it (macOS).

    ANY failure degrades to a printed hint with the exact manual command — at 3AM a
    traceback here would kill the whole verification session over a playback hiccup.
    Returns True iff audio actually played.
    """
    start = max(0.0, float(center_s) - before)
    dur = float(before + after)
    tmp = os.path.join(tempfile.gettempdir(), "earcheck_%d.wav" % os.getpid())
    manual = ("ffmpeg -ss %.1f -t %.1f -i '%s' /tmp/clip.wav && afplay /tmp/clip.wav"
              % (start, dur, audio_path))
    try:
        # -ss before -i = fast seek; -ac 1 keeps the temp cut small. Output silenced:
        # ffmpeg noise on every span would bury the transcript text being judged.
        rc = subprocess.call(
            ["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", str(dur),
             "-i", audio_path, "-ac", "1", tmp],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if rc != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
            print("  (couldn't cut audio — check the file/seconds; manually: %s)" % manual)
            return False
        rc = subprocess.call(["afplay", tmp])
        if rc != 0:
            print("  (afplay failed — play it manually: %s)" % manual)
            return False
        return True
    except FileNotFoundError:
        print("  (need ffmpeg + afplay on PATH — brew install ffmpeg; manually: %s)" % manual)
        return False
    except Exception as e:                                     # noqa: BLE001
        print("  (playback error: %s — manually: %s)" % (e, manual))
        return False
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _getch():
    """One raw keypress, no Enter — the whole point is one-key verdicts for a hand
    that types with difficulty. Non-tty stdin (pipes) falls back to line reads so the
    tool still works when driven by a script; EOF means quit-and-save, never hang."""
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        return line[:1] if line else "q"
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    if ch == "\x03":            # raw mode eats Ctrl-C; re-raise so progress saves
        raise KeyboardInterrupt
    return ch


def _read_replacement():
    """The one place typing happens, and only when (e)dit was chosen. Own function so
    tests (and future dictation hookup) can swap it without touching the loop."""
    try:
        return input("  replacement> ").strip()
    except EOFError:
        return ""


def _resolution_path(draft_path):
    return draft_path + ".ear.json"


def _load_resolutions(path):
    """Missing/corrupt file -> start fresh, never traceback: a half-written json from
    a crash must not lock the operator out of his own session."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return [r for r in data.get("resolved", [])
                if isinstance(r, dict) and "line_no" in r and "decision" in r]
    except (OSError, ValueError):
        return []


def _save_resolutions(path, resolved, total_flagged):
    data = {
        # Sorted for stable diffs; the schema is the contract other tools read.
        "resolved": sorted(resolved, key=lambda r: r["line_no"]),
        "total_flagged": total_flagged,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _fmt_ts(seconds):
    s = int(round(seconds))
    if s >= 3600:
        return "%d:%02d:%02d" % (s // 3600, (s % 3600) // 60, s % 60)
    return "%02d:%02d" % (s // 60, s % 60)


def _record(resolved, line_no, decision, replacement=None):
    # Re-deciding a line (an old "unresolved" coming back) replaces, never duplicates.
    resolved[:] = [r for r in resolved if r["line_no"] != line_no]
    resolved.append({"line_no": line_no, "decision": decision,
                     "replacement": replacement})


def run(draft_path, audio_path):
    """Step through every still-open flagged span. Saves after EVERY verdict."""
    text = open(draft_path, encoding="utf-8").read()
    flagged = [e for e in parse_draft(text) if e["flagged"]]
    if not flagged:
        print("no ⚠ / **?Speaker:** spans in %s — nothing to ear-check."
              % os.path.basename(draft_path))
        return 0

    res_path = _resolution_path(draft_path)
    resolved = _load_resolutions(res_path)
    # keep/edit are decided; "unresolved" re-queues by design (u = "come back to it").
    done = {r["line_no"] for r in resolved if r["decision"] != "unresolved"}
    todo = [e for e in flagged if e["line_no"] not in done]

    print("earcheck — %d flagged span(s), %d already resolved, %d to go"
          % (len(flagged), len(flagged) - len(todo), len(todo)))
    if not todo:
        print("all resolved — verdicts in %s" % res_path)
        return 0
    print("keys: (k)eep as written  (e)dit  (u)nresolved  (r)eplay  (q)uit+save\n")

    try:
        for n, e in enumerate(todo, 1):
            print("[%d/%d] line %d @ %s" % (n, len(todo), e["line_no"],
                                            _fmt_ts(e["approx_seconds"])))
            print("  %s" % e["text"])
            cut_and_play(audio_path, e["approx_seconds"])
            while True:
                key = _getch().lower()
                if key == "r":
                    cut_and_play(audio_path, e["approx_seconds"])
                elif key == "k":
                    _record(resolved, e["line_no"], "keep")
                    print("  -> keep\n")
                    break
                elif key == "e":
                    _record(resolved, e["line_no"], "edit", _read_replacement())
                    print("  -> edited\n")
                    break
                elif key == "u":
                    _record(resolved, e["line_no"], "unresolved")
                    print("  -> unresolved (will re-queue next run)\n")
                    break
                elif key == "q":
                    _save_resolutions(res_path, resolved, len(flagged))
                    decided = sum(1 for r in resolved if r["decision"] != "unresolved")
                    print("saved %s — %d/%d decided; re-run to continue."
                          % (res_path, decided, len(flagged)))
                    return 0
                else:
                    print("  ? keys: k=keep  e=edit  u=unresolved  r=replay  q=quit+save")
            # Save per-verdict, not per-session: a crash mid-run loses ONE keypress max.
            _save_resolutions(res_path, resolved, len(flagged))
    except KeyboardInterrupt:
        _save_resolutions(res_path, resolved, len(flagged))
        decided = sum(1 for r in resolved if r["decision"] != "unresolved")
        print("\nsaved %s — %d/%d decided; re-run to continue."
              % (res_path, decided, len(flagged)))
        return 0

    open_count = sum(1 for r in resolved if r["decision"] == "unresolved")
    print("done — %d/%d resolved (%d unresolved will re-queue) -> %s"
          % (len(resolved), len(flagged), open_count, res_path))
    return 0
