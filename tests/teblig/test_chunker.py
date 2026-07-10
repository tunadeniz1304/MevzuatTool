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
    _azalan_kardesleri_ele,
    _ONDALIK,
    _MIN_GOVDE,
    _MIN_GIRIS,
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


def test_yaprak_maksimum_granulerite_dala_gore_degisir():
    """Sabit seviye YOK: her dal kendi derinliğine kadar iner (350474'te derinlik 1..5).
    '1.' hiç alt-numarası olmadığı için yaprak; '2.1.1' derin dalda yaprak."""
    m = (f"1. Tanimlar{P}{_govde()}{P}"
         f"2. Verginin Konusu{P}{_govde()}{P}"
         f"2.1. Konu{P}{_govde()}{P}"
         f"2.1.1. Alt Konu{P}{_govde()}{P}"
         f"2.1.2. Diger Alt Konu{P}{_govde()}{P}"
         f"2.2. Kapsam{P}{_govde()}")
    bs = split_bolumler(m)
    nolar = [b.no for b in bs]
    assert "1" in nolar                    # alt-numarası yok → yaprak
    assert "2.1.1" in nolar and "2.1.2" in nolar   # en derin dal alındı
    assert "2.2" in nolar                  # kardeş dal kendi derinliğinde


def test_ara_dugum_girisi_kaybolmaz_ayri_birim_olur():
    """ÖLÇÜM (350474): 82 ara düğümün 82'si de gerçek hüküm metni taşıyor; salt-başlık YOK.
    Bunları atmak metnin %22.7'sini (139.021 krk) aranamaz hale getiriyordu.
    '2.1' hem giriş metni hem alt-bölüm taşıyorsa: giriş AYRI birim, alt-bölümler AYRI."""
    m = (f"2.1. Verginin konusu{P}{_govde(500)}{P}"
         f"2.1.1. Konsolide hasilat siniri{P}{_govde()}{P}"
         f"2.1.2. Ikinci alt{P}{_govde()}")
    bs = split_bolumler(m)
    nolar = [b.no for b in bs]
    assert "2.1" in nolar, "ara düğümün giriş metni birim olmalı (içerik kaybı)"
    assert "2.1.1" in nolar and "2.1.2" in nolar
    giris = next(b for b in bs if b.no == "2.1")
    assert "2.1.1" not in giris.body, "giriş, çocuğunun metnini yutmamalı"


def test_ara_dugum_salt_baslik_ise_birim_olmaz():
    """ÖLÇÜM (328127): 17 ara düğümün 14'ü salt başlık (57-68 krk), hemen alt başlığı gelir.
    Bunlar birim DEĞİL — `ust` metadata'sında yaşar. Aksi halde 14 çöp chunk."""
    m = (f"4.4. ATIK ile ilgili hususlar{P}"          # < _MIN_GIRIS → salt başlık
         f"4.4.1. Birinci{P}{_govde()}{P}"
         f"4.4.2. Ikinci{P}{_govde()}")
    bs = split_bolumler(m)
    nolar = [b.no for b in bs]
    assert "4.4" not in nolar, "salt başlık birim olmamalı"
    assert nolar == ["4.4.1", "4.4.2"]
    assert bs[0].ust == [("4.4", "ATIK ile ilgili hususlar")]


def test_ondalik_ust_zincir_onek_uyumlu():
    """'2.1' yalnız '2'nin altına bağlanmalı (konum çakışması yetmez, önek de uymalı)."""
    m = (f"1. Bir{P}{_govde()}{P}1.1. Bir Bir{P}{_govde()}{P}1.2. Bir Iki{P}{_govde()}{P}"
         f"2. Iki{P}{_govde()}{P}2.1. Iki Bir{P}{_govde()}{P}2.2. Iki Iki{P}{_govde()}")
    bs = split_bolumler(m)
    d = {b.no: [u[0] for u in b.ust] for b in bs}
    assert d.get("1.1") == ["1"]
    assert d.get("2.1") == ["2"]
    assert d.get("2.2") == ["2"]


# ── AZALAN-KARDEŞ ELEME (tablo satırı '1. Yıl / 2. Yıl / 3. Yıl') ───

