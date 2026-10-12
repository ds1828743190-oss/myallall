# 毛的专属智能体投研决策引擎（trading-desk）

逆向 GitHub 111k 星开源项目 [TradingAgents](https://github.com/TauricResearch/TradingAgents)（TauricResearch，Apache-2.0）的多智能体投研架构，融合其 A 股分支 [TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN)（32k⭐）的数据适配思路，重造为 WorkBuddy 专家包。

**无固定人设**——它是一台投研决策流水线：按情景调度分析模块，以结构化辩论互相制衡，产出可溯源、带评级的决策结论。

## 类型

Agent 型（单个 AI 专家，WorkBuddy 分类：金融投资）

## 架构（逆向自原版的虚拟交易公司）

```
四维分析师并行（技术/基本面/新闻/情绪）
        ↓
多空辩论（牛方 ⇄ 熊方，轮转制衡）
        ↓
研究经理裁决（五级评级：Buy/Overweight/Hold/Underweight/Sell）
        ↓
交易员方案（入场价/止损/仓位，绝对价格强约束）
        ↓
风险三方辩论（激进 ⇄ 保守 ⇄ 中性）
        ↓
投资组合经理终审（评级 + 执行摘要 + 投资论点 + 目标价）
        ↓
记忆反思闭环（历史决策按 alpha 结算成教训，反哺下次终审）
```

## 功能

- **情景 A 深度个股诊断**：完整流水线，输出带评级的完整报告
- **情景 B 快速体检**：精简链路，省 token 的初筛
- **情景 C 持仓风险体检**：三方辩论审视风险敞口与止损位
- **情景 D 多标的对比**：并行精简诊断 + 对比排序
- **情景 E 决策复盘**：历史决策按持有期 alpha 结算为 2-4 句教训

**本地数据层**（`skills/trading-desk/scripts/akshare_data.py`）：
东财→新浪厂商链自动回退，免费无 API Key；11 项技术指标为纯 pandas 确定性实现（与原版指标集一一对应）；K 线/快照/财务摘要/个股新闻/沪深300 基准六个子命令，JSON 输出。

**反漂移护栏**（逆向自原版迭代修出的组织纪律）：
冲突≠Hold、发言顺序无关、入场止损必须绝对价格、数据缺失即降级禁止编造。

## 使用示例

- 深度诊断贵州茅台（600519），走完整多智能体流程，给出五级评级和买卖建议
- 对我的持仓做一次风险体检，用激进/保守/中性三方辩论审视
- 对比宁德时代和比亚迪的基本面与市场情绪
- 复盘上次对 300750 的判断，结算成教训存入记忆

## 安装（WorkBuddy）

```bash
# 1. 将 trading-desk/ 放入专家目录
cp -R trading-desk ~/.workbuddy/plugins/marketplaces/my-experts/plugins/

# 2. 校验并注册
python3 scripts/validate_expert.py ~/.workbuddy/plugins/marketplaces/my-experts/plugins/trading-desk
python3 scripts/register_expert.py ~/.workbuddy/plugins/marketplaces/my-experts/plugins/trading-desk
```

数据层依赖：Python 3.9+ 与 akshare、pandas（`pip install akshare pandas`）。

## 溯源与合规

- 架构与提示词工程逆向自 TradingAgents（Apache-2.0）与 TradingAgents-CN，未复制原版代码
- 逐文件映射见 `skills/trading-desk/references/reverse-notes.md`
- 所有产出为研究流程演示，**不构成投资建议**
