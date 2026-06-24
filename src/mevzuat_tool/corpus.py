"""Madde → RAG korpus chunk ({id, text, metadata}) dönüşümü (Faz 4 — temiz korpus artifact).

Modüler sınır (CLAUDE.md): bağımsız teslim edilebilir JSONL `{id, text, metadata}`.
  - text   = madde_baslik + body_temiz → embedding girdisi (anlamsal arama bunun üzerinde).
  - metadata = hiyerarşi + yürürlük + kaynak + fıkra/bent ağacı + değişiklik künyeleri +
               dipnot/tablo. Filtreleme (yürürlük), atıf (kanun_no+madde_no), gösterim için.
Boş-gövde maddeler (içeriksiz işlenmiş maddeler) korpusa GİRMEZ. Mülga DAHİL ama işaretli
(tarihsel sorgu için; yurutluk='mülga' ile filtrelenebilir).
"""
import re
from dataclasses import asdict

from mevzuat_tool.enrich import Madde

# İçeriksiz yönlendirme notu: maddenin TÜM gövdesi '(... yerine işlenmiştir.)' veya
# '(... ile ilgili olup ... işlenmiştir.)' gibi bir nottan ibaret — gerçek hüküm BAŞKA kanuna
# işlenmiş, burada yok (değişiklik paketlerinde yaygın; RAG'a girerse boş/yanıltıcı sonuç).
# Yalnız gövde BAŞTAN SONA bu desense filtreler; içinde 'işlenmiştir' geçen GERÇEK madde dokunulmaz.
_ISLENMIS_NOTU = re.compile(
    r"^\(?\s*[^)]*?(?:yerine\s+işlenmiş|ile\s+ilgili\s+olup)[^)]*?\)?\.?\s*$",
    re.IGNORECASE,
)


def _sadece_islenmis_notu(govde: str) -> bool:
    """Gövde tamamen içeriksiz yönlendirme notu mu? (gerçek hüküm yok)."""
    return bool(_ISLENMIS_NOTU.match(govde.strip()))


def _govde_tablosuz(m: Madde) -> str:
    """body_temiz'den HTML tablolarını çıkar. enrich tabloları body_temiz sonuna '\\n\\n<md>'
    olarak gömüyor (tablolar alanında da yapısal duruyor). Embedding text'ine dev tablolar
    girmemeli (boyut aşımı + sayı-yığını anlamsal gürültü); tablo metadata.tablolar'da kalır."""
    govde = (m.body_temiz or m.body or "").strip()
    for tablo in (m.tablolar or []):
        govde = govde.replace("\n\n" + tablo, "").replace(tablo, "")
    return govde.strip()


def _text(m: Madde) -> str:
    """Embedding girdisi: başlık varsa ilk satır olarak başa, ardından temiz gövde (tablosuz)."""
    govde = _govde_tablosuz(m)
    if m.madde_baslik:
        return f"{m.madde_baslik}\n{govde}".strip()
    return govde


def madde_to_chunk(m: Madde, kanun_ad: str, kanun_no: str) -> dict | None:
    """Bir Madde'yi korpus chunk'ına çevir. Boş gövde VEYA sadece-işlenmiştir-notu → None.

    m.id mevzuatId tabanlıdır (enrich'e mid verilir → 'MID-madde'; globalde benzersiz).
    kanun_no AYRI parametredir: kanun numarası globalde benzersiz DEĞİL (6551 iki kanun) ve
    id çok-parçalı olabilir ('MID-5-3') → id'den parse güvenilmez."""
    govde = (m.body_temiz or m.body or "").strip()
    if not govde or _sadece_islenmis_notu(govde):
        return None
    text = _text(m)
    # Tablo çıkınca geriye anlamlı metin kalmadıysa (sadece-tablo / sadece-başlık madde) → filtrele.
    if not _govde_tablosuz(m):
        return None
    return {
        "id": m.id,
        "text": text,
        "metadata": {
            "kanun_no": kanun_no,
            "kanun_ad": kanun_ad,
            "madde_no": m.no,
            "madde_baslik": m.madde_baslik,
            "madde_tipi": m.madde_tipi,
            "yurutluk": m.yurutluk,
            "maddeId": m.maddeId,
            "kitap_no": m.kitap_no, "kitap_baslik": m.kitap_baslik,
            "kisim_no": m.kisim_no, "kisim_baslik": m.kisim_baslik,
            "bolum_no": m.bolum_no, "bolum_baslik": m.bolum_baslik,
            "ayirim_no": m.ayirim_no, "ayirim_baslik": m.ayirim_baslik,
            "hiyerarsi_yolu": m.hiyerarsi_yolu,
            # zengin: iç içe dataclass ağaçları asdict ile JSON-serileştirilebilir dict'e döner
            "fikralar": [asdict(f) for f in m.fikralar],
            "degisiklik_gecmisi": [asdict(d) for d in m.degisiklik_gecmisi],
            "dipnotlar": [asdict(d) for d in m.dipnotlar],
            "tablolar": list(m.tablolar),
        },
    }


def maddeler_to_chunks(maddeler, kanun_ad: str, kanun_no: str) -> list[dict]:
    """Madde listesini korpus chunk listesine çevir; boş-gövde + içeriksiz-not maddeleri eler."""
    out = []
    for m in maddeler:
        c = madde_to_chunk(m, kanun_ad, kanun_no)
        if c is not None:
            out.append(c)
    return out
