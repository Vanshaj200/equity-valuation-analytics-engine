"""Forward DCF with a WACC x terminal-growth sensitivity grid."""
import numpy as np
import pandas as pd


def dcf(base_revenue, net_cash, shares_cr, growth, fcf_margin, wacc, terminal_growth):
    """Five-year DCF. Cash flows are discounted at year-end; Rs Cr throughout.

    Returns a dict with the projection table, EV, equity value and value/share (Rs).
    """
    if wacc <= terminal_growth:
        raise ValueError("WACC must exceed terminal growth")
    n = len(growth)
    revenue = base_revenue * np.cumprod(1 + np.array(growth))
    fcf = revenue * np.array(fcf_margin)
    t = np.arange(1, n + 1)
    discount = (1 + wacc) ** t
    pv_fcf = fcf / discount
    terminal_value = fcf[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal = terminal_value / discount[-1]
    ev = pv_fcf.sum() + pv_terminal
    equity = ev + net_cash
    return {
        "projection": pd.DataFrame({"year": t, "revenue": revenue, "fcf": fcf,
                                    "discount_factor": 1 / discount, "pv_fcf": pv_fcf}),
        "pv_fcf": pv_fcf.sum(),
        "terminal_value": terminal_value,
        "pv_terminal": pv_terminal,
        "enterprise_value": ev,
        "net_cash": net_cash,
        "equity_value": equity,
        "value_per_share": equity / shares_cr,
    }


def net_cash_of(ann, include_investments=False):
    """Net cash from the latest balance sheet: cash - borrowings (+ investments)."""
    last = ann.iloc[-1]
    return last["cash"] - last["borrowings"] + (last["investments"] if include_investments else 0)


def sensitivity(base_revenue, net_cash, shares_cr, growth, fcf_margin, waccs, tgs):
    """Value/share grid: rows = WACC, columns = terminal growth."""
    grid = pd.DataFrame(index=[f"{w:.1%}" for w in waccs], columns=[f"{g:.1%}" for g in tgs], dtype=float)
    for w in waccs:
        for g in tgs:
            grid.loc[f"{w:.1%}", f"{g:.1%}"] = dcf(base_revenue, net_cash, shares_cr,
                                                    growth, fcf_margin, w, g)["value_per_share"]
    grid.index.name, grid.columns.name = "WACC", "Terminal growth"
    return grid


def value_company(ann, meta, assumptions, sens=None):
    """Run the DCF (and optional grid) for one cleaned company.

    assumptions: the `dcf` block of config.yaml. sens: the `sensitivity` block.
    """
    base = ann["sales"].iloc[-1]
    nc = net_cash_of(ann, assumptions.get("include_investments", False))
    shares = meta["shares_cr"]
    out = dcf(base, nc, shares, assumptions["revenue_growth"], assumptions["fcf_margin"],
              assumptions["wacc"], assumptions["terminal_growth"])
    out["base_revenue"], out["shares_cr"] = base, shares
    out["market_price"] = meta.get("Current Price")
    out["upside"] = out["value_per_share"] / out["market_price"] - 1 if out["market_price"] else np.nan
    if sens:
        out["sensitivity"] = sensitivity(base, nc, shares, assumptions["revenue_growth"],
                                         assumptions["fcf_margin"], sens["wacc"],
                                         sens["terminal_growth"])
    return out