def test_azalan_kardes_tablo_satiri_elenir():
    """ÖLÇÜM (350474): metin sonundaki tablo `1. Yıl`, `2. Yıl`, `3. Yıl` başlıkları
    kök bölüm numaralarıyla ÇAKIŞIYOR (no benzersiz değil, konum benzersiz).
    Aynı önek altında numara GERİ giderse o işaret bölüm değildir (kanun `_bentler` koşusu).
    Ölçülen kapı: 4/4 sahte elendi, 0 gerçek kurban."""
    m = (f"1. Tanimlar{P}{_govde()}{P}"
         f"2. Verginin Konusu{P}{_govde()}{P}"
         f"3. Muafiyet{P}{_govde()}{P}"
         f"1. Yil{P}2. Yil{P}3. Yil{P}Kazanc 100 EUR")   # tablo: 1'e geri döner
    isaretler = list(_ONDALIK.finditer(m))
    temiz = _azalan_kardesleri_ele(isaretler)
    assert [x.group(1) for x in temiz] == ["1", "2", "3"]
    assert len(isaretler) == 6 and len(temiz) == 3


def test_azalan_kardes_farkli_onek_gerileme_sayilmaz():
    """'2.3' → '3.1': önek değişti (2 → 3), son parça 3→1 düştü ama bu GERİLEME DEĞİL.
    Aksi halde her yeni üst-bölümün ilk çocuğu elenirdi."""
    m = (f"2.1. Bir{P}{_govde()}{P}2.2. Iki{P}{_govde()}{P}2.3. Uc{P}{_govde()}{P}"
         f"3.1. Bir{P}{_govde()}{P}3.2. Iki{P}{_govde()}")
    isaretler = list(_ONDALIK.finditer(m))
    assert len(_azalan_kardesleri_ele(isaretler)) == len(isaretler)


def test_azalan_kardes_esitlik_de_elenir():
    """Aynı önek altında aynı numara iki kez → ikincisi sahte (tekrar eden tablo başlığı)."""
    m = (f"1. Bir{P}{_govde()}{P}2. Iki{P}{_govde()}{P}2. Iki Tekrar{P}{_govde()}")
    isaretler = list(_ONDALIK.finditer(m))
    temiz = _azalan_kardesleri_ele(isaretler)
    assert [x.group(1) for x in temiz] == ["1", "2"]


def test_azalan_kardes_kapisi_split_bolumler_icinde_uygulanir():
    """ENTEGRASYON (mutasyon testiyle bulunan boşluk): `_azalan_kardesleri_ele` yalnız
    doğrudan çağrıldığında değil, `_ondalik_bolumler` AKIŞINDA da devrede olmalı.
    Kapıyı akıştan silmek birim testlerini kırmıyordu — bu test kırar.

    Gerçek veri (350474): metin sonundaki `1. Yıl / 2. Yıl / 3. Yıl` tablosu kök
    bölümlerle aynı no'yu taşır; elenmezse yaprak ağacı bozulur ve `2` iki kez birim olur."""
    m = (f"1. Tanimlar{P}{_govde()}{P}"
         f"2. Verginin Konusu{P}{_govde()}{P}"
         f"2.1. Alt Konu{P}{_govde()}{P}"
         f"2.2. Diger Alt{P}{_govde()}{P}"
         f"3. Muafiyet{P}{_govde()}{P}"
         f"1. Yil{P}2. Yil{P}3. Yil{P}Kazanc 100 EUR ve digerleri burada listelenir.")
    nolar = [b.no for b in split_bolumler(m)]
    assert len(nolar) == len(set(nolar)), f"tablo satırı elenmedi, no tekrar ediyor: {nolar}"
    # `2` dolgun girişi olan ara düğüm → kendisi de birim (bkz. test_ara_dugum_girisi_kaybolmaz)
    assert nolar == ["1", "2", "2.1", "2.2", "3"]
    # Elenen İŞARET'tir, METİN değil: tablo `3` biriminin gövdesinde kalır (içerik kaybı yok).
    assert "Yil" in next(b for b in split_bolumler(m) if b.no == "3").body


