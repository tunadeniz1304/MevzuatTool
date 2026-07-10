"""corpus.py — Madde → RAG korpus chunk ({id, text, metadata}) dönüşümü (Faz 4).

text = madde_baslik + body_temiz (embedding girdisi). metadata zengin: hiyerarşi + yürürlük +
fıkra/bent ağacı + değişiklik künyeleri + dipnot/tablo. Boş-gövde maddeler filtrelenir
(içeriksiz işlenmiş maddeler — RAG'a gitmez). Mülga DAHİL ama yurutluk ile işaretli.
"""
from kanun.corpus import madde_to_chunk, maddeler_to_chunks
from kanun.enrich import enrich, Madde
from kanun.chunker import Article
from kanun.tree import parse_tree

TREE = parse_tree(
    "- ÜÇÜNCÜ BÖLÜM - Haklar ve Yükümlülükler (maddeId:10)\n"
    "  - Madde No: 11 - İlgili kişinin hakları: (maddeId:1643063)\n"
)


# id = mevzuatId (mid) tabanlı (globalde benzersiz; kanun_no tekrar edebilir — 6551 iki kanun).
# enrich'e mid verilir → m.id = 'MID-madde'. kanun_no madde_to_chunk'a AYRI parametre (id'den
# parse edilmez; '7084-5-3' gibi çok-parçalı id'de kanun_no yanlış parse olurdu).
MID = "104383"


def _madde(no, body):
    maddeler, _ = enrich([Article(no=no, body=body)], TREE, MID)
    return maddeler[0]


def test_chunk_id_and_text():
    m = _madde("11", "(1) Herkes, veri sorumlusuna başvurabilir.")
    c = madde_to_chunk(m, kanun_ad="KİŞİSEL VERİLERİN KORUNMASI KANUNU", kanun_no="6698")
    assert c["id"] == "104383-11"               # id MID tabanlı (benzersiz)
    # text = başlık + temiz gövde (başlık ilk satır, gövde ardından)
    assert c["text"].startswith("İlgili kişinin hakları")
    assert "Herkes, veri sorumlusuna başvurabilir." in c["text"]


def test_chunk_metadata_core_fields():
    m = _madde("11", "(1) Herkes başvurabilir.")
    c = madde_to_chunk(m, kanun_ad="KVKK", kanun_no="6698")
    md = c["metadata"]
    assert md["kanun_no"] == "6698"             # gerçek kanun_no (ayrı parametre, id'den DEĞİL)
    assert md["kanun_ad"] == "KVKK"
    assert md["madde_no"] == "11"
    assert md["madde_baslik"] == "İlgili kişinin hakları"
    assert md["yurutluk"] == "yürürlükte"
    assert md["bolum_no"] == "ÜÇÜNCÜ BÖLÜM"
    assert md["bolum_baslik"] == "Haklar ve Yükümlülükler"
    # null seviyeler de alan olarak DURUR (filtre tutarlılığı için)
    assert md["kitap_no"] is None


def test_chunk_metadata_embeds_fikra_tree():
    # Zengin metadata: fıkra/bent ağacı gömülü (dict listesi olarak, JSON-serileştirilebilir).
    m = _madde("11", "(1) Herkes, şu haklara sahiptir:\na) öğrenme,\nb) düzeltme isteme.")
    c = madde_to_chunk(m, kanun_ad="KVKK", kanun_no="6698")
    fk = c["metadata"]["fikralar"]
    assert isinstance(fk, list) and len(fk) == 1
    assert fk[0]["no"] == "(1)"
    assert [b["isaret"] for b in fk[0]["bentler"]] == ["a)", "b)"]


