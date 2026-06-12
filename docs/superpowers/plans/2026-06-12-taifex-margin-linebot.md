# 股票期貨保證金查詢 LINE Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LINE bot：傳「華新」即回覆該股票期貨的保證金級距、依結算價的正式保證金、依即時價的盤中估算；資料由 GitHub Actions 每日爬取 commit 進 repo。

**Architecture:** GitHub Actions 每交易日 18:00 (台北) 跑 `crawler/`，爬期交所保證金一覽表 (HTML) 與 OpenAPI 全市場結算價，健檢後寫入 `data/*.json` commit。Render 免費方案跑 `bot/`（FastAPI + line-bot-sdk v3 webhook），查詢時從 raw.githubusercontent 讀資料（10 分鐘記憶體快取）、即時股價當下抓 Yahoo（TWSE MIS 備援）。

**Tech Stack:** Python 3.12、FastAPI、line-bot-sdk 3.x、httpx、BeautifulSoup4 + lxml、pytest、GitHub Actions、Render。

**已驗證的資料來源（2026-06-12 實測）:**

| 資料 | 來源 | 重點 |
|---|---|---|
| 保證金比例 | `GET https://www.taifex.com.tw/cht/5/stockMargining` | server-rendered HTML；四張子表後綴 `_a`(股票期貨 292 檔)/`_b`(ETF 期貨)/`_c`/`_d`(選擇權，不解析)。td 的 `headers` 屬性是穩定錨點：`bond_id_a`、`commodity_stock_id_a`、`bond_ch_name1_a`、`bond_ch_name2_a`、`bond_cate_a`、`bond_rate1/2/3`（注意：`_a` 表的 rate 欄 **無** `_a` 後綴；`_b` 表為 `bond_rate1_b` 等，且 `_b` 表的值為固定金額字串如 "52,000"、無 `bond_cate_b` 級距欄）。儲存格文字含尾隨空白需 strip。頁面含「更新日期：YYYY/MM/DD」 |
| 結算價 | `GET https://openapi.taifex.com.tw/v1/DailyMarketReportFut` | 全市場期貨 JSON (~840KB)。欄位：`Date`("20260611")、`Contract`("CSF")、`ContractMonth(Week)`("202606"，價差單含 "/")、`SettlementPrice`(可能為 "NULL"、"-")、`TradingSession`("一般"/"盤後")。取 `一般` 時段、非價差、最近月 |
| 即時股價 | `GET https://query1.finance.yahoo.com/v8/finance/chart/{id}.TW?range=1d&interval=1d`（上櫃為 `.TWO`）；備援 `GET https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{id}.tw`（上櫃 `otc_{id}.tw`） | 皆需 `User-Agent: Mozilla/5.0`。Yahoo 取 `chart.result[0].meta.regularMarketPrice`；MIS 取 `msgArray[0].z`（"-" 表示無成交） |

**保證金計算規則（金額正確性關鍵；2026-06-12 對實際頁面 fixture 驗證後修正）:**

- **股票期貨（`_a` 表）**：表列為「級距 + 三種適用比例」。`保證金 = 價格 × 乘數 × 適用比例`，乘數：一般 2,000 股、名稱以「小型」開頭 100 股。四捨五入到整數元（round half up，**勿用 Python 內建 `round()`**，它是銀行家捨入）。
- **ETF 期貨（`_b` 表）**：表列即為**固定金額**（結算/維持/原始保證金，單位元，例：NYF 元大台灣50ETF期貨 = 52,000/54,000/71,000），**無級距欄（無 `bond_cate_b`）、無比例、不需價格計算**——直接顯示公告金額，也不需即時價與結算價。

**最終檔案結構:**

```
taifex-margin-bot/
├── crawler/__init__.py
├── crawler/margins.py        # 抓+解析保證金一覽表
├── crawler/settlements.py    # 抓+解析 OpenAPI 結算價
├── crawler/run.py            # 進入點：健檢 + 寫 data/*.json
├── bot/__init__.py
├── bot/data_source.py        # 讀 GitHub raw JSON + TTL 快取
├── bot/matcher.py            # 名稱/代號比對
├── bot/quotes.py             # 即時股價 (Yahoo + MIS 備援)
├── bot/reply.py              # 乘數、保證金計算、訊息排版
├── bot/service.py            # 查詢主流程 build_answer()
├── bot/app.py                # FastAPI + LINE webhook
├── data/                     # Actions 每日 commit
├── tests/fixtures/margin.html
├── tests/test_margins.py  test_settlements.py  test_matcher.py
├── tests/test_reply.py  test_service.py  test_data_source.py  test_app.py
├── .github/workflows/crawl.yml
├── requirements.txt  render.yaml  README.md  .gitignore
```

---

### Task 1: 專案腳手架

**Files:**
- Create: `requirements.txt`, `.gitignore`, `crawler/__init__.py`, `bot/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: 建立 requirements.txt**

```
fastapi==0.115.*
uvicorn[standard]==0.34.*
line-bot-sdk==3.*
httpx==0.28.*
beautifulsoup4==4.*
lxml==5.*
pytest==8.*
```

- [ ] **Step 2: 建立 .gitignore**

```
__pycache__/
*.pyc
.venv/
.pytest_cache/
```

- [ ] **Step 3: 建立空的 `crawler/__init__.py`、`bot/__init__.py`、`tests/__init__.py`（三個空檔案）**

- [ ] **Step 4: 建立虛擬環境並安裝**

Run: `python -m venv .venv && .venv/Scripts/pip install -r requirements.txt`
Expected: 安裝成功無錯誤。之後所有 `pytest`/`python` 指令都用 `.venv/Scripts/` 下的執行檔。

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .gitignore crawler/__init__.py bot/__init__.py tests/__init__.py
git commit -m "chore: project scaffolding"
```

