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
    """Parse a percentage string like '16.20%' → 0.162."""
    cleaned = text.replace("%", "").strip()
    return round(float(cleaned) / 100, 6) if cleaned else 0.0


def _ntd(text: str) -> float:
    """Parse a comma-formatted NTD amount like '52,000' → 52000.0."""
    cleaned = text.replace(",", "").strip()
    return float(cleaned) if cleaned else 0.0


def parse_margins(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    contracts = []
    for suffix, category in TABLES.items():
        rate_sfx = "" if suffix == "a" else f"_{suffix}"
        # _a table: rates are percentages ("16.20%"); _b table: rates are NTD amounts ("52,000")
        parse_rate = _pct if suffix == "a" else _ntd
        for id_td in soup.find_all("td", attrs={"headers": f"bond_id_{suffix}"}):
            tr = id_td.find_parent("tr")

            def cell(header: str) -> str:
                td = tr.find("td", attrs={"headers": header})
                return td.get_text(strip=True) if td else ""

            contracts.append({
                "code": cell(f"bond_id_{suffix}"),
                "stock_id": cell(f"commodity_stock_id_{suffix}"),
                "name": cell(f"bond_ch_name1_{suffix}"),
                "underlying_name": cell(f"bond_ch_name2_{suffix}"),
                "category": category,
                "level": cell(f"bond_cate_{suffix}"),
                "clearing_rate": parse_rate(cell(f"bond_rate1{rate_sfx}")),
                "maintenance_rate": parse_rate(cell(f"bond_rate2{rate_sfx}")),
                "initial_rate": parse_rate(cell(f"bond_rate3{rate_sfx}")),
            })
    m = re.search(r"更新日期：(\d{4}/\d{2}/\d{2})", html)
    return {"updated_at": m.group(1) if m else "", "contracts": contracts}
