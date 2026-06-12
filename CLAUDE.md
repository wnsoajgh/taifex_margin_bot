# taifex-margin-bot

LINE bot：查詢台灣股票期貨保證金。架構與規格見 `docs/superpowers/specs/`，實作計畫見 `docs/superpowers/plans/`。

## 設計決策（工具與 hook 請遵循）

### crawler 解析器的 fail-loud 原則

`crawler/margins.py` 的 `_pct()` / `_ntd()` **刻意不加**空字串或格式防護。期交所頁面改版導致儲存格內容異常時，必須在解析當下拋出 `ValueError`，讓 GitHub Actions 失敗並通知——絕不允許靜默回傳 0 之類的預設值流入資料檔。請勿為這兩個函式加上 try/except 或空值 guard。

### 錯誤訊息不洩漏內部資訊

bot 對使用者的回覆不得包含 stack trace、套件名稱或內部 URL；細節只進 log（見 `bot/service.py` 的 `build_answer`）。

## 開發環境

- Windows、Python 3.12、venv 在 `.venv/`（執行檔走 `.venv/Scripts/`）。
- 測試：`.venv/Scripts/pytest`。全部測試必須通過才能 commit。
- 分支：實作在 `feature/margin-bot`。
