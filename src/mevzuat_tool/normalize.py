import re

_DASHES = ("–", "—", "‒")  # – — ‒ → -


def normalize_text(raw: str) -> str:
    text = raw
    for d in _DASHES:
        text = text.replace(d, "-")
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)  # tek satır kırığı → boşluk; \n\n korunur
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()