def test_roma_alti_nokta_ayracli_alt_baslik_yakalanir():
    """ÖLÇÜM (107458): roma altındaki alt-başlıklar TİRE değil NOKTA kullanıyor
    (`1. Dijital Ortamda Sunulan Reklam Hizmetleri`). Yalnız tire arayan desen bunları
    göremiyordu → 36.191 krk'lık tek roma bloğu (BGE-M3 tavanını 1.45× aşıyor).
    Ayraç [-–.] olunca: 0 → 18 birim, max 10.370 krk, dev chunk YOK.
    Gürültü kontrolü: 106785/120107'de birim sayısı DEĞİŞMEDİ (100, 107)."""
    m = (f"I- VERGININ KONUSU{P}"
         f"1. Dijital Ortamda Sunulan Reklam Hizmetleri{P}{_govde()}{P}"
         f"2. Dijital Ortamda Yapilan Icerik Satislari{P}{_govde()}{P}"
         f"II- MUKELLEF{P}"
         f"1. Mukellef{P}{_govde()}{P}"
         f"2. Vergi Sorumlusu{P}{_govde()}")
    bs = split_birimler(m)
    assert [b.no for b in bs] == ["1", "2", "1", "2"]
    assert all(b.tip == "bolum" for b in bs)
    assert bs[0].ust == [("I", "VERGININ KONUSU")]
    assert bs[-1].ust == [("II", "MUKELLEF")]


def test_roma_alt_basligi_olmayan_bolum_kendisi_yaprak_olur():
    """ÖLÇÜM (105921): 6 roma bölümünün yalnız 1'inde alt-başlık var. Alt seçilince
    diğer 5'in içeriği (I- VERGİNİN KONUSU 10.321 krk, V- MATRAH 7.137 krk …) KAYBOLUYORDU
    — alt kapsama yalnız %5.8. 107458/106785/120107'de de her birinde 1 roma kayıp.

    Ondalık ailedeki yaprak kuralının roma karşılığı: alt-başlığı OLMAYAN roma bölümü
    kendisi atomik birimdir."""
    m = (f"I- VERGININ KONUSU{P}{_govde(600)}{P}"          # alt-başlığı yok → kendisi yaprak
         f"II- MUKELLEF{P}"
         f"1- Gercek Kisiler{P}{_govde()}{P}"
         f"2- Tuzel Kisiler{P}{_govde()}")
    bs = split_birimler(m)
    nolar = [b.no for b in bs]
    assert "I" in nolar, "alt-başlığı olmayan roma bölümü kaybolmamalı"
    assert "1" in nolar and "2" in nolar
    roma_birim = next(b for b in bs if b.no == "I")
    assert not roma_birim.ust
    assert next(b for b in bs if b.no == "1").ust == [("II", "MUKELLEF")]


def test_roma_alti_dolgun_giris_ayri_birim_olur():
    """Roma bölümünün hem giriş metni hem alt-başlıkları varsa giriş de birim olur
    (ondalık `_MIN_GIRIS` kuralının roma karşılığı)."""
    m = (f"I- GENEL{P}{_govde(500)}{P}"                    # dolgun giriş
         f"1- Birinci Alt{P}{_govde()}{P}"
         f"2- Ikinci Alt{P}{_govde()}{P}"
         f"II- OZEL{P}"
         f"1- Baska Alt{P}{_govde()}{P}"
         f"2- Diger Alt{P}{_govde()}")
    bs = split_birimler(m)
    nolar = [b.no for b in bs]
    assert "I" in nolar, "dolgun roma girişi birim olmalı"
    assert nolar.count("1") == 2 and nolar.count("2") == 2
    giris = next(b for b in bs if b.no == "I")
    assert "Birinci Alt" not in giris.body, "giriş, alt-başlığın metnini yutmamalı"


def test_roma_salt_baslik_girisi_birim_olmaz():
    """`I- BASLIK` hemen ardından `1-` geliyorsa giriş salt başlıktır → birim değil."""
    m = (f"I- GENEL{P}1- Birinci{P}{_govde()}{P}2- Ikinci{P}{_govde()}{P}"
         f"II- OZEL{P}1- Ucuncu{P}{_govde()}{P}2- Dorduncu{P}{_govde()}")
    nolar = [b.no for b in split_birimler(m)]
    assert "I" not in nolar and "II" not in nolar
    assert nolar == ["1", "2", "1", "2"]


