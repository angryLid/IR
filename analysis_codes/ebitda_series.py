#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐年 EBITDA 序列 + 正常化 EBITDA（口径修正）。

背景：此前"悲观正常化"（2022-2025）用的是 EBIT（= 营业利润 + 财务费用，approximation），
但 EV/EBITDA 方法论的钢铁行业 5-7x 倍数对应的是 **EBITDA**（EBIT + 折旧摊销）口径。
EBITDA 显著大于 EBIT（钢铁重资产折旧摊销高），因此必须补上折旧摊销，否则合理价被系统性低估。

数据缺口处理（用户确认：邻年插补）：
  新浪现金流量表在 2022（年报列）与 2023（全年）缺失"固定资产折旧"行。
  因宝钢固定资产折旧历年稳定在 ~190 亿（2017-2025 均为此量级），
  对缺失年份用相邻有值年份做线性插补，并在结果中显式标记 interpolated=True。
  无形资产摊销、长期待摊费用摊销两年完整，使用真实值。

输入：
  - data/derived/annual_earnings_series.json   （逐年 EBIT/EBIT利润率/ROE/EPS，来源利润表+资产负债表）
  - data/financial/600019_cashflow_{year}.csv  （现金流量表补充资料：折旧摊销，单位万元）
输出：
  - data/derived/ebitda_series.json（逐年 EBITDA = EBIT + 折旧摊销，含插补标记）
  - 悲观情景(2022-2025) Normalized EBITDA

折旧摊销口径：固定资产折旧 + 无形资产摊销 + 长期待摊费用摊销
（新浪免费页未见"使用权资产折旧"单列行，按 0 处理并披露）

