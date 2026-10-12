---
name: trading-desk
description: Multi-agent investment decision engine modules. Load when running any trading-desk scenario (diagnosis, checkup, comparison, review). Contains analyst module prompts, debate protocols, decision/output protocol, memory reflection and the local A-share data tool.
metadata:
  version: "1.0.0"
  source: "Reverse-engineered from TauricResearch/TradingAgents (Apache-2.0) + hsliuping/TradingAgents-CN"
---

# trading-desk 技能模块库（毛的专属智能体投研决策引擎）

本技能是「毛的专属智能体投研决策引擎」的模块载体。按 Agent MD 的情景路由调用：

## 使用顺序

1. **取数据**：跑 `scripts/akshare_data.py`（见 `references/data-akshare.md`），把 JSON 结果作为唯一事实来源注入分析
2. **分析师模块**（可并行）：`references/module-analysts.md` 中的 M1-M4 模板
3. **辩论协议**：`references/module-debate.md` 中的 M5 多空辩论 / M8 风险三方辩论
4. **决策链**：`references/module-decision.md` 中的 M6 研究裁决 → M7 交易方案 → M9 终审，输出协议同样在此
5. **复盘**：`references/module-memory.md`（M10）

## 硬约束

- 所有结论必须锚定 `akshare_data.py` 的真实输出；接口失败即声明数据缺失并降级置信度，禁止编造数字
- 评级与输出协议字段为强约束，见 `references/module-decision.md`
- 每次最终输出结尾附「以上为多智能体研究流程产出，不构成投资建议」

## 溯源

架构与提示词模板逆向自 TauricResearch/TradingAgents（111k⭐，Apache-2.0）的 `tradingagents/agents/`、`graph/`、`memory/`，A股数据层思路来自 hsliuping/TradingAgents-CN（32k⭐）。逐条映射见 `references/reverse-notes.md`。
