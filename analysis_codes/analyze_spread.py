#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合成钢材-原材料价差序列并做趋势观察。

原料成本近似（行业常用吨钢系数）：
    吨钢铁矿消耗 ≈ 1.6 吨；吨钢焦炭消耗 ≈ 0.5 吨。
    原料成本 ≈ 1.6 × 铁矿价 + 0.5 × 焦炭价
    螺纹价差 ≈ RB − 原料成本；  热卷价差 ≈ HC − 原料成本

注意：这是"钢材−(铁矿+焦炭)"两原料腿的**代理价差**，不含废钢、电、折旧、人工，
不代表当期钢厂毛利（详见 README-futures.md 局限项）。

用法：
  .venv/bin/python analyze_spread.py --symbols RB0,HC0,I0,J0 \
      --start 2014 --end 2025 --indir data/futures/monthly --outdir data/futures
"""
import argparse
import os

import pandas as pd

# 吨钢原料系数（行业近似）
IRON_ORE_PER_TON = 1.6   # 吨钢铁矿（吨）
COKE_PER_TON = 0.5       # 吨钢焦炭（吨）


def load_monthly(symbol, start, end, indir):
    path = os.path.join(indir, f"{symbol}_{start}-{end}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    df["ym"] = pd.to_datetime(
        dict(year=df["year"], month=df["month"], day=1)
    ).dt.to_period("M")
    df = df.set_index("ym")[["monthly_volume_weighted_price", "month_end_close"]]
    df.columns = [f"{symbol}_wavg", f"{symbol}_close"]
    return df


def main():
    ap = argparse.ArgumentParser(description="合成钢材-原材料价差序列")
    ap.add_argument("--symbols", default="RB0,HC0,I0,J0")
    ap.add_argument("--start", type=int, default=2014)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--indir", default="data/futures/monthly")
    ap.add_argument("--outdir", default="data/futures")
    args = ap.parse_args()

    syms = [s.strip() for s in args.symbols.split(",")]
    frames = [load_monthly(s, args.start, args.end, args.indir) for s in syms]
    price = pd.concat(frames, axis=1).sort_index()

    # 用量加权月均价做价差主口径
    rb = price["RB0_wavg"]
    hc = price["HC0_wavg"]
    iron = price["I0_wavg"]
    coke = price["J0_wavg"]

    raw_cost = IRON_ORE_PER_TON * iron + COKE_PER_TON * coke
    spread = pd.DataFrame({
        "RB(螺纹)": rb,
        "HC(热卷)": hc,
        "iron(铁矿)": iron,
        "coke(焦炭)": coke,
        "raw_cost(原料成本)": raw_cost,
        "RB_spread(螺纹价差)": rb - raw_cost,
        "HC_spread(热卷价差)": hc - raw_cost,
    })
    spread = spread.round(1)

    os.makedirs(args.outdir, exist_ok=True)
    out_path = os.path.join(args.outdir, f"spread_{args.start}-{args.end}.csv")
    spread.to_csv(out_path, encoding="utf-8-sig")
    print(f"[OK] {out_path} ({len(spread)} 个月)")
    print(spread.to_string())


if __name__ == "__main__":
    main()