---

### Task 2: 保證金一覽表解析器

**Files:**
- Create: `crawler/margins.py`
- Create: `tests/fixtures/margin.html`（真實頁面存檔）
- Test: `tests/test_margins.py`

- [ ] **Step 1: 下載真實頁面當 fixture**

Run: `curl -s "https://www.taifex.com.tw/cht/5/stockMargining" -H "User-Agent: Mozilla/5.0" -o tests/fixtures/margin.html`
Expected: 檔案約 500KB。用 `grep -c bond_id_a tests/fixtures/margin.html` 確認 > 200。

- [ ] **Step 2: 寫失敗測試 `tests/test_margins.py`**

```python
from pathlib import Path
from crawler.margins import parse_margins

FIXTURE = Path(__file__).parent / "fixtures" / "margin.html"


def _load():
    return parse_margins(FIXTURE.read_text(encoding="utf-8"))


def test_parses_csf_row():
    data = _load()
    csf = next(c for c in data["contracts"] if c["code"] == "CSF")
    assert csf["stock_id"] == "1605"
    assert csf["name"] == "華新期貨"
    assert "華新麗華" in csf["underlying_name"]
    assert csf["category"] == "stock"
    assert csf["level"].startswith("級距")
    assert 0.05 <= csf["clearing_rate"] <= csf["maintenance_rate"] <= csf["initial_rate"] <= 0.40


def test_contract_count_and_categories():
    data = _load()
    cats = {c["category"] for c in data["contracts"]}
    assert len(data["contracts"]) > 100
    assert cats == {"stock", "etf"}


def test_parses_etf_row_as_fixed_amounts():
    data = _load()
    nyf = next(c for c in data["contracts"] if c["code"] == "NYF")
    assert nyf["category"] == "etf"
    assert nyf["initial_amount"] >= nyf["maintenance_amount"] >= nyf["clearing_amount"] >= 1000
    assert "initial_rate" not in nyf and "level" not in nyf


def test_updated_at_format():
    data = _load()
    assert len(data["updated_at"]) == 10 and data["updated_at"][4] == "/"


def test_values_are_stripped():
    data = _load()
    for c in data["contracts"]:
        for k in ("code", "stock_id", "name"):
            assert c[k] == c[k].strip() and c[k]
```

- [ ] **Step 3: 跑測試確認失敗**

Run: `.venv/Scripts/pytest tests/test_margins.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'crawler.margins'`

- [ ] **Step 4: 實作 `crawler/margins.py`**

```python
import re

import httpx
from bs4 import BeautifulSoup

MARGIN_URL = "https://www.taifex.com.tw/cht/5/stockMargining"
HEADERS = {"User-Agent": "Mozilla/5.0"}
# 子表後綴 -> 商品類別；_c/_d 為選擇權，不解析
TABLES = {"a": "stock", "b": "etf"}


def fetch_margin_html() -> str:
    resp = httpx.get(MARGIN_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def _pct(text: str) -> float:
    cleaned = text.replace("%", "").strip()
    return round(float(cleaned) / 100, 6) if cleaned else 0.0   # 空儲存格→0，由 validate 擋下


def _ntd(text: str) -> int:
    cleaned = text.replace(",", "").strip()
    return int(cleaned) if cleaned else 0


def parse_margins(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    contracts = []
    for suffix, category in TABLES.items():
        for id_td in soup.find_all("td", attrs={"headers": f"bond_id_{suffix}"}):
            tr = id_td.find_parent("tr")

            def cell(header: str) -> str:
                td = tr.find("td", attrs={"headers": header})
                return td.get_text(strip=True) if td else ""

            row = {
                "code": cell(f"bond_id_{suffix}"),
                "stock_id": cell(f"commodity_stock_id_{suffix}"),
                "name": cell(f"bond_ch_name1_{suffix}"),
                "underlying_name": cell(f"bond_ch_name2_{suffix}"),
                "category": category,
            }
            if category == "stock":   # _a 表：級距 + 比例（rate 欄無後綴）
                row.update({
                    "level": cell("bond_cate_a"),
                    "clearing_rate": _pct(cell("bond_rate1")),
                    "maintenance_rate": _pct(cell("bond_rate2")),
                    "initial_rate": _pct(cell("bond_rate3")),
                })
            else:                     # _b 表：ETF 期貨為公告固定金額（元）
                row.update({
                    "clearing_amount": _ntd(cell(f"bond_rate1_{suffix}")),
                    "maintenance_amount": _ntd(cell(f"bond_rate2_{suffix}")),
                    "initial_amount": _ntd(cell(f"bond_rate3_{suffix}")),
                })
            contracts.append(row)
    m = re.search(r"更新日期：(\d{4}/\d{2}/\d{2})", html)
    return {"updated_at": m.group(1) if m else "", "contracts": contracts}
```

- [ ] **Step 5: 跑測試確認通過**

Run: `.venv/Scripts/pytest tests/test_margins.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add crawler/margins.py tests/test_margins.py tests/fixtures/margin.html
git commit -m "feat: parse TAIFEX stock-futures margin table"
```

