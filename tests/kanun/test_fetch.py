"""fetch.py — Retry-After-uyumlu çekim çekirdeği testleri (ağ yok, sahte client + sahte sleep)."""
import asyncio

import pytest

from kanun.fetch import _post_with_retry, _RateState


class _FakeResp:
    def __init__(self, status, headers=None, body=None):
        self.status_code = status
        self.headers = headers or {}
        self._body = body or {}

    def json(self):
        return self._body


class _FakeClient:
    """Sırayla verilen yanıtları döndüren sahte httpx client."""
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def post(self, url, json=None):
        self.calls += 1
        return self._responses.pop(0)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _recorder():
    """Beklenen süreleri kaydeden sahte async sleep."""
    slept = []

    async def _sleep(s):
        slept.append(s)
    return slept, _sleep


def test_returns_body_on_200():
    ok = _FakeResp(200, body={"metadata": {"FMTY": "SUCCESS"}, "data": {"x": 1}})
    client = _FakeClient([ok])
    slept, sleep = _recorder()
    body = _run(_post_with_retry(client, "/x", {}, _RateState(), sleep=sleep))
    assert body == {"metadata": {"FMTY": "SUCCESS"}, "data": {"x": 1}}
    assert client.calls == 1
    assert slept == []  # 200 → hiç beklemez


def test_429_then_200_waits_retry_after():
    r429 = _FakeResp(429, headers={"retry-after": "17"})
    ok = _FakeResp(200, body={"metadata": {"FMTY": "SUCCESS"}, "data": {}})
    client = _FakeClient([r429, ok])
    slept, sleep = _recorder()
    body = _run(_post_with_retry(client, "/x", {}, _RateState(), sleep=sleep))
    assert body["metadata"]["FMTY"] == "SUCCESS"
    assert client.calls == 2
    assert len(slept) == 1 and 17 <= slept[0] <= 18.5  # Retry-After=17 + küçük tampon


def test_429_uses_default_when_header_missing():
    r429 = _FakeResp(429, headers={})  # Retry-After yok
    ok = _FakeResp(200, body={"metadata": {"FMTY": "SUCCESS"}, "data": {}})
    client = _FakeClient([r429, ok])
    slept, sleep = _recorder()
    _run(_post_with_retry(client, "/x", {}, _RateState(), sleep=sleep))
    assert len(slept) == 1 and slept[0] >= 15  # makul varsayılan (>=15s)


def test_gives_up_after_max_retries():
    rs = [_FakeResp(429, headers={"retry-after": "1"}) for _ in range(10)]
    client = _FakeClient(rs)
    _, sleep = _recorder()
    with pytest.raises(RuntimeError):
        _run(_post_with_retry(client, "/x", {}, _RateState(), sleep=sleep, max_tries=4))
    assert client.calls == 4


def test_rate_state_proactive_pacing_after_bucket():
    # 10 başarılı istekten sonra _RateState proaktif bekleme önerir (kova ~10).
    rs = _RateState(bucket=10, cooldown=17)
    waits = [rs.before_request() for _ in range(12)]
    assert waits[0] == 0 and waits[9] == 0      # ilk 10 serbest
    assert waits[10] >= 17                        # 11. istek öncesi kova doldu → bekle


# --- fetch_tree disk cache (Faz 4: tekrar-üretim ucuzlasın; tree'ler API'den bir kez çekilir) ---

def _fetcher_no_net(tmp_path):
    """Ağsız MevzuatFetcher: client None (çağrılırsa patlar → cache okunduğunu kanıtlar)."""
    from kanun.fetch import MevzuatFetcher
    f = MevzuatFetcher.__new__(MevzuatFetcher)
    f.cache = tmp_path
    f._client = None
    f._rate = _RateState()
    return f


