"""fetch.py — Retry-After-uyumlu çekim çekirdeği testleri (ağ yok, sahte client + sahte sleep)."""
import asyncio

import pytest

from mevzuat_tool.fetch import _post_with_retry, _RateState


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
    from mevzuat_tool.fetch import MevzuatFetcher
    f = MevzuatFetcher.__new__(MevzuatFetcher)
    f.cache = tmp_path
    f._client = None
    f._rate = _RateState()
    return f


def test_fetch_tree_reads_cache_without_network(tmp_path):
    import json as _json
    from mevzuat_tool.fetch import parse_tree_json
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
