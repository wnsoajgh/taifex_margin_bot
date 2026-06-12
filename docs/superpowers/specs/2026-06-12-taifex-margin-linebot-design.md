# 股票期貨保證金查詢 LINE Bot — 設計文件

日期：2026-06-12
狀態：待使用者審核

## 目的

使用者在 LINE 傳股票名稱（如「華新」）、股票代號（1605）或期貨代碼（CSF），bot 回覆該檔股票期貨所需的保證金：

- 保證金級距與「原始／維持／結算」三種適用比例
- **正式保證金**：依前一交易日期貨結算價計算
- **盤中估算**：依標的股票即時價計算

計算公式（股票期貨）：`保證金 = 價格 × 乘數 × 適用比例`，四捨五入到元；乘數一般為 2,000 股、「小型」契約為 100 股。
**ETF 期貨例外（2026-06-12 對實際頁面驗證）**：保證金一覽表對 ETF 期貨直接公告**固定金額**（結算/維持/原始，單位元），無級距與比例，bot 直接顯示公告金額，不需價格計算。

## 整體架構（方案 A）

```
GitHub Actions（每日排程）                Render 免費方案
┌────────────────────────┐               ┌─────────────────────┐
│ crawler                │   commit      │ LINE webhook server │
│ 1. 爬保證金一覽表       │ ──────────▶  │ (FastAPI +          │
│ 2. 爬股票期貨結算價     │   data/*.json │  line-bot-sdk v3)   │
└────────────────────────┘               └──────────┬──────────┘
                                  讀取 raw.githubusercontent  │ 查詢時即時抓
                                                              ▼
                                                    Yahoo Finance 即時股價
```

- 程式碼與每日資料同放一個 GitHub repo（公開或私有皆可；私有時 bot 用 token 讀 raw 檔）。
- 每日爬蟲由 GitHub Actions 排程執行，不依賴 Render（免費方案休眠時排程不可靠）。
- 資料以 JSON commit 回 repo，天然保留每日歷史（git log 即異動紀錄）。

## 資料來源

| 資料 | 來源 | 取得時機 |
|------|------|---------|
| 保證金級距與比例 | `taifex.com.tw/cht/5/stockMargining`（server-rendered HTML 表格） | 每日爬 |
| 期貨前一日結算價 | 期交所盤後「股票期貨每日交易行情」下載端點（實作前先驗證確切 URL 與欄位；取**最近月**契約的結算價） | 每日爬 |
| 標的股票即時價 | Yahoo Finance chart API（`1605.TW`），失敗時 fallback 到 TWSE MIS API | 查詢當下 |

## 元件

### 1. crawler（Python 模組 `crawler/`）

- `fetch_margins()`：抓 stockMargining 表 → 解析出每檔的期貨代碼、標的代號、中文簡稱、標的證券名稱、級距、三種比例、頁面更新日期。
- `fetch_settlements()`：抓股票期貨盤後行情 → 每檔最近月契約結算價與交易日。
- 輸出 `data/margins.json`、`data/settlements.json`（含 `updated_at` 欄位）。
- 解析結果做基本健檢（筆數 > 100、比例在 5%–40% 區間），不合理即拋錯讓 Actions 失敗，避免壞資料 commit 進去。

### 2. GitHub Actions workflow（`.github/workflows/crawl.yml`）

- 排程：週一至週五台北時間 18:00（UTC 10:00）跑一次（結算價於收盤後公布，18:00 已穩定）。
- 步驟：checkout → 跑 crawler → 資料有變動才 commit & push。
- 失敗時 GitHub 會寄通知信，即為爬蟲監控。

### 3. bot（Python 模組 `bot/`，部署於 Render）

