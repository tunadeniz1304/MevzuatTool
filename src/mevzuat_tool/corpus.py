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


_PREFIX_ETIKET = {"gecici": "Geçici", "ek": "Ek", "mukerrer": "Mükerrer"}


def _hiyerarsi_yolu(m: Madde) -> str | None:
    """hiyerarsi_yolu'nun sonundaki donor 'Madde N' parçasını chunk'ın GERÇEK etiketiyle düzelt.
    enrich, Geçici/Ek/Mükerrer maddelere son ASIL maddenin yolunu miras verir → son 'Madde N'
    yanlış (Bug 3). Bölüm/kısım bağlamı korunur, sadece terminal 'Madde N' düzeltilir."""
    hy = m.hiyerarsi_yolu
    if hy is None or m.madde_tipi == "asil":
        return hy
    # madde_no 'Geçici 1' / 'Ek 2' → etiket 'Geçici Madde 1' / 'Ek Madde 2'
    prefix = _PREFIX_ETIKET.get(m.madde_tipi)
    if not prefix:
        return hy
    sira = m.no.split(None, 1)[1] if " " in m.no else m.no
    etiket = f"{prefix} Madde {sira}"
    return re.sub(r"Madde \S+$", etiket, hy)


def _saf_artefakt(govde: str) -> bool:
    """Gövde sadece fıkra-no '(1)' / dipnot '[2]' / madde-no '24-' artefaktından mı ibaret?
    Bu işaretler + boşluk + noktalama çıkınca geriye <3 anlamlı harf kalıyorsa gerçek metin yok
    (Bug 4: 104624-10 '(1) (2) (3)', 103829-66 '[27]', 104863-1 '4 -'). Embedding gürültüsü."""
    cekirdek = re.sub(r"\(\d+\)|\[\d+\]|\d+|[\s.;,\-]", "", govde)
    return len(cekirdek) < 3


def _tablo_duz(md_tablo: str) -> str:
    """Markdown tabloyu DÜZ metne çevir (strip_html'in body'ye gömdüğü form). '|' ayraçları ve
    '---' hizalama satırı kaldırılır, boşluk normalize edilir. '| Sıra | İl |\\n|---|\\n| 1 |
    ANKARA |' → 'Sıra İl 1 ANKARA'."""
    satirlar = [s for s in md_tablo.splitlines() if not re.match(r"^\s*\|?[\s:|-]*\|?\s*$", s)]
    duz = " ".join(s.replace("|", " ") for s in satirlar)
    return re.sub(r"\s+", " ", duz).strip()


def _govde_tablosuz(m: Madde) -> str:
    """body_temiz'den tabloları çıkar. enrich markdown tabloyu body_temiz'e gömüyor AMA strip_html
    DÜZLEŞTİRİLMİŞ formu ('Sıra No İl 1 ANKARA...') da text'e koyabilir (Bug 1: 6749 M12 = 160K).
    Hem markdown formu hem düz formu çıkar. Tablo metadata.tablolar'da yapısal kalır (kayıpsız)."""
    govde = (m.body_temiz or m.body or "").strip()
    for tablo in (m.tablolar or []):
        govde = govde.replace("\n\n" + tablo, "").replace(tablo, "")
        # düzleştirilmiş form: boşluk-normalize karşılaştırmayla çıkar (markdown ↔ düz farkını yut)
        duz = _tablo_duz(tablo)
        if duz and len(duz) > 20:
            govde_norm = re.sub(r"\s+", " ", govde)
            i = govde_norm.find(duz)
            if i != -1:
                # düz tabloyu (boşluk-normalize konumundan) çıkarmak için orijinal govde'de eşle
                govde = re.sub(re.escape(duz).replace(r"\ ", r"\s+"), " ", govde, count=1)
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
    govde_t = _govde_tablosuz(m)
    if not govde_t:
        return None      # tablo çıkınca metin kalmadı (sadece-tablo/başlık)
    # Saf artefakt ('(1) (2)', '[27]', '24-') → filtrele (embedding gürültüsü). AMA mülga maddeyi
    # ELEME: mülga gövdesi künye temizlenince '(1)' gibi görünür ama tarihsel sorgu için tutulur
    # (CLAUDE.md ilke 5; yurutluk='mülga' ile işaretli). Sadece YÜRÜRLÜKTEKİ artefaktlar elenir.
    if m.yurutluk != "mülga" and _saf_artefakt(govde_t):
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
            "hiyerarsi_yolu": _hiyerarsi_yolu(m),
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
