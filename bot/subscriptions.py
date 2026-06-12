"""訂閱名單儲存：GitHub secret gist（{userId: [期貨代碼...]}）。

訂閱檔含 LINE userId，不放 public repo；secret gist 以不可猜測的 URL 保護。
讀寫頻率極低（訂閱動作 + 每日推播各一次），不做快取。
"""
import json
import os

import httpx

GIST_API = "https://api.github.com/gists/{gist_id}"
FILE_NAME = "subscriptions.json"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ.get('GIST_TOKEN', '')}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "taifex-margin-bot",
    }


def _url() -> str:
    return GIST_API.format(gist_id=os.environ.get("SUBS_GIST_ID", ""))


def load() -> dict:
    resp = httpx.get(_url(), headers=_headers(), timeout=10)
    resp.raise_for_status()
    file_entry = resp.json()["files"].get(FILE_NAME)
    if not file_entry:
        return {}
    content = file_entry.get("content") or ""
    return json.loads(content) if content.strip() else {}


def _save(subs: dict) -> None:
    resp = httpx.patch(_url(), headers=_headers(), timeout=10, json={
        "files": {FILE_NAME: {"content": json.dumps(subs, ensure_ascii=False, indent=1)}}})
    resp.raise_for_status()


def add(user_id: str, code: str) -> bool:
    """訂閱；已訂閱過回 False。"""
    subs = load()
    codes = subs.setdefault(user_id, [])
    if code in codes:
        return False
    codes.append(code)
    _save(subs)
    return True


def remove(user_id: str, code: str) -> bool:
    """退訂；原本未訂閱回 False。"""
    subs = load()
    codes = subs.get(user_id, [])
    if code not in codes:
        return False
    codes.remove(code)
    if not codes:
        del subs[user_id]
    _save(subs)
    return True


def codes_for(user_id: str) -> list:
    return load().get(user_id, [])
