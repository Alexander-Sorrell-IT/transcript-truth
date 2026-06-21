"""transcript-truth audio command -- point it at audio (+ optionally a transcript)
and get a plain-English receipt of every place the transcript doesn't match the audio.

  # check a transcript against its audio:
  python -m transcript_truth.check_audio clip.wav --transcript draft.txt

  # inline text:
  python -m transcript_truth.check_audio clip.wav --text "群島や湖では..."

  # no transcript? it transcribes, then self-checks against a 2nd independent read:
  python -m transcript_truth.check_audio clip.wav

Every flag is readable without knowing the language: kana sounds + English glosses.
"""
import argparse, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.verdict import verify


def asr(path, lang, model="medium"):
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(path, language=lang, task="transcribe")
    return "".join(s.text for s in segs).strip()


def main(argv=None):
    p = argparse.ArgumentParser(prog="transcript-truth audio")
    p.add_argument("audio", help="path to audio file (wav/mp3/flac)")
    p.add_argument("--transcript", help="path to the transcript to check")
    p.add_argument("--text", help="the transcript text inline (instead of a file)")
    p.add_argument("--lang", default="ja", help="language code (default ja)")
    p.add_argument("--model", default="medium", help="whisper size (default medium)")
    a = p.parse_args(argv)

    if not os.path.exists(a.audio):
        p.error(f"audio not found: {a.audio}")

    print(f"listening to {os.path.basename(a.audio)} ...", flush=True)
    evidence = asr(a.audio, a.lang, a.model)   # independent read of the audio

    if a.text:
        claim = a.text.strip()
    elif a.transcript:
        claim = open(a.transcript, encoding="utf-8").read().strip()
    else:
        print("(no transcript given -- self-checking against a second read)\n")
        claim = evidence
        evidence = asr(a.audio, a.lang, "small")

    flags = verify(claim, evidence)
    print("\n" + "=" * 64)
    print(f"TRANSCRIPT : {claim}")
    print(f"AUDIO SAYS : {evidence}")
    print("=" * 64)
    if not flags:
        print("RECEIPT: clean -- the transcript matches the audio.")
        return 0
    print(f"RECEIPT: {len(flags)} place(s) to check\n")
    for i, f in enumerate(flags, 1):
        print(f"{i}. [{f['layer']}/{f['verdict']}]")
        print(f"     transcript: {f['claim']}")
        print(f"     audio     : {f['audio']}")
        print(f"     why       : {f['why']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
