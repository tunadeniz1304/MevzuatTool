from kanun.dipnot import Dipnot, split_dipnot_apendiksi, baglanan_dipnotlar


def test_splits_trailing_footnote_block_of_three_or_more():
    body = (
        "Madde gövdesi burada biter.\n"
        "[1] 9/4/2003-4842 sayılı Kanunla eklenmiştir.\n"
        "[2] 22/7/1998-4369 sayılı Kanunla değiştirilmiştir.\n"
        "[3] İptal: Anayasa Mahkemesi kararı.\n"
    )
    clean, dipnotlar = split_dipnot_apendiksi(body)
    assert clean == "Madde gövdesi burada biter."
    assert [d.no for d in dipnotlar] == [1, 2, 3]
    assert dipnotlar[0].text == "9/4/2003-4842 sayılı Kanunla eklenmiştir."
    assert dipnotlar[2].text == "İptal: Anayasa Mahkemesi kararı."


def test_below_threshold_is_noop():
    body = "Gövde metni. [5] tek referans satırı.\n[6] ikinci satır."
    clean, dipnotlar = split_dipnot_apendiksi(body)
    assert clean == body
    assert dipnotlar == []


def test_no_footnotes_returns_body_unchanged():
    body = "Sıradan madde gövdesi, dipnot yok."
    clean, dipnotlar = split_dipnot_apendiksi(body)
    assert clean == body
    assert dipnotlar == []


def test_links_inline_markers_to_footnotes():
    tum = [Dipnot(1, "birinci"), Dipnot(2, "ikinci"), Dipnot(3, "üçüncü")]
    body = "Bu hüküm [2] ve ayrıca [3] ile değişti."
    bagli = baglanan_dipnotlar(body, tum)
    assert [d.no for d in bagli] == [2, 3]


def test_unmatched_marker_is_skipped():
    tum = [Dipnot(1, "birinci")]
    body = "Atıf [9] global listede yok."
    assert baglanan_dipnotlar(body, tum) == []


def test_duplicate_markers_dedup_keep_order():
    tum = [Dipnot(5, "beş"), Dipnot(7, "yedi")]
    body = "[7] sonra yine [7] ve [5]."
    bagli = baglanan_dipnotlar(body, tum)
    assert [d.no for d in bagli] == [7, 5]


def test_splits_inline_single_line_appendix():
    # normalize sonrası gerçek senaryo: tek satırda boşlukla ayrık [n] entry'leri
    body = "Madde gövdesi biter. [1] birinci tanım. [2] ikinci tanım. [3] üçüncü tanım."
    clean, dipnotlar = split_dipnot_apendiksi(body)
    assert clean == "Madde gövdesi biter."
    assert [d.no for d in dipnotlar] == [1, 2, 3]
    assert dipnotlar[1].text == "ikinci tanım."


# --- Yoğunluk-bazlı apendiks ayrımı (7174 M8 over-split bug) ---
# Gerçek apendiks: kuyrukta TOPLU '[1] tanım. [2] tanım.' bloğu — işaretler YOĞUN (kısa aralıklı).
# Yayılmış-referans: '[1]'..'[2]'..'[3]' madde gövdesine binlerce karakter arayla dağılmış (her biri
# bir fıkranın değişiklik-dipnotu REFERANSI, tanım değil) → apendiks SAYILMAMALI, gövde korunur.

def test_spread_references_are_not_appendix():
    # 7174 M8 deseni: [1],[2],[3] uzun gövdeye binlerce karakter arayla yayılmış (referanslar).
    seg = "A" * 2000
    body = (f"(1) Cezalar uygulanır.[1] {seg} (2) Devam eder.[2] {seg} (3) Son fıkra.[3] {seg}")
    clean, dip = split_dipnot_apendiksi(body)
    # Yayılmış işaretler apendiks başı sayılmamalı; gövdenin tamamı (3. fıkra dahil) korunmalı.
    assert "Son fıkra" in clean
    assert len(clean) > 5000          # gövde kesilmedi


def test_dense_trailing_block_is_appendix():
    # Gerçek apendiks: kuyrukta yoğun blok (kısa aralıklı) → ayrılır.
    body = "Madde gövdesi uzun metin burada biter. [1] birinci tanım. [2] ikinci tanım. [3] üçüncü tanım."
    clean, dip = split_dipnot_apendiksi(body)
    assert clean == "Madde gövdesi uzun metin burada biter."
    assert [d.no for d in dip] == [1, 2, 3]


def test_spread_body_start_references_long_body_not_appendix():
    # 102939 M11 deseni: [1] gövde başında (40. krk), [2..5] tüm gövdeye yayılmış (706,2202,2973),
    # son işaret kuyruğa yakın (kısa kuyruk) AMA bunlar gövde-içi REFERANSLAR. Gövde-başı az metin +
    # uzun toplam gövde → apendiks değil (yoksa 2996ch gövde 40ch'a kesilir).
    seg = "C" * 700
    body = (f"İlk hüküm[1] burada {seg} ikinci kısım[2] devam {seg} üçüncü[3] bölüm {seg} "
            f"dördüncü[4] kısım {seg} beşinci[5] son hüküm uygulanır.")
    clean, dip = split_dipnot_apendiksi(body)
    assert "son hüküm uygulanır" in clean
    assert len(clean) > 2000          # uzun gövde [1]@başta diye kesilmemeli


def test_dense_but_body_start_references_are_not_appendix():
    # 5335 M30 over-truncation bug: [1] gövdenin BAŞINDA (28. krk), ardından [2..5] yoğun (ort
    # aralık ~419<800) ama bunlar gövde-içi REFERANSLAR — gerçek apendiks değil. Apendiks kuyrukta
    # olur; gövde-başında başlayan '[1]' apendiks SAYILMAMALI (yoksa 3998ch gövde 28ch'a kesilir).
    seg = "B" * 600
    body = (f"Cumhurbaşkanı tarafından atanan[1] görevlendirilenler ile {seg} "
            f"yükseköğretim kurumları[2] ve[3] {seg} sağlık personeli[4] hakkında[5] {seg} "
            f"bu hüküm uygulanır ve süreç tamamlanır.")
    clean, dip = split_dipnot_apendiksi(body)
    # gövde-başı '[1]' apendiks başı değil → gövdenin tamamı korunur
    assert "süreç tamamlanır" in clean
    assert len(clean) > 1500          # 3998→28 over-truncation OLMAMALI
