from mevzuat_tool.enrich import _madde_tipi, enrich, Madde
from mevzuat_tool.chunker import Article
from mevzuat_tool.tree import parse_tree

TREE = parse_tree(
    "- DÖRDÜNCÜ KISIM - Verginin Tarhı (maddeId:9)\n"
    "  - BİRİNCİ BÖLÜM - Beyan Esası (maddeId:10)\n"
    "    - Madde No: 84 - Beyanname çeşitleri: (maddeId:1279029)\n"
)

TREE_BLEED = parse_tree(
    "- DÖRDÜNCÜ KISIM - X (maddeId:9)\n"
    "  - BİRİNCİ BÖLÜM - Beyan Esası (maddeId:10)\n"
    "    - Madde No: 84 - Beyanname çeşitleri: (maddeId:1279029)\n"
    "  - YEDİNCİ BÖLÜM - Diğer Kazanç (maddeId:20)\n"
    "    - Madde No: 85 - Gelire giren: (maddeId:30)\n"
)


def _maddeler(arts, tree):
    maddeler, _dipnotlar = enrich(arts, tree, "193")
    return maddeler


def test_madde_tipi_from_no():
    assert _madde_tipi("84") == "asil"
    assert _madde_tipi("257/A") == "asil"
    assert _madde_tipi("Geçici 84") == "gecici"
    assert _madde_tipi("Ek 2") == "ek"
    assert _madde_tipi("Mükerrer 80") == "mukerrer"


def test_enrich_returns_tuple_of_maddeler_and_dipnotlar():
    arts = [Article(no="84", body="içerik.")]
    res = enrich(arts, TREE, "193")
    assert isinstance(res, tuple) and len(res) == 2
    maddeler, dipnotlar = res
    assert isinstance(maddeler, list) and isinstance(dipnotlar, list)


def test_enrich_asil_joins_tree():
    arts = [Article(no="84", body="Gelir Vergisi beyanları: ...")]
    m = _maddeler(arts, TREE)[0]
    assert m.madde_tipi == "asil"
    assert m.madde_baslik == "Beyanname çeşitleri"


def test_enrich_strips_leading_islenmis_aralik_note():
    # Gövde başı içeriksiz-aralık yönlendirme notu ('11- (...işlenmiştir.)') gerçek içerik DEĞİL,
    # bir sonraki içeriksiz maddenin notu. Gövdeden kırpılmalı. Gerçek veri: 6756 M10.
    body = ("11- (4/1/1961 tarihli ve 211 sayılı Türk Silahlı Kuvvetleri İç Hizmet Kanunu ile "
            "ilgili olup yerine işlenmiştir.) MADDE 12 ila 20 - (26/10/1963 tarihli ve 357 sayılı "
            "Askeri Hakimler Kanunu ile ilgili olup yerine işlenmiştir.)")
    arts = [Article(no="10", body=body)]
    m = _maddeler(arts, TREE)[0]
    assert m.body == ""  # tamamı içeriksiz yönlendirme notu → boş kalmalı


def test_enrich_keeps_real_body_with_paren_one():
    # Koruma: '(1)' fıkrasıyla başlayan GERÇEK madde dokunulmaz (içinde MADDE N ila M atfı olsa bile).
    # Gerçek veri: 6769 M165.
    body = "(1) Bu Kanunun uygulanmasına ilişkin yönetmelikler Kurum tarafından yürürlüğe konulur."
    arts = [Article(no="84", body=body)]
    m = _maddeler(arts, TREE)[0]
    assert m.body == body  # gerçek içerik korunur


def test_enrich_keeps_body_starting_with_text():
    # Koruma: düz metinle başlayan gerçek madde dokunulmaz. Gerçek veri: 6758 M37 ('Ekli (3)...').
    body = "Ekli (3) sayılı listede yer alan kadro ihdas edilerek genel kadroya eklenmiştir."
    arts = [Article(no="84", body=body)]
    m = _maddeler(arts, TREE)[0]
    assert m.body == body


