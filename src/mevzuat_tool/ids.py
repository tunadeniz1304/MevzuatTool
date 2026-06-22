"""Benzersiz chunk id atama (Faz 3 follow-up #7).

Çifte madde no (iki ayrı `Geçici 1`) ve sonek maddeler (`123/A`) için çakışmasız id üretir.
Faz 4 JSONL `{id, ...}` bu id'ye dayanır. Deterministik (content sırasına bağlı).
"""


def slug(no: str) -> str:
    # Türkçe karakter sadeleştir, boşluk/eğik çizgi at.
    s = (no
         .replace("ç", "c").replace("Ç", "C")
         .replace("ğ", "g").replace("Ğ", "G")
         .replace("ı", "i").replace("İ", "I")
         .replace("ş", "s").replace("Ş", "S")
         .replace("ü", "u").replace("Ü", "U")
         .replace("ö", "o").replace("Ö", "O"))
    return "".join(ch for ch in s if ch.isalnum())


def assign_ids(maddeler, kanun_no: str) -> None:
    # Önce her slug için kaç kez geçtiğini say (çakışma tespiti).
    sayim: dict[str, int] = {}
    for m in maddeler:
        sayim[slug(m.no)] = sayim.get(slug(m.no), 0) + 1
    gorulen: dict[str, int] = {}
    for m in maddeler:
        s = slug(m.no)
        if sayim[s] > 1:
            gorulen[s] = gorulen.get(s, 0) + 1
            m.id = f"{kanun_no}-{s}-{gorulen[s]}"
        else:
            m.id = f"{kanun_no}-{s}"
