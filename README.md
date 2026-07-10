# Investment Research — A 股估值研究工作台

基于 [opencode](https://opencode.ai) 的 AI 驱动投资研究项目。通过 MCP 数据源、行业专用研究方法论和标准化报告模板，对 A 股上市公司进行系统化估值分析。

## 快速开始

### 环境要求

- [opencode](https://opencode.ai) CLI
- [uv](https://docs.astral.sh/uv/)（AKShare One MCP 通过 `uvx` 运行）

### 安装

```bash
git clone <repo-url> investment-research
cd investment-research
opencode
```

`opencode.json` 中已预配置两个 A 股 MCP 数据源，无需额外 API Key：

| MCP Server | 启动方式 | 数据覆盖 |
|---|---|---|
| AKShare One MCP | `uvx akshare-one-mcp`（本地） | 历史行情、实时数据、三表、内部人交易、技术指标 |
| 中国股票数据 MCP | 远程 `http://82.156.17.205/cnstock/mcp` | 基本信息、行情、近五年财务、技术指标 |

### 研究一只股票

在 opencode 对话中直接输入公司名称或股票代码即可：

```
> 研究招商银行的估值
> 分析青岛啤酒当前是否值得买入
> 帮我看看国投电力
```

AI 会自动完成以下流程：

1. **识别行业** → 匹配对应的 research skill（见下表）
2. **收集数据** → 通过 MCP 拉取行情、三表、财务指标等
3. **选择估值方法** → 至少两种方法交叉验证
4. **生成报告** → 写入 `reports/{公司简称}/report.md`

## 已覆盖行业与研究方法论

| Skill | 适用行业 | 估值方法 | 模板 |
|---|---|---|---|
| `banking-research` | 银行（招商银行、建设银行等） | DDM、PB+ROE、RIM | `valuation-report.md` |
| `consumer-research` | 消费品（青岛啤酒、贵州茅台等） | DCF（量价拆分）、DDM、可比公司 | `valuation-report-consumer.md` |
| `power-utility-research` | 电力/公用事业（国投电力、长江电力等） | DCF、DDM、可比公司 EV/EBITDA | `valuation-report.md` |
| `raw-material-processing` | 原料加工（安琪酵母、梅花生物等） | Normalized Earnings + EV/EBITDA、DCF 含产能建模、可比公司 | `valuation-report.md` |

未覆盖的行业：AI 会先分析商业模式与财务特征，确定合适的估值方法并向你说明理由，再开展研究。

## 项目结构

```
investment-research/
├── AGENTS.md                          # AI 研究规则：角色定义、数据来源、报告要求
├── opencode.json                      # MCP Server 配置
├── .agents/skills/                    # 行业专用研究方法论
│   ├── banking-research/SKILL.md
│   ├── consumer-research/SKILL.md
│   ├── power-utility-research/SKILL.md
│   └── raw-material-processing/SKILL.md
├── templates/                         # 报告模板
│   ├── valuation-report.md            # 通用模板
│   └── valuation-report-consumer.md   # 消费品行业模板（含量价拆分、渠道结构）
└── reports/                           # 已完成的研究报告
    ├── 招商银行/
    │   ├── report.md
    │   └── data/
    ├── 建设银行/
    ├── 光大银行/
    ├── 长沙银行/
    ├── 青岛啤酒/
    ├── 安琪酵母/
    └── 国投电力/
```

## 报告核心框架

每份报告回答三个问题：

1. **内在价值** — 该企业值多少？
2. **市场预期** — 当前价格隐含了什么增长假设？
3. **估值判断** — 偏高、偏低还是合理？给出价格区间。

报告要求：

- 至少两种估值方法交叉验证（DCF / DDM / 可比公司 / PB+ROE / RIM 等）
- 所有关键假设显式列出
- 对增长率、折现率、利润率等关键变量做敏感性分析
- 同时呈现看多和看空论点
- 量化数据优先，定性判断为辅
- 末尾附免责声明

## 扩展

### 添加新行业 skill

在 `.agents/skills/` 下新建目录，编写 `SKILL.md`，定义该行业的：

- 适用判断条件
- 专用财务指标
- 推荐估值方法
- 行业特有风险框架

### 配置更多数据源

在 `opencode.json` 的 `mcp` 字段中添加 MCP Server。详见 `AGENTS.md` 中的「可用 MCP Server」清单，涵盖 A 股、美股及全球市场的免费与付费数据源。

## 免责声明

本项目所有研究报告仅供研究参考，不构成任何投资建议。投资有风险，决策需谨慎。
