from mevzuat_tool.chunker import split_articles


def test_splits_on_madde_markers_case_insensitive():
    text = "Madde 1- (1) Birinci. MADDE 2- (1) İkinci. Madde 3 - (1) Üçüncü."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["1", "2", "3"]
    assert arts[0].body.startswith("(1) Birinci")


def test_stops_at_islenemeyen_appendix():
    # B3 hayalet chunk: '... SAYILI ... KANUNA İŞLENEMEYEN ...' başlığı, başka kanunlara ait
    # işlenememiş maddelerin ekidir — bu kanunun maddesi DEĞİL. Buradan sonrası madde üretmemeli.
    # Gerçek veri: 6183, '...İŞLENEMEYEN GEÇİCİ MADDELER' sonrası Geçici 1 beş kez doğuyordu.
    text = ("MADDE 1- Asıl hüküm. MADDE 2- İkinci hüküm. "
            "21/7/1953 TARİHLİ VE 6183 SAYILI ANA KANUNA İŞLENEMEYEN GEÇİCİ MADDELER "
            "GEÇİCİ MADDE 1- Başka kanundan. GEÇİCİ MADDE 2- Yine başka.")
    arts = split_articles(text)
    assert [a.no for a in arts] == ["1", "2"]  # İŞLENEMEYEN sonrası hayalet maddeler yok
    assert "İŞLENEMEYEN" not in arts[-1].body.upper()  # son maddeye de yutturulmaz


def test_islenemeyen_word_in_normal_content_not_cut():
    # Koruma: 'işlenemeyen' kelimesi normal madde içeriğinde (başlık deseni OLMADAN) geçerse
    # kesim yapılmaz. (Yanlış-pozitif önleme.)
    text = "MADDE 1- Sisteme işlenemeyen kayıtlar reddedilir. MADDE 2- İkinci hüküm."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["1", "2"]


def test_body_does_not_swallow_level_heading():
    # B (seviye-başlık bleed): gövde sonuna sızan 'X. BÖLÜM/KISIM ...' yapısal başlığı kırpılmalı.
    # Madde içinde yeni BÖLÜM başlamaz — o bir sonraki yapısal birimin başlığıdır. Gerçek veri:
    # 3402 M34 '...bağlar. ALTINCI BÖLÜM Mali Hükümler...'; 7545 M4 '...edilir. İKİNCİ BÖLÜM...'.
    text = "MADDE 1- Bu hükümler uygulanır. ALTINCI BÖLÜM Mali Hükümler MADDE 2- İkinci."
    arts = split_articles(text)
    assert arts[0].body == "Bu hükümler uygulanır."  # 'ALTINCI BÖLÜM...' yutulmaz
    assert arts[1].body == "İkinci."


def test_ordinal_word_in_content_not_cut():
    # Koruma: 'ikinci fıkra', 'üçüncü kişi' gibi sıra-sözcüğü BÖLÜM/KISIM olmadan geçerse kesilmez.
    text = "MADDE 1- Bu maddenin ikinci fıkrası ve üçüncü kişiler hakkında uygulanır."
    arts = split_articles(text)
    assert arts[0].body == "Bu maddenin ikinci fıkrası ve üçüncü kişiler hakkında uygulanır."


def test_body_does_not_swallow_next_article_title():
    # B (gövde-taşma): HTML'de sonraki maddenin başlığı ('Amaç:') marker'dan önce gelince
    # önceki maddenin gövdesine yapışıyor. Gövde sonundaki '. <Başlık>:' kuyruğu kırpılmalı.
    # Gerçek veri (2629 M1): '...uygulanır. Amaç: Madde 2 - ...'
    text = "Madde 1 - Bu Kanun ilgili personel hakkında uygulanır. Amaç: Madde 2 - Bu Kanunun amacı düzenlemektir."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["1", "2"]
    assert arts[0].body == "Bu Kanun ilgili personel hakkında uygulanır."  # 'Amaç:' yutulmamalı
    assert arts[1].body.startswith("Bu Kanunun amacı")


def test_real_body_ending_with_colon_kept_when_last():
    # Koruma: SON maddede yutacak sonraki madde yok → kırpma yapılmaz (içerik korunur).
    text = "Madde 1 - Birinci madde. Madde 2 - Aşağıdakiler şunlardır:"
    arts = split_articles(text)
    assert arts[1].body == "Aşağıdakiler şunlardır:"  # son madde, kırpılmaz


