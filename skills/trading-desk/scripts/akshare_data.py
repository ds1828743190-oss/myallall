#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股本地数据层 — trading-desk 专家包（逆向自 TradingAgents dataflows，akshare 实现）

子命令:
  kline <code> [--days N]          日线 OHLCV（前复权）
  indicators <code> [--days N]     11 项技术指标（与原版 market_analyst 指标集一一对应）
  snapshot <code>                  实时快照（精确价格的唯一事实来源）
  fundamentals <code>              财务摘要（最近 8 个报告期）
  news <code> [--limit N]          个股新闻（东财）
  benchmark [--days N]             沪深300 日线收盘（M10 alpha 用）
  spread                           沪深300股债利差（策略卡1专用：1/PE_TTM − 10年国债收益率）

输出: JSON → stdout；失败输出 {"error": ...} 且退出码 1。
依赖: akshare, pandas（托管 venv 已装）。全部免费数据源，无需 API Key。
"""
import argparse
import contextlib
import io
import json
import sys
import time
from datetime import datetime, timedelta

import pandas as pd

# pandas 3 默认 pyarrow 字符串后端的 RE2 引擎拒绝 akshare 内部含 \u 转义的正则，
# 进程内切回 python 存储规避（仅影响本脚本，不动全局环境）。
pd.set_option("mode.string_storage", "python")

import akshare as ak

EXIT_OK, EXIT_ERR = 0, 1


def _err(msg: str) -> dict:
    return {"error": msg}


def _retry(fn, times: int = 2, delay: float = 1.5):
    """东财接口经代理偶发抖动，统一重试一次。"""
    last: Exception = None  # type: ignore[assignment]
    for i in range(times):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last = exc
            if i + 1 < times:
                time.sleep(delay)
    raise last


def _ymd(days_back: int) -> tuple[str, str]:
    end = datetime.now()
    start = end - timedelta(days=days_back)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def fetch_kline(code: str, days: int = 300) -> pd.DataFrame:
    """日线（前复权）。vendor 链：东财 → 新浪（同源故障时自动切换）。"""
    start, end = _ymd(days)
    try:
        df = _retry(lambda: ak.stock_zh_a_hist(symbol=code, period="daily",
                                               start_date=start, end_date=end, adjust="qfq"))
        source = "eastmoney"
    except Exception:  # noqa: BLE001 — 厂商链：主源失败切备源
        sym_prefix = "sh" if code.startswith(("6", "9", "5")) else ("bj" if code.startswith(("4", "8")) else "sz")
        df = _retry(lambda: ak.stock_zh_a_daily(symbol=f"{sym_prefix}{code}",
                                                start_date=start, end_date=end, adjust="qfq"))
        source = "sina"
    if df is None or df.empty:
        raise ValueError(f"kline 两个数据源均返回空数据: {code}")
    df = df.rename(columns={
        "日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
        "最低": "low", "成交量": "volume", "成交额": "amount",
        "涨跌幅": "pct_chg", "换手率": "turnover",
    })
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values("date").reset_index(drop=True)
    df.attrs["source"] = source
    return df


# ---------------------------------------------------------------------------
# 指标实现：纯 pandas 确定性函数（D8：显式公式，无黑箱）
# 与原版 market_analyst 指标集对应：ma50/ma200/ema10, macd/macds/macdh,
# rsi14, boll_mid/boll_ub/boll_lb, atr14, vwma20
# ---------------------------------------------------------------------------

def sma(s: pd.Series, n: int) -> pd.Series:
    """简单移动平均"""
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    """指数移动平均（span 口径，与 TA-Lib EMA 一致）"""
    return s.ewm(span=n, adjust=False).mean()


def macd(s: pd.Series, fast: int = 12, slow: int = 26, sig: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD: 快慢 EMA 之差；signal 为其 EMA9；hist 为差值"""
    line = ema(s, fast) - ema(s, slow)
    signal = line.ewm(span=sig, adjust=False).mean()
    hist = line - signal
    return line, signal, hist


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    """Wilder RSI：涨跌幅用 alpha=1/n 的 Wilder 平滑"""
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / n, adjust=False).mean()
    rs = avg_gain / avg_loss  # avg_loss=0 → inf → RSI=100；avg_gain=0 → RSI=0
    out = 100 - 100 / (1 + rs)
    out = out.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)  # 双零（全程平盘）→ 50
    return out.where(avg_loss != 0, 100.0)


