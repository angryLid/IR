#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
正常化盈利（Normalized Earnings）计算 —— Step 2 说明性演示。

基于周期窗口判定（用户确认：2015-2025 完整窗口，2022-2025 按下行段计入），
对窗口内 EPS / EBIT / EBIT利润率 / ROE 取统计量（简单平均 / 中位数 / 去峰谷），
展示不同口径下正常化盈利的水平差异。

单位：EPS(元/股)、EBIT(亿元)、EBIT利润率(%)、ROE(%)。
不构成估值结论或投资建议。
"""
import json
import os

DATA = os.path.join(os.path.dirname(__file__), "data")
DERIVED_DIR = os.path.join(DATA, "derived")
WINDOW = list(range(2015, 2026))  # 2015-2025


def load():
    with open(os.path.join(DERIVED_DIR, "annual_earnings_series.json"), encoding="utf-8") as f:
        return json.load(f)


def mean(xs):
    return sum(xs) / len(xs)


def median(xs):
    s = sorted(xs)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def fmt(x):
    return f"{x:,.3f}" if x is not None else "n/a"


def main():
    rows = load()
    win = [r for r in rows if r["year"] in WINDOW]
    assert len(win) == 11, f"窗口应有 11 年，实际 {len(win)}"

    print("=" * 92)
    print(f"正常化盈利 | 周期窗口 2015-2025（11年，用户确认完整窗口）")
    print("=" * 92)

    metrics = {
        "EPS(元)": ("eps", 1, 2),
        "EBIT(亿)": ("ebit_wan", 1e4, 1),
        "EBIT利润率%": ("ebit_margin_pct", 1, 1),
        "ROE%": ("roe_pct", 1, 1),
    }

    # 各口径值
    print(f"\n{'指标':<14}{'简单平均':>12}{'中位数':>12}{'去峰谷(2015/16/21)':>18}")
    simple = {}
    median_s = {}
    drop = {}
    for label, (key, div, nd) in metrics.items():
        vals = [r[key] / div for r in win if r[key] is not None]
        # 去峰谷：去掉谷底 2015/2016 与顶点 2021
        non_extreme = [r[key] / div for r in win
                       if r[key] is not None and r["year"] not in (2015, 2016, 2021)]
        simple[label] = mean(vals)
        median_s[label] = median(vals)
        drop[label] = mean(non_extreme)
        print(f"{label:<14}{fmt(simple[label]):>12}{fmt(median_s[label]):>12}"
              f"{fmt(drop[label]):>18}")

    # 近三年加权（2023-2025，反映结构性下行后的当下盈利水平）
    print(f"\n{'指标':<14}{'最近3年均(2023-25)':>18}")
    for label, (key, div, nd) in metrics.items():
        recent = [r[key] / div for r in win if r[key] is not None and r["year"] >= 2023]
        print(f"{label:<14}{fmt(mean(recent)):>18}")

    # 对比：仅取 2021 顶点年 vs 2015 谷底年
    print("\n对照（单年，周期位置扭曲演示）:")
    y21 = next(r for r in win if r["year"] == 2021)
    y15 = next(r for r in win if r["year"] == 2015)
    print(f"  2021 顶点: EPS={y21['eps']:.2f}  ROE={y21['roe_pct']:.1f}%  "
          f"EBIT={y21['ebit_wan']/1e4:.0f}亿") 
    print(f"  2015 谷底: EPS={y15['eps']:.2f}  ROE={y15['roe_pct']:.1f}%  "
          f"EBIT={y15['ebit_wan']/1e4:.0f}亿")


if __name__ == "__main__":
    main()
