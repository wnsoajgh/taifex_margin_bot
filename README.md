# 股票期貨保證金查詢 LINE Bot

LINE 傳「P/華新」「P/1605」「P/CSF」→ 回覆保證金級距、依結算價的正式保證金、依即時價的盤中估算。ETF 期貨直接顯示期交所公告的固定保證金金額；處置中契約會加註警示。**只有 `P/` 開頭的訊息會觸發回覆**（不分大小寫、容許全形），其他訊息一律不回應。

注意：金額為期交所公告之最低標準；券商（尤其對處置股）可能自行加收，實際以券商為準。

## 架構

- `crawler/`：GitHub Actions 每交易日 18:00 (台北) 爬期交所「股票期貨保證金一覽表」(HTML) 與 OpenAPI 全市場結算價，健檢通過才 commit 到 `data/`。
- `bot/`：FastAPI webhook 部署於 Render，讀 `data/` 的 raw JSON（10 分鐘快取），股票期貨另抓即時價（Yahoo，TWSE MIS 備援）。

## 本機開發

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/pytest
.venv/Scripts/python -m crawler.run   # 手動跑一次爬蟲
```

## 部署步驟

### 1. GitHub

1. 建立 GitHub repo（建議公開，bot 才能直接讀 raw JSON；私有需另行處理認證，不建議）。
2. `git remote add origin <repo-url> && git push -u origin master`
3. repo → Actions → 確認 `daily-crawl` 存在，手動 **Run workflow** 一次，確認綠燈且 `data/` 有更新 commit。

### 2. LINE Developers

1. https://developers.line.biz/ → 建立 Provider → 建立 **Messaging API** channel。
2. Basic settings 頁取得 **Channel secret**。
3. Messaging API 頁簽發 **Channel access token (long-lived)**。
4. LINE Official Account Manager → 回應設定：關閉「自動回應訊息」，Webhook 維持啟用。

### 3. Render

1. https://render.com → New → Web Service → 連結 GitHub repo（自動讀 `render.yaml`）。
2. 設定環境變數：
   - `LINE_CHANNEL_SECRET`／`LINE_CHANNEL_ACCESS_TOKEN`：上一步取得的值
   - `DATA_BASE_URL`：`https://raw.githubusercontent.com/<你的帳號>/taifex-margin-bot/master/data`
3. 部署完成後取得網址 `https://xxx.onrender.com`，瀏覽器開 `/health` 應回 `{"ok":true}`。

### 4. 接上 webhook

1. LINE Developers → Messaging API → Webhook URL 填 `https://xxx.onrender.com/callback` → Verify 應為 Success。
2. 用 QR code 加 bot 好友，傳「P/華新」測試。

### 5.（選配）冷啟動緩解

Render 免費方案閒置 15 分鐘休眠，第一則訊息要等約 30–60 秒。可到 https://cron-job.org 建免費排程，於台股交易時段（台北 08:30–14:00）每 10 分鐘 GET `https://xxx.onrender.com/health`。

## 資料正確性說明

- 正式保證金以**前一交易日近月結算價**計算，與券商實際收取一致（券商於盤後依結算價調整）。
- 盤中估算以標的股票即時價計算，僅供參考。
- ETF 期貨保證金為期交所公告固定金額，與價格無關。
- 期交所調整保證金比例時（公告生效日），以每日爬回的最新比例為準。