def test_madde_status_from_fikra_tree_all_mulga():
    # Madde statüsü FIKRA AĞACINDAN: TÜM fıkralar mülga → madde mülga. Gerçek veri: 7081 M10
    # '(1) (Mülga:...) (2) (Mülga:...)'. (Konum-kuralı bunu yürürlükte sanıyordu — kenar durum.)
    body = "(1) (Mülga: 13/2/2018-7098/EK MADDE 1 md.) (2) (Mülga: 13/2/2018-7098/5 md.)"
    m = _maddeler([Article(no="84", body=body)], TREE)[0]
    assert m.yurutluk == "mülga"


def test_madde_status_from_fikra_tree_one_active():
    # En az bir fıkra yürürlükte → madde yürürlükte. Gerçek veri: 5651 M3 (1 fıkra iptal, gerisi var).
    body = ("(1) Erişim sağlayıcılar esaslara uyar. (2) (İptal: Anayasa Mahkemesinin 2/10/2014 "
            "tarihli kararı ile) (3) Yer sağlayıcı yükümlülüklere tabidir.")
    m = _maddeler([Article(no="84", body=body)], TREE)[0]
    assert m.yurutluk == "yürürlükte"


def test_madde_status_single_fikra_iptal_is_mulga():
    # Tek fıkra ve o iptal → madde mülga. Gerçek veri: 7071 M34 '(1) (İptal: AYM ...)'.
    body = "(1) (İptal: Anayasa Mahkemesinin 14/11/2019 tarihli ve E.2018/1 kararı ile)"
    m = _maddeler([Article(no="84", body=body)], TREE)[0]
    assert m.yurutluk == "mülga"


def test_enrich_prefixed_inherits_section_and_flags():
    arts = [
        Article(no="84", body="asıl madde."),
        Article(no="Geçici 84", body="(Ek: 3/4/2013-6456/1 md.) geçici hüküm."),
    ]
    g = _maddeler(arts, TREE)[1]
    assert g.madde_tipi == "gecici"
    assert g.maddeId is None
    assert g.madde_baslik is None
    assert g.bolum_no == "BİRİNCİ BÖLÜM"


def test_enrich_strips_section_header_bleed():
    arts = [
        Article(no="84", body="asıl içerik. YEDİNCİ BÖLÜM Diğer Kazanç Gelire giren:"),
        Article(no="85", body="sonraki."),
    ]
    m = _maddeler(arts, TREE_BLEED)[0]
    assert "YEDİNCİ BÖLÜM" not in m.body
    assert m.body == "asıl içerik."


def test_enrich_status_uses_clean_body_not_next_madde_bleed():
    arts = [
        Article(no="84", body="bu madde yürürlükte. YEDİNCİ BÖLÜM Diğer Kazanç Gelire giren:"),
        Article(no="85", body="(Mülga: 1/1/2020-1234 md.) sonraki."),
    ]
    m = _maddeler(arts, TREE_BLEED)[0]
    assert m.yurutluk == "yürürlükte"


# --- Over-truncation regresyon testleri (gerçek-veri: KVKK M23, 7405 M30, 7315 M3, 7071 M1) ---
# Kök neden: _strip_bleed marker'ı gövdenin HER YERİNDE arıyordu; bleed yalnız SONDA olur.

# Sonraki maddenin başlığı 'Başkan' — KVKK M23 gerçek deseni (başlık gövdenin İÇİNDE tekrar eder).
_TREE_OT = parse_tree(
    "- Madde No: 23 - Kurulun çalışma esasları: (maddeId:23)\n"
    "- Madde No: 24 - Başkan: (maddeId:24)\n"
)


