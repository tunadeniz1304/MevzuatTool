from mevzuat_tool.chunker import split_articles


def test_splits_on_madde_markers_case_insensitive():
    text = "Madde 1- (1) Birinci. MADDE 2- (1) İkinci. Madde 3 - (1) Üçüncü."
    arts = split_articles(text)
    assert [a.no for a in arts] == ["1", "2", "3"]
    assert arts[0].body.startswith("(1) Birinci")


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


def test_bent_level_status_unchanged_by_position():
    # Koruma: alt-birim (konum_duyarli=False varsayılan) içindeki Mülga o birimi mülga yapar —
    # konum bakılmaz. Bent 'b) (Mülga:...)' → bent mülga (madde-seviyesi mantığı uygulanmaz).
    from mevzuat_tool.chunker import extract_status
    assert extract_status("b) içerik metni (Mülga: 1/1/2020-1234 md.)") == "mülga"


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
