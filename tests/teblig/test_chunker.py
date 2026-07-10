"""teblig/chunker.py — madde bölme + tebliğ-sonu ek kırpma + bölüm hiyerarşisi.

Testlerin çoğu 1283 gerçek tebliğ üzerinde ÖLÇÜLEN davranışı kilitler (ADR-0014: türler arası
sıfır kod paylaşımı; kanun testleri ayrı kopya).
"""
import pytest

from teblig.chunker import (
    Birim,
    split_birimler,
    split_bolumler,
    _strip_teblig_sonu_ek,
    _sirali_kosu,
    _MIN_GOVDE,
)

P = "\x1f"   # paragraf sınırı (strip_html koyar)


# ── MADDE bölme (baskın durum: 1283 tebliğin %96'sı) ────────────────

def test_madde_bolme_temel():
    m = f"Amaç{P}MADDE 1 - (1) Bu Tebliğ amacı...{P}Kapsam{P}MADDE 2 - (1) Kapsam şudur."
    bs = split_birimler(m)
    assert [b.no for b in bs] == ["1", "2"]
    assert all(b.tip == "madde" for b in bs)
    assert "Bu Tebliğ amacı" in bs[0].body


def test_madde_prefix_ek_gecici():
    m = f"MADDE 1 - (1) A.{P}Geçici MADDE 1 - (1) B.{P}Ek MADDE 2 - (1) C."
    assert [b.no for b in split_birimler(m)] == ["1", "Geçici 1", "Ek 2"]


# ── TEBLİĞ-SONU EK KIRPMA (ölçüm: 38 tebliğ, 107 sahte madde, 0 gerçek kayıp) ──

def test_ek_form_kuyrugu_kirpilir():
    """Ek-2B maliyet formundaki 'Hammadde 1 (Raw Material 1)' satırı 'Madde 1 (' sanılıyordu.
    Gerçek veri: 350781 (İthalatta Gözetim) — 9 gerçek madde + 2 sahte."""
    m = (f"MADDE 8 - (1) Bu Tebliğ yayımı tarihinde yürürlüğe girer.{P}"
         f"MADDE 9 - (1) Bu Tebliğ hükümlerini Ticaret Bakanı yürütür.{P}"
         f"Ek-1{P}GÖZETİM BELGESİ BAŞVURU FORMU{P}"
         f"Hammadde 1 (Raw Material 1){P}Yardımcı Madde 2 (Auxiliary Material 2){P}" + "x" * 200)
    bs = split_birimler(m)
    assert [b.no for b in bs] == ["8", "9"]          # sahte 1 ve 2 elendi
    assert "Raw Material" not in bs[-1].body


def test_tumu_buyuk_cetvel_kuyrugu_kirpilir():
    """VUK tebliğlerinde 'MADDE 104  İlanın şekli  30.000' tablo satırı madde sanılıyordu.
    Gerçek veri: 350586 — 5 gerçek madde + 18 sahte."""
    m = (f"MADDE 5 - (1) Bu Tebliğ hükümlerini Hazine ve Maliye Bakanı yürütür.{P}"
         f"VERGİ USUL KANUNUNDA YER ALAN VE UYGULANACAK OLAN HAD VE TUTARLARA İLİŞKİN LİSTE{P}"
         f"MADDE 104 - İlanın şekli 30.000{P}MADDE 177 - Bilanço hesabı 2.000.000")
    bs = split_birimler(m)
    assert [b.no for b in bs] == ["5"]


def test_mesru_kucuk_harf_kuyruk_kirpilmaz():
    """Anchor sonrası kuyruk ne 'Ek-N' ne tümü-büyük → KIRPMA YOK (0-FP kapısı)."""
    m = (f"MADDE 3 - (1) Bu Tebliğ hükümlerini Ticaret Bakanı yürütür.{P}"
         + "Bu hüküm yayımı tarihinde uygulanmaya başlanır ve ilgili kurumlarca izlenir. " * 3)
    assert _strip_teblig_sonu_ek(m) == m


def test_anchor_yoksa_kirpilmaz():
    m = f"MADDE 1 - (1) A." + P + "SOME TAIL " * 20
    assert _strip_teblig_sonu_ek(m) == m


def test_kisa_kuyruk_kirpilmaz():
    m = f"MADDE 9 - (1) Bu Tebliğ hükümlerini Bakan yürütür.{P}EK-1"
    assert _strip_teblig_sonu_ek(m) == m       # <30 karakter kuyruk


# ── SIRALI KOŞU (kanun _bentler koşu mantığının karşılığı) ──────────

def test_sirali_kosu_temel():
    assert _sirali_kosu(["1", "2", "3", "4"]) == 4


def test_sirali_kosu_ust_bolumde_sifirlanir():
    """'I-' altında 1,2,3 → 'II-' altında yine 1,2 → koşu kırılmaz, yeniden başlar."""
    assert _sirali_kosu(["1", "2", "3", "1", "2"]) == 3


def test_sirali_kosu_tablo_satiri_kirilir():
    """'1. Yıl / 2. Yıl / 1. Yıl' gibi tablo satırları sıçrar (350474'te gerçek veri)."""
    assert _sirali_kosu(["5", "9", "2", "7"]) <= 1


def test_sirali_kosu_ondalik_son_parcaya_bakar():
    assert _sirali_kosu(["2.1", "2.2", "2.3"]) == 3


# ── BÖLÜM HİYERARŞİSİ (MADDE yoksa) ────────────────────────────────

