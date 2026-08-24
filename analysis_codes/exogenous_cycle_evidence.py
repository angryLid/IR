#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
外生周期证据：期货价差/价格分位 + 地产新开工同比 + PMI 年均
配合 identify_cycle.py 的盈利序列，共同支持周期窗口判定（方法论 §3.2 Step 1）。

期货数据为"主力连续"免费替代（新浪主连），仅用于周期分位/方向/拐点辅助，
不代表当期钢厂毛利（方法论 §3.1 免费期货替代局限）。
"""
import csv
import os
from collections import OrderedDict

DATA = os.path.join(os.path.dirname(__file__), "data")


def load_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.reader(f))


def parse_ym(s):
    # "2014-01" -> (2014,1)；"2025年12月" -> (2025,12)
    s = s.strip()
    if "年" in s:
        import re
        m = re.match(r"(\d{4})年(\d{1,2})月", s)
        return (int(m.group(1)), int(m.group(2)))
    y, m = s.split("-")
    return (int(y), int(m))


def percentile(seq, x):
    """求 x 在样本 seq 中的百分位(0-100)，线性插值近似。"""
    s = sorted(seq)
    if not s:
        return None
    import bisect
    n = len(s)
    # 用 (rank-1)/(n-1) 最近邻估计
    idx = bisect.bisect_left(s, x)
    idx = min(max(idx - 1, 0), n - 1)
    return (idx / (n - 1)) * 100


def main():
    print("=" * 96)
    print("外生周期证据 | 期货主力连续（免费替代，仅方向/分位辅助）")
    print("=" * 96)

    rows = load_csv(os.path.join(DATA, "futures", "spread_2014-2025.csv"))
    header = rows[0]
    # columns: ym, RB, HC, iron, coke, raw_cost, RB_spread, HC_spread
    recs = []
    for r in rows[1:]:
        if len(r) < 2 or not r[0].strip():
            continue
        def num(i):
            try:
                return float(r[i]) if i < len(r) and r[i].strip() else None
            except ValueError:
                return None
        recs.append({"ym": parse_ym(r[0]), "RB": num(1), "HC": num(2),
                     "RB_spread": num(6), "HC_spread": num(7)})

    # 全样本的 RB / HC 价格分位与 RB_spread 分位
    rb_vals = [x["RB"] for x in recs if x["RB"] is not None]
    hc_vals = [x["HC"] for x in recs if x["HC"] is not None]
    rb_sp_vals = [x["RB_spread"] for x in recs if x["RB_spread"] is not None]

    # 按年份聚合价差均值，粗看拐点
    by_year = OrderedDict()
    for x in recs:
        y = x["ym"][0]
        if y not in by_year:
            by_year[y] = {"rb": [], "hc": [], "rbsp": []}
        if x["RB"] is not None:
            by_year[y]["rb"].append(x["RB"])
        if x["HC"] is not None:
            by_year[y]["hc"].append(x["HC"])
        if x["RB_spread"] is not None:
            by_year[y]["rbsp"].append(x["RB_spread"])

    print(f"{'年':<6}{'RB均价':>9}{'RB价分位%':>10}{'HC均价':>9}"
          f"{'HC价分位%':>10}{'RB价差平均':>11}{'RB价差分位%':>11}")
    for y in sorted(by_year):
        d = by_year[y]
        rb = sum(d["rb"]) / len(d["rb"]) if d["rb"] else None
        hc = sum(d["hc"]) / len(d["hc"]) if d["hc"] else None
        rbsp = sum(d["rbsp"]) / len(d["rbsp"]) if d["rbsp"] else None
        print(f"{y:<6}{rb:>9.0f}{percentile(rb_vals, rb):>10.0f}"
              f"{hc:>9.0f}{percentile(hc_vals, hc):>10.0f}"
              f"{rbsp:>11.0f}{percentile(rb_sp_vals, rbsp) if rbsp is not None else '':>11.0f}")

    # 地产新开工
    print("\n" + "=" * 96)
    print("外生周期证据 | 地产新开工面积（累计同比%）与制造业 PMI（年均）")
    print("=" * 96)
    for fname, label in [
        ("real_estate_area_total_2014-2025.csv", "房地产新开工累计同比%"),
        ("real_estate_area_residential_2014-2025.csv", "商品住宅新开工累计同比%"),
    ]:
        rows2 = load_csv(os.path.join(DATA, "macro", fname))
        hdr = rows2[0]
        # 找"新开工"的累计增长列（总/商品住宅）
        start_yoy_col = None
        for i, h in enumerate(hdr):
            if "新开工" in h and "累计增长" in h:
                start_yoy_col = i
                break
        annual_yoy = {}
        for r in rows2[1:]:
            if len(r) < 2 or not r[0].strip():
                continue
            ym = parse_ym(r[0])
            if ym[1] != 12:  # 只取 12 月（全年累计）
                continue
            try:
                annual_yoy[ym[0]] = float(r[start_yoy_col])
            except (ValueError, IndexError):
                pass
        print(f"\n[{label}]")
        print("  " + "  ".join(f"{y}:{v:+.1f}" for y, v in sorted(annual_yoy.items())))

    # PMI 年均
    pmi_rows = load_csv(os.path.join(DATA, "macro", "pmi_eastmoney.csv"))
    pmi_hdr = pmi_rows[0]
    man_idx = pmi_hdr.index("manufacturing_index")
    by_year_pmi = OrderedDict()
    for r in pmi_rows[1:]:
        if not r or not r[0].strip():
            continue
        ym = parse_ym(r[0])
        y = ym[0]
        if y < 2014 or y > 2025:
            continue
        try:
            by_year_pmi.setdefault(y, []).append(float(r[man_idx]))
        except (ValueError, IndexError):
            pass
    print("\n[制造业PMI年均]")
    print("  " + "  ".join(f"{y}:{sum(v)/len(v):.1f}" for y, v in sorted(by_year_pmi.items())))


if __name__ == "__main__":
    main()