def test_fetch_tree_reads_cache_without_network(tmp_path):
    import json as _json
    from kanun.fetch import parse_tree_json
    # Ham API children JSON'unu cache'e elle yaz (gerçek fetch_tree formatı).
    children = [{"maddeNo": "1", "maddeId": "100", "maddeBaslik": "Amaç", "children": []}]
    (tmp_path / "treejson_555.json").write_text(_json.dumps(children), encoding="utf-8")
    f = _fetcher_no_net(tmp_path)
    nodes = _run(f.fetch_tree("555"))            # client None → ağa gitmeden cache'ten okumalı
    assert len(nodes) == 1
    assert nodes[0].madde_no == "1"
    assert nodes[0].madde_baslik == "Amaç"
    # parse_tree_json ile birebir aynı sonucu vermeli (cache = ham children)
    assert nodes == parse_tree_json(children)


def test_fetch_tree_writes_cache_after_fetch(tmp_path):
    # Cache yoksa API'den çeker VE diske yazar (sonraki çağrı ağsız olsun).
    children = [{"maddeNo": "7", "maddeId": "70", "maddeBaslik": "Tanım", "children": []}]
    ok = _FakeResp(200, body={"metadata": {"FMTY": "SUCCESS"}, "data": {"children": children}})
    f = _fetcher_no_net(tmp_path)
    f._client = _FakeClient([ok])
    nodes = _run(f.fetch_tree("777"))
    assert nodes[0].madde_no == "7"
    cache_file = tmp_path / "treejson_777.json"
    assert cache_file.exists()                   # cache yazıldı
    import json as _json
    assert _json.loads(cache_file.read_text(encoding="utf-8"))[0]["maddeNo"] == "7"


def test_fetch_tree_empty_not_cached(tmp_path):
    # 0-madde (FMTY != SUCCESS) → cache YAZILMAZ (boş cache sonraki gerçek çekimi engellemesin).
    fail = _FakeResp(200, body={"metadata": {"FMTY": "FAIL"}, "data": {}})
    f = _fetcher_no_net(tmp_path)
    f._client = _FakeClient([fail])
    nodes = _run(f.fetch_tree("888"))
    assert nodes == []
    assert not (tmp_path / "treejson_888.json").exists()


# ── FAZ 22: strip_html paragraf sınırını \x1f ile korur ──
from kanun.fetch import strip_html


def test_strip_html_p_sinirina_unit_separator_koyar():
    # Ham HTML'de her fıkra ayrı <p>. strip_html bu sınıra \x1f koyar → fıkra bölme için sinyal.
    html = "<p>Birinci fıkra metni.</p><p>İkinci fıkra metni.</p>"
    out = strip_html(html)
    assert "\x1f" in out
    # iki fıkra sınırla ayrık, içerik korunur
    parcalar = [p for p in out.split("\x1f") if p.strip()]
    assert len(parcalar) == 2
    assert "Birinci fıkra" in parcalar[0]
    assert "İkinci fıkra" in parcalar[1]


def test_strip_html_br_hala_satir_kirigi():
    # <br> davranışı DEĞİŞMEZ (paragraf değil, satır-içi kırık) — normalize onu boşluk yapar.
    html = "Satır bir<br>Satır iki"
    out = strip_html(html)
    assert "\x1f" not in out          # <br> paragraf sınırı değil


# ── Liste yanıtı (searchDocuments) → kanun-düzeyi R.G. tarihi/sayısı ──
from kanun.fetch import LISTE_CACHE, liste_cache_oku, parse_liste_kaydi

# Gerçek bedesten mevzuatList kaydı (KVKK; canlı yanıt 2026-10-18 — alan adları ve tipleri birebir).
_KVKK_KAYIT = {
    "mevzuatId": "104383",
    "mevzuatNo": 6698,
    "mevzuatAdi": "KİŞİSEL VERİLERİN KORUNMASI KANUNU",
    "mevzuatTur": {"id": 1, "name": "KANUN", "description": "Kanunlar",
                   "maddeSonuRegex": ".*Bu.*Kanun.*hükümlerini.*yürütür\\."},
    "mevzuatTertip": 5,
    "kayitTarihi": "2024-06-03T12:14:13.297",
    "guncellemeTarihi": None,
    "resmiGazeteTarihi": "2016-04-07T00:00:00",
    "resmiGazeteSayisi": "29677",
    "url": "https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=6698&MevzuatTur=1&MevzuatTertip=5",
    "mukerrer": "HAYIR",
    "ekler": None,
    "gerekceId": None,
}
_BOS_RG = {"resmi_gazete_tarihi": None, "resmi_gazete_sayisi": None}


