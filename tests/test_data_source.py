import bot.data_source as ds


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_and_cache(monkeypatch):
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        return FakeResp({"updated_at": "2026/06/11", "contracts": []})

    monkeypatch.setattr(ds.httpx, "get", fake_get)
    ds._cache.clear()

    t = [1000.0]
    monkeypatch.setattr(ds.time, "monotonic", lambda: t[0])

    assert ds.get_json("margins.json")["updated_at"] == "2026/06/11"
    assert ds.get_json("margins.json")  # 快取內，不再打網路
    assert len(calls) == 1

    t[0] += ds.TTL_SECONDS + 1          # 過期後重抓
    ds.get_json("margins.json")
    assert len(calls) == 2


def test_expired_cache_kept_on_fetch_error(monkeypatch):
    """重抓失敗時退回上一份快取，bot 不因 GitHub 短暫故障而掛掉。"""
    ds._cache.clear()
    t = [1000.0]
    monkeypatch.setattr(ds.time, "monotonic", lambda: t[0])
    monkeypatch.setattr(ds.httpx, "get",
                        lambda url, **kw: FakeResp({"date": "20260611", "prices": {}}))
    ds.get_json("settlements.json")

    def boom(url, **kw):
        raise ds.httpx.ConnectError("down")

    monkeypatch.setattr(ds.httpx, "get", boom)
    t[0] += ds.TTL_SECONDS + 1
    assert ds.get_json("settlements.json")["date"] == "20260611"
