from mevzuat_tool.fikra import Bent, Fikra, parse_fikralar


def test_splits_paren_numbered_fikralar():
    body = "(1) Birinci fıkra. (2) İkinci fıkra."
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)", "(2)"]
    assert fs[0].text.startswith("(1) Birinci")


def test_no_paren_number_is_single_unnumbered_fikra():
    body = "Numarasız tek paragraf gövde."
    fs = parse_fikralar(body)
    assert len(fs) == 1
    assert fs[0].no is None
    assert fs[0].text == "Numarasız tek paragraf gövde."


def test_splits_letter_bentler_within_fikra():
    body = "Aşağıdakiler kazançtır:\na) birinci bent\nb) ikinci bent"
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["a)", "b)"]
    assert f.bentler[1].text == "b) ikinci bent"


def test_splits_numbered_bentler_within_fikra():
    body = "Şunlar:\n1. birinci\n2. ikinci\n3. üçüncü"
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["1.", "2.", "3."]


def test_bent_level_yurutluk():
    body = "Liste:\na) yürürlükteki bent\nb) (Mülga: 1/1/2020-1234 md.) kaldırılan bent"
    f = parse_fikralar(body)[0]
    assert f.bentler[0].yurutluk == "yürürlükte"
    assert f.bentler[1].yurutluk == "mülga"


def test_splits_inline_numbered_bentler_single_line():
    # normalize-sonrası: tek satırda boşlukla ayrık numaralı bentler
    body = "Şunlar gelirdir: 1. birinci gelir, 2. ikinci gelir, 3. üçüncü gelir."
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["1.", "2.", "3."]


def test_non_sequential_numbers_are_not_bentler():
    # '103.' gibi madde/yıl atıfları sıralı 1,2,3 koşusu oluşturmadığı için bent SAYILMAZ
    body = "103. maddede belirtilen oran ve 1985. yıldan beri uygulanan kural."
    f = parse_fikralar(body)[0]
    assert f.bentler == []


def test_splits_alt_bentler_within_bent():
    # Resmî hiyerarşi: madde → fıkra → bent → alt bent. Alt-bent işareti '1)' '2)' (parantez-rakam),
    # bent ('a)') içinde yer alır. Gerçek veri ([7528] M13): 'a) ... : 1) ... 2) ...'.
    body = "(1) Disiplin:\na) Çalışma usulü: 1) birinci alt bent 2) ikinci alt bent\nb) Karar şekli"
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["a)", "b)"]
    abent = f.bentler[0].alt_bentler
    assert [a.isaret for a in abent] == ["1)", "2)"]
    assert abent[0].text.startswith("1) birinci alt bent")


def test_bent_without_alt_bentler_has_empty_list():
    # Alt-bent içermeyen bent → alt_bentler boş liste (alan her zaman var).
    body = "Liste:\na) basit bent\nb) ikinci basit bent"
    f = parse_fikralar(body)[0]
    assert f.bentler[0].alt_bentler == []


def test_alt_bent_non_sequential_not_split():
    # Bent metnindeki '1) ... 5) ...' sıralı koşu değilse alt-bent SAYILMAZ (yıl/atıf gürültüsü).
    body = "a) 1) tek başına bir alt bent ama 7) atlamalı numara, alt-bent değil"
    f = parse_fikralar(body)[0]
    assert f.bentler[0].alt_bentler == []


def test_inline_paren_number_references_are_not_fikra():
    # A: cümle ortasında '(1), (2) ve (3) sayılı cetveller' fıkra DEĞİL — cetvel atfı.
    # Gerçek veri (5564 M3): tek hüküm, 3 fıkraya bölünmemeli.
    body = "(1) Toksik maddeler bu Kanunun eki (1), (2) ve (3) sayılı cetvellerde gösterilmiştir."
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)"]  # tek gerçek fıkra; (2),(3) cetvel atfı


def test_fikra_reference_within_sentence_not_split():
    # A: 'birinci fıkrasının (2), (3) numaralı bentleri' fıkra atfı — fıkra başı sanılmamalı.
    body = "(1) Birinci fıkra. Bu maddenin (2), (3) numaralı bentleri uygulanmaz."
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)"]