def _kayit(mid, **alanlar):
    k = dict(_KVKK_KAYIT, mevzuatId=mid)
    k.update(alanlar)
    return k


def _liste_sayfasi(docs, total):
    return _FakeResp(200, body={"metadata": {"FMTY": "SUCCESS"},
                                "data": {"mevzuatList": docs, "total": total, "start": 0}})


class _KayitliClient(_FakeClient):
    """İstek gövdelerini de kaydeden sahte client (hangi tür/sayfa istendi?)."""
    def __init__(self, responses):
        super().__init__(responses)
        self.istekler = []

    async def post(self, url, json=None):
        self.istekler.append((url, json))
        return await super().post(url, json=json)


def test_parse_liste_kaydi_gercek_bicim():
    assert parse_liste_kaydi(_KVKK_KAYIT) == {"resmi_gazete_tarihi": "2016-04-07",
                                              "resmi_gazete_sayisi": "29677"}


def test_parse_liste_kaydi_saat_gurultusu_atilir():
    # Yeni kayıtlarda saat kısmı kayıt-zamanı gürültüsü (canlı 7540: '2025-02-27T10:39:37.023');
    # tarih kısmı R.G. tarihidir. Yalın ISO tarih de kabul.
    r = parse_liste_kaydi(_kayit("340691", resmiGazeteTarihi="2025-02-27T10:39:37.023"))
    assert r["resmi_gazete_tarihi"] == "2025-02-27"
    r = parse_liste_kaydi(_kayit("1", resmiGazeteTarihi="2016-04-07"))
    assert r["resmi_gazete_tarihi"] == "2016-04-07"


def test_parse_liste_kaydi_kayit_yoksa_none():
    # Cache'te kanunun liste kaydı yok / kayıt bozuk → alanlar None (build kırılmaz).
    assert parse_liste_kaydi(None) == _BOS_RG
    assert parse_liste_kaydi({}) == _BOS_RG
    assert parse_liste_kaydi("bozuk") == _BOS_RG
    eksik = {k: v for k, v in _KVKK_KAYIT.items() if not k.startswith("resmiGazete")}
    assert parse_liste_kaydi(eksik) == _BOS_RG


def test_parse_liste_kaydi_bozuk_deger_none_hata_atmaz():
    # ISO dışı biçim / geçersiz gün / yanlış tip → None (tahmin yok, asla exception yok).
    for tarih in ("", "   ", "07.04.2016", "2016-13-45T00:00:00", "2016-02-30", "abc",
                  "2016-04-07X", 20160407, None, {"x": 1}):
        r = parse_liste_kaydi(_kayit("1", resmiGazeteTarihi=tarih))
        assert r["resmi_gazete_tarihi"] is None, tarih
    for sayi in ("", "  ", None, True, 1.5, ["29677"]):
        r = parse_liste_kaydi(_kayit("1", resmiGazeteSayisi=sayi))
        assert r["resmi_gazete_sayisi"] is None, sayi


def test_parse_liste_kaydi_sayi_str_normalize():
    # R.G. sayısı kanun_no gibi str tutulur; int gelirse çevrilir, kenar boşluğu atılır.
    assert parse_liste_kaydi(_kayit("1", resmiGazeteSayisi=29677))["resmi_gazete_sayisi"] == "29677"
    assert parse_liste_kaydi(_kayit("1", resmiGazeteSayisi=" 29677 "))["resmi_gazete_sayisi"] == "29677"


def test_liste_cache_oku_yok_bos_bozuk(tmp_path):
    assert liste_cache_oku(tmp_path) == {}                    # cache yok → {} (alanlar None olur)
    (tmp_path / LISTE_CACHE).write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError):
        liste_cache_oku(tmp_path)                             # beklenmedik biçim
    (tmp_path / LISTE_CACHE).write_text("{bozuk", encoding="utf-8")
    with pytest.raises(ValueError):
        liste_cache_oku(tmp_path)                             # bozuk JSON


