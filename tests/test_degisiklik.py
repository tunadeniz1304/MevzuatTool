from mevzuat_tool.degisiklik import Degisiklik, parse_kunyeler, temizle_kunyeler


def test_parses_degisik_with_date_law_madde():
    body = "(Değişik: 9/4/2003-4842/3 md.) Bu fıkra değişti."
    k = parse_kunyeler(body)
    assert len(k) == 1
    assert k[0].tip == "degisik"
    assert k[0].tarih == "2003-04-09"
    assert k[0].kanun_no == "4842"
    assert k[0].madde == "3"
    assert k[0].ham_metin == "(Değişik: 9/4/2003-4842/3 md.)"


def test_parses_ek_and_mulga_types():
    body = "(Ek: 22/7/1998-4369/29 md.) ... (Mülga: 1/1/2006-5436/5 md.) ..."
    tipler = [k.tip for k in parse_kunyeler(body)]
    assert tipler == ["ek", "mulga"]


def test_parses_kapsam_phrase():
    body = "(Değişik birinci fıkra: 16/6/2009-5904/1 md.) içerik."
    k = parse_kunyeler(body)[0]
    assert k.tip == "degisik"
    assert k.kapsam == "birinci fıkra"


def test_anayasa_mahkemesi_iptal_is_iptal_type():
    body = "Hüküm. (İptal: Anayasa Mahkemesi'nin 12/11/2020 tarihli kararı.)"
    k = parse_kunyeler(body)
    assert any(x.tip == "iptal" for x in k)


def test_parse_failure_keeps_ham_metin():
    # Tarih/kanun parse edilemese de künye yakalanır, ham_metin dolu kalır.
    body = "(Değişik: bozuk-format-tarihsiz) içerik."
    k = parse_kunyeler(body)
    assert len(k) == 1
    assert k[0].ham_metin == "(Değişik: bozuk-format-tarihsiz)"
    assert k[0].tarih is None
    assert k[0].kanun_no is None


def test_temizle_kunyeler_removes_them():
    body = "(Değişik: 9/4/2003-4842/3 md.) Asıl içerik burada."
    assert temizle_kunyeler(body) == "Asıl içerik burada."