EBITDA = EBIT + 折旧摊销（EBIT 沿用近似口径 = 营业利润 + 财务费用）
"""
import argparse
import csv
import json
import os
import re
import statistics as st

DATA = os.path.join(os.path.dirname(__file__), "data")
FIN_DIR = os.path.join(DATA, "financial")
DERIVED_DIR = os.path.join(DATA, "derived")

YEARS = list(range(2015, 2026))  # 2015-2025

DEPR_KEY = "固定资产折旧、油气资产折耗、生产性物资折旧"
DA_KEYS = [
    DEPR_KEY,
    "无形资产摊销",
    "长期待摊费用摊销",
    "使用权资产折旧",
]


def strip_prefix(name):
    return re.sub(r"^[一二三四五六七八九十]+、", "", name)


def to_number(s):
    if s is None:
        return None
    s = s.strip().replace(",", "").replace("--", "")
    return float(s) if s else None


def read_cashflow_da(stockid, year):
    """读某年现金流表，返回 {key: 值}（万元），缺失项为 None。取 12-31 年报列。"""
    path = os.path.join(FIN_DIR, f"{stockid}_cashflow_{year}.csv")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig") as f:
        rd = csv.reader(f)
        next(rd)
        found = {}
        for row in rd:
            if not row or not row[0].strip():
                continue
            name = strip_prefix(row[0].strip())
            if name in DA_KEYS:
                found[name] = to_number(row[3]) if len(row) > 3 else None
    return found


def interpolate_depr(stockid):
    """对固定资产折旧缺失年份做线性插补，返回 {year: (value, interpolated)}。"""
    # 收集各年固定资产折旧原始值
    raw = {}
    for y in YEARS:
        d = read_cashflow_da(stockid, y)
        raw[y] = d.get(DEPR_KEY) if d else None

    result = {}
    sorted_y = sorted(raw)
    for y in sorted_y:
        if raw[y] is not None:
            result[y] = (raw[y], False)
            continue
        # 前方最近有值
        prev = next((yy for yy in reversed(sorted_y)
                     if yy < y and raw[yy] is not None), None)
        # 后方最近有值
        nxt = next((yy for yy in sorted_y
                    if yy > y and raw[yy] is not None), None)
        if prev is not None and nxt is not None:
            span = nxt - prev
            frac = (y - prev) / span
            val = raw[prev] + (raw[nxt] - raw[prev]) * frac
        elif prev is not None:
            val = raw[prev]
        elif nxt is not None:
            val = raw[nxt]
        else:
            val = None
        result[y] = (val, True)
    return result


def main():
    ap = argparse.ArgumentParser(description="逐年 EBITDA 序列 + 正常化 EBITDA")
    ap.add_argument("--stockid", default="600019", help="股票代码，如 600782")
    ap.add_argument("--name", default=None, help="公司名称（仅显示用），默认取 stockid")
    args = ap.parse_args()
    stockid = args.stockid
    label = args.name or stockid

    with open(os.path.join(DERIVED_DIR, f"annual_earnings_series_{stockid}.json"), encoding="utf-8") as f:
        rows = json.load(f)

    # 固定资产折旧（含插补）
    depr = interpolate_depr(stockid)

    print("=" * 104)
    print(f"逐步 EBITDA 序列 | EBIT + 折旧摊销（单位：亿元）| {stockid} {label}")
    print("=" * 104)
    print(f"{'年':<6}{'EBIT(亿)':>10}{'固定折旧(亿)':>13}{'其他摊销(亿)':>12}"
          f"{'DA合计(亿)':>11}{'EBITDA(亿)':>11}{'EBITDA利润率%':>13}")
    print(" " * 6 + "(插补以*标记)")

    out = []
    for r in rows:
        y = r["year"]
        if y not in YEARS:
            continue
        d = read_cashflow_da(stockid, y) or {}
        depr_val, interp = depr[y]
        # 其他摊销 = 无形资产 + 长期待摊
        other_da = sum(v for k, v in d.items()
                       if k in ("无形资产摊销", "长期待摊费用摊销") and v)
        da = (depr_val or 0) + (other_da or 0)
        if depr_val is None and not other_da:
            print(f"{y:<6}  (无现金流表)")
            continue
        ebit = r["ebit_wan"] / 1e4
        ebitda = ebit + da / 1e4
        rev = r["rev_wan"] / 1e4 if r["rev_wan"] else None
        m = (ebitda / rev * 100) if rev else None
        mark = "*" if interp else ""
        out.append({
            "year": y, "ebit_wan": r["ebit_wan"], "depr_wan": depr_val,
            "other_da_wan": other_da, "da_wan": da, "da_interpolated": interp,
            "ebitda_wan": r["ebit_wan"] + da, "ebitda": ebitda,
            "ebitda_margin_pct": m, "roe_pct": r["roe_pct"],
        })
        print(f"{y}{mark:<5}{(ebit if ebit else 0):>10.1f}"
              f"{(depr_val or 0)/1e4:>13.1f}{(other_da or 0)/1e4:>12.1f}"
              f"{da/1e4:>11.1f}{ebitda:>11.1f}{(m if m else 0):>13.2f}")

    print("\n注：* 表示固定资产折旧为邻年插补值（2022/2023 新浪源数据缺失，用户确认插补处理）")

    print("\n" + "=" * 104)
    print("悲观情景正常化 EBITDA（2022-2025 均值，方法 A，与 EBIT 口径同框架）")
    print("=" * 104)
    nxt = [x for x in out if 2022 <= x["year"] <= 2025]
    norm_ebitda = st.mean([x["ebitda"] for x in nxt])
    norm_ebit = st.mean([x["ebit_wan"] / 1e4 for x in nxt])
    norm_da = st.mean([x["da_wan"] / 1e4 for x in nxt])
    norm_depr = st.mean([x["depr_wan"] / 1e4 for x in nxt])
    norm_margin = st.mean([x["ebitda_margin_pct"] for x in nxt])
    print(f"  Normalized EBITDA (22-25均值)      = {norm_ebitda:.1f} 亿")
    print(f"  其中 Normalized EBIT(22-25均值)    = {norm_ebit:.1f} 亿  ← 此前悲观口径")
    print(f"       Normalized 固定折旧(22-25均值)= {norm_depr:.1f} 亿（含2年插补）")
    print(f"       Normalized 其他摊销(22-25均值)= {norm_da - norm_depr:.1f} 亿")
    print(f"  Normalized EBITDA利润率            = {norm_margin:.2f}%")
    print(f"\n  => EBITDA/EBIT 比值 = {norm_ebitda/norm_ebit:.2f}x（重资产放大效应）")

    cyc = [x for x in out if 2015 <= x["year"] <= 2021]
    base_ebitda = st.mean([x["ebitda"] for x in cyc])
    print(f"\n  上周期基准(2015-2021) Normalized EBITDA = {base_ebitda:.1f} 亿（对照）")

    with open(os.path.join(DERIVED_DIR, f"ebitda_series_{stockid}.json"), "w", encoding="utf-8") as f:
        json.dump({"symbol": stockid, "series": out, "normalized_2022_2025": {
            "ebitda": norm_ebitda, "ebit": norm_ebit, "da": norm_da,
            "depr": norm_depr, "ebitda_margin_pct": norm_margin,
            "base_2015_2021_ebitda": base_ebitda,
            "interpolation_note": "2022/2023固定资产折旧为邻年线性插补（如适用）",
        }}, f, ensure_ascii=False, indent=2)
    print(f"\n[Saved] data/derived/ebitda_series_{stockid}.json")


if __name__ == "__main__":
    main()