def test_real_fikra_after_sentence_end_is_kept():
    # A koruma: cümle-sonu ('. ') sonrası gelen sıralı '(n)' GERÇEK fıkra — kaçırılmamalı.
    body = "(1) Birinci fıkra hükmü. (2) İkinci fıkra hükmü. (3) Üçüncü fıkra hükmü."
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)", "(2)", "(3)"]


def test_fikra_after_kunye_paren_close_is_split():
    # Gerçek veri (6698/KVKK M6): künye-fıkrası ')' ile biter, ardından sıralı '(n) (' gelir.
    # '(2) (Mülga:...md.)' fıkrasının sonu ')' olduğu için '(3)' yutulmamalı — ayrı fıkra.
    # Sinyal: '(n)' + boşluk + AÇILIŞ-PAREN '(' (künye başı) güçlü fıkra-başıdır; atıf değil.
    body = ("(1) Özel nitelikli kişisel veridir. "
            "(2) (Mülga:2/3/2024-7499/33 md.) "
            "(3) (Değişik:2/3/2024-7499/33 md.) İşlenmesi yasaktır. "
            "(4) Yeterli önlem şarttır.")
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)", "(2)", "(3)", "(4)"]
    assert fs[1].text == "(2) (Mülga:2/3/2024-7499/33 md.)"
    assert fs[1].yurutluk == "mülga"


def test_paren_number_ref_after_close_paren_not_fikra():
    # A koruma (yanlış-pozitif): künye-kapanışı ')' sonrası gelse de, '(n)' ardından
    # KÜÇÜK harf/kelime gelirse (açılış-paren değil) bu atıftır, fıkra başı DEĞİL.
    body = "(1) Bu hüküm (5237 sayılı Kanun md.) ile (2) numaralı bende tabidir."
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)"]  # '(2) numaralı' atıf — bölünmemeli


def test_leading_kunye_before_fikra_one_does_not_collapse():
    # Bug 2: madde künye/başlık '(Başlığı ile Birlikte Değişik: ...)' ile başlayıp ardından
    # '(1) (2) (3)' fıkraları geliyorsa, lider künye fıkra bölmeyi ÇÖKERTMEMELİ. Künye '(1)'den
    # önce preamble; sonraki numaralı fıkralar ayrı tutulur. Gerçek veri: ÇEK 5941 M6, Vatandaşlık.
    body = ("(Başlığı ile Birlikte Değişik: 15/7/2016-6728/64 md.) "
            "(1) Karşılıksız çek bedeli ödenir. (2) İkinci fıkra hükmü. (3) Üçüncü fıkra hükmü.")
    fs = parse_fikralar(body)
    # numaralı fıkralar yakalanmalı (lider künye yutmamalı)
    assert [f.no for f in fs if f.no] == ["(1)", "(2)", "(3)"]


def test_leading_kunye_ek_madde_fikralari():
    # Ek madde künye-lider deseni (103294-Ek2): '(TARİH-md.) (1) ... (2) ...'.
    body = "(4/4/2015-6645/79 md.) (1) Kamu kurumlarında çalışanlar. (2) Bu kişilerin hakları."
    fs = parse_fikralar(body)
    assert [f.no for f in fs if f.no] == ["(1)", "(2)"]


def test_fikra_status_derived_from_bentler_one_mulga_keeps_yururlukte():
    # A2 (FAZ 1): bent-listeli fıkrada TEK gömülü '(Mülga:)' TÜM fıkrayı mülga YAPMAMALI.
    # Fıkra statüsü bent ağacından türetilir: en az bir bent yürürlükte → fıkra yürürlükte.
    # Gerçek veri: 103829-3 (Nüfus K. 5490 Tanımlar) — 29 bent, yalnız 'ç)' mülga, 28 canlı.
    body = ("Bu Kanunda geçen deyimlerden; a) Bakanlık: İçişleri Bakanlığını, "
            "b) Genel Müdürlük: Nüfus İşleri Genel Müdürlüğünü, "
            "ç) (Mülga: 1/1/2020-1234/5 md.) "
            "d) Nüfus kütüğü: kişisel bilgileri gösteren kütüğü, ifade eder.")
    f = parse_fikralar(body)[0]
    assert f.yurutluk == "yürürlükte"            # fıkra: en az bir bent canlı
    assert f.bentler[2].isaret == "ç)"
    assert f.bentler[2].yurutluk == "mülga"      # yalnız ç) mülga


