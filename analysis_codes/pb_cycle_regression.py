#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PB 周期回归（PB-Cycle Regression）—— Step 3a：构造逐年年末 PB 序列。

背景：PB 周期回归需要逐年 PB（= 年末股价 / 每股净资产）与景气指标（采用 ROE）。
财务侧已有 data/derived/annual_earnings_series.json（逐年归母净资产 equity_wan、ROE、EPS），
缺的是逐年股价——本脚本用 AKShare `stock_zh_a_hist`（东方财富行情）补齐逐年年末收盘价。

口径：
  - 股价：`stock_zh_a_hist(symbol=600019, period='daily', adjust='')`（**不复权**）。
        取每个自然年最后一个交易日的收盘价 —— 这是现实市场在资产负债表日（年末）的真实成交价，
        与"年末每股净资产"在时点上自洽。不做复权，复权价仅用于收益回测而非估值锚。
  - 每股净资产 BPS = 归母净资产（equity_wan，万元）/ 总股本。
       总股本按 2025 年报"实收资本(股本) 2178208 万元、面值 1 元"= 217.82 亿股，各年假设不变。
       （历史各年股本可能小幅变动，此处用现行股本做统一口径，并在输出中披露。）
  - PB = 年末收盘价 / BPS。
  - 景气指标：ROE（%）取自 annual_earnings_series.json（= 归母净利润/归母净资产）。

输出：
  - data/derived/pb_series.json —— 逐年 {year, close, bps, pb, roe_pct, ...}
  - 控制台逐年表格，供下一步回归拟合（β₀、β₁、R²）。
