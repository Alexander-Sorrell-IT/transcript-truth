"""Deterministic clean-verbatim finishing pass (no model). Removes standalone fillers
wherever they sit (not just comma-trailed) and fixes mixed-script punctuation (English
word + full-width 。/、 -> half-width). Pairs with the `mixed_punctuation` scanner so the
auditor flags what this fixes.
"""
import re

# Vocalic hesitations — never meaning-bearing, remove anywhere (with trailing 、, space, or none).
_FILLERS_ALWAYS = ["えーと", "えーっと", "えっと", "ええと", "ええっと", "えー",
                   "あのー", "あのう", "そのー", "うーん", "んーと", "あー", "うー"]
# Demonstratives that are fillers ONLY before English or when comma-set-off (あの人=that person stays).
_FILLERS_CTX = ["あの", "その", "なんか", "まあ", "まぁ"]


def clean_verbatim_finish(text):
    for f in _FILLERS_ALWAYS:
        text = re.sub(rf"{f}[、,]?\s*", "", text)
    for f in _FILLERS_CTX:
        text = re.sub(rf"{f}[、,]\s*", "", text)            # comma-set-off -> filler
        text = re.sub(rf"{f}\s+(?=[A-Za-z])", "", text)     # right before English -> filler
    # English word followed by full-width punctuation -> English punctuation
    text = re.sub(r"([A-Za-z])。", r"\1. ", text)
    text = re.sub(r"([A-Za-z])、", r"\1, ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return re.sub(r" +\n", "\n", text)
