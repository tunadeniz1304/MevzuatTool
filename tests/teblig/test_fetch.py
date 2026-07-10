"""teblig/fetch.py — parti-tabanlı rate limit + ağaçsız tebliğ + sessiz-hata kapısı.

Ağ yok: sahte client + enjekte edilen sleep. (kanun/test_fetch.py ile aynı desen, ayrı kopya —
ADR-0014: türler arası sıfır kod paylaşımı.)
"""
import asyncio

import pytest

from teblig.fetch import _post_with_retry, _HizSinirlayici, strip_html


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
        self.payloads = []

    async def post(self, url, json=None):
        self.calls += 1
        self.payloads.append(json)
        return self._responses.pop(0)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _recorder():
    slept = []

    async def _sleep(s):
        slept.append(s)

    return slept, _sleep


# ── _post_with_retry ─────────────────────────────────────────────

def test_200_dondurur_beklemez():
    ok = _FakeResp(200, body={"metadata": {"FMTY": "SUCCESS"}, "data": {"x": 1}})
    c = _FakeClient([ok])
    slept, sleep = _recorder()
    body = _run(_post_with_retry(c, "/x", {}, _HizSinirlayici(), sleep=sleep))
    assert body["data"] == {"x": 1}
    assert c.calls == 1
    assert slept == []            # ilk istek: parti sayacı 0 → hiç beklemez


def test_429_retry_after_kadar_bekler():
    # Retry-After DÜRÜST olduğu ölçüldü (30 dedi → 30.3 sn'de açıldı) → tam o kadar beklenmeli.
    r429 = _FakeResp(429, headers={"retry-after": "27"})
    ok = _FakeResp(200, body={"metadata": {"FMTY": "SUCCESS"}, "data": {}})
    c = _FakeClient([r429, ok])
    slept, sleep = _recorder()
    _run(_post_with_retry(c, "/x", {}, _HizSinirlayici(), sleep=sleep))
    assert c.calls == 2
    assert any(27 <= s <= 28.5 for s in slept)


def test_429_header_yoksa_varsayilan_bekler():
    r429 = _FakeResp(429, headers={})
    ok = _FakeResp(200, body={"metadata": {"FMTY": "SUCCESS"}, "data": {}})
    c = _FakeClient([r429, ok])
    slept, sleep = _recorder()
    _run(_post_with_retry(c, "/x", {}, _HizSinirlayici(), sleep=sleep))
    assert any(s >= 25 for s in slept)   # ölçülen pencere ~29-30 sn


def test_max_tries_sonunda_pes_eder():
    rs = [_FakeResp(429, headers={"retry-after": "1"}) for _ in range(10)]
    c = _FakeClient(rs)
    _, sleep = _recorder()
    with pytest.raises(RuntimeError):
        _run(_post_with_retry(c, "/x", {}, _HizSinirlayici(), sleep=sleep, max_tries=4))
    assert c.calls == 4


# ── _HizSinirlayici: PARTİ modeli (sabit aralık DEĞİL) ────────────

def test_parti_dolunca_pencere_kadar_bekler():
    """Ölçüm: aralık önemsiz, pencere başına SAYI önemli. parti=3 → 4. istekte pencere beklenir."""
    h = _HizSinirlayici(parti=3, pencere=31.0)
    slept, sleep = _recorder()
    for _ in range(4):
        _run(h.bekle(sleep=sleep))
    # 1. istek: bekleme yok. 2-3.: parti-içi küçük aralık. 4.: pencere (31 sn).
    assert slept[0] != 31.0
    assert 31.0 in slept
    assert sum(1 for s in slept if s == 31.0) == 1


def test_parti_ici_kucuk_aralik():
    h = _HizSinirlayici(parti=5, pencere=31.0)
    slept, sleep = _recorder()
    for _ in range(3):
        _run(h.bekle(sleep=sleep))
    assert len(slept) == 2                 # ilk istek beklemez
    assert all(0 < s < 1 for s in slept)   # parti içi: nezaket aralığı


def test_geri_cekil_parti_kucultur_ve_sayaci_sifirlar():
    h = _HizSinirlayici(parti=9, pencere=31.0)
    h._sayac = 5
    h.geri_cekil()
    assert h.parti == 8      # kota tahminimiz fazlaymış → küçült
    assert h._sayac == 0     # pencere zaten Retry-After ile beklenecek


def test_geri_cekil_taban_3():
    h = _HizSinirlayici(parti=3, pencere=31.0)
    for _ in range(5):
        h.geri_cekil()
    assert h.parti == 3      # sonsuza kadar küçülmez


# ── Sessiz-hata kapısı: pageSize>20 → HTTP 200 ama FMTY=ERROR ─────

def _fetcher_no_net(tmp_path):
    from teblig.fetch import TebligFetcher
    f = TebligFetcher.__new__(TebligFetcher)
    f.cache = tmp_path
    f._client = None
    f._hiz = _HizSinirlayici()
    return f