---

### Task 3: 結算價解析器

**Files:**
- Create: `crawler/settlements.py`
- Test: `tests/test_settlements.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_settlements.py`**

```python
from crawler.settlements import parse_settlements

ROWS = [
    # 盤後時段帶「數字」結算價，且排在最前：時段過濾一旦失效，CSF 會變 34.5 而非 34.2
    {"Date": "20260611", "Contract": "CSF", "ContractMonth(Week)": "202606",
     "SettlementPrice": "34.5", "TradingSession": "盤後"},
    # 正常列：近月 + 次月（應取近月 202606）
    {"Date": "20260611", "Contract": "CSF", "ContractMonth(Week)": "202606",
     "SettlementPrice": "34.2", "TradingSession": "一般"},
    {"Date": "20260611", "Contract": "CSF", "ContractMonth(Week)": "202607",
     "SettlementPrice": "34.25", "TradingSession": "一般"},
    # 價差單（月份含 /），且 CDF 沒有其他有效列：價差過濾一旦失效，CDF 會出現在結果
    {"Date": "20260611", "Contract": "CDF", "ContractMonth(Week)": "202606/202607",
     "SettlementPrice": "0.16", "TradingSession": "一般"},
    # 無效結算價：略過（ZZF 不應出現在結果）
    {"Date": "20260611", "Contract": "ZZF", "ContractMonth(Week)": "202606",
     "SettlementPrice": "-", "TradingSession": "一般"},
]


def test_nearest_month_settlement():
    out = parse_settlements(ROWS)
    assert out == {"date": "20260611", "prices": {"CSF": 34.2}}


def test_empty_input():
    assert parse_settlements([]) == {"date": "", "prices": {}}
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/pytest tests/test_settlements.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 實作 `crawler/settlements.py`**

```python
import httpx