def _govde(n=400):
    return "İçerik cümlesi burada devam eder. " * (n // 33)


def test_roma_bolum_tek_seviye():
    """120106 deseni: yalnız roma başlık, alt seviye yok."""
    m = (f"I- AMAÇ VE KAPSAM{P}{_govde()}{P}"
         f"II- DAYANAK{P}{_govde()}{P}"
         f"III- TANIMLAR{P}{_govde()}")
    bs = split_birimler(m)
    assert [b.no for b in bs] == ["I", "II", "III"]
    assert all(b.tip == "bolum" and not b.ust for b in bs)
    assert bs[0].baslik.startswith("AMAÇ")


def test_roma_ust_n_tire_alt_atomik():
    """120107 deseni: 'I-' üst bölüm gövdesi dev (ölçüm: medyan 40.739 krk, tavanı aşar),
    altındaki '1-' alt-başlıkları atomik birim olur (medyan 2.433 krk)."""
    m = (f"I- KESİNLEŞMİŞ ALACAKLAR{P}"
         f"1- Alacağın Türü{P}{_govde()}{P}"
         f"2- İşletme Kayıtları{P}{_govde()}{P}"
         f"3- Belediye Alacakları{P}{_govde()}{P}"
         f"II- DAVA SAFHASINDAKİ ALACAKLAR{P}"
         f"1- Dava Konusu{P}{_govde()}{P}"
         f"2- Uzlaşma{P}{_govde()}")
    bs = split_birimler(m)
    assert [b.no for b in bs] == ["1", "2", "3", "1", "2"]
    assert bs[0].ust == [("I", "KESİNLEŞMİŞ ALACAKLAR")]
    assert bs[-1].ust == [("II", "DAVA SAFHASINDAKİ ALACAKLAR")]


def test_ondalik_seviye_secimi_en_az_tavan_asan():
    """Ölçüm (350474, 613K): 'en derin seviye' kuralı 28 birim + 195K dev chunk üretiyordu.
    Doğru kural: en az tavan-aşan seviye. Burada seviye 2 seçilmeli (seviye 1 gövdesi dev)."""
    ust = "A" * 30000            # seviye-1 gövdesi tavanı aşacak kadar büyük
    m = (f"1. Birinci Bolum{P}{ust}{P}"
         f"1.1. Alt Bir{P}{_govde()}{P}"
         f"1.2. Alt Iki{P}{_govde()}{P}"
         f"1.3. Alt Uc{P}{_govde()}{P}"
         f"2. Ikinci Bolum{P}"
         f"2.1. Alt Bir{P}{_govde()}{P}"
         f"2.2. Alt Iki{P}{_govde()}")
    bs = split_birimler(m)
    assert all(b.tip == "bolum" for b in bs)
    assert [b.no for b in bs] == ["1.1", "1.2", "1.3", "2.1", "2.2"]
    assert bs[0].ust and bs[0].ust[0][0] == "1"       # üst zincir doğru bağlandı


def test_ondalik_ust_zincir_onek_uyumlu():
    """'2.1' yalnız '2'nin altına bağlanmalı (konum çakışması yetmez, önek de uymalı).
    Seviye-1 gövdesi tavanı aşacak kadar büyük → seviye-2 atomik birim olur."""
    dev = "A" * 30000
    m = (f"1. Bir{P}{dev}{P}1.1. Bir Bir{P}{_govde()}{P}1.2. Bir Iki{P}{_govde()}{P}"
         f"2. Iki{P}2.1. Iki Bir{P}{_govde()}{P}2.2. Iki Iki{P}{_govde()}")
    bs = split_bolumler(m)
    d = {b.no: [u[0] for u in b.ust] for b in bs}
    assert d.get("1.1") == ["1"]
    assert d.get("2.1") == ["2"]
    assert d.get("2.2") == ["2"]


def test_sirali_kosu_onek_bazli():
    """Ondalık koşu ÖNEK bazında sayılır: '1.1,1.2' ve '2.1,2.2' ayrı gruplar (her biri 2).
    Düz sayımda son parçalar 1,2,1,2 olur → yanlış sonuç verirdi."""
    assert _sirali_kosu(["1.1", "1.2", "2.1", "2.2"]) == 2
    assert _sirali_kosu(["1.1", "2.1"]) == 1          # her grupta tek eleman: sıralılık kanıtı yok


def test_cetvel_listesi_bolum_sayilmaz():
    """106345 deseni: '1. Form A  2. Form B ...' — medyan gövde < _MIN_GOVDE → bölüm DEĞİL.
    Aksi halde 51 adet ~91 karakterlik çöp birim üretiliyordu."""
    m = P.join(f"{i}. Butce cetveli Form {i}" for i in range(1, 12))
    assert split_bolumler(m) == []


def test_bolum_yoksa_bos_liste():
    m = "Bilindiği üzere bu tebliğ yayımlanmıştır. " * 20
    assert split_birimler(m) == []          # çağıran (corpus) tek-chunk'a düşer


def test_madde_bolumden_once_gelir():
    """MADDE varsa bölüm deseni aranmaz (öncelik sırası)."""
    m = f"I- BOLUM{P}MADDE 1 - (1) Hüküm.{P}MADDE 2 - (1) Hüküm."
    bs = split_birimler(m)
    assert all(b.tip == "madde" for b in bs)
    assert [b.no for b in bs] == ["1", "2"]


def test_tek_bolum_isareti_yetersiz():
    """Tek eşleşme desen değil rastlantı olabilir → _MIN_BOLUM=2."""
    assert split_bolumler(f"I- TEK BASLIK{P}{_govde()}") == []
