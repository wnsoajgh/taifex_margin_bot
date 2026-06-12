import os
import time

import httpx

# 部署時設成 https://raw.githubusercontent.com/<github帳號>/taifex-margin-bot/<branch>/data
DATA_BASE_URL = os.environ.get("DATA_BASE_URL", "").rstrip("/")
TTL_SECONDS = 600
_cache: dict[str, tuple[float, dict]] = {}


def get_json(name: str) -> dict:
    now = time.monotonic()
    cached = _cache.get(name)
    if cached and now - cached[0] < TTL_SECONDS:
        return cached[1]
    try:
        resp = httpx.get(f"{DATA_BASE_URL}/{name}",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        if cached:          # 抓失敗時沿用過期快取（刻意設計：GitHub 短暫故障不影響服務）
            return cached[1]
        raise
    _cache[name] = (now, data)
    return data


def get_margins() -> dict:
    return get_json("margins.json")


def get_settlements() -> dict:
    return get_json("settlements.json")