def test_text_excludes_flattened_table_form():
    # Bug 1: enrich tabloyu MARKDOWN olarak metadata'ya, ama strip_html DÜZLEŞTİRİLMİŞ formu
    # ('Sıra No İl 1 ANKARA...') text'e koyuyor. _govde_tablosuz markdown'ı arayıp düz formu
    # bulamıyordu → 160K dev chunk. Düzleştirilmiş tablo da text'ten çıkarılmalı (gerçek veri 6749 M12).
    markdown = "| Sıra | İl |\n| --- | --- |\n| 1 | ANKARA |\n| 2 | İZMİR |"
    # body'de tablo DÜZ form olarak (strip_html çıktısı gibi) gömülü:
    duz = "Sıra İl 1 ANKARA 2 İZMİR"
    arts = [Article(no="103", body=f"(1) Bu Kanunu Bakanlar Kurulu yürütür. {duz}")]
    maddeler, _ = enrich(arts, TREE, MID, html_tables={"103": [markdown]})
    c = madde_to_chunk(maddeler[0], kanun_ad="X", kanun_no="6698")
    assert "Bakanlar Kurulu yürütür" in c["text"]      # gerçek madde korunur
    assert "ANKARA" not in c["text"]                    # düz tablo formu çıkarıldı
    assert "İZMİR" not in c["text"]
    assert c["metadata"]["tablolar"] == [markdown]      # markdown metadata'da durur


def test_text_excludes_tables_but_metadata_keeps_them():
    # Tablolar embedding text'ine GİRMEZ (dev tablolar embedding'i aşırır + anlamsal gürültü),
    # ama metadata.tablolar'da yapısal DURUR (kaybolmaz, erişilebilir). enrich body_temiz'e
    # tabloyu gömüyor → corpus text üretirken çıkarılır.
    tablo = "| dilim | oran |\n| --- | --- |\n| 18.000 TL | %15 |\n| 40.000 TL | %20 |"
    arts = [Article(no="103", body="(1) Gelir vergisi şu tarifeye göre alınır:")]
    maddeler, _ = enrich(arts, TREE, MID, html_tables={"103": [tablo]})
    c = madde_to_chunk(maddeler[0], kanun_ad="GVK", kanun_no="193")
    assert "tarifeye göre alınır" in c["text"]        # gerçek gövde korunur
    assert "%15" not in c["text"]                      # tablo text'e GİRMEDİ
    assert "| dilim |" not in c["text"]
    assert c["metadata"]["tablolar"] == [tablo]        # tablo metadata'da DURUYOR


_TREE_H = parse_tree(
    "- ÜÇÜNCÜ BÖLÜM - Son Hükümler (maddeId:10)\n"
    "  - Madde No: 84 - Asıl madde: (maddeId:840)\n"
)


def test_hiyerarsi_yolu_gecici_uses_own_label():
    # Bug 3: Geçici/Ek maddede hiyerarsi_yolu sonu donor 'Madde N' yerine kendi etiketini ('Geçici
    # Madde 1') kullanmalı. enrich cur_path'i son ASIL maddeden miras alır → son 'Madde N' yanlış.
    arts = [Article(no="84", body="asıl içerik metni burada."),
            Article(no="Geçici 1", body="(1) Geçici hüküm uygulanır.")]
    maddeler, _ = enrich(arts, _TREE_H, MID)
    chunks = maddeler_to_chunks(maddeler, kanun_ad="X", kanun_no="6698")
    gecici = [c for c in chunks if c["metadata"]["madde_no"] == "Geçici 1"][0]
    hy = gecici["metadata"]["hiyerarsi_yolu"]
    assert hy.endswith("Geçici Madde 1"), hy          # donor 'Madde 84' DEĞİL
    assert "Madde 84" not in hy
    assert "Son Hükümler" in hy                         # bölüm bağlamı korunur


def test_hiyerarsi_yolu_asil_unchanged():
    # KORUMA: asıl madde hiyerarsi_yolu DEĞİŞMEZ (zaten doğru 'Madde N').
    arts = [Article(no="84", body="asıl madde içeriği.")]
    maddeler, _ = enrich(arts, _TREE_H, MID)
    c = maddeler_to_chunks(maddeler, kanun_ad="X", kanun_no="6698")[0]
    assert c["metadata"]["hiyerarsi_yolu"].endswith("Madde 84")


