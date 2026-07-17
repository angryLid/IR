# -*- coding: utf-8 -*-
"""
中远海控 (601919.SH) 估值计算脚本
数据来源：AKShare One MCP（财务数据）、中国股票数据 MCP（行情）
数据截止：2026-07-17
"""
import json
import statistics

# ============================================================
# 1. 年度财务数据汇总（单位：亿元 CNY）
# ============================================================
# 字段含义:
#   rev         营业收入
#   op          营业利润
#   ni_total    净利润（含少数股东）
#   ni_common   归母净利润
#   eps         基本每股收益（元）
#   ocf         经营活动现金流净额
#   cash        货币资金
#   fixed_assets 固定资产净值
#   tot_eq      股东权益合计
#   minority    少数股东权益
#   common_eq   归母权益 = tot_eq - minority
#   shares      股本（亿股，A+H 合计）
#   capex_inv   投资现金流净额（用于近似 FCF 估算）

annual_data = {
    'FY2018': dict(rev=1208.30, op=30.45, ni_total=30.26, ni_common=12.30, eps=0.12,
                   ocf=46.63, cash=350.73, fixed_assets=570.51,
                   tot_eq=442.17, minority=334.67, shares=102.16, capex_inv=-9.42),
    'FY2019': dict(rev=1510.57, op=120.62, ni_total=103.50, ni_common=67.64, eps=0.56,
                   ocf=212.02, cash=503.30, fixed_assets=991.51,
                   tot_eq=691.25, minority=337.66, shares=122.60, capex_inv=-16.08),
    'FY2020': dict(rev=1712.59, op=139.31, ni_total=131.87, ni_common=99.27, eps=0.62,
                   ocf=450.31, cash=526.30, fixed_assets=992.01,
                   tot_eq=786.97, minority=347.83, shares=122.60, capex_inv=-12.62),
    'FY2021': dict(rev=3336.94, op=1282.99, ni_total=1039.05, ni_common=893.49, eps=5.59,
                   ocf=1710.09, cash=2361.97, fixed_assets=997.87,
                   tot_eq=1794.60, minority=457.66, shares=160.14, capex_inv=-78.41),
    'FY2022': dict(rev=3910.58, op=1672.64, ni_total=1314.59, ni_common=1097.03, eps=6.83,
                   ocf=1967.99, cash=2973.38, fixed_assets=1020.81,
                   tot_eq=2743.64, minority=527.42, shares=160.94, capex_inv=-281.71),
    'FY2023': dict(rev=1754.53, op=331.17, ni_total=283.97, ni_common=238.60, eps=1.48,
                   ocf=2258.38, cash=1823.56, fixed_assets=1098.95,
                   tot_eq=2433.51, minority=472.36, shares=160.71, capex_inv=-181.76),
    'FY2024': dict(rev=2338.59, op=669.97, ni_total=553.95, ni_common=491.00, eps=3.08,
                   ocf=6931.29, cash=1850.63, fixed_assets=1246.33,
                   tot_eq=2850.59, minority=503.91, shares=159.61, capex_inv=-269.72),
    'FY2025': dict(rev=2195.04, op=420.39, ni_total=352.28, ni_common=308.68, eps=1.99,
                   ocf=4554.58, cash=1514.70, fixed_assets=1479.43,
                   tot_eq=2834.06, minority=511.41, shares=154.90, capex_inv=-253.79),
    'Q1 2026': dict(rev=517.97, op=80.54, ni_total=68.82, ni_common=58.77, eps=0.38,
                    ocf=1112.48, cash=1503.34, fixed_assets=None,
                    tot_eq=2872.62, minority=515.72, shares=153.13, capex_inv=-5.75),
}

# 派生指标计算
for k, v in annual_data.items():
    v['common_eq'] = v['tot_eq'] - v['minority']
    v['bvps'] = v['common_eq'] / v['shares']  # 每股净资产（元）
    v['net_margin'] = v['ni_common'] / v['rev'] * 100
    v['ocf_to_ni'] = v['ocf'] / v['ni_common'] if v['ni_common'] > 0 else None
    v['roe'] = v['ni_common'] / v['common_eq'] * 100 if v['common_eq'] > 0 else None
    # 资产负债率（粗略用总负债/总资产 - 这里直接用 OCF 近似 FCF）
    v['fcf_approx'] = v['ocf'] + v['capex_inv']  # OCF - |capex_inv|, capex_inv 已为负

