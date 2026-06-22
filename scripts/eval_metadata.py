# scripts/eval_metadata.py
"""Faz 3 metadata enrichment doğrulaması — kanun-only cache'inde invariant kontrolü.

Çalıştırma: ./.venv/Scripts/python.exe scripts/eval_metadata.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from mevzuat_tool.normalize import normalize_text
from mevzuat_tool.chunker import split_articles
from mevzuat_tool.tree import parse_tree
from mevzuat_tool.enrich import enrich

LAWS = {"TCK": "103228", "VUK": "103006", "KVKK": "104383", "GVK": "103111"}


def _load(mid: str):
    content = pathlib.Path(f"data/raw/content_{mid}.md").read_text(encoding="utf-8")
    tree_txt = pathlib.Path(f"data/raw/tree_{mid}.txt").read_text(encoding="utf-8")
    arts = split_articles(normalize_text(content))
    maddeler, _dipnotlar = enrich(arts, parse_tree(tree_txt), mid)
    return maddeler


def _load_full(mid: str):
    content = pathlib.Path(f"data/raw/content_{mid}.md").read_text(encoding="utf-8")
    tree_txt = pathlib.Path(f"data/raw/tree_{mid}.txt").read_text(encoding="utf-8")
    arts = split_articles(normalize_text(content))
    return enrich(arts, parse_tree(tree_txt), mid)  # (maddeler, dipnotlar)


for label, mid in LAWS.items():
    maddeler = _load(mid)
    asil = sum(1 for m in maddeler if m.madde_tipi == "asil")
    pref = len(maddeler) - asil
    eksik = sum(1 for m in maddeler if m.madde_tipi == "asil" and m.maddeId is None)
    print(f"{label}: {len(maddeler)} madde (asil={asil}, prefixli={pref}, ağaçta-yok-asil={eksik})")

# TCK invariant'lar (gerekceId suffix'li ağaç satırları parse edilmeli)
tck = {m.no: m for m in _load("103228")}
assert tck["1"].maddeId is not None, "TCK Madde 1 maddeId null — gerekceId suffix regex'i bozuk!"
assert tck["1"].madde_baslik, "TCK Madde 1 başlık boş — ağaç join başarısız!"
tck_eksik = sum(1 for m in _load("103228") if m.madde_tipi == "asil" and m.maddeId is None)
assert tck_eksik < 5, f"TCK'da {tck_eksik} asil madde ağaçta yok — gerekceId regex'i hâlâ bozuk!"
print(f"\n[OK] TCK invariant'lar geçti (Madde 1 join OK, agaçta-yok-asil={tck_eksik}).")

# GVK-spesifik invariant'lar
gvk = {m.no: m for m in _load("103111")}
assert "YEDİNCİ BÖLÜM" not in gvk["79"].body, "Madde 79 sızması temizlenmedi!"
assert gvk["84"].madde_baslik == "Beyanname çeşitleri", f"Madde 84 başlık yanlış: {gvk['84'].madde_baslik!r}"
assert "Geçici 84" in gvk and gvk["Geçici 84"].madde_tipi == "gecici", "Geçici 84 flag yanlış!"
print("[OK] GVK invariant'lar geçti (79 sızmasız, 84 başlık='Beyanname çeşitleri', Geçici 84 flag='gecici').")

# --- Faz 3 follow-up invariant'ları (GVK) ---
gvk_maddeler, gvk_dipnotlar = _load_full("103111")
gvk = {m.no: m for m in gvk_maddeler}

# #1 dipnot apendiksi: Geçici 5 body_temiz << ham article (83K) olmalı; apendiks ayrıldı.
# Madde.body zaten apendiks-ayrilmis govdedir (~25K); raw article 83418 krk idi.
# Apendiksin ayrildiginin kaniti: global dipnot sayisi 221 ve body_temiz < 30000.
if "Geçici 5" in gvk:
    ham = len(gvk["Geçici 5"].body)
    temiz = len(gvk["Geçici 5"].body_temiz)
    assert temiz < 30000, \
        f"Gecici 5 body_temiz siski: {temiz} krk (ham article 83418'di; apendiks ayrilmadi?)"

# #2 dipnotlar global listede toplandı.
assert len(gvk_dipnotlar) > 50, f"GVK global dipnot sayısı düşük: {len(gvk_dipnotlar)} — apendiks ayrıştırma eksik!"

# #5 fıkra/bent: Madde 70 birden çok bent içerir.
if "70" in gvk:
    toplam_bent = sum(len(f.bentler) for f in gvk["70"].fikralar)
    assert toplam_bent >= 5, f"Madde 70 bent sayısı düşük: {toplam_bent} — bent bölme eksik!"

# #3 değişiklik künyeleri: en az bir maddede yapısal künye var.
assert any(m.degisiklik_gecmisi for m in gvk_maddeler), "GVK'da hiç değişiklik künyesi parse edilmedi!"
ornek = next(k for m in gvk_maddeler for k in m.degisiklik_gecmisi if k.kanun_no)
assert ornek.kanun_no, "Değişiklik künyesinde kanun_no boş!"

# #7 benzersiz id: tüm id'ler çakışmasız.
ids = [m.id for m in gvk_maddeler]
assert len(ids) == len(set(ids)), "GVK'da çakışan chunk id'leri var — benzersiz id bozuk!"

print("[OK] Follow-up invariant'lar geçti (dipnot ayrıldı, künyeler parse, Madde 70 bentli, id benzersiz).")
