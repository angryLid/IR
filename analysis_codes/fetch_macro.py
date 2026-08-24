#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拉取钢铁行业周期研究所用的**免费宏观/需求数据**并落盘为原始 CSV（akshare）。

来源与接口（均经实测可用，见 ../../methodology/cyclical-earnings-normalization.md
§3.1「宏观/需求数据免费可得性实测」）：
  - 制造业 PMI            : ak.macro_china_pmi()   （东财官方，月度 2008 起）
  - 房地产新开工/施工/竣工面积: ak.macro_china_nbs_nation(kind='月度数据',
    path='房地产>房地产施工、竣工面积')（国家统计局，月度，可回溯到 2014）

口径注意：
  - 地产数据返回的是**当年累计值**（1 月至当月的累计），不是当月单月。
    当月值 = 本月累计 - 上月累计；若看同比，用累计同比即可（不受累计影响）。
  - PMI 为综合指数：>50 扩张、<50 收缩。

用法：
  .venv/bin/python fetch_macro.py --item pmi
  .venv/bin/python fetch_macro.py --item real_estate --start 2014 --end 2025
  建议两个都跑：
  .venv/bin/python fetch_macro.py --all --start 2014 --end 2025
"""
import argparse
import os
import time

import akshare as ak
import pandas as pd

RAW_DIR = "data/macro"


def fetch_pmi(outdir: str):
    """东财官方制造业/非制造业 PMI（月度）。一次调用拿全历史。"""
    os.makedirs(outdir, exist_ok=True)
    out_path = os.path.join(outdir, "pmi_eastmoney.csv")
    if os.path.exists(out_path):
        print(f"[SKIP] {out_path} 已存在（如需重拉请删除）")
        return
    print("  …请求 PMI …")
    df = ak.macro_china_pmi()  # 中文列：月份, 制造业-指数, ...
    # 统一列名为英文，便于程序读取
    df = df.rename(columns={
        "月份": "period",
        "制造业-指数": "manufacturing_index",
        "制造业-同比增长": "manufacturing_yoy",
        "非制造业-指数": "non_manufacturing_index",
        "非制造业-同比增长": "non_manufacturing_yoy",
    })
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[OK] {out_path} ({len(df)} 行, 期间 {df['period'].iloc[0]} ~ {df['period'].iloc[-1]})")


# 统计局地产各指标的可读名称映射（指标名含中文，展示用）
RE_PATHS = {
    "all": "房地产>房地产施工、竣工面积",          # 总口径：施工/新开工/竣工
    "residential": "房地产>商品住宅施工、竣工面积",  # 住宅口径：施工/新开工/竣工
}


def fetch_real_estate(outdir: str, start: int, end: int, scope: str):
    """国家统计局房地产面积：新开工/施工/竣工（累计值，月度）。"""
    os.makedirs(outdir, exist_ok=True)
    period_str = f"{start}-{end}"
    tag = "residential" if scope == "residential" else "total"
    out_path = os.path.join(outdir, f"real_estate_area_{tag}_{period_str}.csv")
    if os.path.exists(out_path):
        print(f"[SKIP] {out_path} 已存在（如需重拉请删除）")
        return

    path = RE_PATHS[scope]
    print(f"  …请求 统计局 path='{path}' {period_str} …")
    time.sleep(2)
    df = ak.macro_china_nbs_nation(
        kind="月度数据", path=path, period=period_str
    )
    if df.empty:
        print(f"[EMPTY] {out_path} 无数据")
        return
    # df: index=指标名(中文), columns=月份(如 2014年3月)。转置成 指标为列、月份为行。
    df = df.T.reset_index().rename(columns={"index": "period"})
    # 统一列名：去指标里的中文计量后缀，保留说明
    df.columns = [str(c) for c in df.columns]
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[OK] {out_path} ({len(df)} 行, 列: {list(df.columns)[:6]}…)")
    print(df.tail(3).head(3).to_string())


def main():
    ap = argparse.ArgumentParser(description="拉取免费宏观/需求数据落盘")
    ap.add_argument("--item", choices=["pmi", "real_estate", "all"],
                    help="pmi=制造业PMI, real_estate=地产面积, all=两者")
    ap.add_argument("--start", type=int, default=2014)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--outdir", default=RAW_DIR)
    args = ap.parse_args()

    items = []
    if args.item == "all" or args.item == "pmi":
        items.append("pmi")
    if args.item == "all" or args.item == "real_estate":
        items.append("real_estate")

    if not items:
        ap.print_help()
        return

    if "pmi" in items:
        fetch_pmi(args.outdir)
    if "real_estate" in items:
        fetch_real_estate(args.outdir, args.start, args.end, "all")
        fetch_real_estate(args.outdir, args.start, args.end, "residential")


if __name__ == "__main__":
    main()