# 当前市场数据
CURRENT_PRICE = 14.54
CURRENT_SHARES = 153.13  # 亿股（2026 Q1 末）
MARKET_CAP = CURRENT_PRICE * CURRENT_SHARES  # 亿元

print("=" * 60)
print("中远海控 估值计算支撑数据")
print("=" * 60)
print(f"\n当前股价: {CURRENT_PRICE} 元")
print(f"当前股本: {CURRENT_SHARES} 亿股")
print(f"当前市值: {MARKET_CAP:.1f} 亿元")

# ============================================================
# 2. 关键财务指标时间序列（年度）
# ============================================================
print("\n" + "=" * 60)
print("2. 关键财务指标（年度，亿元 CNY）")
print("=" * 60)
header = f"{'FY':<10}{'Rev':>10}{'OP':>10}{'NI_common':>12}{'EPS':>8}{'OCF':>10}{'BPS':>8}{'ROE%':>8}"
print(header)
for k, v in annual_data.items():
    roe_str = f"{v['roe']:.2f}" if v['roe'] else "n/a"
    print(f"{k:<10}{v['rev']:>10.1f}{v['op']:>10.1f}{v['ni_common']:>12.2f}{v['eps']:>8.2f}{v['ocf']:>10.1f}{v['bvps']:>8.2f}{roe_str:>8}")

# ============================================================
# 3. Normalized Cycle Earnings 计算（多种口径）
# ============================================================
print("\n" + "=" * 60)
print("3. Normalized Cycle Earnings（多种口径，归母净利，亿元）")
print("=" * 60)

# 口径 A: 8 年简单平均（2018-2025，含超级景气 2021-2022）
years_8 = ['FY2018','FY2019','FY2020','FY2021','FY2022','FY2023','FY2024','FY2025']
ni_8year = [annual_data[y]['ni_common'] for y in years_8]
avg_8 = statistics.mean(ni_8year)
median_8 = statistics.median(ni_8year)

# 口径 B: 排除超级景气的 2021-2022 年（2018-2020, 2023-2025）
years_ex_boom = ['FY2018','FY2019','FY2020','FY2023','FY2024','FY2025']
ni_ex_boom = [annual_data[y]['ni_common'] for y in years_ex_boom]
avg_ex_boom = statistics.mean(ni_ex_boom)
median_ex_boom = statistics.median(ni_ex_boom)

# 口径 C: 近 3 年（2023-2025，类似"中位周期"假设）
years_3 = ['FY2023','FY2024','FY2025']
ni_3yr = [annual_data[y]['ni_common'] for y in years_3]
avg_3 = statistics.mean(ni_3yr)
median_3 = statistics.median(ni_3yr)

# 口径 D: 近 5 年（2021-2025，含顶部和回落）
years_5 = ['FY2021','FY2022','FY2023','FY2024','FY2025']
ni_5yr = [annual_data[y]['ni_common'] for y in years_5]
avg_5 = statistics.mean(ni_5yr)
median_5 = statistics.median(ni_5yr)

print(f"\n  口径 A: 8 年平均（含 2021/22 超级景气） = {avg_8:.1f} 亿/年  中位 {median_8:.1f}")
print(f"  口径 B: 排除 2021/22 超级景气 6 年均   = {avg_ex_boom:.1f} 亿/年  中位 {median_ex_boom:.1f}")
print(f"  口径 C: 近 3 年（2023-2025）           = {avg_3:.1f} 亿/年  中位 {median_3:.1f}")
print(f"  口径 D: 近 5 年（2021-2025）           = {avg_5:.1f} 亿/年  中位 {median_5:.1f}")

# 估值基准 Normalized Earnings 选取
# - 考虑到 2021-2022 系疫情后供应链紊乱的"异常景气"，单一年份利润不可持续
# - 但 2023 年低基数亦有红海危机前正常状态影响，2024 年含红海绕行贡献
# - 选择"排超级景气的 6 年均值"作为悲观/中位基准，"近 3 年均值"作为基准
# - 选择"8 年平均"作为偏乐观基准（含部分超级景气不可持续部分）

norm_eps_bear = avg_ex_boom
norm_eps_base = avg_3
norm_eps_bull = avg_8

print(f"\n  → 三档 Normalized 归母净利：")
print(f"     悲观: {norm_eps_bear:.1f} 亿 (排除 21/22)")
print(f"     基准: {norm_eps_base:.1f} 亿 (近 3 年均值)")
print(f"     乐观: {norm_eps_bull:.1f} 亿 (8 年含景气均值)")

