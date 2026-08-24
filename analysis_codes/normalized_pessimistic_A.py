#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
正常化盈利（Normalized Earnings）—— 周期框架 + "下一周期更弱"假设

框架（用户确认）：
  1. 上一完整周期 = 2015-2021（谷2015/16 → 顶2021），波形完整，作为基准。
  2. 下一周期（2022起）总体上弱于上一周期（地产需求中枢不可逆下移）。
  3. 悲观情景主口径 = 方法 A：以 2022-2025 四年均值作为下一周期的正常化中枢。

输出：上一周期基准 / 下一周期下移校准(δ) / 悲观(方法A)正常化值。
单位：EPS(元/股)、ROE(%)、EBIT利润率(%)、EBIT(亿元)。
仅供研究参考，不构成投资建议。
"""
import json
import os
import statistics as st

DATA = os.path.join(os.path.dirname(__file__), "data")
DERIVED_DIR = os.path.join(DATA, "derived")
CYCLE = list(range(2015, 2022))     # 上一完整周期 2015-2021
NEXT = list(range(2022, 2026))      # 下一周期已发生 2022-2025

METRICS = [
    ("EPS(元)", "eps", 1, "{:.3f}"),
    ("ROE%", "roe_pct", 1, "{:.2f}"),
    ("EBIT利润率%", "ebit_margin_pct", 1, "{:.2f}"),
    ("EBIT(亿)", "ebit_wan", 1e4, "{:.1f}"),
]


def load():
    with open(os.path.join(DERIVED_DIR, "annual_earnings_series.json"), encoding="utf-8") as f:
        return json.load(f)


def mean(xs):
    return st.mean(xs) if xs else None


def main():
    rows = load()
    cyc = [r for r in rows if r["year"] in CYCLE]
    nxt = [r for r in rows if r["year"] in NEXT]

    print("=" * 92)
    print("正常化盈利 | 周期框架 + 下一周期更弱（悲观=方法A）")
    print("=" * 92)
    print(f"\n{'指标':<14}{'上周期基准2015-21':>18}{'下周期已发生22-25':>18}{'下移幅度δ':>12}")
    print(" " * 14 + "(波形完整·均值)" + " " * 2 + "(方法A·悲观主口径)")

    results = {}
    for lbl, key, div, fmt in METRICS:
        b = mean([r[key] / div for r in cyc])
        n = mean([r[key] / div for r in nxt])
        delta = (n / b - 1) * 100 if b else None
        results[lbl] = n
        d = fmt.format(delta) if delta is not None and "EPS" not in lbl and "EBIT(" not in lbl else (
            fmt.format(delta) if delta is not None else "n/a")
        print(f"{lbl:<14}{fmt.format(b):>18}{fmt.format(n):>18}{d:>12}")

    print("\n结论（悲观情景·方法A正常化主口径）：")
    for lbl, v in results.items():
        print(f"  Normalized {lbl} = {v:.3f}" if "EPS" in lbl else
              (f"  Normalized {lbl} = {v:.2f}" if "ROE" in lbl or "EBIT利润率" in lbl else
               f"  Normalized {lbl} = {v:.1f}"))

    # 落盘
    out = {
        "method": "A",
        "scenario": "pessimistic",
        "upper_cycle": {"label": "2015-2021", "years": CYCLE},
        "next_cycle": {"label": "2022-2025", "years": NEXT},
        "assumption": "下一周期弱于上一周期（地产需求中枢不可逆下移）；悲观主口径=2022-2025均值",
        "normalized": {k: v for (k, _, _, _), v in zip(METRICS, results.values())},
        "source": "data/derived/annual_earnings_series.json",
    }
    os.makedirs(DERIVED_DIR, exist_ok=True)
    with open(os.path.join(DERIVED_DIR, "normalized_pessimistic_A.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n[Saved] data/derived/normalized_pessimistic_A.json")


if __name__ == "__main__":
    main()