def test_enrich_does_not_truncate_on_midbody_marker_repeat():
    # KVKK M23: 'Başkan' kelimesi gövde içinde geçiyor; over-truncate ETMEMELİ (tüm gövde korunur).
    body = ("(1) Kurulun toplantı günlerini ve gündemini Başkan belirler. "
            "(2) Kurul, başkan dâhil en az altı üye ile toplanır ve karar alır.")
    arts = [Article(no="23", body=body), Article(no="24", body="(1) Başkan seçilir.")]
    m = _maddeler(arts, _TREE_OT)[0]
    assert "altı üye ile toplanır" in m.body          # gövdenin sonu KORUNDU
    assert len(m.body) > 100                            # %96 silinmedi


# Sonraki başlık = bu maddenin de konusu (7315 M3 'Arşiv araştırması' — gövde onunla başlıyor).
_TREE_OT2 = parse_tree(
    "- Madde No: 3 - Genel esaslar: (maddeId:3)\n"
    "- Madde No: 4 - Arşiv araştırması: (maddeId:4)\n"
)


def test_enrich_does_not_truncate_when_body_starts_with_next_title():
    body = "(1) Arşiv araştırması, statü gereği yapılan inceleme ve değerlendirmedir; sonuçları saklanır."
    arts = [Article(no="3", body=body), Article(no="4", body="(1) İçerik.")]
    m = _maddeler(arts, _TREE_OT2)[0]
    assert "saklanır" in m.body                          # baştan kesilmedi
    assert len(m.body) > 50


# Tek-karakter / salt-rakam marker (7071 M1: marker '4', gövdedeki 442'de kesiyordu).
_TREE_OT3 = parse_tree(
    "- Madde No: 1 - Kapsam: (maddeId:1)\n"
    "- Madde No: 2 - 4: (maddeId:2)\n"
)


def test_enrich_ignores_too_short_marker():
    body = "(1) Bu Kanun, 18/3/1924 tarihli ve 442 sayılı Köy Kanununu kapsar."
    arts = [Article(no="1", body=body), Article(no="2", body="(1) Sonraki.")]
    m = _maddeler(arts, _TREE_OT3)[0]
    assert "442 sayılı Köy Kanununu kapsar" in m.body    # '4'te kesilmedi


def test_enrich_madde_marker_bleed_at_tail_IS_stripped():
    # POZİTİF kesim (review açığı): madde-başlığı marker'ı gövdenin SON %15'inde GERÇEK kuyruk-bleed
    # olarak dururken kırpılmalı. 'Görevler' sonraki madde başlığı, gövde sonuna sızmış.
    body = "(1) Kurul kararları kesin niteliktedir ve derhâl uygulanır; itiraz yolu kapalıdır. Görevler"
    arts = [Article(no="5", body=body), Article(no="6", body="(1) İçerik.")]
    tree = parse_tree(
        "- Madde No: 5 - Karar: (maddeId:5)\n"
        "- Madde No: 6 - Görevler: (maddeId:6)\n"
    )
    m = _maddeler(arts, tree)[0]
    assert m.body.endswith("itiraz yolu kapalıdır.")     # kuyruk-bleed 'Görevler' kırpıldı
    assert "Görevler" not in m.body


# --- C1/C2 (FAZ 4): kolonsuz sonraki-madde başlığı + kenar-numara kuyruk sızması ---

def test_enrich_strips_colonless_high_confidence_header_tail():
    # C1: tree'de OLMAYAN kolonsuz kapanış-başlığı ('Yürürlük') gövde kuyruğuna sızmış. Yüksek-güven
    # sözlükle kesilir (332571-16 'Hizmet puanı' / 7474 gibi tree↔HTML uyuşmazlığı genel deseni).
    body = ("(1) Bu maddenin uygulanmasına ilişkin hususlar yönetmelikle belirlenir. Yürürlük")
    arts = [Article(no="16", body=body), Article(no="17", body="(1) İçerik.")]
    tree = parse_tree("- Madde No: 16 - Atama: (maddeId:16)\n")   # M17 tree'de YOK (uyuşmazlık)
    m = _maddeler(arts, tree)[0]
    assert m.body.endswith("yönetmelikle belirlenir.")
    assert "Yürürlük" not in m.body