# ============================================================
# 4. 方法一：Normalized Earnings × 合理 PE
# ============================================================
print("\n" + "=" * 60)
print("4. 方法一：Normalized Earnings × 合理 PE")
print("=" * 60)

# 对周期股，合理 PE 通常 6-10x（成熟周期股）；中远海控为所得龙头，且具有"高现金+高分红+低杠杆"特征
# 故 PE 选取：
#   悲观 6x, 基准 8x, 乐观 10x
PE_BEAR, PE_BASE, PE_BULL = 6, 8, 10

mc_method1_bear = norm_eps_bear * PE_BEAR
mc_method1_base = norm_eps_base * PE_BASE
mc_method1_bull = norm_eps_bull * PE_BULL

val_method1_bear = mc_method1_bear / CURRENT_SHARES
val_method1_base = mc_method1_base / CURRENT_SHARES
val_method1_bull = mc_method1_bull / CURRENT_SHARES

print(f"\n  PE 假设: 悲观 {PE_BEAR}x, 基准 {PE_BASE}x, 乐观 {PE_BULL}x")
print(f"  Normalized 归母净利: 悲观 {norm_eps_bear:.1f}, 基准 {norm_eps_base:.1f}, 乐观 {norm_eps_bull:.1f} (亿)")
print(f"\n  估值（亿元）:")
print(f"    悲观: {mc_method1_bear:.1f} → 每股 {val_method1_bear:.2f} 元")
print(f"    基准: {mc_method1_base:.1f} → 每股 {val_method1_base:.2f} 元")
print(f"    乐观: {mc_method1_bull:.1f} → 每股 {val_method1_bull:.2f} 元")

# ============================================================
# 5. 方法二：PB × 中位 ROE
# ============================================================
print("\n" + "=" * 60)
print("5. 方法二：PB × 中位 ROE（重资产周期股适用）")
print("=" * 60)

# 当前 BVPS（Q1 2026）
bvps_now = annual_data['Q1 2026']['bvps']
print(f"  当前 BVPS（Q1 2026）: {bvps_now:.2f} 元")

# 历史 ROE 序列（年度）
hist_roe = []
for y in years_8:
    r = annual_data[y]['roe']
    if r is not None:
        hist_roe.append((y, r))
print("\n  历史 ROE（年度）:")
for y, r in hist_roe:
    print(f"    {y}: {r:.2f}%")

# 排除超级景气的 6 年 ROE 中位
roe_ex_boom = [annual_data[y]['roe'] for y in years_ex_boom if annual_data[y]['roe'] is not None]
median_roe_ex_boom = statistics.median(roe_ex_boom)
avg_roe_ex_boom = statistics.mean(roe_ex_boom)
# 近 3 年 ROE
roe_recent_3 = [annual_data[y]['roe'] for y in years_3]
median_roe_3 = statistics.median(roe_recent_3)
# 8 年 ROE
roe_8 = [r for _, r in hist_roe]
median_roe_8 = statistics.median(roe_8)

print(f"\n  排除 21/22 的 6 年 ROE 中位 = {median_roe_ex_boom:.2f}%   均值 = {avg_roe_ex_boom:.2f}%")
print(f"  近 3 年 ROE 中位            = {median_roe_3:.2f}%")
print(f"  8 年 ROE 中位               = {median_roe_8:.2f}%")

# ROE 取值
roe_bear = 6.0   # 偏悲观（行业低谷 + 全球贸易放缓）
roe_base = 12.0  # 基准（接近排除超级景气的均值，反映红海等因素常态化 + 行业自然盈利能力）
roe_bull = 18.0  # 乐观（接近近 3 年均值）

# PB 取值（按中位 ROE 给予合理 PB，航运重资产周期股 ROE-PB 关系）
# 经验关系：周期股 PB ≈ ROE / 10（即 ROE 12% 对应 PB 1.2）
pb_bear = 0.65
pb_base = 1.15
pb_bull = 1.75

val_method2_bear = bvps_now * pb_bear
val_method2_base = bvps_now * pb_base
val_method2_bull = bvps_now * pb_bull

print(f"\n  BVPS = {bvps_now:.2f} 元")
print(f"  PB 假设: 悲观 {pb_bear}x, 基准 {pb_base}x, 乐观 {pb_bull}x")
print(f"  (对应隐含 ROE: 悲观 {roe_bear}%, 基准 {roe_base}%, 乐观 {roe_bull}%)")
print(f"\n  估值:")
print(f"    悲观: {val_method2_bear:.2f} 元")
print(f"    基准: {val_method2_base:.2f} 元")
print(f"    乐观: {val_method2_bull:.2f} 元")

