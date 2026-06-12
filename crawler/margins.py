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
    return round(float(cleaned) / 100, 6) if cleaned else 0.0


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
