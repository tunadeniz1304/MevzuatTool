import re

# Tire-varyantları → normal hyphen (U+002D). Madde markerinde görülen tüm Unicode tireler:
# U+2010 hyphen, U+2011 non-breaking hyphen, U+2012 figure dash, U+2013 en dash,
# U+2014 em dash, U+2015 horizontal bar, U+2212 minus sign. (U+2212 [6223] kanununda
# madde markerini bozuyordu → chunker 0 parça çıkarıyordu.)
_DASHES = ("‐", "‑", "‒", "–", "—", "―", "−")  # ‐ ‑ ‒ – — ― − → -


def normalize_text(raw: str) -> str:
    text = raw
    text = text.replace("­", "")  # soft-hyphen (görünmez kelime-bölme ipucu) → kaldır
    for d in _DASHES:
        text = text.replace(d, "-")
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)  # tek satır kırığı → boşluk; \n\n korunur
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()