def test_fetch_kanun_liste_reads_cache_without_network(tmp_path):
    import json as _json
    (tmp_path / LISTE_CACHE).write_text(_json.dumps({"104383": _KVKK_KAYIT}, ensure_ascii=False),
                                        encoding="utf-8")
    f = _fetcher_no_net(tmp_path)            # client None → ağa giderse patlar
    assert _run(f.fetch_kanun_liste()) == {"104383": _KVKK_KAYIT}


def test_fetch_kanun_liste_sayfalar_cache_yazar_ids_dokunmaz(tmp_path):
    # 3 kayıt / page_size=2 → 2 sayfa. Ham kayıtlar mid'e göre cache'lenir; yalnız KANUN istenir;
    # _kanun_ids.txt (build'in kanun seti/sırası) DEĞİŞMEZ.
    import json as _json
    ids_path = tmp_path / "_kanun_ids.txt"
    ids_path.write_text("6698\t104383\tKVKK", encoding="utf-8")
    k1, k2, k3 = _kayit("1"), _kayit("2"), _kayit("3", resmiGazeteSayisi="30000")
    f = _fetcher_no_net(tmp_path)
    f._client = _KayitliClient([_liste_sayfasi([k1, k2], 3), _liste_sayfasi([k3], 3)])
    liste = _run(f.fetch_kanun_liste(page_size=2))
    assert list(liste) == ["1", "2", "3"]
    assert liste["3"]["resmiGazeteSayisi"] == "30000"
    assert [i[1]["data"]["pageNumber"] for i in f._client.istekler] == [1, 2]
    assert all(i[0] == "/searchDocuments" and i[1]["data"]["mevzuatTurList"] == ["KANUN"]
               for i in f._client.istekler)
    assert _json.loads((tmp_path / LISTE_CACHE).read_text(encoding="utf-8")) == liste
    assert ids_path.read_text(encoding="utf-8") == "6698\t104383\tKVKK"


def test_fetch_kanun_liste_tekillestirir(tmp_path):
    # Aynı mevzuatId iki sayfada gelirse ilk görülen kazanır (fetch_kanun_ids ile aynı kural).
    f = _fetcher_no_net(tmp_path)
    f._client = _FakeClient([_liste_sayfasi([_kayit("1"), _kayit("2")], 3),
                             _liste_sayfasi([_kayit("2", resmiGazeteSayisi="99")], 3)])
    liste = _run(f.fetch_kanun_liste(page_size=2))
    assert list(liste) == ["1", "2"]
    assert liste["2"]["resmiGazeteSayisi"] == "29677"


def test_fetch_kanun_liste_fmty_hata_cache_yazmaz(tmp_path):
    # Sessiz-hata kapısı: 200 + FMTY=ERROR (ör. pageSize>20) → RuntimeError, cache YAZILMAZ.
    hata = _FakeResp(200, body={"metadata": {"FMTY": "ERROR",
                                             "FMTE": "Kayıt sayısı 20'den fazla olamaz"}, "data": {}})
    f = _fetcher_no_net(tmp_path)
    f._client = _FakeClient([hata])
    with pytest.raises(RuntimeError):
        _run(f.fetch_kanun_liste())
    assert not (tmp_path / LISTE_CACHE).exists()


def test_fetch_kanun_liste_bos_yanit_cache_yazmaz(tmp_path):
    f = _fetcher_no_net(tmp_path)
    f._client = _FakeClient([_liste_sayfasi([], 0)])
    assert _run(f.fetch_kanun_liste()) == {}
    assert not (tmp_path / LISTE_CACHE).exists()


def test_fetch_kanun_liste_bozuk_cache_yeniden_ceker(tmp_path):
    (tmp_path / LISTE_CACHE).write_text("{bozuk", encoding="utf-8")
    f = _fetcher_no_net(tmp_path)
    f._client = _FakeClient([_liste_sayfasi([_kayit("1")], 1)])
    liste = _run(f.fetch_kanun_liste())
    assert list(liste) == ["1"]
    assert liste_cache_oku(tmp_path) == liste      # bozuk cache onarıldı
