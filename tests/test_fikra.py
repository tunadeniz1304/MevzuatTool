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
