#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把抓取到的三大报表 CSV 清洗成结构化 JSON，供人工校验与后续计算。

输入：scrape_sina_financial.py 产出的 data/{stockid}_{stmt}_{year}.csv
      CSV 列：科目, 层级(0/1), 类型(section/item/total), {报告日期}_1.._4
输出：data/{stockid}_{stmt}_{year}.json

JSON 结构：
{
  "meta": {...来源与口径信息...},
  "statement": "利润表 / 资产负债表 / 现金流量表",
  "unit": "万元",
  "periods": ["2025-12-31", ...],
  "items": [{"name": "...", "level": 0/1, "kind": "section/item/total",
             "values": {"2025-12-31": 数值或null, ...}}, ...],
  "summary": {关键科目速览，便于人工核对}
}

用法：
  python3 clean_financial_data.py --stockid 600019 --years 2025 --indir data --outdir data
"""
import argparse
import csv
import json
import os
import re

UNIT = "万元"  # 新浪财经三大报表单位

STMT_LABELS = {
    "profit": "利润表",
    "balance": "资产负债表",
    "cashflow": "现金流量表",
}

# 每张报表用于 summary 的关键科目（按名称模糊匹配，便于人工核对）
SUMMARY_KEYS = {
    "profit": ["营业总收入", "营业成本", "营业利润", "利润总额", "净利润",
               "归属于母公司所有者的净利润", "基本每股收益(元/股)"],
    "balance": ["货币资金", "应收票据及应收账款", "存货", "流动资产合计",
                "资产总计", "短期借款", "应付票据及应付账款", "流动负债合计",
                "长期借款", "负债合计", "实收资本(或股本)", "归属于母公司股东权益合计",
                "所有者权益(或股东权益)合计", "负债和所有者权益(或股东权益)总计"],
    "cashflow": ["经营活动现金流入小计", "经营活动产生的现金流量净额",
                 "投资活动产生的现金流量净额", "筹资活动产生的现金流量净额",
                 "现金及现金等价物净增加额", "期末现金及现金等价物余额"],
}


def to_number(s):
    """'--' 或空 -> None；'1,234.5' -> 1234.5（千分位已在抓取时去除，此处兜底）。"""
    if s is None:
        return None
    s = s.strip().replace(",", "").replace("--", "")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def build_items(rows, periods):
    items = []
    for row in rows:
        # row: [科目, 层级, 类型, 值1..值4]
        name = row[0].strip()
        level = int(row[1]) if row[1] in ("0", "1") else 0
        kind = row[2].strip() if len(row) > 2 else "item"
        values = row[3 : 3 + len(periods)]
        if not values:
            values = [None] * len(periods)  # section 行无数值列时补全为 null
        val_map = {p: to_number(v) for p, v in zip(periods, values)}
        items.append({"name": name, "level": level, "kind": kind, "values": val_map})
    return items


def build_summary(items, periods, stmt):
    """对每个关键科目做模糊匹配：科目名去掉编号前缀（一、二、…）后按子串匹配。"""
    def strip_prefix(name):
        return re.sub(r"^[一二三四五六七八九十]+、", "", name)

    def find(name_key):
        for it in items:
            if strip_prefix(it["name"]) == name_key:
                return it
        # 退而求其次：子串包含匹配（注意避免"净利润"误配"归属于母公司所有者的净利润"等）
        for it in items:
            n = strip_prefix(it["name"])
            if n == name_key:
                return it
        return None

    summary = {}
    for key in SUMMARY_KEYS[stmt]:
        found = find(key)
        if found:
            summary[key] = {p: found["values"][p] for p in periods}
        else:
            summary[key] = {p: None for p in periods}
    return summary


def process(stockid, stmt, year, indir, outdir):
    csv_path = os.path.join(indir, f"{stockid}_{stmt}_{year}.csv")
    json_path = os.path.join(outdir, f"{stockid}_{stmt}_{year}.json")

    if not os.path.exists(csv_path):
        print(f"[SKIP] 无 CSV，跳过 {os.path.basename(csv_path)}")
        return None

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        # header: 科目, 层级, 类型, 日期...
        periods = header[3:]
        rows = [r for r in reader if r and r[0].strip()]

    items = build_items(rows, periods)
    summary = build_summary(items, periods, stmt)

    doc = {
        "meta": {
            "stockid": stockid,
            "year": year,
            "statement": STMT_LABELS[stmt],
            "unit": UNIT,
            "periods_type": "累计值(截至该报告日)",
            "source": "新浪财经-上市公司财务报表页",
            "url_template": (
                "https://money.finance.sina.com.cn/corp/go.php/"
                f"vFD_{stmt.upper()}/stockid/{stockid}/ctrl/{year}/displaytype/4.phtml"
            ),
        },
        "periods": periods,
        "items": items,
        "summary": summary,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"[OK] {json_path} ({len(items)}个科目)")
    return doc


def main():
    ap = argparse.ArgumentParser(description="清洗新浪财报 CSV 为 JSON")
    ap.add_argument("--stockid", required=True)
    ap.add_argument("--years", required=True, help="如 '2025' 或 '2015-2025'")
    ap.add_argument("--indir", default="data")
    ap.add_argument("--outdir", default="data")
    args = ap.parse_args()

    if "-" in args.years:
        start, end = args.years.split("-")
        years = list(range(int(start), int(end) + 1))
    else:
        years = [int(args.years)]

    os.makedirs(args.outdir, exist_ok=True)
    for stmt in STMT_LABELS:
        for year in years:
            process(args.stockid, stmt, year, args.indir, args.outdir)


if __name__ == "__main__":
    main()