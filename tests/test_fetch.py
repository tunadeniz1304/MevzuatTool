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