def test_pure_artifact_madde_is_filtered():
    # Bug 4: gövdesi sadece fıkra-no/dipnot-işareti/madde-no artefaktı olan madde (anlamlı metin yok)
    # → korpusa GİRMEZ (embedding gürültüsü). Gerçek veri: 104624-10 '(1) (2) (3)', 103829-66 '[27]'.
    for artefakt in ["(1) (2) (3)", "[27]", "(1)", "24-", "[2]"]:
        m = _madde("11", artefakt)
        assert madde_to_chunk(m, kanun_ad="X", kanun_no="6698") is None, f"{artefakt!r} elenmedi"


def test_short_but_meaningful_madde_is_kept():
    # KORUMA: kısa ama ANLAMLI madde elenmemeli (gerçek hüküm). '(1) Yürürlüktedir.' gibi.
    m = _madde("11", "(1) Bu hüküm yürürlüktedir.")
    c = madde_to_chunk(m, kanun_ad="X", kanun_no="6698")
    assert c is not None and "yürürlüktedir" in c["text"]


def test_dipnot_isaretleri_text_ve_bentten_temizlenir():
    # D1 (FAZ 5): '[n]' dipnot işaretleri text ve bent metninde gürültü olarak kalıyordu (text
    # 5801, bent 1863 chunk). Embedding girdisinden temizlenir. Gerçek veri: 328134-3 gibi.
    m = _madde("11", "(1) Vakıf şu faaliyetlerde bulunur:[1]\na) eğitim vermek,[2]\nb) yardım etmek.")
    c = madde_to_chunk(m, kanun_ad="X", kanun_no="6698")
    assert "[1]" not in c["text"] and "[2]" not in c["text"]      # text temiz
    assert "faaliyetlerde bulunur" in c["text"]                    # içerik korundu
    # bent metinleri de temiz
    for fk in c["metadata"]["fikralar"]:
        for b in fk["bentler"]:
            assert "[" not in b["text"] or "]" not in b["text"]


def test_dipnot_temizleme_dipnotlar_metadatasini_bozmaz():
    # D1 KORUMA: '[n]' temizleme yalnız text/bent metnini etkiler; metadata.dipnotlar[] alanı
    # AYRI tutulur (m.dipnotlar, asdict ile serileşir) → DOKUNULMAZ.
    from kanun.dipnot import Dipnot
    m = _madde("11", "(1) Hüküm şudur[1] ve devamı böyledir.")
    m.dipnotlar = [Dipnot(no=1, text="Birinci dipnot tanımı metni.")]   # dipnot bağı kurulmuş gibi
    c = madde_to_chunk(m, kanun_ad="X", kanun_no="6698")
    assert "[1]" not in c["text"]                                  # text'te işaret temizlendi
    assert "Hüküm şudur" in c["text"]                              # içerik korundu
    assert len(c["metadata"]["dipnotlar"]) == 1                    # dipnotlar[] KORUNDU
    assert c["metadata"]["dipnotlar"][0]["text"] == "Birinci dipnot tanımı metni."


def test_table_only_madde_is_filtered():
    # Madde gövdesi SADECE tablodan ibaretse (gerçek metin yok), tablo text'ten çıkınca text boş
    # kalır → chunk korpusa GİRMEZ (anlamsız boş text embedding'e gitmesin).
    tablo = "| a | b |\n| --- | --- |\n| 1 | 2 |"
    arts = [Article(no="103", body="")]
    maddeler, _ = enrich(arts, TREE, MID, html_tables={"103": [tablo]})
    c = madde_to_chunk(maddeler[0], kanun_ad="X", kanun_no="193")
    assert c is None                                   # sadece-tablo madde → filtrele


def test_chunk_is_json_serializable():
    import json
    m = _madde("11", "(Değişik: 2/3/2024-7499/33 md.) (1) Herkes başvurabilir.")
    c = madde_to_chunk(m, kanun_ad="KVKK", kanun_no="6698")
    s = json.dumps(c, ensure_ascii=False)        # patlamadan serileşmeli
    assert "104383-11" in s                       # id MID tabanlı
    assert '"kanun_no": "6698"' in s              # kanun_no ayrı metadata
    # değişiklik künyesi de metadata'da yapısal
    assert len(c["metadata"]["degisiklik_gecmisi"]) == 1