def test_fikra_status_derived_from_bentler_all_mulga_is_mulga():
    # A2 koruma: TÜM bentler mülga ise fıkra GERÇEKTEN mülga kalır (tam-mülga korunur).
    body = ("Liste: a) (Mülga: 1/1/2020-1/1 md.) "
            "b) (Mülga: 1/1/2020-1/1 md.) "
            "c) (Mülga: 1/1/2020-1/1 md.)")
    f = parse_fikralar(body)[0]
    assert [b.yurutluk for b in f.bentler] == ["mülga", "mülga", "mülga"]
    assert f.yurutluk == "mülga"


def test_fikra_without_bentler_status_unchanged():
    # A2 koruma: bentsiz (düz) fıkrada davranış DEĞİŞMEZ — extract_status aynen.
    assert parse_fikralar("Düz bir fıkra metni, yürürlükte.")[0].yurutluk == "yürürlükte"
    assert parse_fikralar("(Mülga: 1/1/2020-1/1 md.)")[0].yurutluk == "mülga"


def test_fikra_after_dipnot_bracket_is_split():
    # B1 (FAZ 2): cümle '.[1]' dipnot işaretiyle bitince sonraki '(2)' fıkra-başı KAÇIYORDU
    # (lookbehind '[.:!?]\s|\n|)\s' içinde ']' yok). Gerçek veri: 189065-5 — '(2)' fıkrası
    # '(1)'e gömülüyordu. Dipnot ']' + boşluk sonrası '(n)' de fıkra-başı sayılmalı.
    body = "(1) Kurum yükümlüdür.[1] (2) Fona ilişkin esaslar belirlenir. (3) Üçüncü fıkra."
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)", "(2)", "(3)"]


def test_fikra_dipnot_bracket_does_not_oversplit():
    # B1 KORUMA: ']' her zaman fıkra-başı tetiklemez — ardından '(n)' + boşluk gelmeli.
    # Cümle-ortası '[1]' atıfı/dipnotu fıkra üretmez.
    body = "(1) Hüküm[1] uygulanır ve devam eder, ikinci cümle de buradadır."
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)"]


def test_fikra_dipnot_bracket_midsentence_not_split():
    # B1 KORUMA (yanlış-pozitif): cümle ORTASINDA '(…)[10] (1) zimmet, irtikâp...' deseni —
    # ']' öncesi nokta YOK (')' var) ve '(n)' sonrası KÜÇÜK harf (cümle devamı). Bu fıkra DEĞİL.
    # Gerçek veri: 103569-28 (Tababet 1219) — B1 ilk hali bu cümleyi yanlışlıkla bölüyordu.
    body = ("Hekimlik mesleğinin icrası için kasten işlenen suçlar, Anayasal düzene karşı "
            "suçlar, (…)[10] (1) zimmet, irtikâp, rüşvet, hırsızlık suçlarından mahkûm "
            "olmamak şarttır.")
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == [None]   # tek numarasız fıkra; '(1)' cümle-ortası, bölünmez


def test_ekli_cetvel_does_not_produce_fake_bentler():
    # B2 (FAZ 2): '(N) SAYILI LİSTE/CETVEL' ekli cetveli sahte fıkra+bent üretiyordu.
    # Gerçek veri: 104030-5 (Büyükşehir 5747 Yürütme) — '(1) Bakanlar Kurulu yürütür.'
    # sonrası '(1) SAYILI LİSTE ADANA...' 862 sahte bent. Cetvel bölünmez; içerik korunur.
    body = ("(1) Bu Kanun hükümlerini Bakanlar Kurulu yürütür. "
            "(1) SAYILI LİSTE ADANA İLİ MAHALLELER 1. Köy A 2. Köy B 3. Köy C "
            "(2) SAYILI LİSTE İZMİR İLİ MAHALLELER 1. Köy D 2. Köy E")
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)"]          # tek gerçek hüküm fıkrası
    assert fs[0].bentler == []                     # cetvelden sahte bent ÜRETİLMEZ
    assert "ADANA" in fs[0].text                   # cetvel içeriği KORUNUR (kayıp yok)


