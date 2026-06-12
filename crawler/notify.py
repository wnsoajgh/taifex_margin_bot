"""比對保證金資料變動並推播給訂閱者（在 GitHub Actions 中於資料 commit 後執行）。

用法：python -m crawler.notify <舊 margins.json> <新 margins.json>
需要環境變數：LINE_CHANNEL_ACCESS_TOKEN、GIST_TOKEN、SUBS_GIST_ID。
推播失敗會拋錯讓 Actions 變紅（通知用途，資料已先 commit 不受影響）。
"""
import json
import os
import sys

import httpx

from bot import subscriptions

PUSH_URL = "https://api.line.me/v2/bot/message/push"
STOCK_FIELDS = (("initial_rate", "原始"), ("maintenance_rate", "維持"), ("clearing_rate", "結算"))
ETF_FIELDS = (("initial_amount", "原始"), ("maintenance_amount", "維持"), ("clearing_amount", "結算"))
MAX_MESSAGE_CHARS = 4_800   # LINE 文字訊息上限 5,000，預留尾行餘裕（季調可能一次動數百檔）


def diff_contracts(old: dict, new: dict) -> dict:
    """回傳 {code: [變動描述行...]}，只含有變動的契約。"""
    old_by = {c["code"]: c for c in old["contracts"]}
    new_codes = {c["code"] for c in new["contracts"]}
    changes = {}
    for code, o in old_by.items():
        if code not in new_codes:
            changes[code] = ["已自保證金一覽表移除（可能下市），請確認是否退訂"]
    for c in new["contracts"]:
        o = old_by.get(c["code"])
        if not o:
            continue
        if o["category"] != c["category"]:
            changes[c["code"]] = ["契約類別變更（股票/ETF 重分類），保證金計算方式改變，請重新查詢"]
            continue
        lines = []
        if c["category"] == "stock":
            if o["level"] != c["level"]:
                lines.append(f"級距：{o['level'] or '處置中'} → {c['level'] or '處置中'}")
            for key, label in STOCK_FIELDS:
                if o[key] != c[key]:
                    lines.append(f"{label}：{o[key]:.2%} → {c[key]:.2%}")
        else:
            for key, label in ETF_FIELDS:
                if o[key] != c[key]:
                    lines.append(f"{label}：{o[key]:,} 元 → {c[key]:,} 元")
        if lines:
            changes[c["code"]] = lines
    return changes


def build_notification(new: dict, changes: dict, subscribed_codes: list) -> str | None:
    """組出單一訂閱者的彙整訊息；其訂閱契約皆無變動時回 None。"""
    hits = [code for code in subscribed_codes if code in changes]
    if not hits:
        return None
    name_by = {c["code"]: c["name"] for c in new["contracts"]}
    header = f"📢 保證金調整通知（{new['updated_at']}）"
    footer = "\n※ 自次一交易日起適用，詳見期交所公告"
    body_parts = []
    for code in hits:
        block = f"\n{name_by.get(code, code)} ({code})\n" + "\n".join(changes[code])
        candidate = "\n".join([header] + body_parts + [block, footer])
        if len(candidate) > MAX_MESSAGE_CHARS:
            body_parts.append(f"\n（另有 {len(hits) - len(body_parts)} 檔變動，請至期交所查詢）")
            break
        body_parts.append(block)
    return "\n".join([header] + body_parts + [footer])


def _push(user_id: str, text: str) -> None:
    resp = httpx.post(PUSH_URL, timeout=10, headers={
        "Authorization": f"Bearer {os.environ['LINE_CHANNEL_ACCESS_TOKEN']}"},
        json={"to": user_id, "messages": [{"type": "text", "text": text}]})
    resp.raise_for_status()


def main(old_path: str, new_path: str) -> None:
    if not os.environ.get("SUBS_GIST_ID"):
        print("subscriptions not configured (SUBS_GIST_ID unset), skipping notify")
        return
    with open(old_path, encoding="utf-8") as f:
        old = json.load(f)
    with open(new_path, encoding="utf-8") as f:
        new = json.load(f)
    changes = diff_contracts(old, new)
    if not changes:
        print("no margin changes")
        return
    sent = failed = 0
    for user_id, codes in subscriptions.load().items():
        text = build_notification(new, changes, codes)
        if not text:
            continue
        try:
            _push(user_id, text)
            sent += 1
        except httpx.HTTPError:
            failed += 1   # 單一訂閱者失敗不可中斷其他人；userId 不進 log
    print(f"{len(changes)} contract(s) changed, notified {sent} subscriber(s), {failed} failed")
    if failed:
        raise SystemExit(f"{failed} push(es) failed")   # 全部送完才讓 run 變紅


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
