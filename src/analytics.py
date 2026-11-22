"""Exploratory metrics: growth, margins, ROE, CAGR and valuation multiples."""
import numpy as np
import pandas as pd


def cagr(series, years):
    """CAGR of the last `years` periods; NaN if the start value is not positive."""
    s = series.dropna()
    if len(s) <= years:
        return np.nan
    start, end = s.iloc[-1 - years], s.iloc[-1]
    if start <= 0 or end <= 0:
        return np.nan
    return (end / start) ** (1 / years) - 1


def yearly_metrics(ann):
    """Per-year metrics for one company (index = fiscal year)."""
    m = pd.DataFrame(index=ann.index)
    m["sales"] = ann["sales"]
    m["net_profit"] = ann["net_profit"]
    m["rev_growth"] = ann["sales"].pct_change()
    m["net_margin"] = ann["net_profit"] / ann["sales"]
    equity = ann["reserves"] + ann["equity_capital"]
    m["equity"] = equity
    m["roe"] = ann["net_profit"] / equity
    m["eps"] = ann["net_profit"] / ann["shares_adj_cr"]
    m["bvps"] = equity / ann["shares_adj_cr"]
    return m


def summary(name, ann, qtr, meta):
    """Latest-year snapshot and valuation multiples for one company."""
    m = yearly_metrics(ann)
    last = m.iloc[-1]
    price, mcap = meta.get("Current Price"), meta.get("Market Capitalization")
    ttm_profit = qtr["net_profit"].iloc[-4:].sum() if len(qtr) >= 4 else np.nan
    net_debt = ann["borrowings"].iloc[-1] - ann["cash"].iloc[-1]
    return {
        "company": name,
        "latest_fy": int(m.index[-1]),
        "price": price,
        "market_cap": mcap,
        "revenue": last["sales"],
        "net_profit": last["net_profit"],
        "rev_growth": last["rev_growth"],
        "rev_cagr_3y": cagr(ann["sales"], 3),
        "rev_cagr_5y": cagr(ann["sales"], 5),
        "net_margin": last["net_margin"],
        "roe": last["roe"],
        "pe": mcap / last["net_profit"] if last["net_profit"] > 0 else np.nan,
        "pe_ttm": mcap / ttm_profit if ttm_profit and ttm_profit > 0 else np.nan,
        "pb": mcap / last["equity"] if last["equity"] > 0 else np.nan,
        "ps": mcap / last["sales"] if last["sales"] > 0 else np.nan,
        "net_debt": net_debt,
    }


def analyse_all(annual, quarterly, meta):
    """Returns ({company: yearly metrics}, snapshot DataFrame)."""
    yearly = {n: yearly_metrics(a) for n, a in annual.items()}
    snap = pd.DataFrame([summary(n, annual[n], quarterly[n], meta[n]) for n in annual])
    return yearly, snap