def test_enrich_high_confidence_word_midbody_not_truncated():
    # C1 OVER-TRUNCATION KORUMA: yüksek-güven kelimesi ('Yürürlük') gövde ORTASINDA/cümle-içinde
    # meşru geçerse KESİLMEZ. Yalnız son %15'te + bağımsız kuyruk ifadesi kesilir.
    body = ("(1) Yürürlük tarihinden önce başlamış işlemler eski hükümlere tabidir ve bu husus "
            "ilgili kurumca ayrıca duyurulur, gerekli tedbirler alınır ve uygulamaya konulur.")
    arts = [Article(no="5", body=body), Article(no="6", body="(1) İçerik.")]
    tree = parse_tree("- Madde No: 5 - Geçiş: (maddeId:5)\n")
    m = _maddeler(arts, tree)[0]
    assert "uygulamaya konulur" in m.body                 # gövde sonu KORUNDU (cümle-içi 'Yürürlük')


def test_enrich_strips_kenar_numara_header_tail():
    # C2: kenar-numaralı sonraki-madde başlığı ('2. Kefalet hâlinde') gövde kuyruğuna sızmış.
    # Gerçek veri: TBK 6098 M139→M140 (103273-139). Tree-doğrulamalı kesilir.
    body = ("(1) Alacağın takası, ancak takas edilebileceği anda zamanaşımına uğramamış olması "
            "koşuluyla ileri sürülebilir. 2. Kefalet hâlinde")
    arts = [Article(no="139", body=body), Article(no="140", body="(1) İçerik.")]
    tree = parse_tree(
        "- Madde No: 139 - 1. Genel olarak: (maddeId:139)\n"
        "- Madde No: 140 - 2. Kefalet hâlinde: (maddeId:140)\n"
    )
    m = _maddeler(arts, tree)[0]
    assert m.body.endswith("ileri sürülebilir.")
    assert "Kefalet" not in m.body


def test_enrich_plain_madde_missing_in_tree_does_not_crash():
    arts = [
        Article(no="84", body="ağaçtaki."),
        Article(no="999", body="ağaçta olmayan düz madde."),
    ]
    m = _maddeler(arts, TREE)[1]
    assert m.madde_tipi == "asil"
    assert m.maddeId is None
    assert m.bolum_no == "BİRİNCİ BÖLÜM"


def test_enrich_propagates_kitap_and_ayirim_fields():
    # #1+#2: KİTAP ve AYIRIM tree'den Madde'ye ayrı alan olarak akmalı (hiyerarşi_yolu'na ek olarak).
    tree = parse_tree(
        "- BİRİNCİ KİTAP - Kişiler Hukuku (maddeId:1)\n"
        "  - İKİNCİ KISIM - Aile (maddeId:2)\n"
        "    - BİRİNCİ BÖLÜM - Nişanlanma (maddeId:3)\n"
        "      - BİRİNCİ AYIRIM - Koşullar (maddeId:4)\n"
        "        - Madde No: 118 - Nişanlanma: (maddeId:1180)\n"
    )
    m = _maddeler([Article(no="118", body="(1) Nişanlanma evlenme vaadiyle olur.")], tree)[0]
    assert m.kitap_no == "BİRİNCİ KİTAP"
    assert m.kitap_baslik == "Kişiler Hukuku"
    assert m.ayirim_no == "BİRİNCİ AYIRIM"
    assert m.ayirim_baslik == "Koşullar"
    assert m.kisim_no == "İKİNCİ KISIM"
    assert m.bolum_no == "BİRİNCİ BÖLÜM"


