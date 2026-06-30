#!/usr/bin/env python3
"""Phase 1 — build a worst-case battery with EXACT ground truth.

We generate the audio from text we control (macOS `say` + ffmpeg), so the reference transcript
and speaker timeline are known perfectly — no manual transcription, no dataset downloads. Each
case targets one real failure mode. Reference saved as <case>.json {text, speakers:[{start,end,speaker}]}.

TTS audio is cleaner than real-world speech, so these numbers are an UPPER bound / pipeline check;
real hard clips get added to the same battery later. But it gives a reproducible baseline today.
"""
import os, json, subprocess, wave, contextlib

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "battery")
os.makedirs(OUT, exist_ok=True)
M, F = "Daniel", "Samantha"          # two distinct voices


def say(voice, text, path):
    aiff = path + ".aiff"
    subprocess.run(["say", "-v", voice, "-o", aiff, text], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", aiff, "-ac", "1", "-ar", "16000", path, "-loglevel", "error"], check=True)
    os.remove(aiff)


def dur(path):
    with contextlib.closing(wave.open(path)) as w:
        return w.getnframes() / w.getframerate()


def ff(args):
    subprocess.run(["ffmpeg", "-y", *args, "-loglevel", "error"], check=True)


def case(name, text, speakers):
    json.dump({"text": text, "speakers": speakers}, open(os.path.join(OUT, name + ".json"), "w"), indent=1)
    print(f"  {name}: {len(text.split())} words, {len(set(s['speaker'] for s in speakers))} speaker(s)")


CLEAN = "The quarterly report shows that revenue increased by fifteen percent this year."
NUMBERS = ("On March third, twenty twenty-five, Doctor Eleanor Vance met the board in Zurich "
           "to approve the forty-seven million dollar acquisition.")
A_LINE = "Did you finish the analysis we talked about on Tuesday?"
B_LINE = "Almost, I just need to double check the figures before the meeting."


def main():
    # 1) clean single speaker
    p = os.path.join(OUT, "clean.wav"); say(F, CLEAN, p)
    case("clean", CLEAN, [{"start": 0, "end": dur(p), "speaker": "S1"}])

    # 2) numbers + proper nouns (a known hard spot for ASR)
    p = os.path.join(OUT, "numbers.wav"); say(M, NUMBERS, p)
    case("numbers", NUMBERS, [{"start": 0, "end": dur(p), "speaker": "S1"}])

    # 3) fast speech (1.5x, pitch preserved)
    src = os.path.join(OUT, "clean.wav"); p = os.path.join(OUT, "fast.wav")
    ff(["-i", src, "-filter:a", "atempo=1.5", p])
    case("fast", CLEAN, [{"start": 0, "end": dur(p), "speaker": "S1"}])

    # 4) low SNR (clean + pink noise)
    p = os.path.join(OUT, "noisy.wav")
    ff(["-i", src, "-f", "lavfi", "-i", "anoisesrc=c=pink:a=0.04", "-filter_complex",
        "[1]atrim=0:30[n];[0][n]amix=inputs=2:duration=first", p])
    case("noisy", CLEAN, [{"start": 0, "end": dur(src), "speaker": "S1"}])

    # 5) two speakers, sequential turns (clean diarization)
    a = os.path.join(OUT, "_a.wav"); b = os.path.join(OUT, "_b.wav")
    say(F, A_LINE, a); say(M, B_LINE, b)
    dA, dB = dur(a), dur(b)
    p = os.path.join(OUT, "two_seq.wav")
    ff(["-i", a, "-i", b, "-filter_complex", "[0][1]concat=n=2:v=0:a=1", p])
    case("two_seq", A_LINE + " " + B_LINE,
         [{"start": 0, "end": dA, "speaker": "S1"}, {"start": dA, "end": dA + dB, "speaker": "S2"}])

    # 6) two speakers OVERLAPPING (crosstalk — the hard one)
    p = os.path.join(OUT, "two_overlap.wav")
    off = max(1.0, dA - 1.5)             # B starts before A finishes
    ff(["-i", a, "-i", b, "-filter_complex",
        f"[1]adelay={int(off*1000)}|{int(off*1000)}[b];[0][b]amix=inputs=2:duration=longest", p])
    case("two_overlap", A_LINE + " " + B_LINE,
         [{"start": 0, "end": dA, "speaker": "S1"}, {"start": off, "end": off + dB, "speaker": "S2"}])

    for t in ("_a.wav", "_b.wav"):
        fp = os.path.join(OUT, t)
        if os.path.exists(fp):
            os.remove(fp)
    print(f"battery written to {OUT}")


if __name__ == "__main__":
    main()
