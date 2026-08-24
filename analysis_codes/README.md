# A 股财务报表数据管道（新浪财经免费源）

周期平均法研究的数据收集层：抓取 → 清洗 → JSON，供估值计算使用。

## 目录结构

```
analysis_codes/
  .venv/                       # uv 创建的虚拟环境（依赖隔离，不入库）
  requirements.txt             # Python 依赖
  scrape_sina_financial.py     # 抓取：新浪三大报表 → 每页一张 CSV
  clean_financial_data.py      # 清洗：CSV → 结构化 JSON（含 meta/summary）
  data/                        # 中间产物（CSV 默认不入库，JSON 建议入库）
```

## 数据流

```
新浪网页 HTML（最原始，未保存）
   ↓ scrape_sina_financial.py（抓取 + 解析，去千分位逗号）
CSV（最接近网页原样的中间产物：科目, 层级, 类型, 四季度累计列）
   ↓ clean_financial_data.py（结构重组 + meta/summary）
JSON（交付物，程序读取/人工校验用）
```

- **CSV 与 JSON 数值等价**（JSON 由 CSV 确定性生成），人工校验看 JSON 即可。
- **单位：万元**（新浪页面口径，JSON 的 meta 中标注）。

## 用法

```bash
# 激活环境（uv 管理）
cd analysis_codes
source .venv/bin/activate   # 或直接用 .venv/bin/python 调用

# 1) 抓取：12 年 × 利润表+资产负债表（串行、每张间隔 30 秒，防反爬）
python3 scrape_sina_financial.py --stockid 600019 --years 2014-2025 \
    --statements profit,balance --outdir data --delay 30

# 2) 清洗：批量生成 JSON
python3 clean_financial_data.py --stockid 600019 --years 2014-2025 \
    --indir data --outdir data
```

报表名参数：`profit`（利润表）/ `balance`（资产负债表）/ `cashflow`（现金流量表）。

## CSV 列结构

| 列 | 说明 |
|----|------|
| 科目 | 报表科目名（一级科目带"一、二、三…"编号前缀） |
| 层级 | 0=一级科目，1=二级科目（缩进） |
| 类型 | `section`（分组标题）/ `item`（科目）/ `total`（合计/总计行） |
| 其余列 | 四个报告节点的**累计值**：12-31(全年)、9-30(前三季)、6-30(半年)、3-31(一季) |

## 已知口径缺口（详见 `methodology/cyclical-earnings-normalization.md` §3.1）

1. **利息费用**：新浪只给"财务费用"总额，EBIT 用"营业利润 + 财务费用"近似（保守方向）；精确值在年报附注。
2. **受限货币资金**：新浪不拆，净债务计算按受限 = 0 处理，敏感性做 ±扰动；精确值在年报附注"使用有限制的货币资金"行。

## 防反爬注意事项

- 必须串行抓取，每张表之间间隔 20–30 秒（`--delay`）。
- 请求带浏览器 UA（脚本内置）。
- 页面为 gb18030 编码，脚本已处理。
- 若某年某表 `[FAIL]`，检查网络后单独补抓该页即可（脚本按文件独立输出，可断点续抓）。