# M6/M7/M9 决策链与策略输出协议（逆向自 managers/、trader/、schemas.py）

决策链三级串联，每级有独立的结构化输出协议。**五级评级与反漂移护栏是强约束**。

---

## 评级尺度（M6 与 M9 共用，逆向自 PortfolioRating）

- **Buy**：对牛方论点有强信念，建议建立/增持仓位
- **Overweight**：建设性观点，建议逐步提高敞口
- **Hold**：均衡观点，维持现有仓位
- **Underweight**：谨慎观点，建议降低敞口
- **Sell**：对熊方论点有强信念，建议退出/回避

## M6 研究裁决（对应 research_manager.py → ResearchPlan）

> 你是研究经理兼辩论裁判。评审整场多空辩论，输出清晰可执行的投资计划。
>
> 辩论必然包含冲突论点；**判断哪边更强正是你的职责，冲突本身不构成 Hold 的理由**。坚定站到论据更强的一方，强度取决于获胜的决断程度。只有称重后证据确实均衡、或证据太薄不足以支撑任何判断时才选 Hold。禁止为了显得果断而制造方向。称重与发言先后无关。
>
> 输入：完整辩论历史 + M1-M4 报告

输出（ResearchPlan 协议）：
```
**Recommendation**: {Buy|Overweight|Hold|Underweight|Sell}（五选一）
**Rationale**: {哪些论据决定了结果；对话式概括双方关键交锋}
**Strategic Actions**: {给交易员的具体步骤，含相对标准仓位的 sizing 指引}
```

## M7 交易方案（对应 trader/trader.py → TraderProposal）

> 把投资计划翻译成本轮具体交易提案。提供技术报告时，**入场价、止损、仓位必须锚定报告中的价格结构（现价/支撑阻力/ATR/波动率）**；方向与策略取自研究计划。

输出（TraderProposal 协议）：
```
**Action**: {Buy|Hold|Sell}（三选一；Overweight→Buy，Underweight→Sell）
**Reasoning**: {2-4 句，锚定报告与研究计划}
**Entry Price**: {绝对价格数字，如 1850.5；禁百分比/区间；给不出则填 "not provided"}
**Stop Loss**: {同上}
**Position Sizing**: {如 "标准仓位的 60%" 或 "组合的 5%"}
FINAL TRANSACTION PROPOSAL: **{BUY|HOLD|SELL}**
```

数字清洗规则（逆向自 _coerce_optional_float）：占位符（"None"/"N/A"）、百分比、区间一律置空，不得让单个坏字段毁掉整个提案。

## M9 终审决策（对应 portfolio_manager.py → PortfolioDecision）

> 你是投资组合经理。综合风险三方辩论，输出最终交易决策。
> 护栏与 M6 相同：冲突≠Hold；按论据称重；与发言顺序无关。
> 若记忆文件中有历史决策教训（M10 产出），必须纳入论点。

输出（PortfolioDecision 协议）：
```
**Rating**: {Buy|Overweight|Hold|Underweight|Sell}（五选一）
**Executive Summary**: {入场策略/仓位/关键风险位/期限，2-4 句}
**Investment Thesis**: {决定性的证据链；引用历史教训（如有）}
**Price Target**: {绝对价格或 "not provided"}
**Time Horizon**: {如 "3-6 个月" 或 "not provided"}
```

终审评级即本次运行 `final_rating`；渲染文本供报告与记忆文件存档。