def test_empty_body_madde_is_filtered():
    # İçeriksiz işlenmiş madde (boş gövde) → korpusa GİRMEZ (None döner).
    m = _madde("11", "")
    assert madde_to_chunk(m, kanun_ad="KVKK", kanun_no="6698") is None


def test_islenmistir_only_body_is_filtered():
    # text'i SADECE 'yerine işlenmiştir' yönlendirme notundan ibaret madde → korpusa GİRMEZ.
    # Gerçek hukuki içerik yok (metin başka kanuna işlendi). Gerçek veri: 7579 M1.
    m = _madde("1", "(22/12/1934 tarihli ve 2644 sayılı Tapu Kanunu ile ilgili olup, yerine işlenmiştir.)")
    assert madde_to_chunk(m, kanun_ad="TAPU ... DEĞİŞİKLİK KANUNU", kanun_no="7579") is None


def test_ilgili_olup_only_body_is_filtered():
    # 'ile ilgili olup ... işlenmiştir' varyantı da içeriksiz → filtrelenir. Gerçek veri: KVKK M30.
    m = _madde("1", "(10/12/2003 tarihli ve 5018 sayılı Kanun ile ilgili olup yerine işlenmiştir.)")
    assert madde_to_chunk(m, kanun_ad="X DEĞİŞİKLİK KANUNU", kanun_no="6698") is None


def test_real_content_with_islenmistir_mention_is_kept():
    # KORUMA (false-positive): gerçek hüküm İÇİNDE 'işlenmiştir' geçse bile, içerik dolu → KALIR.
    body = ("(1) Kişisel veriler, kanunda öngörülen usullere uygun işlenir ve sicile işlenmiştir. "
            "(2) Veri sorumlusu gerekli tedbirleri alır ve denetimleri yapar.")
    m = _madde("11", body)
    c = madde_to_chunk(m, kanun_ad="KVKK", kanun_no="6698")
    assert c is not None                          # gerçek içerik elenmemeli
    assert "tedbirleri alır" in c["text"]


def test_uzun_parantezsiz_gercek_hukum_ile_ilgili_olup_is_kept():
    # FAZ 20 (213:93 gövde-kaybı) HEDEF testi: gerçek hüküm cümle İÇİNDE 'ile ilgili olup' geçse
    # ve parantez HİÇ olmasa bile (gerçek redirect notlarının aksine), içerik dolu → KALIR.
    # Gerçek veri: VUK (213) madde 93 "Tebliğ esasları" — GERÇEK gövde (342 karakter, cümle-başı,
    # tarih/'N sayılı'/'MADDE N' ile BAŞLAMAZ). Önceki fix bunu 116 karaktere kısaltmıştı — bu,
    # >200 şartının yanlışlıkla doğru görünmesine yol açmıştı; burada TAM uzunluk kullanılır.
    body = (
        "Tahakkuk fişinden gayri, vergilendirme ile ilgili olup, hüküm ifade eden bilümum "
        "vesikalar ve yazılar adresleri bilinen gerçek ve tüzel kişilere posta vasıtasiyle "
        "ilmühaberli taahhütlü olarak, adresleri bilinmeyenlere ilan yolu ile tebliğ edilir. "
        "Şu kadar ki, ilgilinin kabul etmesi şartiyle, tebliğin daire veya komisyonda "
        "yapılması caizdir."
    )
    assert len(body) > 200                        # istisna şartlarından biri: UZUN
    m = _madde("93", body)
    c = madde_to_chunk(m, kanun_ad="VERGİ USUL KANUNU", kanun_no="213")
    assert c is not None                          # gerçek hüküm elenmemeli
    assert "hüküm ifade eden" in c["text"]