def test_ntire_sicrayan_numara_bolum_sayilmaz():
    """ÖLÇÜM (107811): roma yok, N- işaretleri ['3','4','1','2','6','10','2','3'] —
    koşu/n = 0.25, ilk işaretten önce metnin %11.4'ü var. Bunlar bölüm başlığı değil,
    madde-içi bent numaraları; içlerinde `a) b) c)` bentleri var ve 74.512 krk'lık
    dev chunk üretiyorlardı. Koşu ORANI kapısı bunu eler."""
    m = (f"Giris paragrafi burada. {_govde()}{P}"
         f"3- Bir Konu{P}{_govde()}{P}4- Baska{P}{_govde()}{P}"
         f"1- Farkli{P}{_govde()}{P}2- Digeri{P}{_govde()}{P}"
         f"6- Atlayan{P}{_govde()}{P}10- Cok Atlayan{P}{_govde()}")
    assert split_bolumler(m) == [], "sıçrayan numaralar bölüm sayılmamalı"


def test_ntire_sirali_cogunluk_bolum_sayilir():
    """Karşı-test: numaralar ardışıksa (1,2,3,4) N- kolu meşrudur — kapı bunu elemez."""
    m = P.join(f"{i}- Bolum Basligi{P}{_govde()}" for i in range(1, 6))
    bs = split_bolumler(m)
    assert [b.no for b in bs] == ["1", "2", "3", "4", "5"]


def test_roma_alti_numara_her_bolumde_1e_doner_elenmez():
    """ÖLÇÜM (106785): `I-` altında 1..6, `II-` altında yine 1..24 — 1'e dönüş MEŞRU.
    Ondalık ailedeki azalan-kardeş kapısı buraya UYGULANMAZ: önek numarada değil konumda.
    Uygulasaydık 100 birimin ~90'ı silinirdi."""
    m = (f"I- BIRINCI{P}1- Alt Bir{P}{_govde()}{P}2- Alt Iki{P}{_govde()}{P}"
         f"II- IKINCI{P}1- Alt Bir{P}{_govde()}{P}2- Alt Iki{P}{_govde()}")
    bs = split_birimler(m)
    assert [b.no for b in bs] == ["1", "2", "1", "2"], "1'e dönüş elenmemeli"
    assert len(bs) == 4


def test_sirali_kosu_onek_bazli():
    """Ondalık koşu ÖNEK bazında sayılır: '1.1,1.2' ve '2.1,2.2' ayrı gruplar (her biri 2).
    Düz sayımda son parçalar 1,2,1,2 olur → yanlış sonuç verirdi."""
    assert _sirali_kosu(["1.1", "1.2", "2.1", "2.2"]) == 2
    assert _sirali_kosu(["1.1", "2.1"]) == 1          # her grupta tek eleman: sıralılık kanıtı yok


# ── PARAGRAF-BAŞI GEVŞETMESİ (aynı paragrafta sıkışmış alt-başlık) ──

def test_ayni_paragrafta_sikismis_alt_baslik_yakalanir():
    """ÖLÇÜM (350474): `2.1.1.` metinde 11 kez geçiyor, paragraf başında yalnız 1 kez.
    HTML'de `2.1. Verginin konusu 2.1.1. Konsolide hasılat sınırı` tek <p>.
    Gevşetme +18 gerçek başlık kazandırdı, +0 gürültü (328127'de +0)."""
    m = f"2.1. Verginin konusu 2.1.1. Konsolide hasilat siniri{P}{_govde()}{P}2.2. Kapsam{P}{_govde()}"
    nolar = [x.group(1) for x in _ONDALIK.finditer(m)]
    assert "2.1.1" in nolar, "aynı paragrafta sıkışmış alt-başlık yakalanmalı"


def test_cumle_ici_ondalik_rakam_baslik_sayilmaz():
    """Gevşetme cümle-içi rakamlara kapı açmamalı: `... 2.1. maddesinde` küçük harfle devam eder.
    Büyük-harf şartı bu yanlış-pozitifi eler (0-FP kapısı)."""
    m = f"1. Genel{P}Bu husus 2.1. maddesinde duzenlenmistir ve 3.2. bendine atifta bulunur.{P}{_govde()}"
    nolar = [x.group(1) for x in _ONDALIK.finditer(m)]
    assert "2.1" not in nolar and "3.2" not in nolar


def test_cumle_sonu_sonrasi_rakam_baslik_sayilmaz():
    """Nokta+boşluk sonrası rakam cümle numarası olabilir; gevşetme yalnız KELİME sonrası
    (cümle-sonu DEĞİL) devreye girer."""
    m = f"1. Genel{P}Hukum boyledir. 2.1. Bir Sonraki{P}{_govde()}"
    nolar = [x.group(1) for x in _ONDALIK.finditer(m)]
    assert nolar.count("2.1") == 0


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
