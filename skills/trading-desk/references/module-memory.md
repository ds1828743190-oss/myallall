# M10 记忆反思协议（逆向自 memory/reflection.py + memory/settlement）

原版用「未决→结算」记忆日志：决策先以 pending 入库，持有 `holding_period_days`（默认 5 个交易日）后用实际涨跌结算，Reflector 生成 2-4 句教训存档，供后续 PM 终审引用。

## 本地实现（不依赖原版 MongoDB）

记忆文件：`skills/trading-desk/memory_log.md`（不存在则创建），每条格式：

```markdown
### {日期} | {代码} | {评级} | pending
- 决策摘要：{Executive Summary 一句}
- 入场/止损：{...}
- 基准：{沪深300 同期}
```

结算时（情景 E，复盘触发）：

1. 用 `akshare_data.py kline` 取决策日与当前日的价格，算持有期收益率与相对沪深300（`index_zh_a_hist` 代码 000300）的 alpha
2. 按 Reflector 模板生成教训（**恰好 2-4 句纯散文**，无列表无标题）：
   > 你是一名交易分析师，正在复盘自己过去的决策，结果已知晓。结果覆盖决策后 {N} 个交易日，可能短于决策时设定的期限。
   > 依次覆盖：① {N} 日 alpha 显示方向判断对错（引用数字），窗口太短不足以检验论点时要直说；② 这段窗口支持或推翻了投资论点的哪一部分；③ 一条可用于下次同类分析的具体教训。
   > 输出将逐字存入记忆日志并被未来分析师重读，每个字都要有信息量。
3. 把条目的 `pending` 改为 `settled`，教训追加进条目；`memory_log_max_entries` 上限（默认 50 条）超出时淘汰最老的已结算条目，pending 永不淘汰
4. 终审（M9）时把全部未决 + 最近已结算条目的教训注入 prompt