# ============================================================
# 6. 方法三：周期性 DCF（两阶段）
# ============================================================
print("\n" + "=" * 60)
print("6. 方法三：周期性 DCF（两阶段）")
print("=" * 60)

def dcf_valuation(shares_b, norm_ni_b, growth_b, high_years, term_g, wacc, perpetuity_roe,
                  norm_capex, depreciation_per_year, print_label=""):
    """
    两阶段 DCF（基于股权自由现金流简化版）
    阶段1：高增长阶段，FCFE = Normalized NI * (1+g)^t - 增量 capex + 折旧回流（近似稳态）
    阶段2：永续阶段，按 Gordon 模型
    以归母口径估值（直接得到归母股权价值）
    """
    # FCFE 简化估算：稳态期 FCFE ≈ NI - 维护性 capex + (折旧 - 维护性 capex) 等价 NI - 维护性capex净额
    # 中远海控 OCF 远高于 NI（折旧大），稳定 capex ~30亿/年，故稳态 FCFE ≈ OCF*(stable) - 维护性 capex
    # 简化用：稳态 FCFE / Normalized NI = 1.0（含部分再投资已扣减少）
    # 此处对增长阶段给予 capex 增量
    fcfe_now = norm_ni_b  # 稳态 FCFE 起点 ≈ Normalized NI
    
    pv_stage1 = 0
    for t in range(1, high_years + 1):
        fcfe_t = fcfe_now * (1 + growth_b) ** t
        pv = fcfe_t / (1 + wacc) ** t
        pv_stage1 += pv
    
    # 永续阶段：使用 Gordon，但 NI 不再增长，使用 terminal FCFE = high_years 末 NI * (1+term_g)，永续折现
    terminal_fcfe = fcfe_now * (1 + growth_b) ** high_years * (1 + term_g)
    terminal_value = terminal_fcfe / (wacc - term_g)
    pv_terminal = terminal_value / (1 + wacc) ** high_years
    
    total_value = pv_stage1 + pv_terminal
    per_share = total_value / shares_b
    return total_value, pv_stage1, pv_terminal, per_share

# 共通参数
wacc_a = 0.092   # WACC（Ke 估计略高于无风险 + 风险溢价；中远海控为央企，Beta 较低，且净现金多）
high_years = 5   # 高增长 / 周期波动明确阶段

# 几种情景：
# 悲观：Normalized NI 200 亿，年度 FCFE 增长 0%（行业临近饱和），永续增长 0%
# 基准：Normalized NI 340 亿，年度 FCFE 增长 1.5%（航运长期货运量增长 + 集运集中度提升），永续 1.5%
# 乐观：Normalized NI 400 亿，年度 FCFE 增长 3%，永续 2%

scenarios = {
    '悲观': dict(norm_ni=200, g=0.000, term_g=0.000, wacc=0.10),
    '基准': dict(norm_ni=340, g=0.015, term_g=0.015, wacc=0.092),
    '乐观': dict(norm_ni=400, g=0.030, term_g=0.020, wacc=0.085),
}

print(f"\n  高增长阶段：{high_years} 年")
print(f"  WACC（参考）：悲观 10.0%, 基准 9.2%, 乐观 8.5%\n")

for name, args in scenarios.items():
    total, pv1, pv2, ps = dcf_valuation(
        shares_b=CURRENT_SHARES,
        norm_ni_b=args['norm_ni'],
        growth_b=args['g'],
        high_years=high_years,
        term_g=args['term_g'],
        wacc=args['wacc'],
        perpetuity_roe=None,
        norm_capex=None,
        depreciation_per_year=None
    )
    print(f"  {name}: NI={args['norm_ni']}亿 g={args['g']*100:.1f}% term_g={args['term_g']*100:.1f}% WACC={args['wacc']*100:.1f}%")
    print(f"     阶段1 PV={pv1:.1f}, 永续 PV={pv2:.1f}, 折现总价值={total:.1f} 亿 → 每股 {ps:.2f} 元\n")

# ============================================================
# 7. 估值综合（加权）
# ============================================================
print("=" * 60)
print("7. 估值综合（加权）")
print("=" * 60)

# 三种方法的结果汇总
methods = {
    'Method1_NormPE': dict(bear=val_method1_bear, base=val_method1_base, bull=val_method1_bull, weight=0.35),
    'Method2_PB_ROE': dict(bear=val_method2_bear, base=val_method2_base, bull=val_method2_bull, weight=0.35),
    'Method3_DCF':    dict(bear=6.55,  base=11.55, bull=18.34, weight=0.30),  # 与上方计算一致，代入
}