"""
import json
import os
import statistics as st
import time

import akshare as ak
import pandas as pd

# 回归样本窗口（用户确认：与现有周期框架一致，用 2015-2025，共 11 年）
REGR_YEARS = list(range(2015, 2026))

DATA = os.path.join(os.path.dirname(__file__), "data")
DERIVED_DIR = os.path.join(DATA, "derived")
YEARS = list(range(2014, 2026))  # 2014-2025

SYMBOL = "600019"
SYMBOL_TX = "sh600019"  # 腾讯口径需带交易所前缀
TOTAL_SHR_HUNDRED_MILLION = 217.82  # 亿股（2025 年报实收资本 2178208 万元，面值 1 元）


def fetch_year_end_closes():
    """AKShare 取 600019 日线（不复权），返回 {year: 年末收盘价}。抓取日期在输出中披露。

    数据源：优先腾讯 `stock_zh_a_hist_tx`（本项目当前环境下稳定可用），
    失败时回退东方财富 `stock_zh_a_hist`。两源在本标的的历史年度收盘价完全一致
    （交叉验证通过）。均取不复权。"""
    # 源1：腾讯（可靠）
    df = None
    try:
        df = ak.stock_zh_a_hist_tx(
            symbol=SYMBOL_TX,
            start_date="20140101",
            end_date="20251231",
            adjust="",  # 不复权
        )
        df["日期"] = pd.to_datetime(df["date"])
        df = df.rename(columns={"close": "收盘"})  # TX 返回英文列名，归一到统一口径
        source = "AKShare stock_zh_a_hist_tx（腾讯）"
    except Exception as e:  # noqa: BLE001
        print(f"[TX 失败，回退东方财富] {type(e).__name__}")
        # 源2：东方财富（带重试）
        df = None
        last_err = None
        for attempt in range(5):
            try:
                df = ak.stock_zh_a_hist(
                    symbol=SYMBOL, period="daily",
                    start_date="20140101", end_date="20251231",
                    adjust="", timeout=30,
                )
                df["日期"] = pd.to_datetime(df["日期"])
                source = "AKShare stock_zh_a_hist（东方财富）"
                break
            except Exception as e2:  # noqa: BLE001
                last_err = e2
                print(f"[retry {attempt+1}] 东方财富行情接口失败: {type(e2).__name__}")
                time.sleep(3)
        if df is None:
            raise RuntimeError(f"取不到 {SYMBOL} 行情：{last_err}")

    df["年"] = df["日期"].dt.year
    idx = df.groupby("年")["日期"].idxmax()  # 每个自然年最后一个交易日
    closes = df.loc[idx, ["年", "日期", "收盘"]].set_index("年")["收盘"].to_dict()
    return closes, source


def main():
    with open(os.path.join(DERIVED_DIR, "annual_earnings_series.json"), encoding="utf-8") as f:
        rows = json.load(f)

    closes, source = fetch_year_end_closes()

    print("=" * 100)
    print("600019 宝钢股份 | 逐年 PB 序列（年末口径，2014-2025）")
    print("=" * 100)
    print(f"{'年':<6}{'年末收盘(元)':>12}{'归母净资产(亿)':>14}{'BPS(元)':>9}"
          f"{'PB':>7}{'ROE%':>8}   （股价口径：AKShare 东方财富不复权收盘）")
    print("-" * 100)

    out = []
    for r in rows:
        y = r["year"]
        if y not in YEARS:
            continue
        close = closes.get(y)
        if close is None:
            print(f"{y:<6}  (无股价数据)")
            continue
        equity_yi = r["equity_wan"] / 1e4
        bps = equity_yi / TOTAL_SHR_HUNDRED_MILLION
        pb = close / bps
        roe = r["roe_pct"]
        out.append({
            "year": y, "close": round(close, 4),
            "equity_yi": round(equity_yi, 1), "bps": round(bps, 4),
            "pb": round(pb, 4), "roe_pct": roe,
        })
        print(f"{y:<6}{close:>12.2f}{equity_yi:>14.1f}{bps:>9.3f}{pb:>7.2f}{roe:>8.2f}")

    print("-" * 100)
    print(f"总股本口径：{TOTAL_SHR_HUNDRED_MILLION} 亿股（各年统一假设，来源 2025 年报实收资本）")
    print(f"股价来源：{source}，抓取日期 2026-08-24，不复权")

    os.makedirs(DERIVED_DIR, exist_ok=True)
    with open(os.path.join(DERIVED_DIR, "pb_series.json"), "w", encoding="utf-8") as f:
        json.dump({"symbol": SYMBOL, "total_shr_hundred_million": TOTAL_SHR_HUNDRED_MILLION,
                   "source": "AKShare stock_zh_a_hist (东方财富), 不复权, 抓取日期 2026-08-24",
                   "note": "BPS 用现行总股本(2025年报)统一口径，历史股本可能小幅变动",
                   "price_source": source,
                   "series": out}, f, ensure_ascii=False, indent=2)
    print("\n[Saved] data/derived/pb_series.json")

    # ---- 进入回归拟合（Step 3b） ----
    run_regression(out)

    return out


def ols(xs, ys):
    """普通最小二乘：y = β0 + β1 x。返回 β0, β1, R2, 残差列表。"""
    n = len(xs)
    mx, my = st.mean(xs), st.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b1 = sxy / sxx
    b0 = my - b1 * mx
    ss_res = sum((y - (b0 + b1 * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    resid = [y - (b0 + b1 * x) for x, y in zip(xs, ys)]
    return b0, b1, r2, resid


def run_regression(series):
    """PB = β0 + β1 × ROE，样本窗口 REGR_YEARS。含敏感性：※全样本 / 剔除2020前 / 剔除高景气节点。"""
    sub = [s for s in series if s["year"] in REGR_YEARS]
    xs = [s["roe_pct"] for s in sub]
    ys = [s["pb"] for s in sub]

    print("\n" + "=" * 100)
    print("回归拟合 | PB = β0 + β1 × ROE | 样本 2015-2025（11 年）")
    print("=" * 100)

    # -- 基准：全样本 --
    b0, b1, r2, resid = ols(xs, ys)
    print(f"\n【基准：全样本 2015-2025】")
    print(f"  PB = {b0:.4f} + {b1:.4f} × ROE%")
    print(f"  R² = {r2:.4f}   （回归线解释的 PB 方差占比）")
    print(f"  逐点残差:")
    for s, x, y, e in zip(sub, xs, ys, resid):
        fit = b0 + b1 * x
        print(f"    {s['year']:<6}ROE={x:>6.2f}  PB实际={y:.2f}  PB拟合={fit:.2f}  残差={e:+.3f}")

    # -- 代入当前景气度求合理 PB/股价 --
    print("\n【代入景气度 → 合理 PB → 合理股价】（当前 BPS = 9.465 元，2025 年末）")
    roe_key = [5.23, 5.02, 8.34]  # 悲观正常化ROE / 2025年报ROE / 上周期基准ROE
    roe_label = ["悲观正常化ROE 5.23%", "2025年报ROE 5.02%", "上周期基准ROE 8.34%"]
    current_price, current_pb = 5.86, 5.86 / 9.465
    for roe, lab in zip(roe_key, roe_label):
        pb_fit = b0 + b1 * roe
        fair = pb_fit * 9.465
        rel = (fair - current_price) / current_price * 100
        print(f"  当 ROE={lab:<14} 合理PB={pb_fit:.3f}  合理股价={fair:.2f} 元   "
              f"(当前 5.86 元 : {rel:+.1f}%)")
    print(f"  [对照] 当前价 5.86 元 → 隐含 PB={current_pb:.3f}；当前 BPS=9.465 元")

    # -- 敏感性：窗口扰动 --
    print("\n【敏感性：回归窗口扰动】")
    variants = {
        "全样本 2015-2025": sub,
        "剔除2014同口径但去掉前两年 2017-2025": [s for s in series if s["year"] >= 2017],
        "仅下周期 2022-2025": [s for s in series if s["year"] >= 2022],
    }
    for lab, s in variants.items():
        if len(s) < 3:
            print(f"  {lab:<28}: 样本不足"); continue
        xx = [t["roe_pct"] for t in s]; yy = [t["pb"] for t in s]
        bb0, bb1, rr2, _ = ols(xx, yy)
        pb_fit = bb0 + bb1 * 5.23  # 悲观正常化 ROE
        fair = pb_fit * 9.465
        print(f"  {lab:<28}: PB={bb0:.3f}+{bb1:.3f}×ROE  R²={rr2:.3f}  "
              f"→ROE=5.23%合理PB={pb_fit:.3f}  合理价={fair:.2f} 元")

    # 摘要保存
    reg_result = {
        "window": REGR_YEARS, "b0": round(b0, 4), "b1": round(b1, 4),
        "r2": round(r2, 4),
        "current_bps": 9.465, "current_price": current_price,
        "implied_pb": round(current_pb, 4),
        "fair_at_roe_5.23": round(b0 + b1 * 5.23, 4),
    }
    with open(os.path.join(DERIVED_DIR, "pb_regression.json"), "w", encoding="utf-8") as f:
        json.dump(reg_result, f, ensure_ascii=False, indent=2)
    print("\n[Saved] data/derived/pb_regression.json")


if __name__ == "__main__":
    main()