def test_splits_madde_with_dot_after_number():
    # Nadir dizgi varyantı: numaradan sonra nokta (TCK Madde 61. / 328.).
    text = "MADDE 61. - (1) Hakim. Madde 62- (1) Komşu. Madde 328. - (1) Devlet."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["61", "62", "328"]
    assert arts[0].body.startswith("(1) Hakim")


def test_dot_tolerance_does_not_match_sentence_number_without_dash():
    # '5. fıkra' gibi tire'siz numara madde başlığı SAYILMAMALI (yan etki kontrolü).
    text = "Madde 10- (1) Bu konuda 5. fıkra hükmü uygulanır."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["10"]


def test_splits_madde_with_footnote_marker_before_dash():
    # Gerçek dizgi (Gümrük): numara ile tire arasında [dipnot] işaret(ler)i.
    # 'Madde 15[14][15] - ...' → numara 15, dipnot işaretleri tüketilir, tire korunur.
    text = "Madde 15[14][15] - 1. Gümrük vergileri. Madde 16[16] - 1. Diğer. Madde 111[69] - 1. Rejim."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["15", "16", "111"]
    assert arts[0].body.startswith("1. Gümrük")


def test_footnote_marker_does_not_break_tireless_guard():
    # [n] toleransı tire şartını GEVŞETMEMELİ: tiresiz '5[3] fıkra' madde sayılmaz.
    text = "Madde 20- (1) Burada 5[3] fıkra hükmü geçerli."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["20"]


def test_splits_tireless_madde_with_uppercase_title():
    # Gerçek dizgi (Borçlar): tire YOK, numaradan sonra BÜYÜK HARF başlık.
    # 'MADDE 428 İşyerinin...' → 428 yakalanır (büyük-harf başlık koşulu).
    text = "MADDE 427- (1) Önceki. MADDE 428 İşyerinin tamamı veya bir bölümü devri. MADDE 429- (1) Sonraki."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["427", "428", "429"]


def test_splits_tireless_madde_with_kunye_paren():
    # Gerçek dizgi (İş Madde 87): tire YOK, numaradan sonra (Mülga/Değişik künyesi.
    text = "Madde 86- (1) Önceki. Madde 87 (Mülga: 20/6/2012-6331/37 md.) Gebe kadınlar. Madde 88- (1) Sonraki."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["86", "87", "88"]


def test_tireless_guard_rejects_inline_lowercase_reference():
    # KRİTİK yan-etki guard'ı: tiresiz kuralı metin-içi küçük-harf atıfları MADDE SAYMAMALI.
    # 'madde 10 hükmü', 'madde 5 ve 6' gibi gövde-içi atıflar başlık değil.
    text = "Madde 1- (1) Bu konuda madde 10 hükmü ve madde 25 fıkrası birlikte uygulanır."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["1"]


def test_tireless_guard_rejects_number_followed_by_lowercase():
    # 'Madde 5 fıkra' (küçük harf 'fıkra') tiresiz → madde DEĞİL (küçük harf koşulu reddeder).
    text = "Madde 30- (1) İlgili madde 5 fıkrasına göre işlem yapılır."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["30"]


def test_tireless_guard_rejects_mixedcase_uppercase_reference():
    # KRİTİK (review bulgusu): KARIŞIK 'Madde N <BÜYÜK kelime>' gövde-içi ATIF madde SAYILMAMALI.
    # 'Madde 32 Tebliğ...', 'Madde 10 Anayasa...' bir başka maddeye atıftır, başlık değil.
    # Tiresiz büyük-harf dalı YALNIZ tam-büyük 'MADDE' ile aktif olmalı (gerçek veri: tiresiz
    # başlıklar hep tam-büyük 'MADDE 428' biçiminde; karışık 'Madde' hep atıf).
    text = (
        "Madde 1- (1) Bu husus Madde 32 Tebliğ hükümlerine tabidir. "
        "İlgili Madde 10 Anayasa'ya uygundur."
    )
    arts = split_articles(text)
    assert [a.no for a in arts] == ["1"]