def test_enrich_titleless_levels_keep_null_baslik():
    # null-tutma kararı: ayraçsız (başlıksız) seviyelerde *_baslik None (no-tekrarı YOK). Medeni 4721.
    tree = parse_tree(
        "- BİRİNCİ KİTAP (maddeId:1)\n"
        "  - BİRİNCİ KISIM (maddeId:2)\n"
        "    - BİRİNCİ BÖLÜM (maddeId:3)\n"
        "      - Madde No: 8 - Hak ehliyeti: (maddeId:80)\n"
    )
    m = _maddeler([Article(no="8", body="(1) Her insanın hak ehliyeti vardır.")], tree)[0]
    assert m.kitap_no == "BİRİNCİ KİTAP" and m.kitap_baslik is None
    assert m.kisim_no == "BİRİNCİ KISIM" and m.kisim_baslik is None
    assert m.bolum_no == "BİRİNCİ BÖLÜM" and m.bolum_baslik is None


def test_enrich_populates_new_fields():
    arts = [Article(no="84", body="(Değişik: 9/4/2003-4842/3 md.) (1) Birinci fıkra.")]
    m = _maddeler(arts, TREE)[0]
    assert m.id == "193-84"
    assert len(m.degisiklik_gecmisi) == 1
    assert m.degisiklik_gecmisi[0].kanun_no == "4842"
    assert "Değişik" not in m.body_temiz
    # Lider künye '(Değişik:...)' preamble (no=None) + gerçek '(1)' fıkra ayrı (Bug 2 fix):
    # künye fıkra bölmeyi çökertmez; numaralı fıkra korunur.
    assert [f.no for f in m.fikralar] == [None, "(1)"]
    assert len([f for f in m.fikralar if f.no]) == 1   # 1 numaralı fıkra


def test_enrich_separates_footnote_appendix_into_global():
    arts = [Article(
        no="84",
        body=(
            "Madde gövdesi.\n"
            "[1] birinci dipnot tanımı.\n"
            "[2] ikinci dipnot tanımı.\n"
            "[3] üçüncü dipnot tanımı."
        ),
    )]
    maddeler, dipnotlar = enrich(arts, TREE, "193")
    assert "[1]" not in maddeler[0].body_temiz
    assert [d.no for d in dipnotlar] == [1, 2, 3]


def test_enrich_links_inline_footnote_to_madde():
    arts = [Article(
        no="84",
        body=(
            "Bu hüküm [2] ile değişti.\n"
            "[1] birinci.\n"
            "[2] ikinci.\n"
            "[3] üçüncü."
        ),
    )]
    maddeler, _ = enrich(arts, TREE, "193")
    assert [d.no for d in maddeler[0].dipnotlar] == [2]


def test_enrich_backward_compatible_without_html():
    # html_* verilmezse mevcut davranış birebir: tablolar boş, dipnotlar regex'ten.
    arts = [Article(no="84", body="(Değişik: 9/4/2003-4842/3 md.) içerik.")]
    maddeler, _ = enrich(arts, TREE, "193")
    m = maddeler[0]
    assert m.tablolar == []
    assert m.madde_baslik == "Beyanname çeşitleri"  # mevcut tree-join korunur


def test_enrich_injects_html_tables():
    arts = [Article(no="103", body="Tarife metni düz halde.")]
    html_tables = {"103": ["| dilim | oran |\n| --- | --- |\n| 18.000 TL | %15 |"]}
    maddeler, _ = enrich(arts, TREE, "193", html_tables=html_tables)
    m = maddeler[0]
    assert len(m.tablolar) == 1
    assert "%15" in m.tablolar[0]
    assert "| dilim | oran |" in m.body_temiz   # body_temiz'e gömüldü


def test_enrich_html_dipnot_overrides_regex():
    from mevzuat_tool.dipnot import Dipnot
    arts = [Article(no="5", body="Metin [1] atıf.\n[1] regex-tanımı.\n[2] x.\n[3] y.")]
    html_dipnotlar = {"5": [Dipnot(no=1, text="ANCHOR-tanımı")]}
    maddeler, _ = enrich(arts, TREE, "193", html_dipnotlar=html_dipnotlar)
    m = maddeler[0]
    assert [d.text for d in m.dipnotlar] == ["ANCHOR-tanımı"]   # anchor asıl