def test_search_fmty_error_sessizce_gecmez(tmp_path, monkeypatch):
    """pageSize>20 verilince sunucu HTTP 200 + metadata.FMTY='ERROR' döner, liste boş gelir.
    Bu SESSİZCE 0-tebliğ olarak geçmemeli — RuntimeError fırlatmalı (gerçek tuzak, yaşandı)."""
    hata = _FakeResp(200, body={
        "metadata": {"FMTY": "ERROR", "FMTE": "data.pageSize=Kayıt sayısı 20'den fazla olamaz"},
        "data": {},
    })
    f = _fetcher_no_net(tmp_path)
    f._client = _FakeClient([hata])
    monkeypatch.setattr("teblig.fetch.asyncio.sleep", lambda *_a, **_k: asyncio.sleep(0))
    with pytest.raises(RuntimeError, match="FMTY"):
        _run(f.fetch_teblig_ids(use_cache=False))


# ── Ağaçsız tebliğ: HATA DEĞİL, kayıt altına alınır ───────────────

def test_agacsiz_teblig_bos_doner_ve_kaydedilir(tmp_path, monkeypatch):
    """Tebliğlerin bir kısmında madde ağacı YOK ('ağaç yapısı mevcut değildir').
    Bu hata değil: [] döner, boş cache YAZILMAZ, mid _agacsiz.txt'ye eklenir."""
    fail = _FakeResp(200, body={"metadata": {"FMTY": "ERROR"}, "data": {}})
    f = _fetcher_no_net(tmp_path)
    f._client = _FakeClient([fail])
    monkeypatch.setattr("teblig.fetch.asyncio.sleep", lambda *_a, **_k: asyncio.sleep(0))
    nodes = _run(f.fetch_tree("350781"))
    assert nodes == []
    assert not (tmp_path / "treejson_350781.json").exists()   # boş cache yazılmaz
    assert "350781" in (tmp_path / "_agacsiz.txt").read_text(encoding="utf-8")


def test_agacsiz_kayitli_mid_tekrar_istenmez(tmp_path):
    """_agacsiz.txt'de olan mid için ağa GİTMEZ (client None → giderse patlar)."""
    (tmp_path / "_agacsiz.txt").write_text("350781\n", encoding="utf-8")
    f = _fetcher_no_net(tmp_path)          # _client None
    assert _run(f.fetch_tree("350781")) == []


def test_agacli_teblig_cache_yazar(tmp_path, monkeypatch):
    children = [{"maddeNo": "1", "maddeId": "27", "maddeBaslik": "Amaç", "children": []}]
    ok = _FakeResp(200, body={"metadata": {"FMTY": "SUCCESS"}, "data": {"children": children}})
    f = _fetcher_no_net(tmp_path)
    f._client = _FakeClient([ok])
    monkeypatch.setattr("teblig.fetch.asyncio.sleep", lambda *_a, **_k: asyncio.sleep(0))
    nodes = _run(f.fetch_tree("352266"))
    assert nodes[0].madde_no == "1" and nodes[0].madde_baslik == "Amaç"
    assert (tmp_path / "treejson_352266.json").exists()


def test_tree_cache_agsiz_okunur(tmp_path):
    import json as _json
    children = [{"maddeNo": "5", "maddeId": "50", "maddeBaslik": "Yetki", "children": []}]
    (tmp_path / "treejson_999.json").write_text(_json.dumps(children), encoding="utf-8")
    f = _fetcher_no_net(tmp_path)          # _client None → ağa giderse patlar
    nodes = _run(f.fetch_tree("999"))
    assert len(nodes) == 1 and nodes[0].madde_no == "5"


# ── Paralellik: ölçülen optimum 3 işçi ──────────────────────────

def test_isci_sayisi_olculen_optimum():
    """Kota tam IP-başına değil; ayrı bağlantı havuzları kısmen ayrı kotaya sahip.
    Ölçüm (9 istek + 31 sn, 3 tur): 1 işçi 0.303 i/s · 3 işçi 0.599 (TEPE) · 5 işçi 0.295.
    5+ işçide 429 cezaları kazancı yer. Bu sabit kazara büyütülmesin."""
    from teblig.fetch import _ISCI
    assert _ISCI == 3


def test_round_robin_paylar_ortusmez_ve_tam_kapsar():
    """İşçiler mid kümelerini bölüşür: çakışma yok (aynı dosyayı iki kez çekmez),
    kayıp yok (her mid tam bir işçiye düşer). `eksik[i::isci]` dilimlemesinin sözleşmesi."""
    eksik = [f"m{i}" for i in range(10)]
    isci = 3
    paylar = [eksik[i::isci] for i in range(isci)]
    hepsi = [m for p in paylar for m in p]
    assert sorted(hepsi) == sorted(eksik)      # kayıp yok
    assert len(hepsi) == len(set(hepsi))       # çakışma yok
    assert all(len(p) >= 3 for p in paylar)    # dengeli dağılım (10/3)


# ── strip_html: kanun ile AYNI sözleşme (\x1f paragraf sınırı) ────

def test_strip_html_paragraf_sinirina_unit_separator():
    out = strip_html("<p>Birinci fıkra.</p><p>İkinci fıkra.</p>")
    parcalar = [p for p in out.split("\x1f") if p.strip()]
    assert len(parcalar) == 2
    assert "Birinci" in parcalar[0] and "İkinci" in parcalar[1]


def test_strip_html_br_paragraf_siniri_degil():
    assert "\x1f" not in strip_html("Satır bir<br>Satır iki")