def test_tireless_uppercase_title_requires_full_caps_MADDE():
    # Tiresiz büyük-harf başlık SADECE tam-büyük 'MADDE' ile (Borçlar 'MADDE 428 İşyerinin').
    # Karışık 'Madde 428 İşyerinin' tek başına (bağlamsız) yakalanmaz — gerçek dizgi tam-büyük.
    full = "MADDE 427- (1) X. MADDE 428 İşyerinin devri konusu. MADDE 429- (1) Y."
    assert [a.no for a in split_articles(full)] == ["427", "428", "429"]
    # künye paren'i kapitalizasyondan bağımsız çalışır (hem MADDE hem Madde):
    paren = "Madde 86- (1) X. Madde 87 (Mülga: 1/1/2020-1234 md.) Z. Madde 88- (1) Y."
    assert [a.no for a in split_articles(paren)] == ["86", "87", "88"]


def test_tireless_guard_rejects_allcaps_body_reference():
    # KRİTİK (2. review turu): tümü-büyük 'MADDE N KAPSAMINDA' gövde-içi ATIF madde SAYILMAMALI.
    # Gerçek tiresiz başlık ilk kelimesi karışık-kapitalizasyon (Borçlar 'MADDE 428 İşyerinin' →
    # 'İşyerinin' Başharf+küçük). Atıf ardından tümü-büyük kelime gelir → tiresiz dal reddetmeli.
    text = (
        "MADDE 1- (1) BU MADDE 5 KAPSAMINDA değerlendirilir; "
        "İLGİLİ MADDE 10 HÜKMÜ uygulanır."
    )
    arts = split_articles(text)
    assert [a.no for a in arts] == ["1"]


def test_tireless_title_first_word_must_be_titlecase():
    # Gerçek tiresiz başlık: Başharf büyük + en az bir küçük harf ('İşyerinin'). Yakalanmalı.
    title = "MADDE 428 İşyerinin devri. MADDE 429- (1) X."
    assert [a.no for a in split_articles(title)] == ["428", "429"]


def test_splits_fikralar_on_paren_numbers():
    from mevzuat_tool.chunker import split_fikralar
    body = "(1) Birinci fıkra. (2) İkinci fıkra."
    assert split_fikralar(body) == ["(1) Birinci fıkra.", "(2) İkinci fıkra."]


def test_detects_mulga_else_yururlukte():
    from mevzuat_tool.chunker import extract_status
    assert extract_status("(Mülga: 1/1/2020-1234 md.) ...") == "mülga"
    assert extract_status("(Değişik: ...) hüküm") == "yürürlükte"
    assert extract_status("normal hüküm") == "yürürlükte"


def test_detects_mulga_when_not_at_start():
    # C2: parantez-ortası '; Mülga:' tüm maddeyi mülga yapar (madde-başı değil ama madde mülga).
    # Gerçek veri: 657 Harita Ek1/Ek2 '(Ek: ...; Mülga: 2/7/2018-KHK-703 md.)' → mülga olmalı.
    from mevzuat_tool.chunker import extract_status
    assert extract_status("(Ek: 1/1/2000-1234 md.; Mülga: 2/7/2018-KHK-703/79 md.)") == "mülga"


def test_detects_aym_iptal_as_mulga():
    # C2: AYM iptali yürürlükten kaldırma anlamına gelir → mülga işaretlenmeli.
    # Gerçek veri: 5651 M9 '(Değişik: ...) (İptal:Anayasa Mahkemesinin 11/10/2023 ...)'.
    from mevzuat_tool.chunker import extract_status
    assert extract_status("(Değişik: 6/2/2014-6518/93 md.) (İptal:Anayasa Mahkemesinin 11/10/2023 tarihli kararı)") == "mülga"


def test_partial_mulga_keeps_madde_yururlukte():
    # C1: nitelikli/kısmi mülga ('Mülga son fıkra', 'Mülga ikinci fıkra') tüm maddeyi mülga YAPMAZ.
    # Gerçek veri: 3402 M3 madde normal başlıyor, ortada '(Mülga son fıkra: ...)' → madde yürürlükte.
    from mevzuat_tool.chunker import extract_status
    body = ("Kadastro ekibi; en az iki kadastro teknisyeni ile üç bilirkişiden oluşur. "
            "(Mülga son fıkra: 11/10/2011-KHK-666/1 md.)")
    assert extract_status(body) == "yürürlükte"


