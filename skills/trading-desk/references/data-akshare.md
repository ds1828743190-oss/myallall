# A股本地数据层手册（逆向自 CN 分支数据适配思路，akshare 实现）

## 工具

`scripts/akshare_data.py`，运行环境：托管 venv（`/Users/xiaolv/.workbuddy/binaries/python/envs/default/bin/python`，已装 akshare + pandas）。全部免费数据源（东财/新浪），无需任何 API Key。

```bash
PY=/Users/xiaolv/.workbuddy/binaries/python/envs/default/bin/python
SK=/Users/xiaolv/.workbuddy/plugins/marketplaces/my-experts/plugins/trading-desk/skills/trading-desk/scripts/akshare_data.py

$PY $SK kline 600519 --days 250        # 日线 OHLCV（前复权），M1 用
$PY $SK indicators 600519              # 内置 11 项指标（默认拉 450 自然日，保证 ma200 有值）
$PY $SK snapshot 600519                # 实时快照（现价/PE/PB/市值），价格唯一事实来源
$PY $SK fundamentals 600519            # 财务摘要（ROE/毛利率/增速…），M2 用
$PY $SK news 600519 --limit 20         # 个股新闻（东财），M3/M4 用
$PY $SK benchmark --days 10            # 沪深300 收盘价，M10 算 alpha 用
$PY $SK spread                         # 沪深300股债利差，M11 策略卡1专用（含区间判定）
```

输出统一为 JSON 到 stdout；失败输出 `{"error": "..."}`，**必须如实处理，禁止编造**。
厂商链（逆向自 CN 分支）：K 线与基准指数为「东财 → 新浪」自动切换（成功返回带 `vendor` 字段）；其余接口内置重试一次。

## 与原版数据面的映射

| 原版工具（美股 vendor） | 本地替代 | 说明 |
|---|---|---|
| get_stock_data (yfinance) | `kline` | 东财日线，qfq 前复权 |
| get_indicators (自算) | `indicators` | 相同 11 项指标，pandas 纯函数实现 |
| get_verified_market_snapshot | `snapshot` | 东财实时盘口，作为精确价格唯一事实来源 |
| get_fundamentals / 三表 (SEC EDGAR) | `fundamentals` | 东财财务摘要（A股口径） |
| get_news / get_global_news | `news` | 东财个股新闻；宏观部分用 M3 的框架分析 |
| get_prediction_markets / FRED | 无直接替代 | 缺失时声明缺失，置信度降级 |
| Reddit / StockTwits 情绪 | `news` 标题情绪 + 资金流（如可得） | A股语境下用东财新闻与龙虎榜思路替代 |
| —（原版无对应） | `spread` | 主人策略卡1专用：股债利差 = 1/PE_TTM − 10年国债收益率；PE 厂商链「乐咕乐股 → 中证指数」，输出 `spread_pct` 与 `zone`（buy/hold/sell，判定阈值来自策略卡：>6 买入带 / <4 卖出带 / 其余持有带） |

## 注意

- 接口已内置「重试一次 + vendor 链回退」；仍失败即声明数据缺失并降级置信度
- 交易日历：`kline` 返回的最后一行即「最新交易日」，分析日期以它为准，不用自然日
- 指标冷启动：`indicators` 默认拉 450 自然日，足以算出 ma200