def test_redirect_notu_parantezsiz_tarih_basi_filtered():
    # FAZ 20 60-FP regresyon testi: önceki fix istisnayı SADECE 'baslar_paren=False' yaptı →
    # >200 şartı kalktı → parantezsiz, tarih/'N sayılı' ile BAŞLAYAN redirect notları (6487:1-11
    # gibi) yanlışlıkla korundu (60 FP). Gerçek veri: 6487 sayılı kanunun 1-11. maddeleri.
    # Bu vaka parantezsiz + kısa (82 kar, 200 altı) OLSA DA regex zaten eşleşiyordu; asıl ayırt
    # edici burada REDIRECT-BAŞLANGICI: tarih ile başlıyor → istisna uygulanmamalı, elenmeli.
    body = "2/6/1934 tarihli ve 2489 sayılı Kefalet Kanunu ile ilgili olup yerine işlenmiştir."
    m = _madde("1", body)
    c = madde_to_chunk(m, kanun_ad="X DEĞİŞİKLİK KANUNU", kanun_no="6487")
    assert c is None                               # redirect notu → elenmeli


def test_7143_gecici_4_uzun_cumle_basi_gercek_hukum_is_kept():
    # 7143:Geçici 4 tipi — uzun, cümle-başı (tarih/'N sayılı' ile BAŞLAMAYAN), içinde
    # 'ile ilgili olup' geçen GERÇEK hüküm. Regresyon-koruma: istisna bunu da korumalı.
    body = (
        "Bu madde kapsamında yapılan başvurular, ilgili vergi dairesince kayıt altına alınır ve "
        "inceleme işlemleri ile ilgili olup, sonuçlandırılıncaya kadar başkaca bir işlem tesis "
        "edilmez; başvuru sahiplerine ayrıca yazılı bildirim yapılır ve süreç izlenir."
    )
    assert len(body) > 200
    m = _madde("Geçici 4", body)
    c = madde_to_chunk(m, kanun_ad="X KANUNU", kanun_no="7143")
    assert c is not None
    assert "kayıt altına alınır" in c["text"]


def test_redirect_notu_kapanis_parantezli_kisa_hala_filtered():
    # KORUMA: gerçek redirect notu (parantezli, KISA) fix SONRASI da hâlâ elenmeli (regresyon yok).
    body = "(2/7/1964 tarih ve 492 sayılı Kanunun 76 ncı maddesinin değiştirilmesi ile ilgili olup, yerine işlenmiştir.)"
    m = _madde("1", body)
    c = madde_to_chunk(m, kanun_ad="X DEĞİŞİKLİK KANUNU", kanun_no="492")
    assert c is None


def test_uzun_kanun_adli_redirect_notu_hala_filtered():
    # FAZ 20 Critical fix: {0,200} karakter sınırı, uzun kanun-adlı redirect notlarını (200+ kar)
    # artık ELEMİYORDU (4 gerçek regresyon: 6824:24, 6745:56, 6009:56, 6569:39). Gerçek ayırt edici
    # parantez-zorunlu olmasıdır, uzunluk değil → sınır kaldırılır, hâlâ elenmeli.
    body = (
        "(22/1/1990 tarihli ve 399 sayılı Kamu İktisadi Teşebbüsleri Personel Rejiminin Düzenlenmesi "
        "ve 233 Sayılı Kanun Hükmünde Kararnamenin Bazı Maddelerinin Yürürlükten Kaldırılmasına Dair "
        "Kanun Hükmünde Kararname ile ilgili olup yerine işlenmiştir.)"
    )
    m = _madde("24", body)
    c = madde_to_chunk(m, kanun_ad="X DEĞİŞİKLİK KANUNU", kanun_no="6824")
    assert c is None


def test_madde_no_onekli_redirect_notu_filtered():
    # FAZ 20 regresyon vakası: önceki fix (parantez-ZORUNLU regex) madde-no önekli redirect
    # notlarını ("4- 5- (...)" biçiminde, açılış '(' madde-no önekinden SONRA gelir) artık
    # eleyemiyordu → 164 redirect notu korpusa sızdı. Dar-istisna yaklaşımı: orijinal regex
    # (parantez OPSİYONEL) + istisna yalnız parantezsiz-uzun gövdeye uygulanır; bu vaka parantez
    # İÇERİYOR (madde-no önekiyle) → istisna uygulanmaz, hâlâ elenmeli.
    body = "4- 5- (634 sayılı Kat Mülkiyeti Kanunu ile ilgili olup, yerine işlenmiştir.)"
    m = _madde("1", body)
    c = madde_to_chunk(m, kanun_ad="X DEĞİŞİKLİK KANUNU", kanun_no="634")
    assert c is None