- FastAPI + line-bot-sdk v3，`POST /callback` 接 webhook，驗證 LINE 簽章，非法請求回 400。
- 另提供 `GET /health` 供喚醒/健檢。
- 查詢流程：
  1. 從 raw.githubusercontent.com 讀兩份 JSON，記憶體快取 10 分鐘。
  2. 比對輸入：依序嘗試「中文簡稱完全相符 → 標的代號相符 → 期貨代碼相符 → 簡稱子字串模糊比對」。
  3. 命中一檔 → 抓即時價 → 組合回覆。
  4. 命中多檔 → 列出候選請使用者再選；零命中 → 回覆找不到並列出最接近的 3 個候選。
- 回覆格式（純文字，之後可升級 Flex Message）：

```
華新期貨 (CSF / 標的 1605 華新)
級距：第2級
原始 16.20%｜維持 12.42%｜結算 12.00%

📌 正式保證金（06/11 結算價 48.5）
原始：48.5 × 2,000 × 16.2% = 15,714 元
維持：12,047 元

📈 盤中估算（即時價 49.2）
原始：≈ 15,941 元
（資料日期：2026/06/11）
```

### 4. 部署（Render）

- `render.yaml` + `requirements.txt`，免費 Web Service。
- 環境變數：`LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN`（私有 repo 時另加 `GITHUB_TOKEN`）。
- 冷啟動緩解（選配）：用 cron-job.org 於台股交易時段每 10 分鐘 ping `/health`。

## 錯誤處理

- **快取資料過期**（資料日期 > 3 個日曆日，例如爬蟲連續失敗）：回覆仍計算，但加註「⚠️ 資料日期較舊」。
- **即時價抓不到**：只回正式保證金，註明「即時估算暫無法取得」。
- **結算價缺漏**（新上市、無近月成交）：以即時股價估算並註明。
- **期交所改版**導致解析失敗：crawler 健檢擋下 → Actions 失敗通知；bot 繼續用最後一份好資料。
- bot 對任何未預期例外回覆固定錯誤訊息，不外洩內部細節（stack trace 只進 log）。

## 測試

- 單元測試（pytest）：
  - HTML/CSV 解析器——以實際抓回的頁面存成 fixture 測。
  - 名稱比對邏輯——完全相符、代號、模糊、多重命中、零命中。
  - 保證金計算——級距比例 × 結算價的金額正確性、四捨五入。
- 整合驗證（手動）：本機以 LINE 官方的 webhook 測試 + ngrok/實際部署後傳訊驗證。

## 訂閱與主動推播（2026-06-12 追加，使用者核准）

- 指令：`P/+名稱` 訂閱、`P/-名稱` 退訂、`P/訂閱` 列清單；訂閱以 LINE userId 區分（多人各自獨立），僅一對一聊天可用。
- 儲存：GitHub **secret gist**（`subscriptions.json`，`{userId: [codes]}`）。bot 經 GitHub API 讀寫（env：`GIST_TOKEN`、`SUBS_GIST_ID`）。不放 public repo 因含 userId。
- 偵測：每日 Actions 爬完後，比對爬前/爬後的 `data/margins.json`（級距、比例、ETF 金額變動）。
- 推播：LINE push API，**一人一天最多一則**（彙整當日所有訂閱契約變動）。從 Actions 發（secrets：`LINE_CHANNEL_ACCESS_TOKEN`、`GIST_TOKEN`、`SUBS_GIST_ID`）。順序：先 commit 資料再推播，推播失敗紅燈但不影響資料。
- 額度：3 使用者 × 最多 22 交易日 = 66 則/月 < 免費 200 則。

## 不做的事（YAGNI）

- 不做歷史查詢。
- 不另外過濾商品類型：保證金一覽表上有的契約（含 ETF 期貨）全部支援。
- 不做多語言、不做群組指令前綴。

## 成功條件

1. 每個交易日 18:00 後 repo 內 JSON 自動更新為當日結算價。
2. LINE 傳「華新」「1605」「CSF」皆能在數秒內收到含兩種金額的正確回覆。
3. 期交所資料異常時 bot 不會回錯誤金額（寧可註明資料日期或回報無法計算）。
