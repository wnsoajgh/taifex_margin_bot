import base64
import hashlib
import hmac
import importlib
import json

from fastapi.testclient import TestClient


def _client(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret")
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "test-token")
    import bot.app
    importlib.reload(bot.app)
    return TestClient(bot.app.app), bot.app


def _sign(body: bytes, secret: str) -> str:
    return base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def test_health(monkeypatch):
    client, _ = _client(monkeypatch)
    assert client.get("/health").json() == {"ok": True}


def test_callback_rejects_bad_signature(monkeypatch):
    client, _ = _client(monkeypatch)
    r = client.post("/callback", content=b"{}",
                    headers={"X-Line-Signature": "bogus"})
    assert r.status_code == 400


def test_callback_accepts_valid_signature(monkeypatch):
    client, mod = _client(monkeypatch)
    sent = []
    monkeypatch.setattr(mod, "_reply", lambda token, text: sent.append((token, text)))
    monkeypatch.setattr(mod.service, "build_answer", lambda q: f"answer:{q}")
    body = json.dumps({"destination": "x", "events": [{
        "type": "message", "mode": "active", "timestamp": 0,
        "webhookEventId": "w", "deliveryContext": {"isRedelivery": False},
        "replyToken": "rtok", "source": {"type": "user", "userId": "U1"},
        "message": {"id": "m1", "type": "text", "quoteToken": "q", "text": "華新"},
    }]}).encode()
    r = client.post("/callback", content=body,
                    headers={"X-Line-Signature": _sign(body, "test-secret")})
    assert r.status_code == 200
    assert sent == [("rtok", "answer:華新")]
