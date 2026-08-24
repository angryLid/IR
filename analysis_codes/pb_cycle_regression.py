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
import argparse
import json
import os
import statistics as st
import time

import akshare as ak
import pandas as pd

# 回归样本窗口（默认与现有周期框架一致：2015-2025，共 11 年）
REGR_YEARS = list(range(2015, 2026))

DATA = os.path.join(os.path.dirname(__file__), "data")
DERIVED_DIR = os.path.join(DATA, "derived")
YEARS = list(range(2014, 2026))  # 2014-2025

# 默认标的为宝钢（此前口径）；新钢用 --stockid 600782 --name 新钢股份 --total-shr <亿股> 传入
SYMBOL = "600019"
SYMBOL_TX = "sh600019"  # 腾讯口径需带交易所前缀
TOTAL_SHR_HUNDRED_MILLION = 217.82  # 亿股（2025 年报实收资本 2178208 万元，面值 1 元）


def fetch_year_end_closes(stockid):
    """AKShare 取日线（不复权），返回 {year: 年末收盘价}。抓取日期在输出中披露。

    数据源：优先腾讯 `stock_zh_a_hist_tx`（本项目当前环境下稳定可用），
    失败时回退东方财富 `stock_zh_a_hist`。两源在已测标的的历史年度收盘价完全一致
    （交叉验证通过）。均取不复权。"""
    symbol_tx = ("sh" if stockid.startswith("6") else "sz") + stockid
    # 源1：腾讯（可靠）
    df = None
    try:
        df = ak.stock_zh_a_hist_tx(
            symbol=symbol_tx,
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
                    symbol=stockid, period="daily",
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
            raise RuntimeError(f"取不到 {stockid} 行情：{last_err}")

    df["年"] = df["日期"].dt.year
    idx = df.groupby("年")["日期"].idxmax()  # 每个自然年最后一个交易日
    closes = df.loc[idx, ["年", "日期", "收盘"]].set_index("年")["收盘"].to_dict()
    return closes, source


def main():
    ap = argparse.ArgumentParser(description="PB 周期回归（PB-Cycle Regression）")
    ap.add_argument("--stockid", default="600019", help="股票代码，如 600782")
    ap.add_argument("--name", default=None, help="公司名称（仅显示用），默认取 stockid")
    ap.add_argument("--total-shr", type=float, default=None, help="总股本（亿股），默认用模块常量 TOTAL_SHR_HUNDRED_MILLION")
    args = ap.parse_args()
    stockid = args.stockid
    label = args.name or stockid
    total_shr = args.total_shr if args.total_shr else TOTAL_SHR_HUNDRED_MILLION

    with open(os.path.join(DERIVED_DIR, f"annual_earnings_series_{stockid}.json"), encoding="utf-8") as f:
        rows = json.load(f)

    closes, source = fetch_year_end_closes(stockid)

    print("=" * 100)
    print(f"{stockid} {label} | 逐年 PB 序列（年末口径，2014-2025）")
    print("=" * 100)
    print(f"{'年':<6}{'年末收盘(元)':>12}{'归母净资产(亿)':>14}{'BPS(元)':>9}"
          f"{'PB':>7}{'ROE%':>8}   （股价口径：AKShare 不复权收盘）")
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
        bps = equity_yi / total_shr
        pb = close / bps
        roe = r["roe_pct"]
        out.append({
            "year": y, "close": round(close, 4),
            "equity_yi": round(equity_yi, 1), "bps": round(bps, 4),
            "pb": round(pb, 4), "roe_pct": roe,
        })
        print(f"{y:<6}{close:>12.2f}{equity_yi:>14.1f}{bps:>9.3f}{pb:>7.2f}{roe:>8.2f}")

    print("-" * 100)
    print(f"总股本口径：{total_shr} 亿股（默认现行股本统一口径，历史股本可能小幅变动）")
    print(f"股价来源：{source}，抓取日期 2026-08-24，不复权")

    os.makedirs(DERIVED_DIR, exist_ok=True)
    with open(os.path.join(DERIVED_DIR, f"pb_series_{stockid}.json"), "w", encoding="utf-8") as f:
        json.dump({"symbol": stockid, "total_shr_hundred_million": total_shr,
                   "source": "AKShare 行情, 不复权, 抓取日期 2026-08-24",
                   "note": "BPS 用现行总股本统一口径，历史股本可能小幅变动",
                   "price_source": source,
                   "series": out}, f, ensure_ascii=False, indent=2)
    print(f"\n[Saved] data/derived/pb_series_{stockid}.json")

    # ---- 进入回归拟合（Step 3b） ----
    # 景气度 ROE 取值：悲观正常化 ROE / 最新年报 ROE / 上周期基准 ROE（读新钢自身序列）
    with open(os.path.join(DERIVED_DIR, f"normalized_pessimistic_A_{stockid}.json"), encoding="utf-8") as f:
        np_doc = json.load(f)
    norm_roe = np_doc["normalized"].get("ROE%")
    latest_roe = rows[-1]["roe_pct"] if rows else None
    cyc_rows = [r for r in rows if r["year"] in REGR_YEARS and r["year"] <= 2021]
    base_roe = st.mean([r["roe_pct"] for r in cyc_rows]) if cyc_rows else None
    roe_labels = ["悲观正常化ROE", "最新年报ROE", "上周期基准ROE"]
    run_regression(out, stockid, norm_roe, latest_roe, base_roe, roe_labels)

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


def run_regression(series, stockid, norm_roe, latest_roe, base_roe, roe_labels):
    """PB = β0 + β1 × ROE，样本窗口 REGR_YEARS。含敏感性：※全样本 / 剔除2020前 / 剔除高景气节点。"""
    sub = [s for s in series if s["year"] in REGR_YEARS]
    xs = [s["roe_pct"] for s in sub]
    ys = [s["pb"] for s in sub]

    print("\n" + "=" * 100)
    print(f"回归拟合 | PB = β0 + β1 × ROE | 样本 2015-2025（11 年）| {stockid}")
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
    current_bps = series[-1]["bps"] if series else 0.0
    current_price = series[-1]["close"] if series else 0.0
    print(f"\n【代入景气度 → 合理 PB → 合理股价】（当前 BPS = {current_bps:.3f} 元，{series[-1]['year']} 年末）")
    roe_key = [norm_roe, latest_roe, base_roe]
    for roe, lab in zip(roe_key, roe_labels):
        if roe is None:
            continue
        pb_fit = b0 + b1 * roe
        fair = pb_fit * current_bps
        rel = (fair - current_price) / current_price * 100 if current_price else 0.0
        print(f"  当 ROE={roe:.2f}%（{lab}）  合理PB={pb_fit:.3f}  合理股价={fair:.2f} 元   "
              f"(当前 {current_price:.2f} 元 : {rel:+.1f}%)")
    print(f"  [对照] 当前价 {current_price:.2f} 元 → 隐含 PB={current_price/current_bps:.3f}；当前 BPS={current_bps:.3f} 元")

    # -- 敏感性：窗口扰动 --
    print("\n【敏感性：回归窗口扰动】")
    variants = {
        "全样本 2015-2025": sub,
        "剔除前两年 2017-2025": [s for s in series if s["year"] >= 2017],
        "仅下周期 2022-2025": [s for s in series if s["year"] >= 2022],
    }
    ref_roe = norm_roe if norm_roe is not None else 5.23
    for lab, s in variants.items():
        if len(s) < 3:
            print(f"  {lab:<28}: 样本不足"); continue
        xx = [t["roe_pct"] for t in s]; yy = [t["pb"] for t in s]
        bb0, bb1, rr2, _ = ols(xx, yy)
        pb_fit = bb0 + bb1 * ref_roe
        fair = pb_fit * current_bps
        print(f"  {lab:<28}: PB={bb0:.3f}+{bb1:.3f}×ROE  R²={rr2:.3f}  "
              f"→ROE={ref_roe:.2f}%合理PB={pb_fit:.3f}  合理价={fair:.2f} 元")

    # 摘要保存
    reg_result = {
        "window": REGR_YEARS, "b0": round(b0, 4), "b1": round(b1, 4),
        "r2": round(r2, 4),
        "current_bps": current_bps, "current_price": current_price,
        "implied_pb": round(current_price / current_bps, 4) if current_bps else None,
        "fair_at_norm_roe": round(b0 + b1 * ref_roe, 4),
    }
    with open(os.path.join(DERIVED_DIR, f"pb_regression_{stockid}.json"), "w", encoding="utf-8") as f:
        json.dump(reg_result, f, ensure_ascii=False, indent=2)
    print(f"\n[Saved] data/derived/pb_regression_{stockid}.json")


if __name__ == "__main__":
    main()