def test_iptal_inside_content_keeps_madde_yururlukte():
    # REGRESYON DÜZELTME (madde seviyesi, konum_duyarli=True): madde GERÇEK İÇERİKLE başlayıp
    # ortasında AYM iptali geçiyorsa bu bir FIKRANIN iptali — tüm madde mülga DEĞİL. 'maddeye
    # iptal' değil 'içerikte iptal'. Gerçek veri: 5651 M3/M5/M6.
    from mevzuat_tool.chunker import extract_status
    body = ("(1) İçerik, yer ve erişim sağlayıcıları yönetmelikle belirlenen esaslara uyar. "
            "(Değişik: 10/9/2014-6552/126 md.; İptal: Anayasa Mahkemesinin 2/10/2014 tarihli kararı)")
    assert extract_status(body, konum_duyarli=True) == "yürürlükte"


def test_mulga_inside_content_keeps_madde_yururlukte():
    # Aynı kural Mülga için: içerik başladıktan sonra gelen '(Mülga: ...)' bir fıkraya aittir.
    from mevzuat_tool.chunker import extract_status
    body = "(1) Birinci fıkra yürürlüktedir. (2) (Mülga: 1/1/2020-1234/5 md.)"
    assert extract_status(body, konum_duyarli=True) == "yürürlükte"


def test_madde_basi_iptal_kunyesi_tam_mulga():
    # Koruma: madde GERÇEK İÇERİK OLMADAN künye ile başlayıp iptal/mülga alıyorsa TAM mülga.
    # 5651 M9: '(Değişik: ...) (İptal: AYM ...)' → içerik yok, künye bloğu → mülga.
    from mevzuat_tool.chunker import extract_status
    body = "(Değişik: 6/2/2014-6518/93 md.) (İptal:Anayasa Mahkemesinin 11/10/2023 kararı)"
    assert extract_status(body, konum_duyarli=True) == "mülga"


def test_dipnot_isareti_kunye_blogunu_bolmez_tam_mulga():
    # E3 (FAZ 14): açılış künye bloğunda künyeler arası '[n]' dipnot işareti girince _KUNYE_PAREN
    # diziyi kıramıyor → '(Mülga:)' açılış-bölgesinde sayılmıyor → madde yanlışlıkla 'yürürlükte'.
    # Gerçek veri: 103912-Gecici14 (5429) — '(Ek:...)[13] (Mülga: KHK-703/99 md.)' MÜLGA olmalı.
    from mevzuat_tool.chunker import extract_status
    body = "(Ek : 13/6/2012-6327/42 md.)[13] (Mülga: 2/7/2018 - KHK-703/99 md.) Yürürlük"
    assert extract_status(body, konum_duyarli=True) == "mülga"


def test_iptal_fikra_kunyesi_tam_mulga():
    # Bug 5: '(İptal fıkra:)' / '(İptal birinci fıkra:)' AYM kararı da iptal sinyalidir ('İptal:'
    # gibi). Madde GERÇEK İÇERİK olmadan SADECE bu künyelerden ibaretse (tüm fıkraları iptal) → mülga.
    # Gerçek veri: 102929-Ek1, 105335-1 (birinci+ikinci+üçüncü fıkra iptal, içerik yok).
    from mevzuat_tool.chunker import extract_status
    body = ("(İptal birinci fıkra: Anayasa Mahkemesinin 10/4/2019 tarihli kararı ile) "
            "(İptal ikinci fıkra: Anayasa Mahkemesinin 10/4/2019 tarihli kararı ile)")
    assert extract_status(body, konum_duyarli=True) == "mülga"


def test_iptal_fikra_tek_kunye_tam_mulga():
    # '(İptal fıkra:)' tek künye (103043-Gecici29): içerik yok → mülga.
    from mevzuat_tool.chunker import extract_status
    body = "(Ek:11/11/2020-7256/14 md.) (İptal fıkra: Anayasa Mahkemesinin 1/6/2023 tarihli kararı ile)"
    assert extract_status(body, konum_duyarli=True) == "mülga"