def test_sayili_kanun_reference_not_treated_as_cetvel():
    # B2 KORUMA (yanlış-pozitif): 'NNNN sayılı Kanun' meşru fıkra metnidir, cetvel DEĞİL —
    # ayırt edici desen '(N) SAYILI' + BÜYÜK-harf LİSTE/CETVEL/TARİFE. 'sayılı' (6844 madde) etkilenmez.
    body = "(1) 5237 sayılı Kanuna göre işlem yapılır. (2) İkinci fıkra hükmü uygulanır."
    fs = parse_fikralar(body)
    assert [f.no for f in fs] == ["(1)", "(2)"]


# ---- B3 (FAZ 3): numaralı asıl-grup iki-seviye (1. > a)) ----

def test_numbered_group_with_harf_subitems_two_level():
    # B3: numaralı üst-grup '1. 2.' + altında harf-bent 'a) b)' → İKİ SEVİYE.
    # Gerçek veri: 103044-3 (Gümrük 4458 Tanımlar). Mevcut hata: a)b)c)... tek düz listeye eziliyordu.
    body = ("Bu Kanunda geçen; 1. \"Müsteşarlık\" deyimi, Gümrük Müsteşarlığını; "
            "2. a) \"Gümrük idaresi\" deyimi, yönetim birimlerini; "
            "b) \"Giriş gümrük idaresi\" deyimi, giriş idaresini; "
            "3. a) \"Eşya\" deyimi, her türlü maddeyi; b) \"Serbest dolaşım\" deyimi, durumu;")
    f = parse_fikralar(body)[0]
    # üst seviye = numaralı grup
    assert [b.isaret for b in f.bentler] == ["1.", "2.", "3."]
    # 1. bentin altında harf yok; 2. ve 3.'ün altında 'a) b)' alt-bent
    assert f.bentler[0].alt_bentler == []
    assert [a.isaret for a in f.bentler[1].alt_bentler] == ["a)", "b)"]
    assert [a.isaret for a in f.bentler[2].alt_bentler] == ["a)", "b)"]
    assert "Gümrük idaresi" in f.bentler[1].alt_bentler[0].text


def test_plain_letter_bentler_unchanged_by_b3():
    # B3 GERİYE-UYUM: numaralı üst-grup YOKsa düz harf-bent davranışı BİREBİR korunur.
    body = "Aşağıdakiler: a) birinci bent b) ikinci bent c) üçüncü bent"
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["a)", "b)", "c)"]
    assert all(b.alt_bentler == [] for b in f.bentler)


def test_plain_numbered_bentler_without_harf_unchanged_by_b3():
    # B3 GERİYE-UYUM: numara var ama harf-bent YOK → düz numara-bent (tek seviye), iki-seviye DEĞİL.
    body = "Şunlar gelirdir: 1. birinci gelir, 2. ikinci gelir, 3. üçüncü gelir."
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["1.", "2.", "3."]
    assert all(b.alt_bentler == [] for b in f.bentler)


def test_harf_ust_numara_alt_NOT_inverted_by_b3():
    # B3 KORUMA (yanlış-pozitif): TTK 6102'de hiyerarşi 'harf ÜST > numara ALT' olabilir
    # (a) ... 1. ... 2. ... b) ...). B3 numara-üst varsaymamalı — İLK yapısal işaret HARF ise
    # harf ÜST kalır. Gerçek veri: 103039-55/181/960 (TTK haksız rekabet, tür değiştirme).
    body = ("Aşağıdakiler haksız rekabettir: a) Aldatıcı reklamlar ve özellikle; "
            "1. Başkalarını kötüleyen, 2. Yanlış bilgi veren beyanlar; "
            "b) Sözleşmeyi ihlale yöneltme.")
    f = parse_fikralar(body)[0]
    # harf ÜST (ilk işaret 'a)'); numara '1. 2.' a)'nın İÇİNDE kalır (üst-bent OLMAZ)
    assert [b.isaret for b in f.bentler] == ["a)", "b)"]
    assert "1. Başkalarını" in f.bentler[0].text   # numara harf-bendin içinde


# ---- Z1 (FAZ 7): roman-rakam 'i)' 3. seviye sızması ----

