#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
期货主力连续行情管道：抓取原始日线 → 本地聚合月线（akshare / 新浪主力连续）。

用途：钢材-原材料价差研究（长材 RB0 / 板材 HC0 / 铁矿 I0 / 焦炭 J0）的免费数据层，
见 README-futures.md 与 ../../methodology/cyclical-earnings-normalization.md §3.1。

设计（关键）：
- **两步分离**：fetch 抓原始日线落盘(入库层) → monthly 纯本地聚合(零网络)。
- **请求控制**：新浪是免费接口，一次 fetch 只对该品种发起 1 次网络请求并 sleep；
  聚合不碰网络。批量多品种时在 --sleep 基础上再额外休眠。
- 只覆盖【期货主力连续】(金融定价)，不代表现货/当期钢厂毛利，详见 README-futures.md。

月成交价口径：
- 新浪只回日成交量 volume(手)、无成交额，故月均价用结算价量加权
  「Σ(settle×volume)/Σ(volume)」，另附月末收盘/结算价。

用法：
  # 1) 抓原始日线（每品种 1 次请求，含延迟）
  .venv/bin/python fetch_futures_monthly.py --fetch RB0 --sleep 3
  .venv/bin/python fetch_futures_monthly.py --fetch HC0 --sleep 3
  ...
  # 2) 本地聚合月线（零网络）
  .venv/bin/python fetch_futures_monthly.py --monthly --symbol RB0 \
      --start 2014 --end 2025 --outdir data/futures/monthly
"""
import argparse
import os
import time

import akshare as ak
import pandas as pd

SYMBOLS = {"RB0": "螺纹钢", "HC0": "热轧卷板", "I0": "铁矿石", "J0": "焦炭"}
RAW_DIR = "data/futures/raw"
MONTHLY_DIR = "data/futures/monthly"


def fetch_raw(symbol: str, sleep_s: float, outdir: str):
    """拉取 symbol 全历史日线并落盘为原始 CSV（每品种一次网络请求）。"""
    os.makedirs(outdir, exist_ok=True)
    out_path = os.path.join(outdir, f"{symbol}_daily.csv")
    if os.path.exists(out_path):
        print(f"[SKIP] {out_path} 已存在，跳过（如需重拉请删除该文件）")
        return out_path

    print(f"  …请求 {symbol} ({SYMBOLS[symbol]}) 全历史日线 …")
    time.sleep(sleep_s)  # 请求前延迟，控制频率
    raw = ak.futures_zh_daily_sina(symbol=symbol)
    raw.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[OK] {out_path} ({len(raw)} 行, 日期 {raw['date'].min()} ~ {raw['date'].max()})")
    return out_path


def _load_daily(raw_path: str) -> pd.DataFrame:
    df = pd.read_csv(raw_path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def build_monthly(symbol: str, start: int, end: int, raw_dir: str, outdir: str) -> pd.DataFrame:
    """从已落盘的原始日线本地聚合 [start, end] 年区间月线（零网络）。"""
    raw_path = os.path.join(raw_dir, f"{symbol}_daily.csv")
    if not os.path.exists(raw_path):
        print(f"[ERROR] 缺原始日线 {raw_path}，请先运行 --fetch {symbol}")
        return pd.DataFrame()

    df = _load_daily(raw_path)
    df = df[(df["date"].dt.year >= start) & (df["date"].dt.year <= end)]
    if df.empty:
        print(f"[EMPTY] {symbol} 在 {start}-{end} 无数据")
        return pd.DataFrame()

    df["ym"] = df["date"].dt.to_period("M")

    def wavg(s):
        v = s["volume"].astype(float)
        return round((s["settle"] * v).sum() / v.sum(), 1)

    rows = []
    for ym, s in df.groupby("ym"):
        rows.append({
            "year": ym.year, "month": ym.month,
            "monthly_traded_sessions": len(s),
            "monthly_volume_sum": int(s["volume"].sum()),
            "monthly_volume_weighted_price": wavg(s),
            "month_end_close": s["close"].iloc[-1],
            "month_end_settle": s["settle"].iloc[-1],
        })
    out = pd.DataFrame(rows)
    out = out.sort_values(["year", "month"]).reset_index(drop=True)

    os.makedirs(outdir, exist_ok=True)
    out_path = os.path.join(outdir, f"{symbol}_{start}-{end}.csv")
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[OK] {out_path} ({len(out)} 个月)")
    return out


def main():
    ap = argparse.ArgumentParser(description="期货主连行情：抓日线→聚月线")
    ap.add_argument("--fetch", metavar="SYMBOL", help="抓取并落盘该品种全历史日线")
    ap.add_argument("--monthly", action="store_true", help="从日线聚合月线")
    ap.add_argument("--symbol", default="RB0", choices=list(SYMBOLS))
    ap.add_argument("--start", type=int, default=2014)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--sleep", type=float, default=3, help="抓取前延迟(秒)")
    ap.add_argument("--rawdir", default=RAW_DIR)
    ap.add_argument("--outdir", default=MONTHLY_DIR)
    args = ap.parse_args()

    if args.fetch:
        fetch_raw(args.fetch, args.sleep, args.rawdir)
        return

    if args.monthly:
        build_monthly(args.symbol, args.start, args.end, args.rawdir, args.outdir)
        return

    ap.print_help()


if __name__ == "__main__":
    main()