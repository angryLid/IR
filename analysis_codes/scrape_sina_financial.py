#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓取新浪财经三大报表（利润表 / 资产负债表 / 现金流量表）。

新浪 URL 结构：
  https://money.finance.sina.com.cn/corp/go.php/vFD_{报表名}/stockid/{代码}/ctrl/{年份}/displaytype/4.phtml

- stockid    : 股票代码，如 600019
- ctrl/{年份}: 该年的报表，返回该年四个报告节点：12-31(全年)、9-30(前三季)、6-30(半年)、3-31(一季)
- displaytype/4: 财务报表类型（4 = 新准则）
- 每页数据都内嵌在 <table id="{报表名}NewTable0"> 中

本脚本用 lxml 直接解析目标表格（绕开 pandas.read_html 在 pandas>=3 对长字符串误判为文件路径的缺陷），
导出的每页 CSV 保留"报表日期 + 四个季度列"的原始结构，供后续清洗层使用。

用法示例：
  python3 scrape_sina_financial.py --stockid 600019 --years 2025 --outdir data
  python3 scrape_sina_financial.py --stockid 600019 --years 2015-2025 --outdir data

输出：data/{stockid}_{stmt}_{year}.csv
"""
import argparse
import os
import re
import time
import requests
from lxml import html as lhtml

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# 报表名 -> 页面路径段（与 URL 中 vFD_ 后面对应）
STATEMENTS = {
    "profit": "ProfitStatement",   # 利润表
    "balance": "BalanceSheet",     # 资产负债表
    "cashflow": "CashFlow",        # 现金流量表
}

# 每个报表对应的表格 id
# 注意：新浪页面的现金流量表也复用 ProfitStatementNewTable0（模板缺陷），因此 cashflow 与 profit 共用同一 id。
# 校验依据：页面标题行（"现金流量表"字样）即为该表真实类型。
TABLE_ID = {
    "profit": "ProfitStatementNewTable0",
    "balance": "BalanceSheetNewTable0",
    "cashflow": "ProfitStatementNewTable0",  # 新浪复用，备案
}


def parse_year_spec(spec):
    """把 '2015-2025' 或 '2025' 解析成年份列表。"""
    if "-" in spec:
        start, end = spec.split("-")
        return list(range(int(start), int(end) + 1))
    return [int(spec)]


def _cell_text(node):
    """提取 <td>/<th> 内文本并清洗。"""
    return "".join(node.itertext()).strip()


def _row_to_list(tr):
    """把一行 <tr> 转成 [科目值, q4, q3, q2, q1] 列表。"""
    return [_cell_text(td) for td in tr.xpath("./td|./th")]


def fetch_page(stockid, stmt, year):
    """
    抓取单张报表页面并解析成行列表。

    返回 (rows, periods)：
      rows    : list[list]，形如 [["一、营业总收入","31,750,779.40",...], ...]（跳过标题/表头/空行）
      periods : list[str]，表头报告日期 ["2025-12-31","2025-09-30","2025-06-30","2025-03-31"]
    """
    url = (
        "https://money.finance.sina.com.cn/corp/go.php/"
        f"vFD_{STATEMENTS[stmt]}/stockid/{stockid}/ctrl/{year}/displaytype/4.phtml"
    )
    resp = requests.get(url, headers=UA, timeout=20)
    resp.raise_for_status()
    html = resp.content.decode("gb18030", errors="replace")

    tree = lhtml.fromstring(html)
    table_id = TABLE_ID[stmt]
    tables = tree.xpath(f'//table[@id="{table_id}"]')
    if not tables:
        raise ValueError(f"未找到表格 id={table_id}（year={year}，可能页面结构变化）")
    table = tables[0]

    periods = []          # 表头报告日期
    rows = []             # 科目行，形如 [科目, 层级, 类型, q4, q3, q2, q1]
    trs = table.xpath(".//tr")
    for tr in trs:
        tds = tr.xpath("./td|./th")
        if not tds:
            continue
        cells = [_cell_text(td) for td in tds]
        first = cells[0]
        if first == "报表日期":
            periods = cells[1:]
            continue
        if ("利润表" in first or "资产负债表" in first or "现金流量表" in first
                or "单位" in first):
            continue  # 标题行（含公司名+报表名、单位）

        # 依据样式判定层级与类型
        style = tds[0].get("style", "")
        pad_m = re.search(r"padding-left:(\d+)px", style)
        pad = int(pad_m.group(1)) if pad_m else 0
        level = 1 if pad >= 30 else 0

        values = cells[1:]
        has_value = any(v not in ("", "--") for v in values)
        if not has_value and pad == 0:
            kind = "section"          # 分组标题：流动资产 / 一、经营活动产生的现金流量 / 六、每股收益
        else:
            kind = "total" if any(k in first for k in ("总计", "合计", "小计")) else "item"
        rows.append([first, level, kind] + values)

    if not rows:
        raise ValueError(f"表格解析后无数据行（year={year}）")
    return rows, periods


def main():
    ap = argparse.ArgumentParser(description="抓取新浪财经三大报表（lxml 解析）")
    ap.add_argument("--stockid", required=True, help="股票代码，如 600019")
    ap.add_argument("--years", required=True, help="年份，如 '2015-2025' 或 '2025'")
    ap.add_argument(
        "--statements",
        default="profit,balance,cashflow",
        help="逗号分隔，profit/balance/cashflow，默认三张全抓",
    )
    ap.add_argument("--outdir", default="data", help="输出目录")
    ap.add_argument("--delay", type=float, default=0.6, help="每次请求间隔秒数")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    years = parse_year_spec(args.years)
    stmts = [s.strip() for s in args.statements.split(",") if s.strip()]
    for s in stmts:
        assert s in STATEMENTS, f"未知报表: {s}"

    for stmt in stmts:
        for year in years:
            out_path = os.path.join(args.outdir, f"{args.stockid}_{stmt}_{year}.csv")
            try:
                rows, periods = fetch_page(args.stockid, stmt, year)
                header = ["科目", "层级", "类型"] + periods
                lines = [header] + rows
                with open(out_path, "w", encoding="utf-8") as f:
                    for line in lines:
                        # 数值里的逗号千分位会破坏 CSV 列对齐，去掉千分位；非字符串（层级整数）转字符串
                        cleaned = [str(c).replace(",", "") if c not in (None, "") else "" for c in line]
                        f.write(",".join(cleaned) + "\n")
                print(f"[OK] {args.stockid} {stmt} {year} -> {os.path.basename(out_path)}  ({len(rows)}行)", flush=True)
            except Exception as e:
                print(f"[FAIL] {stmt} {year}: {e}", flush=True)
            time.sleep(args.delay)


if __name__ == "__main__":
    main()