OPENAPI_URL = "https://openapi.taifex.com.tw/v1/DailyMarketReportFut"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_daily_report() -> list[dict]:
    resp = httpx.get(OPENAPI_URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.json()


def parse_settlements(rows: list[dict]) -> dict:
    best: dict[str, tuple[str, float]] = {}
    date = ""
    for r in rows:
        month = (r.get("ContractMonth(Week)") or "").strip()
        if r.get("TradingSession") != "一般" or not month or "/" in month:
            continue
        try:
            price = float(r.get("SettlementPrice", ""))
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        code = (r.get("Contract") or "").strip()
        if code and (code not in best or month < best[code][0]):
            best[code] = (month, price)
        date = r.get("Date", date)
    return {"date": date, "prices": {c: p for c, (_, p) in sorted(best.items())}}
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/Scripts/pytest tests/test_settlements.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add crawler/settlements.py tests/test_settlements.py
git commit -m "feat: parse nearest-month settlement prices from TAIFEX OpenAPI"
```

---

### Task 4: 爬蟲進入點（健檢 + 寫檔）

**Files:**
- Create: `crawler/run.py`
- Test: `tests/test_run.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_run.py`**

```python
import pytest

from crawler.run import validate_margins, validate_settlements


def _margins(n=150, rate=0.162):
    return {"updated_at": "2026/06/11", "contracts": [
        {"code": f"C{i:03d}", "stock_id": str(1000 + i), "name": f"測試{i}期貨",
         "underlying_name": "x", "category": "stock", "level": "級距1",
         "clearing_rate": 0.10, "maintenance_rate": 0.1035, "initial_rate": rate}
        for i in range(n)
    ]}


def test_validate_margins_ok():
    validate_margins(_margins())  # 不應拋錯


def test_validate_margins_too_few_rows():
    with pytest.raises(ValueError, match="too few"):
        validate_margins(_margins(n=50))


def test_validate_margins_bad_rate():
    with pytest.raises(ValueError, match="rate"):
        validate_margins(_margins(rate=0.9))


def test_validate_margins_bad_etf_amount():
    data = _margins()
    data["contracts"].append({
        "code": "NYF", "stock_id": "0050", "name": "元大台灣50ETF期貨",
        "underlying_name": "x", "category": "etf",
        "clearing_amount": 52000, "maintenance_amount": 54000, "initial_amount": 100})
    with pytest.raises(ValueError, match="amount"):
        validate_margins(data)


def test_validate_settlements_coverage():
    codes = {c["code"] for c in _margins()["contracts"]}
    prices = {c: 10.0 for c in list(codes)[:130]}
    validate_settlements({"date": "20260611", "prices": prices}, codes)  # 86% 覆蓋 OK
    with pytest.raises(ValueError, match="coverage"):
        validate_settlements({"date": "20260611", "prices": {}}, codes)


def test_validate_settlements_missing_date():
    with pytest.raises(ValueError, match="date"):
        validate_settlements({"date": "", "prices": {"A": 1.0}}, {"A"})
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/pytest tests/test_run.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 實作 `crawler/run.py`**

```python
import json
from pathlib import Path

from crawler.margins import fetch_margin_html, parse_margins
from crawler.settlements import fetch_daily_report, parse_settlements

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def validate_margins(data: dict) -> None:
    rows = data["contracts"]
    if len(rows) <= 100:
        raise ValueError(f"too few margin rows: {len(rows)}")
    if not data["updated_at"]:
        raise ValueError("missing updated_at date")
    for c in rows:
        if not (c["code"] and c["stock_id"] and c["name"]):
            raise ValueError(f"empty field in row: {c}")
        if c["category"] == "stock":
            for k in ("clearing_rate", "maintenance_rate", "initial_rate"):
                # 範圍放寬於 spec 的 5%-40%：處置股票加收後比例較高
                if not 0.03 <= c[k] <= 0.45:
                    raise ValueError(f"{c['code']} {k} rate out of range: {c[k]}")
        else:  # ETF 期貨為公告固定金額
            for k in ("clearing_amount", "maintenance_amount", "initial_amount"):
                if not 1_000 <= c[k] <= 10_000_000:
                    raise ValueError(f"{c['code']} {k} amount out of range: {c[k]}")


def validate_settlements(data: dict, margin_codes: set[str]) -> None:
    if not data["date"]:
        raise ValueError("missing settlement date")
    covered = margin_codes & set(data["prices"])
    if len(covered) < 0.8 * len(margin_codes):
        raise ValueError(f"settlement coverage too low: {len(covered)}/{len(margin_codes)}")


def main() -> None:
    margins = parse_margins(fetch_margin_html())
    validate_margins(margins)
    settlements = parse_settlements(fetch_daily_report())
    validate_settlements(settlements, {c["code"] for c in margins["contracts"]})
    DATA_DIR.mkdir(exist_ok=True)
    for name, payload in (("margins.json", margins), ("settlements.json", settlements)):
        (DATA_DIR / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK margins={len(margins['contracts'])} settlements={len(settlements['prices'])}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/Scripts/pytest tests/test_run.py -v`
Expected: 6 passed

- [ ] **Step 5: 實際跑一次爬蟲（整合驗證）**

Run: `.venv/Scripts/python -m crawler.run`
Expected: 印出 `OK margins=3xx settlements=2xx`，`data/margins.json` 與 `data/settlements.json` 生成。抽查 `data/margins.json` 中 CSF 的比例與網頁一致。

- [ ] **Step 6: Commit（含第一份資料）**

```bash
git add crawler/run.py tests/test_run.py data/
git commit -m "feat: crawler entrypoint with sanity checks and JSON output"
```

---

### Task 5: GitHub Actions 每日排程

**Files:**
- Create: `.github/workflows/crawl.yml`

- [ ] **Step 1: 建立 workflow**

```yaml
name: daily-crawl

on:
  schedule:
    - cron: "0 10 * * 1-5"   # UTC 10:00 = 台北 18:00，週一至週五
  workflow_dispatch: {}

jobs:
  crawl:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python -m crawler.run
      - name: Commit updated data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          git diff --cached --quiet || git commit -m "data: daily update"
          git push
```

- [ ] **Step 2: 本機驗證 YAML 語法**

Run: `.venv/Scripts/python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/crawl.yml',encoding='utf-8')); print('yaml ok')"`
（若無 yaml 套件先 `.venv/Scripts/pip install pyyaml`，僅本機驗證用，不加入 requirements.txt）
Expected: `yaml ok`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/crawl.yml
git commit -m "ci: daily crawl workflow at 18:00 Taipei on weekdays"
```

注意：排程要等 repo push 上 GitHub 後才會生效（Task 11）。屆時用 Actions 頁面的 **Run workflow**（workflow_dispatch）手動觸發一次驗證。

---

### Task 6: 查詢比對器

**Files:**
- Create: `bot/matcher.py`
- Test: `tests/test_matcher.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_matcher.py`**

```python
from bot.matcher import find

C = [
    {"code": "CSF", "stock_id": "1605", "name": "華新期貨", "category": "stock"},
    {"code": "PBF", "stock_id": "2492", "name": "華新科期貨", "category": "stock"},
    {"code": "CDF", "stock_id": "2330", "name": "台積電期貨", "category": "stock"},
    {"code": "QFF", "stock_id": "2330", "name": "小型台積電期貨", "category": "stock"},
    {"code": "NYF", "stock_id": "0050", "name": "元大台灣50ETF期貨", "category": "etf"},
]


def test_exact_short_name():
    hit, cands = find("華新", C)
    assert hit["code"] == "CSF" and cands == []


def test_exact_short_name_beats_substring():
    hit, _ = find("台積電", C)          # 不應撞到「小型台積電期貨」
    assert hit["code"] == "CDF"


def test_stock_id():
    hit, cands = find("1605", C)
    assert hit["code"] == "CSF"


def test_stock_id_multiple_hits_returns_candidates():
    hit, cands = find("2330", C)        # 大小台積電同標的
    assert hit is None and {c["code"] for c in cands} == {"CDF", "QFF"}


def test_futures_code_case_insensitive():
    hit, _ = find("csf", C)
    assert hit["code"] == "CSF"


def test_fullwidth_input():
    hit, _ = find("１６０５", C)
    assert hit["code"] == "CSF"


def test_substring_candidates():
    hit, cands = find("華", C)
    assert hit is None and len(cands) == 2


def test_no_match_close_suggestions():
    hit, cands = find("台積店", C)      # 錯字 → difflib 相近建議
    assert hit is None and any("台積電" in c["name"] for c in cands)


def test_no_match_at_all():
    hit, cands = find("完全不存在的東西", C)
    assert hit is None and cands == []
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/pytest tests/test_matcher.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 實作 `bot/matcher.py`**

```python
import difflib
import unicodedata


def _norm(text: str) -> str:
    # NFKC：全形轉半形；upper：期貨代碼不分大小寫
    return unicodedata.normalize("NFKC", text).strip().upper()


def _base_name(contract: dict) -> str:
    name = contract["name"]
    return name[:-2] if name.endswith("期貨") else name


def find(query: str, contracts: list[dict]) -> tuple[dict | None, list[dict]]:
    """回傳 (唯一命中, 候選清單)。唯一命中時候選為空；多重/零命中時命中為 None。"""
    q = _norm(query)
    if not q:
        return None, []

    for key in ("code", "stock_id"):
        hits = [c for c in contracts if _norm(c[key]) == q]
        if len(hits) == 1:
            return hits[0], []
        if hits:
            return None, hits

    hits = [c for c in contracts if _base_name(c) == q or c["name"] == q]
    if len(hits) == 1:
        return hits[0], []
    if hits:
        return None, hits

    subs = [c for c in contracts if q in _base_name(c)]
    if len(subs) == 1:
        return subs[0], []
    if subs:
        return None, subs[:5]

    by_base = {_base_name(c): c for c in contracts}
    close = difflib.get_close_matches(q, by_base.keys(), n=3, cutoff=0.5)
    return None, [by_base[n] for n in close]
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/Scripts/pytest tests/test_matcher.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add bot/matcher.py tests/test_matcher.py
git commit -m "feat: contract matcher (code/stock-id/name/fuzzy)"
```

---

### Task 7: 保證金計算與訊息排版

**Files:**
- Create: `bot/reply.py`
- Test: `tests/test_reply.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_reply.py`**

```python
from bot.reply import calc_margin, format_reply, multiplier

CSF = {"code": "CSF", "stock_id": "1605", "name": "華新期貨",
       "underlying_name": "華新麗華股份有限公司", "category": "stock",
       "level": "級距2", "clearing_rate": 0.12,
       "maintenance_rate": 0.1242, "initial_rate": 0.162}


def test_multiplier_rules():
    assert multiplier({"name": "華新期貨"}) == 2000
    assert multiplier({"name": "小型台積電期貨"}) == 100


def test_format_reply_etf_fixed_amounts():
    nyf = {"code": "NYF", "stock_id": "0050", "name": "元大台灣50ETF期貨",
           "underlying_name": "元大台灣卓越50證券投資信託基金", "category": "etf",
           "clearing_amount": 52000, "maintenance_amount": 54000, "initial_amount": 71000}
    msg = format_reply(nyf, settlement_price=None, settlement_date="",
                       live_price=None, data_date="2026/06/11", stale=False)
    assert "71,000" in msg and "54,000" in msg and "52,000" in msg
    assert "固定金額" in msg and "結算價" not in msg


def test_calc_margin_rounds_half_up():
    assert calc_margin(34.2, 0.162, 2000) == 11081      # 11080.8
    assert calc_margin(34.2, 0.1242, 2000) == 8495      # 8495.28
    assert calc_margin(0.25, 0.10, 2000) == 50          # 50.0 整數邊界


def test_format_reply_full():
    msg = format_reply(CSF, settlement_price=34.2, settlement_date="20260611",
                       live_price=37.65, data_date="2026/06/11", stale=False)
    assert "華新期貨 (CSF)" in msg
    assert "1605" in msg and "華新麗華" in msg
    assert "級距2" in msg and "16.20%" in msg
    assert "11,081" in msg                      # 正式原始保證金
    assert "8,495" in msg                       # 正式維持保證金
    assert "12,199" in msg                      # 盤中估算 37.65*2000*0.162=12198.6
    assert "2026/06/11" in msg


def test_format_reply_no_live_price():
    msg = format_reply(CSF, settlement_price=34.2, settlement_date="20260611",
                       live_price=None, data_date="2026/06/11", stale=False)
    assert "即時" in msg and "無法取得" in msg


def test_format_reply_no_settlement():
    msg = format_reply(CSF, settlement_price=None, settlement_date="",
                       live_price=37.65, data_date="2026/06/11", stale=False)
    assert "12,199" in msg and "結算價" in msg and "缺" in msg


def test_format_reply_stale_warning():
    msg = format_reply(CSF, settlement_price=34.2, settlement_date="20260611",
                       live_price=None, data_date="2026/06/01", stale=True)
    assert "⚠️" in msg
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/pytest tests/test_reply.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 實作 `bot/reply.py`**

```python
def multiplier(contract: dict) -> int:
    # 僅股票期貨以價格計算保證金；「小型」契約乘數為 100 股
    return 100 if contract["name"].startswith("小型") else 2_000


def calc_margin(price: float, rate: float, mult: int) -> int:
    return int(price * rate * mult + 0.5)  # round half up；內建 round() 是銀行家捨入


def _fmt_date(yyyymmdd: str) -> str:
    return f"{yyyymmdd[4:6]}/{yyyymmdd[6:8]}" if len(yyyymmdd) == 8 else yyyymmdd


def _footer(data_date: str, stale: bool) -> list[str]:
    lines = ["", f"資料日期：{data_date}"]
    if stale:
        lines.append("⚠️ 資料日期較舊，金額僅供參考")
    return lines


def format_reply(contract: dict, settlement_price: float | None, settlement_date: str,
                 live_price: float | None, data_date: str, stale: bool) -> str:
    header = [
        f"{contract['name']} ({contract['code']})",
        f"標的：{contract['stock_id']} {contract['underlying_name']}",
    ]
    if contract["category"] == "etf":
        return "\n".join(header + [
            "ETF 期貨保證金為公告固定金額：",
            f"原始：{contract['initial_amount']:,} 元",
            f"維持：{contract['maintenance_amount']:,} 元",
            f"結算：{contract['clearing_amount']:,} 元",
        ] + _footer(data_date, stale))

    mult = multiplier(contract)
    init, maint = contract["initial_rate"], contract["maintenance_rate"]
    lines = header + [
        f"{contract['level']}｜原始 {init:.2%}｜維持 {maint:.2%}｜結算 {contract['clearing_rate']:.2%}",
        "",
    ]
    if settlement_price is not None:
        lines += [
            f"📌 正式保證金（{_fmt_date(settlement_date)} 結算價 {settlement_price:g}）",
            f"原始：{settlement_price:g} × {mult:,} × {init:.2%} = {calc_margin(settlement_price, init, mult):,} 元",
            f"維持：{calc_margin(settlement_price, maint, mult):,} 元",
        ]
    else:
        lines.append("📌 正式保證金：結算價資料缺漏，暫無法計算")
    lines.append("")
    if live_price is not None:
        lines += [
            f"📈 盤中估算（即時 {live_price:g}）",
            f"原始：≈ {calc_margin(live_price, init, mult):,} 元",
        ]
    else:
        lines.append("📈 即時價暫時無法取得")
    return "\n".join(lines + _footer(data_date, stale))
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/Scripts/pytest tests/test_reply.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add bot/reply.py tests/test_reply.py
git commit -m "feat: margin calculation and reply formatting"
```

---

### Task 8: 即時股價模組

**Files:**
- Create: `bot/quotes.py`
- Test: `tests/test_quotes.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_quotes.py`**（純函式測解析，網路層薄殼不測）

```python
from bot.quotes import parse_mis_price, parse_yahoo_price


def test_parse_yahoo_price():
    payload = {"chart": {"result": [{"meta": {"regularMarketPrice": 37.65}}]}}
    assert parse_yahoo_price(payload) == 37.65


def test_parse_yahoo_price_missing():
    assert parse_yahoo_price({"chart": {"result": None}}) is None
    assert parse_yahoo_price({}) is None


def test_parse_mis_price():
    assert parse_mis_price({"msgArray": [{"z": "37.6500"}]}) == 37.65


def test_parse_mis_price_no_trade():
    assert parse_mis_price({"msgArray": [{"z": "-"}]}) is None
    assert parse_mis_price({"msgArray": []}) is None
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/pytest tests/test_quotes.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 實作 `bot/quotes.py`**

```python
import httpx

HEADERS = {"User-Agent": "Mozilla/5.0"}
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1d"
MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={market}_{stock_id}.tw&json=1&delay=0"


def parse_yahoo_price(payload: dict) -> float | None:
    try:
        return float(payload["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def parse_mis_price(payload: dict) -> float | None:
    try:
        return float(payload["msgArray"][0]["z"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def get_live_price(stock_id: str) -> float | None:
    """上市為主、上櫃備援；Yahoo 失敗再退 TWSE MIS。全失敗回 None。"""
    for symbol in (f"{stock_id}.TW", f"{stock_id}.TWO"):
        try:
            resp = httpx.get(YAHOO_URL.format(symbol=symbol), headers=HEADERS, timeout=5)
            price = parse_yahoo_price(resp.json())
            if price:
                return price
        except httpx.HTTPError:
            pass
    for market in ("tse", "otc"):
        try:
            resp = httpx.get(MIS_URL.format(market=market, stock_id=stock_id),
                             headers=HEADERS, timeout=5)
            price = parse_mis_price(resp.json())
            if price:
                return price
        except (httpx.HTTPError, ValueError):
            pass
    return None
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/Scripts/pytest tests/test_quotes.py -v`
Expected: 4 passed

- [ ] **Step 5: 手動驗證真實網路**

Run: `.venv/Scripts/python -c "from bot.quotes import get_live_price; print(get_live_price('1605'), get_live_price('6488'))"`
Expected: 兩個都印出合理價格（6488 環球晶為上櫃，驗證 .TWO/otc 路徑）。非交易時間印出前收盤價也算通過。

- [ ] **Step 6: Commit**

```bash
git add bot/quotes.py tests/test_quotes.py
git commit -m "feat: live quote fetcher with Yahoo primary and TWSE MIS fallback"
```

---

### Task 9: 資料來源（GitHub raw + TTL 快取）

**Files:**
- Create: `bot/data_source.py`
- Test: `tests/test_data_source.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_data_source.py`**

```python
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
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/pytest tests/test_data_source.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 實作 `bot/data_source.py`**

```python
import os
import time

import httpx

# 部署時設成 https://raw.githubusercontent.com/<github帳號>/taifex-margin-bot/main/data
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
        if cached:          # 抓失敗時沿用過期快取
            return cached[1]
        raise
    _cache[name] = (now, data)
    return data


def get_margins() -> dict:
    return get_json("margins.json")


def get_settlements() -> dict:
    return get_json("settlements.json")
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/Scripts/pytest tests/test_data_source.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add bot/data_source.py tests/test_data_source.py
git commit -m "feat: data source with TTL cache and stale-cache fallback"
```

---

### Task 10: 查詢主流程 service

**Files:**
- Create: `bot/service.py`
- Test: `tests/test_service.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_service.py`**

```python
import bot.service as svc

MARGINS = {"updated_at": "2026/06/11", "contracts": [
    {"code": "CSF", "stock_id": "1605", "name": "華新期貨",
     "underlying_name": "華新麗華股份有限公司", "category": "stock",
     "level": "級距2", "clearing_rate": 0.12,
     "maintenance_rate": 0.1242, "initial_rate": 0.162},
    {"code": "PBF", "stock_id": "2492", "name": "華新科期貨",
     "underlying_name": "華新科技股份有限公司", "category": "stock",
     "level": "級距2", "clearing_rate": 0.12,
     "maintenance_rate": 0.1242, "initial_rate": 0.162},
]}
SETTLEMENTS = {"date": "20260611", "prices": {"CSF": 34.2}}


def _patch(monkeypatch, today="2026/06/12"):
    monkeypatch.setattr(svc.data_source, "get_margins", lambda: MARGINS)
    monkeypatch.setattr(svc.data_source, "get_settlements", lambda: SETTLEMENTS)
    monkeypatch.setattr(svc.quotes, "get_live_price", lambda sid: 37.65)
    monkeypatch.setattr(svc, "_today_str", lambda: today)


def test_hit(monkeypatch):
    _patch(monkeypatch)
    msg = svc.build_answer("華新")
    assert "華新期貨 (CSF)" in msg and "11,081" in msg and "⚠️" not in msg


def test_candidates(monkeypatch):
    _patch(monkeypatch)
    msg = svc.build_answer("華")
    assert "華新期貨" in msg and "華新科期貨" in msg and "找到多筆" in msg


def test_not_found(monkeypatch):
    _patch(monkeypatch)
    msg = svc.build_answer("完全不存在的東西")
    assert "找不到" in msg


def test_stale_data_warning(monkeypatch):
    _patch(monkeypatch, today="2026/06/20")
    assert "⚠️" in svc.build_answer("華新")


def test_internal_error_is_masked(monkeypatch):
    monkeypatch.setattr(svc.data_source, "get_margins",
                        lambda: (_ for _ in ()).throw(RuntimeError("secret detail")))
    msg = svc.build_answer("華新")
    assert "secret" not in msg and "稍後再試" in msg
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/pytest tests/test_service.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 實作 `bot/service.py`**

```python
import logging
from datetime import date, datetime

from bot import data_source, quotes
from bot.matcher import find
from bot.reply import format_reply

log = logging.getLogger(__name__)
STALE_DAYS = 3
HELP_TEXT = "請輸入股票名稱、代號或期貨代碼，例如：華新、1605、CSF"


def _today_str() -> str:
    return date.today().strftime("%Y/%m/%d")


def _is_stale(data_date: str) -> bool:
    try:
        d = datetime.strptime(data_date, "%Y/%m/%d").date()
    except ValueError:
        return True
    today = datetime.strptime(_today_str(), "%Y/%m/%d").date()
    return (today - d).days > STALE_DAYS


def build_answer(query: str) -> str:
    try:
        return _answer(query)
    except Exception:
        log.exception("query failed: %r", query)   # 細節只進 log，不回給使用者
        return "系統暫時無法服務，請稍後再試"


def _answer(query: str) -> str:
    margins = data_source.get_margins()
    hit, candidates = find(query, margins["contracts"])
    if hit is None and candidates:
        names = "\n".join(f"・{c['name']} ({c['code']})" for c in candidates)
        return f"找到多筆相符，請再輸入完整一點：\n{names}"
    if hit is None:
        return f"找不到「{query}」相關的股票期貨。\n{HELP_TEXT}"

    settlements = data_source.get_settlements()
    is_etf = hit["category"] == "etf"   # ETF 期貨為公告固定金額，不需任何報價
    return format_reply(
        hit,
        settlement_price=None if is_etf else settlements["prices"].get(hit["code"]),
        settlement_date=settlements.get("date", ""),
        live_price=None if is_etf else quotes.get_live_price(hit["stock_id"]),
        data_date=margins["updated_at"],
        stale=_is_stale(margins["updated_at"]),
    )
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/Scripts/pytest tests/test_service.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add bot/service.py tests/test_service.py
git commit -m "feat: query service orchestrating data, matching and reply"
```

---

### Task 11: FastAPI + LINE webhook

**Files:**
- Create: `bot/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_app.py`**

```python
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
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/Scripts/pytest tests/test_app.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.app'`

- [ ] **Step 3: 實作 `bot/app.py`**

```python
import logging
import os

from fastapi import FastAPI, HTTPException, Request
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (ApiClient, Configuration, MessagingApi,
                                  ReplyMessageRequest, TextMessage)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from bot import service

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI()
handler = WebhookHandler(os.environ.get("LINE_CHANNEL_SECRET", ""))
_configuration = Configuration(
    access_token=os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", ""))


def _reply(reply_token: str, text: str) -> None:
    with ApiClient(_configuration) as client:
        MessagingApi(client).reply_message(ReplyMessageRequest(
            reply_token=reply_token, messages=[TextMessage(text=text)]))


@handler.add(MessageEvent, message=TextMessageContent)
def on_text_message(event: MessageEvent) -> None:
    _reply(event.reply_token, service.build_answer(event.message.text))


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/callback")
async def callback(request: Request) -> str:
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="invalid signature")
    return "OK"
```

注意：測試 monkeypatch `mod._reply`，但 `on_text_message` 是在 import 時就註冊到 handler 的 closure——它呼叫的是模組層級名稱 `_reply`，monkeypatch 替換模組屬性後 closure 會拿到新函式（Python 名稱晚綁定），所以測試可行。

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/Scripts/pytest tests/test_app.py -v`
Expected: 3 passed

- [ ] **Step 5: 全套測試**

Run: `.venv/Scripts/pytest -v`
Expected: 全部通過（43 個測試）

- [ ] **Step 6: Commit**

```bash
git add bot/app.py tests/test_app.py
git commit -m "feat: FastAPI LINE webhook with signature verification"
```

---

### Task 12: 部署設定 + README

**Files:**
- Create: `render.yaml`, `README.md`

- [ ] **Step 1: 建立 render.yaml**

```yaml
services:
  - type: web
    name: taifex-margin-bot
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn bot.app:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: LINE_CHANNEL_SECRET
        sync: false
      - key: LINE_CHANNEL_ACCESS_TOKEN
        sync: false
      - key: DATA_BASE_URL
        sync: false
```

- [ ] **Step 2: 建立 README.md**

````markdown
# 股票期貨保證金查詢 LINE Bot

LINE 傳「華新」「1605」「CSF」→ 回覆保證金級距、依結算價的正式保證金、依即時價的盤中估算。

## 架構

- `crawler/`：GitHub Actions 每交易日 18:00 (台北) 爬期交所「股票期貨保證金一覽表」與 OpenAPI 結算價，健檢後 commit 到 `data/`。
- `bot/`：FastAPI webhook 部署於 Render，讀 `data/` 的 raw JSON（10 分鐘快取），即時價查詢當下抓 Yahoo / TWSE MIS。

## 本機開發

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/pytest
.venv/Scripts/python -m crawler.run   # 手動跑一次爬蟲
```

## 部署步驟

### 1. GitHub

1. 建立 GitHub repo（公開最簡單；私有則 bot 讀 raw 需另加 token，DATA_BASE_URL 改用 `https://<token>@raw.githubusercontent.com/...` 不建議，建議公開）。
2. `git remote add origin <repo-url> && git push -u origin master`
3. repo → Actions → 確認 `daily-crawl` 存在，手動 **Run workflow** 一次，確認綠燈且 `data/` 有更新 commit。

### 2. LINE Developers

1. https://developers.line.biz/ → 建立 Provider → 建立 **Messaging API** channel。
2. Basic settings 頁取得 **Channel secret**。
3. Messaging API 頁簽發 **Channel access token (long-lived)**。
4. Messaging API 頁關閉「自動回應訊息」（Auto-reply messages → Disabled），保留 Webhook → Enabled。

### 3. Render

1. https://render.com → New → Web Service → 連結 GitHub repo（會自動讀 `render.yaml`）。
2. 設定環境變數：
   - `LINE_CHANNEL_SECRET`／`LINE_CHANNEL_ACCESS_TOKEN`：上一步取得的值
   - `DATA_BASE_URL`：`https://raw.githubusercontent.com/<你的帳號>/taifex-margin-bot/master/data`
3. 部署完成後取得網址 `https://xxx.onrender.com`，瀏覽器開 `/health` 應回 `{"ok":true}`。

### 4. 接上 webhook

1. LINE Developers → Messaging API → Webhook URL 填 `https://xxx.onrender.com/callback` → Verify 應為 Success。
2. 用 QR code 加 bot 好友，傳「華新」測試。

### 5.（選配）冷啟動緩解

Render 免費方案閒置 15 分鐘休眠，第一則訊息要等約 30–60 秒。可到 https://cron-job.org 建免費排程，於台股交易時段（台北 08:30–14:00，UTC 00:30–06:00）每 10 分鐘 GET `https://xxx.onrender.com/health`。

## 資料正確性說明

- 正式保證金以**前一交易日近月結算價**計算，與券商實際收取一致（券商於盤後依結算價調整）。
- 盤中估算以標的股票即時價計算，僅供參考。
- 期交所調整保證金比例時（公告生效日），以每日爬回的最新比例為準。
````

- [ ] **Step 3: Commit**

```bash
git add render.yaml README.md
git commit -m "chore: Render config and deployment README"
```

---

### Task 13: 上線與端對端驗證（手動，依 README 執行）

- [ ] **Step 1: 推上 GitHub**：建 repo、`git push -u origin master`。
- [ ] **Step 2: 手動觸發 Actions**：`daily-crawl` Run workflow → 綠燈、`data/` 有新 commit。
- [ ] **Step 3: 部署 Render**：依 README §3 設好三個環境變數 → `/health` 回 `{"ok":true}`。
- [ ] **Step 4: 接 webhook**：LINE console Verify Success。
- [ ] **Step 5: 實測五個案例**：
  - 「華新」→ 回 CSF 完整保證金（與 `data/margins.json` 內比例、結算價手算一致）
  - 「1605」「csf」→ 同上
  - 「台積電」→ 回 CDF（非小型）
  - 「華」→ 回候選清單
  - 「亂打xyz」→ 回找不到 + 使用說明
- [ ] **Step 6: 確認隔日 18:00 後 `data/` 自動更新**（看 repo commit 紀錄）。

---

## 驗收對照（對 spec 的成功條件）

1. 每交易日 18:00 後 JSON 自動更新 → Task 5 + 13-6
2. 「華新」「1605」「CSF」秒回兩種金額 → Task 6–11 + 13-5
3. 資料異常不回錯誤金額 → Task 4 健檢、Task 9 快取備援、Task 10 過期警示與錯誤遮罩