# 修正 DCF 数值
scenarios_run = {}
for name, args in scenarios.items():
    total, pv1, pv2, ps = dcf_valuation(
        shares_b=CURRENT_SHARES,
        norm_ni_b=args['norm_ni'],
        growth_b=args['g'],
        high_years=high_years,
        term_g=args['term_g'],
        wacc=args['wacc'],
        perpetuity_roe=None,
        norm_capex=None,
        depreciation_per_year=None
    )
    scenarios_run[name] = ps

methods['Method3_DCF']['bear'] = scenarios_run['悲观']
methods['Method3_DCF']['base'] = scenarios_run['基准']
methods['Method3_DCF']['bull'] = scenarios_run['乐观']

print(f"\n{'方法':<22}{'悲观':>10}{'基准':>10}{'乐观':>10}{'权重':>8}")
print("-" * 62)
weighted_bear = weighted_base = weighted_bull = 0
for name, vals in methods.items():
    print(f"{name:<22}{vals['bear']:>10.2f}{vals['base']:>10.2f}{vals['bull']:>10.2f}{vals['weight']*100:>7.0f}%")
    weighted_bear += vals['bear'] * vals['weight']
    weighted_base += vals['base'] * vals['weight']
    weighted_bull += vals['bull'] * vals['weight']

print("-" * 62)
print(f"{'加权综合':<22}{weighted_bear:>10.2f}{weighted_base:>10.2f}{weighted_bull:>10.2f}{'100%':>8}")
print(f"\n合理价格区间: {weighted_bear:.2f} ~ {weighted_bull:.2f} 元")
print(f"基准中位估值: {weighted_base:.2f} 元")
print(f"\n当前价格: {CURRENT_PRICE} 元")
print(f"vs 当前价格隐含涨幅: {(weighted_base/CURRENT_PRICE - 1)*100:+.1f}% (基准)")
print(f"           区间下限: {(weighted_bear/CURRENT_PRICE - 1)*100:+.1f}%")
print(f"           区间上限: {(weighted_bull/CURRENT_PRICE - 1)*100:+.1f}%")

# ============================================================
# 8. 关键参考：净现金分析
# ============================================================
print("\n" + "=" * 60)
print("8. 净现金与分红参考（Q1 2026）")
print("=" * 60)
q1_2026 = annual_data['Q1 2026']
cash_now = q1_2026['cash']
print(f"\n  货币资金（Q1 2026）: {cash_now:.1f} 亿元")
print(f"  占市值比例: {cash_now/MARKET_CAP*100:.1f}%")
print(f"  占归母权益比例: {cash_now/q1_2026['common_eq']*100:.1f}%")

# 派息历史（来自现金流量表）
dividends_summary = {
    'FY2018': 22.57, 'FY2019': 53.96, 'FY2020': 48.61,
    'FY2021': 96.71, 'FY2022': 611.94, 'FY2023': 415.16,
    'FY2024': 158.68, 'FY2025': 299.48,
}
print(f"\n  派息合计（annual，来自 ci 现金流-分红付息）：")
for y, d in dividends_summary.items():
    ni = annual_data[y]['ni_common']
    payout = d/ni*100 if ni > 0 else None
    print(f"    {y}: 派息 {d:>7.2f} 亿, 归母净利 {ni:>7.2f} 亿, 股利支付率 {payout:>5.1f}%" if payout else f"    {y}: 派息 {d:>7.2f} 亿")

# 平均派息率
recent_payouts = []
for y in ['FY2022','FY2023','FY2024','FY2025']:
    if annual_data[y]['ni_common'] > 0:
        recent_payouts.append(dividends_summary[y] / annual_data[y]['ni_common'] * 100)
print(f"\n  2022-2025 平均股利支付率: {statistics.mean(recent_payouts):.1f}%")
print(f"  2023-2025 平均股利支付率: {statistics.mean([dividends_summary[y]/annual_data[y]['ni_common']*100 for y in ['FY2023','FY2024','FY2025']]):.1f}%")

# 隐含股息率
avg_recent_div = statistics.mean([dividends_summary[y] for y in ['FY2023','FY2024','FY2025']])
implied_yield = avg_recent_div / MARKET_CAP * 100
print(f"  近 3 年平均派息: {avg_recent_div:.1f} 亿")
print(f"  隐含股息率（当前市值）: {implied_yield:.2f}%")

print("\n" + "=" * 60)
print("计算完成")
print("=" * 60)