def test_boslukli_tireli_madde_no_onekli_redirect_notu_filtered():
    # Aynı regresyon vakasının boşluklu-tire varyantı ("6 - 7 - 8 - (...)").
    body = "6 - 7 - 8 - (4447 sayılı Kanunun bazı maddeleri ile ilgili olup, yerine işlenmiştir.)"
    m = _madde("1", body)
    c = madde_to_chunk(m, kanun_ad="X DEĞİŞİKLİK KANUNU", kanun_no="4447")
    assert c is None


def test_maddeler_to_chunks_filters_empty():
    arts = [Article(no="11", body="(1) Dolu madde."), Article(no="12", body="   ")]
    maddeler, _ = enrich(arts, TREE, MID)
    chunks = maddeler_to_chunks(maddeler, kanun_ad="KVKK", kanun_no="6698")
    assert [c["metadata"]["madde_no"] for c in chunks] == ["11"]   # boş 12 elendi


def test_mulga_madde_is_included_but_marked():
    # Mülga madde korpusta KALIR (tarihsel sorgu) ama yurutluk='mülga' ile işaretli.
    m = _madde("11", "(1) (Mülga: 1/1/2020-1234/5 md.)")
    c = madde_to_chunk(m, kanun_ad="KVKK", kanun_no="6698")
    assert c is not None
    assert c["metadata"]["yurutluk"] == "mülga"


def test_madde_to_chunk_has_mevzuat_id():
    # FAZ 19: tertip-çakışması — metadata'ya benzersiz mevzuat_id (id ilk parçası) eklenir.
    # kanun_no benzersiz değil (3201 iki kanun: Emniyet Teşkilat + Yurt Dışı Sosyal Güvenlik)
    # ama mevzuat_id (mid tabanlı) benzersizdir.
    m = _madde("5", "(1) Örnek hüküm metni burada yer alır.")
    c = madde_to_chunk(m, kanun_ad="EMNİYET TEŞKİLAT KANUNU", kanun_no="3201")
    assert c["metadata"]["mevzuat_id"] == "104383"     # id ilk parçası (MID)
    assert c["metadata"]["kanun_no"] == "3201"          # kanun_no aynen korunur




# ── FAZ 22f: yönlendirme chunk üretici (build_corpus'ta atıf-alan işlenmiş-maddeler için) ──
from kanun.corpus import yonlendirme_chunk


def test_yonlendirme_chunk_uretir():
    # İçeriksiz "3065 sayılı ... yerine işlenmiştir" → yönlendirme chunk (madde bulunur, gövde boş).
    m = _madde("21", "(25/10/1984 tarihli ve 3065 sayılı Katma Değer Vergisi Kanunu ile ilgili olup yerine işlenmiştir.)")
    c = yonlendirme_chunk(m, kanun_ad="X", kanun_no="4842")
    assert c is not None
    assert c["metadata"]["madde_tipi"] == "islenmistir_yonlendirme"
    assert c["metadata"]["yerine_islenmistir"] is True
    assert c["metadata"]["tasindigi_kanun"] == "3065"
    assert c["metadata"]["madde_no"] == "21"
    assert c["text"] == ""


def test_yonlendirme_chunk_normal_madde_none():
    # Normal içerikli madde → yönlendirme DEĞİL (None). yonlendirme_chunk yalnız işlenmiştir-notu için.
    m = _madde("11", "Bu madde yürürlüktedir ve hüküm ifade eder.")
    assert yonlendirme_chunk(m, kanun_ad="X", kanun_no="6698") is None


def test_yonlendirme_chunk_hedefsiz_none():
    # Hedef kanunu ('NNNN sayılı') çıkarılamayan not → None (yönlendirilecek hedef yok).
    m = _madde("5", "(Mülga: 1/1/2020)")
    assert yonlendirme_chunk(m, kanun_ad="X", kanun_no="4842") is None
