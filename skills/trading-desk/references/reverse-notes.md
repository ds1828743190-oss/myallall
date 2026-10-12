# 逆向溯源：原版架构 → 本专家包映射

原版：TauricResearch/TradingAgents @ main（111k⭐，Apache-2.0，Python/LangGraph）
A股分支：hsliuping/TradingAgents-CN @ v1.0-preview（32k⭐，数据适配层思路）

## 编排结构（原版 graph/setup.py 的 LangGraph DAG）

```
START ──► Market Analyst ─┐
      ──► Sentiment Analyst ─┤（4 分析师为独立子图，并行、
      ──► News Analyst ─┤     各自带工具循环，max_tool_rounds=20
      ──► Fundamentals Analyst ─┤  超限强制 wrap_up 收报告）
      ──► Memory Log ─┘
          │ 全部完成后
          ▼
   Bull Researcher ⇄ Bear Researcher   （辩论轮转，count>=2×max_debate_rounds 退出）
          ▼
   Research Manager（deep LLM 裁决 → ResearchPlan 结构化输出）
          ▼
   Trader（quick LLM → TraderProposal：Action/Entry/Stop/Sizing）
          ▼
   Aggressive ⇄ Conservative ⇄ Neutral（风险辩论，count>=3×max_risk_discuss_rounds）
          ▼
   Portfolio Manager（deep LLM 终审 → PortfolioDecision，final_rating）──► END
```

LLM 分层：quick 档（分析师/研究员/辩手/交易员）与 deep 档（研究经理/PM）分开配置。
WorkBuddy 版映射：分析/辩论 = 本体多轮子调用；裁决/终审 = 升级推理档位；编排 = Agent MD 情景路由。

## 文件级映射

| 原版文件 | 本包载体 |
|---|---|
| agents/analysts/market_analyst.py（≤8 指标选择 + verified snapshot 护栏） | references/module-analysts.md M1 |
| agents/analysts/fundamentals_analyst.py | 同上 M2 |
| agents/analysts/news_analyst.py（含宏观数据与预测市场工具） | 同上 M3（预测市场/FRED 无 A 股替代，声明缺失降级） |
| agents/analysts/sentiment_analyst.py（六档+0-10 分+置信度结构化） | 同上 M4 |
| agents/researchers/bull_bear_researcher.py（辩论状态机：history/count/current_response） | references/module-debate.md M5 |
| agents/managers/research_manager.py（五级评级 + "冲突≠Hold"护栏） | references/module-decision.md M6 |
| agents/trader/trader.py（绝对价格清洗、价格结构锚定） | 同上 M7 |
| agents/risk_mgmt/{aggressive,conservative,neutral}_debator.py | references/module-debate.md M8 |
| agents/managers/portfolio_manager.py（PortfolioDecision 结构化 + 记忆教训注入） | 同上 M9 |
| agents/schemas.py（Pydantic 协议 + _coerce_optional_float 数字清洗） | 同上「输出协议」节 |
| graph/conditional_logic.py（2×N / 3×N 轮转规则） | Agent MD 情景 A 步骤 2/5 |
| memory/reflection.py（2-4 句教训、holding window 声明） | references/module-memory.md M10 |
| default_config.py（benchmark_map：.SS→000001.SS 上证 / .SZ→399001.SZ） | module-memory.md（基准改用沪深300 000300） |
| dataflows/vendors/*（yfinance/alpha_vantage/SEC/Reddit…） | scripts/akshare_data.py（东财系免费源） |
| CN: providers/ 分市场优先级链、chinese_finance 舆情 | data-akshare.md 映射表 |

## 保留的原版核心设计（逆向要点）

1. **双 LLM 档位**：便宜快的跑量大模块，深思考的只做两处裁决
2. **分析师私有子图**：并行且互不污染消息历史；工具轮数硬上限 + 强制收报告（防死循环跑爆递归限制）
3. **辩论状态机**：count 计数轮转 + 最新发言人决定下家，路由表全覆盖防漂移
4. **反漂移护栏**：「冲突本身不是 Hold 的理由」「与发言顺序无关」「百分比/占位符数字一律清洗为空」——这些是原版迭代中用 issue 修出来的（#1058/#1288/#1088/#1420），全部保留
5. **证据优先**：verified snapshot 是精确价格唯一事实来源；矛盾标注而非调和
6. **记忆闭环**：决策 → pending → 持有期后按 alpha 结算 → 2-4 句教训 → 反哺终审