def test_roman_i_does_not_split_letter_bent_repeated():
    # Z1: '2. ... a) ... i) ... b) ... i) ...' — roman 'i)' (3. seviye) harf-bent SANILIYOR,
    # harf-listesine kardeş giriyor → 'b)' BOŞ kalır (içeriği i)'ye kaçar). Gerçek veri: 103017-Ek2
    # (Damga V. 488 Ek 2). KESİN-ROMAN sinyali: 'i)' TEKRARLI (harf-listede imkansız).
    # Doğru davranış: roman 'i)' bir önceki harf-bendin metnine dahil; ayrı alt-bent OLMAZ.
    # (B3 iki-seviye tetiklensin diye '1.' + '2.' çoklu numara — gerçek veride de öyle.)
    body = ("Tanımlar şunlardır: "
            "1. Birinci grup tek tanım, "
            "2. Aşağıdaki işlemler müstesnadır: "
            "a) Yatırım programında yer alan yatırımlar. i) Tam mükellef olması hâlinde uygulanır. "
            "b) Savunma sanayii işlemleri. i) Onaylanan projeler kapsamındadır. "
            "c) İmalatçı firmaların işlemleri.")
    f = parse_fikralar(body)[0]
    ust = f.bentler[1]                                   # '2.' üst-bent
    altler = ust.alt_bentler
    # roman 'i)' ayrı alt-bent OLMAZ; yalnız harf-bentler a) b) c)
    assert [a.isaret for a in altler] == ["a)", "b)", "c)"]
    # 'b)' BOŞ kalmaz — kendi içeriğini korur, roman i) metni a)/b)'ye gömülü kalır
    assert "Savunma sanayii" in altler[1].text
    assert all(len(a.text) > 5 for a in altler)          # hiçbir harf-bent boş değil
    # içerik kaybı yok: roman i) metni üst-bent / harf-bent text'inde korunur
    assert "Tam mükellef" in ust.text
    assert "Onaylanan projeler" in ust.text


def test_roman_i_empty_preceding_letter_bent():
    # Z1: 'i)' TEK ama önceki harf-bent BOŞ ('f)' içeriksiz, çünkü içeriği i)'ye kaçtı) → roman.
    # Gerçek veri: 103044-227 (Gümrük 4458). 'e) f) i) g) h)' — f) boş, i) f)'nin alt-bendi.
    body = ("Şartlar şunlardır: "
            "1. Birinci grup tek tanım, "
            "2. İkinci grup şartları: "
            "a) Vatandaş olmak, b) Ehliyet sahibi olmak, c) Haklardan mahrum olmamak, "
            "d) Suç işlememiş olmak, e) Çıkarılmamış olmak, "
            "f) i) Hukuk veya iktisat dallarında öğrenim görmüş olmak, "
            "g) Staj yapmış olmak, h) Sınavı kazanmış olmak.")
    f = parse_fikralar(body)[0]
    ust = f.bentler[1]                                   # '2.' üst-bent
    altler = ust.alt_bentler
    # roman 'i)' ayrı alt-bent OLMAZ; f) içeriğini korur (boş kalmaz)
    assert "i)" not in [a.isaret for a in altler]
    assert [a.isaret for a in altler] == ["a)", "b)", "c)", "d)", "e)", "f)", "g)", "h)"]
    fbent = [a for a in altler if a.isaret == "f)"][0]
    assert "Hukuk veya iktisat" in fbent.text             # i) içeriği f)'ye dahil
    assert len(fbent.text) > 5                             # f) boş değil


def test_legit_harf_i_not_treated_as_roman():
    # Z1 KORUMA (yanlış-pozitif): MEŞRU harf-bent 'i)' (Türkçe alfabe '...h) i) j)...', ı) atlanmış)
    # roman SANILMAMALI. Gerçek veri: 103111-89 (GVK), 103006-Mukerrer298 (VUK). Sinyal: 'i)' TEK +
    # komşular dolu + sıralı (önceki harf boş DEĞİL). Bu liste düz harf-bent kalır, dokunulmaz.
    body = ("Yapılan harcamalar: "
            "1. Birinci grup tek tanım, "
            "2. İkinci grup harcamaları: "
            "a) Ulusal projelere, b) Kültür birikimine, c) Sanat eserlerine, d) Tarihî yapılara, "
            "e) Müzelere, f) Taşınmaz varlıklara, g) Envanter çalışmalarına, h) Kültür varlıklarına, "
            "i) Somut olmayan mirasa, j) Kütüphane ve müzelere ilişkin harcamalar.")
    f = parse_fikralar(body)[0]
    ust = f.bentler[1]                                   # '2.' üst-bent
    isaretler = [a.isaret for a in ust.alt_bentler]
    # 'i)' MEŞRU harf-bent — listede kendi yerinde kalır (roman sanılıp silinmez)
    assert "i)" in isaretler
    assert isaretler == ["a)", "b)", "c)", "d)", "e)", "f)", "g)", "h)", "i)", "j)"]


