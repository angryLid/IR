#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周期识别（Step 1）：判断"一个完整的钢铁周期"的边界。

输入：data/financial/ 下 600019 利润表/资产负债表 CSV（单位：万元，取每年 12-31 年报口径）、
      data/futures/spread_2014-2025.csv（期货主力连续价差代理）、
      data/macro/*.csv（地产新开工、PMI）
输出：data/derived/annual_earnings_series.json（逐年盈利序列）
输出：逐年盈利序列（EPS/EBIT/EBIT利润率/归母净利/归母净资产/ROE）
      + 外生周期证据（期货价差分位、地产新开工同比、PMI 年均）
      —— 供判断周期窗口边界使用，不做最终估值。

口径（遵循方法论 §3.1）：
  - EBIT(近似) = 营业利润 + 财务费用
  - EBIT 利润率 = EBIT / 营业收入
  - ROE = 归母净利润 / 归母净资产
  - 归母净资产 = 归属于母公司股东权益合计
"""
import csv
import os
import re
from collections import defaultdict

import argparse

DATA = os.path.join(os.path.dirname(__file__), "data")
FIN_DIR = os.path.join(DATA, "financial")      # 三大报表 CSV 所在目录
DERIVED_DIR = os.path.join(DATA, "derived")    # 衍生计算文件输出目录
YEARS = list(range(2014, 2026))  # 2014-2025

# 关键科目（精确名称匹配，来自清洗脚本可核对的 summary 名）
PROFIT_KEYS = {
    "revenue": "营业收入",
    "op_profit": "营业利润",
    "fin_expense": "财务费用",
    "net_profit": "归属于母公司所有者的净利润",
    "eps": "基本每股收益(元/股)",
}
BALANCE_KEYS = {
    "equity": "归属于母公司股东权益合计",
    "cash": "货币资金",
    "st_loan": "短期借款",
    "lt_loan": "长期借款",
    "bond": "应付债券",
    "lease": "租赁负债",
    "cur_lt_debt": "一年内到期的非流动负债",
}


def to_number(s):
    if s is None:
        return None
    s = s.strip().replace(",", "").replace("--", "")
    return float(s) if s else None


def strip_prefix(name):
    return re.sub(r"^[一二三四五六七八九十]+、", "", name)


def read_annual(stockid, stmt, year):
    """读某年 CSV，返回 {clean_name: annual_value(万元或元/股)}。取 12-31 年报列。"""
    path = os.path.join(FIN_DIR, f"{stockid}_{stmt}_{year}.csv")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        periods = header[3:]
        if not periods:
            return None
        annual = periods[0]  # 首个报告日，即为 {year}-12-31
        out = {}
        for row in reader:
            if not row or not row[0].strip():
                continue
            name = strip_prefix(row[0].strip())
            idx = 3  # 第一个值列位置
            val = to_number(row[idx]) if idx < len(row) else None
            out[name] = val
    return out


def main():
    ap = argparse.ArgumentParser(description="周期识别（Step 1）")
    ap.add_argument("--stockid", default="600019", help="股票代码，如 600782")
    ap.add_argument("--name", default=None, help="公司名称（仅显示用），默认取 stockid")
    args = ap.parse_args()
    stockid = args.stockid
    label = args.name or stockid

    rows = []
    for y in YEARS:
        p = read_annual(stockid, "profit", y)
        b = read_annual(stockid, "balance", y)
        if p is None:
            print(f"[SKIP] 无 {y} 利润表")
            continue
        rev = p.get("营业收入")
        ebit = None
        if p.get("营业利润") is not None and p.get("财务费用") is not None:
            ebit = p["营业利润"] + p["财务费用"]
        ebit_margin = (ebit / rev * 100) if (ebit is not None and rev) else None
        np_att = p.get("归属于母公司所有者的净利润")
        eps = p.get("基本每股收益(元/股)")
        equity = b.get("归属于母公司股东权益合计") if b else None
        roe = (np_att / equity * 100) if (np_att is not None and equity) else None
        rows.append({
            "year": y,
            "rev_wan": rev,
            "np_att_wan": np_att,          # 归母净利润（万元）
            "eps": eps,                     # 元/股
            "ebit_wan": ebit,               # 万元
            "ebit_margin_pct": ebit_margin,
            "equity_wan": equity,           # 归母净资产（万元）
            "roe_pct": roe,
        })

    print("=" * 96)
    print(f"{stockid} {label} | 逐年盈利序列（年报口径，2014-2025）")
    print("=" * 96)
    print(f"{'年':<5}{'营收(亿)':>10}{'归母净利(亿)':>13}{'EPS(元)':>9}"
          f"{'EBIT(亿)':>10}{'EBIT利润率%':>11}{'归母净资产(亿)':>14}{'ROE%':>8}")
    for r in rows:
        def e(x):
            return "" if x is None else f"{x/1e4:.1f}"
        def f2(x):
            return "" if x is None else f"{x:.2f}"
        def f1(x):
            return "" if x is None else f"{x:.1f}"
        print(f"{r['year']:<5}{e(r['rev_wan']):>10}{e(r['np_att_wan']):>13}"
              f"{f2(r['eps']):>9}{e(r['ebit_wan']):>10}"
              f"{f1(r['ebit_margin_pct']):>11}{e(r['equity_wan']):>14}{f1(r['roe_pct']):>8}")

    import json
    os.makedirs(DERIVED_DIR, exist_ok=True)
    out_path = os.path.join(DERIVED_DIR, f"annual_earnings_series_{stockid}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"\n[Saved] {out_path}")


if __name__ == "__main__":
    main()
