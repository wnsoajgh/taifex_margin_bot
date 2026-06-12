# taifex-margin-bot

LINE bot：查詢台灣股票期貨保證金。架構與規格見 `docs/superpowers/specs/`，實作計畫見 `docs/superpowers/plans/`。

## 設計決策（工具與 hook 請遵循）

### crawler 資料的 fail-loud 原則

期交所頁面改版導致解析出異常資料時，爬蟲必須失敗（讓 GitHub Actions 通知），絕不允許壞資料寫進 `data/`。實作上分兩層：

- `crawler/margins.py` 的 `_pct()` / `_ntd()`：空儲存格回傳 0；非空但格式異常直接拋 `ValueError`。
- `crawler/run.py` 的 `validate_margins()` / `validate_settlements()`：範圍與覆蓋率檢查，0 值（含上面的空儲存格情形）必定超出範圍而拋 `ValueError`。

請勿移除驗證層的範圍檢查，也勿讓任何解析失敗被 try/except 吞掉。

### 錯誤訊息不洩漏內部資訊

bot 對使用者的回覆不得包含 stack trace、套件名稱或內部 URL；細節只進 log（見 `bot/service.py` 的 `build_answer`）。

## 開發環境

- Windows、Python 3.12、venv 在 `.venv/`（執行檔走 `.venv/Scripts/`）。
- 測試：`.venv/Scripts/pytest`。全部測試必須通過才能 commit。
- 分支：實作在 `feature/margin-bot`。
