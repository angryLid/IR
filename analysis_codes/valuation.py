#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新钢股份（600782）估值汇总脚本 —— Normalized Earnings × 行业倍数。

口径与宝钢报告（reports/600019 宝钢股份/report.md §4）完全一致：
  - 路线一（主锚）：合理 EV = Normalized EBITDA × EV/EBITDA 区间(5-7x)
                    → 股权价值 = 合理EV − 净债务 → 每股 = 股权价值 ÷ 总股本
  - 路线二（副锚）：合理价 = Normalized EPS × 周期中性 PE 区间(8-12x)
  - 交叉验证：PB 周期回归（独立检验是否失效）
  - 质量折价敏感性：因新钢盈利质量低于宝钢行业标杆，单列 4x 档折价分析

输入：从 data/derived/ 读取新钢独立的派生数据。
输出：控制台估值表格 + data/derived/valuation.json

仅供研究参考，不构成投资建议。
"""
import argparse
import json
import os

DATA = os.path.join(os.path.dirname(__file__), "data")
DERIVED_DIR = os.path.join(DATA, "derived")

EV_EBITDA_RANGE = (5.0, 6.0, 7.0)   # 行业正常化倍数：下限/中枢/上限
PE_RANGE = (8.0, 10.0, 12.0)        # 周期中性 PE：下限/中枢/上限
QUALITY_DISCOUNT_MULT = 4.0         # 质量折价档（EV/EBITDA 4x，弱于行业5-7x下沿）


def load(stockid, fname):
    with open(os.path.join(DERIVED_DIR, fname.format(stockid=stockid)), encoding="utf-8") as f:
        return json.load(f)


def fmt_yuan(v):
    return f"{v:.2f} 元"


def main():
    ap = argparse.ArgumentParser(description="新钢股份估值汇总（Normalized × 行业倍数）")
    ap.add_argument("--stockid", default="600782")
    ap.add_argument("--total-shr", type=float, required=True, help="总股本（亿股）")
    ap.add_argument("--net-debt", type=float, required=True, help="净债务（亿元，有息负债−货币资金）")
    ap.add_argument("--current-price", type=float, required=True, help="当前股价（元）")
    args = ap.parse_args()
    sid = args.stockid

    ebitda_doc = load(sid, "ebitda_series_{stockid}.json")
    norm_doc = load(sid, "normalized_pessimistic_A_{stockid}.json")

    norm = norm_doc["normalized"]
    norm_ebitda = ebitda_doc["normalized_2022_2025"]["ebitda"]
    norm_eps = norm.get("EPS(元)")
    total_shr = args.total_shr

    print("=" * 96)
    print(f"{sid} 估值汇总 | 悲观情景（Normalized = 2022-2025 均值，与宝钢同口径）")
    print("=" * 96)
    print(f"  Normalized EBITDA = {norm_ebitda:.1f} 亿")
    print(f"  Normalized EPS    = {norm_eps:.3f} 元")
    print(f"  总股本 = {total_shr:.2f} 亿股 | 净债务 = {args.net_debt:.1f} 亿 | 当前价 = {args.current_price:.2f} 元")

    print("\n【路线一：EV/EBITDA 主锚（行业 5/6/7x）】")
    print(f"{'EV/EBITDA':>10}{'合理EV(亿)':>12}{'股权价值(亿)':>14}{'合理每股':>10}")
    ev_rows = []
    for m in EV_EBITDA_RANGE:
        ev = norm_ebitda * m
        eq = ev - args.net_debt
        ps = eq / total_shr
        ev_rows.append((m, ev, eq, ps))
        print(f"{m:>8.1f}x{ev:>12.1f}{eq:>14.1f}{ps:>10.2f} 元")

    print("\n【路线二：PE 副锚（周期中性 8/10/12x）】")
    print(f"{'PE':>10}{'合理每股':>10}")
    pe_rows = []
    for m in PE_RANGE:
        ps = norm_eps * m
        pe_rows.append((m, ps))
        print(f"{m:>8.1f}x{ps:>10.2f} 元")

    print("\n【质量折价敏感性（单列，EV/EBITDA 4x）】")
    m = QUALITY_DISCOUNT_MULT
    ev = norm_ebitda * m
    eq = ev - args.net_debt
    ps = eq / total_shr
    print(f"{m:>8.1f}x{ev:>12.1f}{eq:>14.1f}{ps:>10.2f} 元  ← 质量折价档（弱于行业 5-7x）")
    q_rows = [(m, ev, eq, ps)]

    # 当前隐含倍数
    cur_ev = args.current_price * total_shr + args.net_debt
    cur_ev_ebitda = cur_ev / norm_ebitda
    cur_pe = args.current_price / norm_eps if norm_eps else None
    print("\n【当前定价对照】")
    print(f"  当前市值 = {args.current_price * total_shr:.0f} 亿 → EV ≈ {cur_ev:.0f} 亿")
    print(f"  当前隐含 EV/EBITDA = {cur_ev_ebitda:.2f}x（对照行业 5-7x）")
    if cur_pe:
        print(f"  当前隐含 PE = {cur_pe:.1f}x（对照中性 8-12x）")

    out = {
        "symbol": sid, "scenario": "pessimistic",
        "normalized": {"ebitda_yi": norm_ebitda, "eps": norm_eps},
        "market": {"total_shr_yi": total_shr, "net_debt_yi": args.net_debt,
                   "current_price": args.current_price,
                   "current_ev_yi": cur_ev,
                   "implied_ev_ebitda": round(cur_ev_ebitda, 2),
                   "implied_pe": round(cur_pe, 1) if cur_pe else None},
        "route_ev_ebitda": [{"mult": m, "ev_yi": ev, "equity_yi": eq, "price": ps}
                            for m, ev, eq, ps in ev_rows],
        "route_pe": [{"mult": m, "price": ps} for m, ps in pe_rows],
        "quality_discount_4x": [{"mult": m, "ev_yi": ev, "equity_yi": eq, "price": ps}
                                for m, ev, eq, ps in q_rows],
    }
    out_path = os.path.join(DERIVED_DIR, f"valuation_{sid}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n[Saved] {out_path}")


if __name__ == "__main__":
    main()