def test_iptal_fikra_inside_content_keeps_yururlukte():
    # KORUMA (false-positive): madde GERÇEK İÇERİKLE başlayıp ortada '(İptal birinci fıkra:)' geçiyorsa
    # bu BİR FIKRANIN iptali — tüm madde mülga DEĞİL (3402 M3 mantığı). Madde yürürlükte kalır.
    from mevzuat_tool.chunker import extract_status
    body = ("(1) Erişim sağlayıcılar esaslara uyar ve gerekli tedbirleri alır. "
            "(İptal ikinci fıkra: Anayasa Mahkemesinin 30/6/2022 tarihli kararı ile)")
    assert extract_status(body, konum_duyarli=True) == "yürürlükte"


def test_bent_level_status_unchanged_by_position():
    # Koruma: alt-birim (konum_duyarli=False varsayılan) içindeki Mülga o birimi mülga yapar —
    # konum bakılmaz. Bent 'b) (Mülga:...)' → bent mülga (madde-seviyesi mantığı uygulanmaz).
    from mevzuat_tool.chunker import extract_status
    assert extract_status("b) içerik metni (Mülga: 1/1/2020-1234 md.)") == "mülga"


def test_iptal_bent_kunyesi_birim_mulga():
    # A1 (FAZ 1): '(İptal bent:)' AYM iptali — '(İptal fıkra:)' ile SİMETRİK olmalı; o ana kadar
    # marker'da yalnız 'fıkra' vardı, 'bent' yoktu (asimetri). Bent-seviyesi (konum_duyarli=False)
    # → o bent mülga. Gerçek veri: 7405 M38, 7354 M5/M6, 7245 M6.
    from mevzuat_tool.chunker import extract_status
    assert extract_status("a) bir hak (İptal bent: Anayasa Mahkemesinin 1/6/2023 tarihli kararı ile)") == "mülga"


def test_iptal_madde_kunyesi_tam_mulga():
    # A3 (FAZ 1): '(İptal madde: AYM ...)' tamamen iptal edilmiş boş madde → mülga. O ana kadar
    # marker '(İptal:)' bekliyordu; 'iptal madde:' araya 'madde' girince eşleşmiyordu (11 madde
    # yanlışlıkla 'yürürlükte'). Gerçek veri: 103326-1..5 (Kanun 221).
    from mevzuat_tool.chunker import extract_status
    body = "(İptal madde: Anayasa Mahkemesinin 21/4/2022 tarihli ve E.2021/119 sayılı kararı ile)"
    assert extract_status(body, konum_duyarli=True) == "mülga"


def test_iptal_bent_inside_content_keeps_madde_yururlukte():
    # A1 KORUMA (yanlış-pozitif): madde GERÇEK İÇERİKLE başlayıp ortada '(İptal bent:)' geçiyorsa
    # bu BİR BENDİN iptali — tüm madde mülga DEĞİL (5651 / iptal-fıkra mantığının analoğu).
    from mevzuat_tool.chunker import extract_status
    body = ("(1) Aşağıdaki haklar tanınır: a) birinci hak. "
            "(İptal bent: Anayasa Mahkemesinin 1/6/2023 tarihli kararı ile)")
    assert extract_status(body, konum_duyarli=True) == "yürürlükte"


def test_tarih_baslangicli_kunye_mulga():
    # 657 statü kaçırma: künye anahtar kelime yerine TARİH/ATIF ile başlıyor ('(2/1/1961- 203/2
    # md. ile gelen ... teselsül ettirilmiştir.; Mülga: 2/7/2018-KHK-703 md.)'). Bu da açılış
    # künyesidir → ';Mülga:' tüm maddeyi mülga yapmalı. Gerçek veri: 657 Ek2/Geçici1/Geçici2.
    from mevzuat_tool.chunker import extract_status
    body = ("(2/1/1961- 203/2 md. ile gelen numarasız ek md. hükmü olup madde numarası teselsül "
            "ettirilmiştir.; Mülga: 2/7/2018 - KHK-703/73 md.)")
    assert extract_status(body, konum_duyarli=True) == "mülga"


