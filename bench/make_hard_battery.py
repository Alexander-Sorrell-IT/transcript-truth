#!/usr/bin/env python3
"""Generate HARD test clips (macOS `say` + ffmpeg) with exact ground truth, into bench/battery/.

The existing battery is clean single-voice TTS where every ASR witness agrees, so multi-model
voting has nothing to resolve. These clips create genuine DISAGREEMENT — the condition the
consensus is built for: British accent + noise, overlapping crosstalk, and a proper-noun/number
dense read. Ground truth is the exact text we synthesized. Prefix `hard_` so they're easy to select.
"""
import os, subprocess, json

BAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "battery")
os.makedirs(BAT, exist_ok=True)


def _say(text, voice, out_aiff, rate=180):
    subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", out_aiff, text], check=True)


def _to_wav(inp, out, extra_filter=None):
    cmd = ["ffmpeg", "-y", "-i", inp]
    if extra_filter:
        cmd += ["-filter_complex", extra_filter]
    cmd += ["-ac", "1", "-ar", "16000", out, "-loglevel", "error"]
    subprocess.run(cmd, check=True)


def _dur(path):
    out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                          "-of", "json", path], capture_output=True, text=True)
    return float(json.loads(out.stdout)["format"]["duration"])


def _write(name, text, speakers):
    json.dump({"text": text, "speakers": speakers},
              open(os.path.join(BAT, name + ".json"), "w"), indent=1)
    print(f"  {name:20} {_dur(os.path.join(BAT, name + '.wav')):.1f}s  '{text[:48]}...'")


def accent_noise():
    """British accent + additive pink noise -> witnesses mishear differently."""
    text = ("The quarterly report from Siobhan and Njoroge showed a fourteen percent rise "
            "in the Ljubljana division before the audit.")
    aiff = os.path.join(BAT, "_tmp.aiff"); _say(text, "Daniel", aiff)
    clean = os.path.join(BAT, "_tmp.wav"); _to_wav(aiff, clean)
    d = _dur(clean)
    # mix voice with pink noise at a moderate SNR (noise ~0.18 gain)
    out = os.path.join(BAT, "hard_accent_noise.wav")
    subprocess.run(["ffmpeg", "-y", "-i", clean, "-f", "lavfi", "-t", f"{d:.2f}",
                    "-i", "anoisesrc=color=pink:amplitude=0.18",
                    "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:weights=1 0.9[a]",
                    "-map", "[a]", "-ac", "1", "-ar", "16000", out, "-loglevel", "error"], check=True)
    os.remove(aiff); os.remove(clean)
    _write("hard_accent_noise", text, [{"start": 0.0, "end": round(d, 2), "speaker": "A"}])


def crosstalk():
    """Two voices that OVERLAP in the middle -> the hard diarization + word-separation case."""
    t1 = "So did the shipment from Reykjavik clear customs on Thursday morning as planned?"
    t2 = "Not yet, they flagged the manifest and I am still waiting on the broker to call back."
    a1 = os.path.join(BAT, "_a.aiff"); _say(t1, "Alex", a1)
    a2 = os.path.join(BAT, "_b.aiff"); _say(t2, "Samantha", a2)
    w1 = os.path.join(BAT, "_a.wav"); _to_wav(a1, w1)
    w2 = os.path.join(BAT, "_b.wav"); _to_wav(a2, w2)
    d1 = _dur(w1)
    delay_ms = int(d1 * 1000 * 0.6)      # speaker B starts at 60% of A -> partial overlap
    out = os.path.join(BAT, "hard_crosstalk.wav")
    subprocess.run(["ffmpeg", "-y", "-i", w1, "-i", w2, "-filter_complex",
                    f"[1:a]adelay={delay_ms}|{delay_ms}[b];[0:a][b]amix=inputs=2:duration=longest[a]",
                    "-map", "[a]", "-ac", "1", "-ar", "16000", out, "-loglevel", "error"], check=True)
    for f in (a1, a2, w1, w2):
        os.remove(f)
    total = _dur(out)
    _write("hard_crosstalk", t1 + " " + t2,
           [{"start": 0.0, "end": round(d1, 2), "speaker": "A"},
            {"start": round(d1 * 0.6, 2), "end": round(total, 2), "speaker": "B"}])


def propernouns():
    """Dense proper nouns + numbers -> the accuracy frontier (the Eleanor/Elena error class)."""
    text = ("Dr. Nguyen and Ms. Okonkwo transferred forty-seven thousand euros to the "
            "Kagiso account in Gaborone on the third of March twenty twenty-five.")
    aiff = os.path.join(BAT, "_p.aiff"); _say(text, "Alex", aiff)
    out = os.path.join(BAT, "hard_propernouns.wav"); _to_wav(aiff, out)
    os.remove(aiff)
    _write("hard_propernouns", text, [{"start": 0.0, "end": round(_dur(out), 2), "speaker": "A"}])


if __name__ == "__main__":
    print("generating hard battery clips...")
    accent_noise(); crosstalk(); propernouns()
    print("done -> bench/battery/hard_*.wav (+ .json ground truth)")