# ---- B4 (FAZ 6): liste-kapanış cümlesi son bentten ayrılır ----

def test_liste_kapanis_cumlesi_son_bende_yapismaz():
    # B4: liste-açan fıkrada (giriş ':' ile biter) kısa-enum bentlerden sonra gelen GERİ-ATIFLI
    # kapanış cümlesi son bende yapışmamalı — o bende AİT DEĞİL, tüm fıkrayı kapatan hükümdür.
    # Gerçek veri: 103111-2 (GVK 193 Madde 2, Gelirin unsurları).
    body = ("Gelire giren kazanç ve iratlar şunlardır: 1. Ticarî kazançlar, 2. Ziraî kazançlar, "
            "3. Ücretler, 4. Serbest meslek kazançları, 5. Gayrimenkul sermaye iratları, "
            "6. Menkul sermaye iratları, 7. Diğer kazanç ve iratlar. Bu Kanunda aksine hüküm "
            "olmadıkça, yukarıda yazılı kazanç ve iratlar gelirin tespitinde gerçek ve safi "
            "miktarları ile nazara alınır.")
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["1.", "2.", "3.", "4.", "5.", "6.", "7."]
    # son bent SADECE kendi öğesini içerir; kapanış cümlesi AYRILMIŞ
    assert f.bentler[-1].text == "7. Diğer kazanç ve iratlar."
    assert "nazara alınır" not in f.bentler[-1].text
    # kapanış cümlesi fıkra metninde KORUNUR (kayıp yok — embedding girdisi bozulmaz)
    assert "nazara alınır" in f.text


def test_ancak_istisna_cumlesi_bentte_kalir():
    # B4 KORUMA (yanlış-pozitif — ilk denemenin 46 FP'sinin sınıfı): bendin MEŞRU ikinci cümlesi
    # ('Ancak ...', 'Bu oran ...') geri-atıflı kapanış DEĞİL — bende KALMALI, kesilmemeli.
    body = ("Aşağıdaki hâllerde uygulanır: a) Birinci hâl, b) İkinci hâl, c) Üçüncü hâl. "
            "Ancak, bu hâllerde idare ayrıca gerekçe göstermek zorundadır.")
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["a)", "b)", "c)"]
    assert "Ancak" in f.bentler[-1].text          # istisna cümlesi son bentte KALIR


def test_coklu_cumle_bent_kirpilmaz():
    # B4 KORUMA: bentler zaten çok-cümleli (noktayla biten tam paragraflar) — liste-açan kısa-enum
    # imzası TUTMAZ (önceki bentler virgülle bitmiyor) → kırpma TETİKLENMEZ.
    body = ("Şu işlemler yapılır: a) İlk işlem tamamlanır. Sonra rapor düzenlenir. "
            "b) İkinci işlem yapılır. Bu Kanunda aksine hüküm olsa bile uygulanır.")
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["a)", "b)"]
    # önceki bent 'a)' kısa-enum değil (noktayla bitiyor) → imza tutmaz → son bent dokunulmaz
    assert "uygulanır" in f.bentler[-1].text


def test_geri_atifsiz_baslik_bu_fixle_kirpilmaz():
    # B4 KORUMA: son öğeden sonra gelen ifade GERİ-ATIFSIZ bir başlık/isim tamlaması ise
    # (fiil-cümlesi değil) bu fix kesmez — başlık sızması ayrı sorun (FAZ 4 C1).
    body = ("Birlik organları şunlardır: 1. Genel Kurul, 2. Yönetim Kurulu, "
            "3. Denetleme Kurulu. Birlik Genel Kurulunun oluşumu")
    f = parse_fikralar(body)[0]
    assert [b.isaret for b in f.bentler] == ["1.", "2.", "3."]
    # 'Birlik Genel Kurulunun oluşumu' geri-atıf değil → B4 kesmez (son bentte kalır)
    assert "Birlik Genel Kurulunun oluşumu" in f.bentler[-1].text