def test_tarih_kunye_ardindan_icerik_yururlukte():
    # Koruma: tarih-künye AÇILIŞTA ama ardından GERÇEK İÇERİK gelip ortada Mülga varsa, içerik
    # başladığı için kısmi (madde yürürlükte). Yanlış-pozitif önleme.
    from mevzuat_tool.chunker import extract_status
    body = ("(2/1/1961-203/2 md. ile gelen madde) Bu madde kapsamında işlemler yürütülür ve "
            "raporlanır. (Mülga son cümle: 1/1/2020-1234 md.)")
    assert extract_status(body, konum_duyarli=True) == "yürürlükte"


def test_prefix_and_suffix_maddeler_get_unique_no():
    text = (
        "Madde 1- (1) Asıl. "
        "GEÇİCİ MADDE 1- (1) Geçici. "
        "Ek Madde 2- (1) Ek. "
        "Mükerrer Madde 257- (1) Mük. "
        "Madde 257/A- (1) Suffix."
    )
    nos = [a.no for a in split_articles(text)]
    assert nos == ["1", "Geçici 1", "Ek 2", "Mükerrer 257", "257/A"]
    assert len(nos) == len(set(nos))  # benzersiz, çakışma yok


def test_strips_kanun_sonu_ek_after_yurutme():
    # BUG 9 (FAZ 15): son madde 'yürütür' + kanun-sonu ek (tümü-büyük cetvel/liste) gövdeye sızmış.
    # Gerçek veri (5996:50 Gıda K., 7440:25): '...Bakanlar Kurulu yürütür. GIDA VE YEM İŞLETMELERİ...
    # 5996 SAYILI KANUNA EK VE DEĞİŞİKLİK GETİREN...'. Anchor sonrası tümü-büyük kuyruk kırpılmalı.
    text = ("MADDE 49- (1) Bu Kanun yayımı tarihinde yürürlüğe girer. "
            "MADDE 50- (1) Bu Kanun hükümlerini Bakanlar Kurulu yürütür. "
            "7440 SAYILI KANUNA EK VE DEĞİŞİKLİK GETİREN MEVZUATIN VEYA ANAYASA "
            "MAHKEMESİ KARARLARININ YÜRÜRLÜĞE GİRİŞ TARİHİNİ GÖSTERİR LİSTE "
            "Değiştiren Kanunun Numarası 7456 Yürürlüğe Giriş Tarihi 15/7/2023")
    arts = split_articles(text)
    assert [a.no for a in arts] == ["49", "50"]
    assert arts[1].body == "(1) Bu Kanun hükümlerini Bakanlar Kurulu yürütür."  # kuyruk kesildi


def test_yurutme_without_ek_kept():
    # Koruma: 'yürütür' + kanun-sonu ek YOK (temiz yürütme maddesi) → kırpma yapılmaz.
    text = "MADDE 10- (1) Bu Kanun hükümlerini Cumhurbaşkanı yürütür."
    arts = split_articles(text)
    assert arts[0].body == "(1) Bu Kanun hükümlerini Cumhurbaşkanı yürütür."


def test_yurutme_with_lowercase_tail_not_cut():
    # Koruma: 'yürütür' sonrası KÜÇÜK-harf devam (meşru hüküm/düz-metin çöp) → KESME (bu faz dışı,
    # ertelenen semantik vaka: 7326:18 CB Kararı düz metin). Sadece tümü-büyük çöp kesilir.
    text = ("MADDE 18- (1) Bu Kanun hükümlerini Cumhurbaşkanı yürütür. Bu Kanunun uygulanması "
            "ile ilgili olarak Cumhurbaşkanı Kararı ile düzenleme yapılır.")
    arts = split_articles(text)
    assert arts[0].body.endswith("düzenleme yapılır.")  # küçük-harf kuyruk KESİLMEZ


def test_yururluk_madde_with_uppercase_law_ref_not_over_cut():
    # Koruma: 'yürürlük' maddesi (yürürlüğe-giriş) 'yürütür' içermez → anchor hiç eşleşmez,
    # tümü-büyük kanun-adı atfı olsa bile dokunulmaz.
    text = ("MADDE 20- (1) Bu Kanunun 5 inci maddesi 6098 SAYILI TÜRK BORÇLAR KANUNU ile birlikte "
            "1/1/2024 tarihinde yürürlüğe girer.")
    arts = split_articles(text)
    assert "6098 SAYILI" in arts[0].body  # yürürlük maddesi kesilmez (anchor yok)
