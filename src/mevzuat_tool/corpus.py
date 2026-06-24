"""Madde → RAG korpus chunk ({id, text, metadata}) dönüşümü (Faz 4 — temiz korpus artifact).

Modüler sınır (CLAUDE.md): bağımsız teslim edilebilir JSONL `{id, text, metadata}`.
  - text   = madde_baslik + body_temiz → embedding girdisi (anlamsal arama bunun üzerinde).
  - metadata = hiyerarşi + yürürlük + kaynak + fıkra/bent ağacı + değişiklik künyeleri +
               dipnot/tablo. Filtreleme (yürürlük), atıf (kanun_no+madde_no), gösterim için.
Boş-gövde maddeler (içeriksiz işlenmiş maddeler) korpusa GİRMEZ. Mülga DAHİL ama işaretli
(tarihsel sorgu için; yurutluk='mülga' ile filtrelenebilir).
"""
from dataclasses import asdict

from mevzuat_tool.enrich import Madde


def _text(m: Madde) -> str:
    """Embedding girdisi: başlık varsa ilk satır olarak başa, ardından temiz gövde."""
    govde = (m.body_temiz or m.body or "").strip()
    if m.madde_baslik:
        return f"{m.madde_baslik}\n{govde}".strip()
    return govde


def madde_to_chunk(m: Madde, kanun_ad: str) -> dict | None:
    """Bir Madde'yi korpus chunk'ına çevir. Boş gövde → None (filtrelenir)."""
    govde = (m.body_temiz or m.body or "").strip()
    if not govde:
        return None
    return {
        "id": m.id or f"{_kanun_no_from_id(m)}-{m.no}",
        "text": _text(m),
        "metadata": {
            "kanun_no": _kanun_no_from_id(m),
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


def _kanun_no_from_id(m: Madde) -> str:
    """id 'KANUNNO-MADDENO' biçimindedir (assign_ids); kanun_no'yu oradan al."""
    if m.id and "-" in m.id:
        return m.id.rsplit("-", 1)[0]
    return ""


def maddeler_to_chunks(maddeler, kanun_ad: str) -> list[dict]:
    """Madde listesini korpus chunk listesine çevir; boş-gövde maddeleri eler."""
    out = []
    for m in maddeler:
        c = madde_to_chunk(m, kanun_ad)
        if c is not None:
            out.append(c)
    return out