def bollinger(s: pd.Series, n: int = 20, k: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """布林带：中轨 SMA20，上下轨 ±k 倍总体标准差（ddof=0）"""
    mid = sma(s, n)
    std = s.rolling(n, min_periods=n).std(ddof=0)
    return mid, mid + k * std, mid - k * std


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Wilder ATR：TR = max(高-低, |高-昨收|, |低-昨收|)，alpha=1/n 平滑"""
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False).mean()


def vwma(df: pd.DataFrame, n: int = 20) -> pd.Series:
    """成交量加权移动平均"""
    pv = (df["close"] * df["volume"]).rolling(n, min_periods=n).sum()
    v = df["volume"].rolling(n, min_periods=n).sum()
    return pv / v.replace(0, pd.NA)


def compute_indicators(df: pd.DataFrame) -> dict:
    """全部 11 项指标，返回最近 60 个交易日的逐日序列 + 最新值。"""
    c = df["close"]
    m, ms, mh = macd(c)
    bm, bu, bl = bollinger(c)
    out = pd.DataFrame({
        "date": df["date"],
        "close": c,
        "ma50": sma(c, 50), "ma200": sma(c, 200), "ema10": ema(c, 10),
        "macd": m, "macd_signal": ms, "macd_hist": mh,
        "rsi14": rsi(c, 14),
        "boll_mid": bm, "boll_upper": bu, "boll_lower": bl,
        "atr14": atr(df, 14), "vwma20": vwma(df, 20),
    }).round(3)
    tail = out.tail(60).where(pd.notnull(out.tail(60)), None).to_dict("records")
    latest = out.iloc[-1].where(pd.notnull(out.iloc[-1]), None).to_dict()
    latest["date"] = df["date"].iloc[-1]
    return {"latest": latest, "series_60d": tail}


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def cmd_kline(code: str, days: int) -> dict:
    df = fetch_kline(code, days)
    keep = ["date", "open", "close", "high", "low", "volume", "amount", "pct_chg", "turnover"]
    cols = [c for c in keep if c in df.columns]
    return {"code": code, "trade_date": df["date"].iloc[-1], "rows": len(df),
            "kline": df[cols].tail(days).to_dict("records")}


def cmd_indicators(code: str, days: int) -> dict:
    # ma200 至少需要 200 根 K 线：450 自然日 ≈ 300 交易日，留足余量
    df = fetch_kline(code, max(days, 450))
    ind = compute_indicators(df)
    return {"code": code, "trade_date": df["date"].iloc[-1], "vendor": df.attrs.get("source"), **ind}


def cmd_snapshot(code: str) -> dict:
    """东财盘口快照；字段名为东财原始字段，全量透传。"""
    df = _retry(lambda: ak.stock_bid_ask_em(symbol=code))
    if df is None or df.empty:
        raise ValueError(f"stock_bid_ask_em 返回空数据: {code}")
    pairs = {str(r["item"]): r["value"] for _, r in df.iterrows()}
    return {"code": code, "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "snapshot": pairs}


def cmd_fundamentals(code: str) -> dict:
    """财务指标摘要：按关键词模糊匹配列名（akshare 版本间列名有差异）。"""
    df = _retry(lambda: ak.stock_financial_analysis_indicator(symbol=code, start_year="2020"))
    if df is None or df.empty:
        raise ValueError(f"stock_financial_analysis_indicator 返回空数据: {code}")
    date_col = next((c for c in df.columns if "日期" in c), df.columns[0])
    keys = {"roe": "净资产收益率", "gross_margin": "毛利率", "net_margin": "净利率",
            "debt_ratio": "资产负债率", "revenue_growth": "营业收入增长", "net_profit_growth": "净利润增长",
            "eps": "每股收益", "ocf_per_share": "每股经营"}
    metrics_by_period = []
    for _, row in df.tail(8).iterrows():
        entry = {"period": str(row[date_col])}
        for key, kw in keys.items():
            col = next((c for c in df.columns if kw in c), None)
            if col is not None and pd.notnull(row[col]):
                entry[key] = row[col]
        metrics_by_period.append(entry)
    return {"code": code, "fundamentals": metrics_by_period}


def cmd_news(code: str, limit: int) -> dict:
    df = _retry(lambda: ak.stock_news_em(symbol=code))
    if df is None or df.empty:
        return {"code": code, "news": []}
    time_col = next((c for c in df.columns if "时间" in c), None)
    title_col = next((c for c in df.columns if "标题" in c), df.columns[0])
    content_col = next((c for c in df.columns if "内容" in c), None)
    src_col = next((c for c in df.columns if "来源" in c), None)
    if time_col is not None:
        df = df.sort_values(time_col, ascending=False)
    items = []
    for _, row in df.head(limit).iterrows():
        items.append({
            "time": str(row[time_col]) if time_col else None,
            "title": str(row[title_col]),
            "content": (str(row[content_col])[:200] if content_col and pd.notnull(row[content_col]) else None),
            "source": str(row[src_col]) if src_col and pd.notnull(row[src_col]) else None,
        })
    return {"code": code, "count": len(items), "news": items}


def cmd_benchmark(days: int) -> dict:
    start, end = _ymd(days)
    try:
        df = _retry(lambda: ak.index_zh_a_hist(symbol="000300", period="daily",
                                               start_date=start, end_date=end))
        df = df.rename(columns={"日期": "date", "收盘": "close"})
        name = "000300 沪深300（东财）"
    except Exception:  # noqa: BLE001 — vendor 链：东财失败切新浪指数
        df = _retry(lambda: ak.stock_zh_index_daily(symbol="sh000300"))
        df = df.rename(columns={"date": "date", "close": "close"})
        name = "000300 沪深300（新浪）"
    if df is None or df.empty:
        raise ValueError("benchmark 两个数据源均返回空数据: 000300")
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values("date")
    cut = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    df = df[df["date"] >= cut]
    return {"index": name, "trade_date": df["date"].iloc[-1],
            "closes": df[["date", "close"]].tail(days).to_dict("records")}


def cmd_spread() -> dict:
    """沪深300股债利差 = 盈利收益率(1/PE_TTM) − 10年期国债收益率（主人策略卡1口径）。
    PE 厂商链：乐咕乐股 → 中证指数官网；国债收益率取近 30 日最新值。"""
    pe_val, pe_date, pe_vendor = None, None, None
    try:
        df = _retry(lambda: ak.stock_index_pe_lg(symbol="沪深300"))
        if df is not None and not df.empty:
            date_col = next((c for c in df.columns if "日期" in c), df.columns[0])
            pe_col = next((c for c in df.columns
                           if "TTM" in str(c).upper() and "中位" not in str(c)), None)
            if pe_col is not None and pd.notnull(df.iloc[-1][pe_col]):
                pe_val = float(df.iloc[-1][pe_col])
                pe_date, pe_vendor = str(df.iloc[-1][date_col]), "legulegu"
    except Exception:  # noqa: BLE001 — vendor 链：乐咕失败切中证指数
        pass
    if pe_val is None:
        df = _retry(lambda: ak.stock_zh_index_value_csindex(symbol="000300"))
        if df is None or df.empty:
            raise ValueError("沪深300估值两个数据源均返回空数据")
        date_col = next((c for c in df.columns if "日期" in c), df.columns[0])
        pe_col = next((c for c in df.columns if "市盈率2" in c),
                      next((c for c in df.columns if "市盈率1" in c), None))
        if pe_col is None:
            raise ValueError(f"中证指数估值未找到市盈率列: {list(df.columns)}")
        pe_val = float(df.iloc[-1][pe_col])
        pe_date, pe_vendor = str(df.iloc[-1][date_col]), "csindex"
    if pe_val <= 0:
        raise ValueError(f"沪深300 PE 非法: {pe_val}")

    start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    bond_df = _retry(lambda: ak.bond_zh_us_rate(start_date=start))
    if bond_df is None or bond_df.empty:
        raise ValueError("bond_zh_us_rate 返回空数据")
    bond_col = next((c for c in bond_df.columns if "中国国债收益率10年" in c), None)
    if bond_col is None:
        raise ValueError(f"bond_zh_us_rate 未找到10年期国债列: {list(bond_df.columns)}")
    bond_rows = bond_df.dropna(subset=[bond_col])
    if bond_rows.empty:
        raise ValueError("10年国债收益率近 30 日无数据")
    bond_date = str(bond_rows.iloc[-1].iloc[0])
    bond_yield = float(bond_rows.iloc[-1][bond_col])

    earnings_yield = 100.0 / pe_val
    spread = round(earnings_yield - bond_yield, 3)
    zone = "buy" if spread > 6 else ("sell" if spread < 4 else "hold")
    return {
        "indicator": "沪深300股债利差（主人策略卡1口径）",
        "spread_pct": spread,
        "earnings_yield_pct": round(earnings_yield, 3),
        "pe_ttm": pe_val,
        "cn10y_yield_pct": bond_yield,
        "pe_date": pe_date, "pe_vendor": pe_vendor,
        "bond_date": bond_date,
        "zone": zone,
        "zone_rules": {
            "buy": "利差>6% → 定投红利ETF",
            "hold": "4%-6% → 策略卡未定义动作，持有观察",
            "sell": "利差<4% → 分批止盈换国债ETF",
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(description="A股本地数据层 (trading-desk)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("kline", "indicators"):
        sp = sub.add_parser(name)
        sp.add_argument("code")
        sp.add_argument("--days", type=int, default=300)
    sub.add_parser("snapshot").add_argument("code")
    sub.add_parser("fundamentals").add_argument("code")
    sp = sub.add_parser("news")
    sp.add_argument("code")
    sp.add_argument("--limit", type=int, default=20)
    sp = sub.add_parser("benchmark")
    sp.add_argument("--days", type=int, default=30)
    sub.add_parser("spread")
    args = p.parse_args()

    try:
        # akshare 内部 tqdm/进度输出会污染 stdout，收集进缓冲区丢弃，保证 stdout 只有一行 JSON
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            if args.cmd == "kline":
                result = cmd_kline(args.code, args.days)
            elif args.cmd == "indicators":
                result = cmd_indicators(args.code, args.days)
            elif args.cmd == "snapshot":
                result = cmd_snapshot(args.code)
            elif args.cmd == "fundamentals":
                result = cmd_fundamentals(args.code)
            elif args.cmd == "news":
                result = cmd_news(args.code, args.limit)
            else:
                result = cmd_benchmark(args.days) if args.cmd == "benchmark" else cmd_spread()
        print(json.dumps(result, ensure_ascii=False, default=str))
        return EXIT_OK
    except Exception as exc:  # noqa: BLE001 — CLI 边界，必须把任何失败转为结构化错误
        print(json.dumps(_err(f"{type(exc).__name__}: {exc}"), ensure_ascii=False))
        return EXIT_ERR


if __name__ == "__main__":
    sys.exit(main())
