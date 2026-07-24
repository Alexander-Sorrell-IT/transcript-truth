"""Regression pin for the T4791286 incident (Japanese GoTranscript channel lost, 2026-07).

ROSTER["ja"] listed four witnesses, but "hf" (HuggingFace Whisper API) was 402-depleted and
returned "" on every call — so Japanese jobs SILENTLY ran on three live ears while the roster
claimed four. Nothing mechanical caught it; the unverified draft shipped and was rated 1/5
("way too many mishears"). Fix pinned here: the free LOCAL whisper witness (mlx-whisper on
the M1 GPU) sits in the ja roster itself, ordered before "hf", so a dead cloud quota can never
again thin the panel. "hf" stays — it degrades gracefully to "" and may get credits back — and
shares ONE vote-family with "whisper" by design (same base weights), so the live local read
adds coverage without ever double-counting a Whisper vote.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.consensus import FAMILY, ROSTER


def test_local_whisper_is_in_ja_roster():
    assert "whisper" in ROSTER["ja"]               # live local ear — a 402 can't kill it


def test_local_whisper_ordered_before_dead_prone_hf():
    ja = ROSTER["ja"]
    assert ja.index("whisper") < ja.index("hf")    # local first; hf kept for graceful degrade / credit return


def test_whisper_and_hf_share_one_vote_family():
    assert FAMILY["whisper"] == FAMILY["hf"]       # same base weights — never double-counted
