import json

import bot.subscriptions as subs


class FakeGist:
    """模擬 GitHub gist API 的 get/patch 往返。"""

    def __init__(self, content="{}"):
        self.content = content
        self.patches = 0

    def get(self, url, **kw):
        return _Resp({"files": {"subscriptions.json": {"content": self.content}}})

    def patch(self, url, **kw):
        self.content = kw["json"]["files"]["subscriptions.json"]["content"]
        self.patches += 1
        return _Resp({})


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _wire(monkeypatch, gist):
    monkeypatch.setattr(subs.httpx, "get", gist.get)
    monkeypatch.setattr(subs.httpx, "patch", gist.patch)


def test_add_and_load(monkeypatch):
    gist = FakeGist()
    _wire(monkeypatch, gist)
    assert subs.add("U1", "DQF") is True
    assert subs.add("U1", "DQF") is False          # 重複訂閱不再寫入
    assert json.loads(gist.content) == {"U1": ["DQF"]}
    assert gist.patches == 1


def test_remove(monkeypatch):
    gist = FakeGist('{"U1": ["DQF", "CSF"], "U2": ["CDF"]}')
    _wire(monkeypatch, gist)
    assert subs.remove("U1", "DQF") is True
    assert subs.remove("U1", "ZZZ") is False
    assert json.loads(gist.content) == {"U1": ["CSF"], "U2": ["CDF"]}


def test_remove_last_drops_user(monkeypatch):
    gist = FakeGist('{"U1": ["DQF"]}')
    _wire(monkeypatch, gist)
    subs.remove("U1", "DQF")
    assert json.loads(gist.content) == {}


def test_codes_for(monkeypatch):
    gist = FakeGist('{"U1": ["DQF"]}')
    _wire(monkeypatch, gist)
    assert subs.codes_for("U1") == ["DQF"]
    assert subs.codes_for("U9") == []


def test_empty_gist_content(monkeypatch):
    gist = FakeGist("")
    _wire(monkeypatch, gist)
    assert subs.load() == {}
