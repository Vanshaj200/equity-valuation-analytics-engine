"""Streamlit dashboard: Paytm turnaround, peer comps, DCF, data checks.

Run:  streamlit run app.py
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import comps as comps_mod
from src import refresh, valuation

st.set_page_config(page_title="Equity Valuation & Analytics Engine", layout="wide")

# One fixed colour per company (never re-assigned when a filter changes)
COLORS = {"Paytm": "#2a78d6", "Angel One": "#eb6834", "CAMS": "#1baf7a", "PB Fintech": "#e87ba4"}
POS, NEG, MUTED = "#2a78d6", "#e34948", "#9a9a95"


@st.cache_data(show_spinner="Running pipeline...")
def load(signature, cfg_mtime):
    """Cached pipeline run; the cache key changes when any export or config changes."""
    return refresh.run_pipeline()


def style(fig, height=380, **kw):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", y=1.12, x=0), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", **kw)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.2)", zeroline=True,
                     zerolinecolor="rgba(128,128,128,0.5)")
    return fig


def pct(v):
    return "n/a" if pd.isna(v) else f"{v:.1%}"


# ---- sidebar: refresh -----------------------------------------------------
with st.sidebar:
    st.header("Data")
    st.caption("Drop a newer Screener export into `data/raw/` (same filename), then refresh.")
    if st.button("Refresh data", type="primary", width='stretch'):
        st.cache_data.clear()
        st.session_state.pop("dcf_init", None)
        st.rerun()
    st.divider()
    st.caption("Files in data/raw/")
    for name, mtime in refresh.raw_signature():
        st.caption(f"{name} - {pd.Timestamp(mtime, unit='s'):%d %b %Y %H:%M}")

R = load(refresh.raw_signature(), refresh.CONFIG_PATH.stat().st_mtime)
cfg, target = R["config"], R["config"]["target"]
st.title("Equity Valuation & Analytics Engine")
st.caption(f"{target} vs fintech peers. Consolidated, Rs Cr, FY{R['annual'][target].index[0]}"
           f"-FY{R['annual'][target].index[-1]}. Source: Screener.in exports.")

tab1, tab2, tab3, tab4 = st.tabs([f"{target} turnaround", "Peer benchmarking", "DCF valuation",
                                  "Data checks"])

# ---- tab 1: turnaround ----------------------------------------------------
with tab1:
    ann, qtr = R["annual"][target], R["quarterly"][target]
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Bar(x=ann.index, y=ann["sales"], marker_color=POS, name="Revenue",
                               hovertemplate="FY%{x}: Rs %{y:,.0f} Cr<extra></extra>"))
        fig.update_xaxes(type="category")
        st.plotly_chart(style(fig, title="Revenue by fiscal year (Rs Cr)", showlegend=False),
                        width='stretch')
    with c2:
        fig = go.Figure(go.Bar(x=ann.index, y=ann["net_profit"], name="Net profit",
                               marker_color=[POS if v >= 0 else NEG for v in ann["net_profit"]],
                               hovertemplate="FY%{x}: Rs %{y:,.0f} Cr<extra></extra>"))
        fig.update_xaxes(type="category")
        st.plotly_chart(style(fig, title="Net profit by fiscal year (Rs Cr)", showlegend=False),
                        width='stretch')
    labels = [f"{t:%b-%y}" for t in qtr.index]
    fig = go.Figure(go.Bar(x=labels, y=qtr["net_profit"],
                           marker_color=[POS if v >= 0 else NEG for v in qtr["net_profit"]],
                           hovertemplate="%{x}: Rs %{y:,.0f} Cr<extra></extra>"))
    st.plotly_chart(style(fig, title="Quarterly net profit (Rs Cr)  -  blue profit, red loss",
                          showlegend=False, height=340), width='stretch')
    y = R["yearly"][target]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(f"FY{y.index[-1]} revenue", f"Rs {y['sales'].iloc[-1]:,.0f} Cr", pct(y["rev_growth"].iloc[-1]) + " YoY")
    k2.metric(f"FY{y.index[-1]} net profit", f"Rs {y['net_profit'].iloc[-1]:,.0f} Cr")
    k3.metric("Worst year loss", f"Rs {y['net_profit'].min():,.0f} Cr", f"FY{y['net_profit'].idxmin()}",
              delta_color="off")
    k4.metric("Profitable quarters (last 8)", f"{(qtr['net_profit'].iloc[-8:] > 0).sum()} of 8")

# ---- tab 2: peers -----------------------------------------------------------
with tab2:
    C = R["comps"]
    flagged = [c for c, m in R["meta"].items() if m["standalone_suspect"]]
    for c in flagged:
        st.warning(f"**{c}**: revenue looks standalone/holding-company ("
                   + "; ".join(R["meta"][c]["flags"]) + "). Shown but excluded from the peer median.")
    show = comps_mod.format_comps(C).rename(columns={
        "company": "Company", "price": "Price (Rs)", "market_cap": "Mkt cap (Rs Cr)",
        "revenue": "Revenue (Rs Cr)", "rev_growth": "Rev growth", "rev_cagr_3y": "Rev CAGR 3y",
        "rev_cagr_5y": "Rev CAGR 5y", "net_margin": "Net margin", "roe": "ROE", "pe": "P/E",
        "pb": "P/B", "comparable": "Comparable"})
    st.dataframe(show, hide_index=True, width='stretch')
    st.caption("P/E uses latest-FY net profit; values above 200x are not meaningful and are left out of the median.")
    companies = [c for c in C["company"] if c in COLORS or c in R["annual"]]
    metrics = [("rev_cagr_3y", "Revenue CAGR 3y", True), ("net_margin", "Net margin", True),
               ("roe", "ROE", True), ("pe", "P/E (x)", False)]
    cols = st.columns(2)
    for i, (m, title, is_pct) in enumerate(metrics):
        d = C[C["company"].isin(R["annual"])]
        vals = d[m]
        fig = go.Figure(go.Bar(
            x=d["company"], y=vals, marker_color=[COLORS.get(c, MUTED) for c in d["company"]],
            text=[("n/a" if pd.isna(v) else f"{v:.1%}" if is_pct else f"{v:,.0f}x") for v in vals],
            textposition="outside", hovertemplate="%{x}: %{text}<extra></extra>"))
        if m == "pe":
            fig.update_yaxes(range=[0, 120])
            fig.add_annotation(text="Axis capped at 120x; Paytm and PB Fintech are far above (not meaningful)",
                               xref="paper", yref="paper", x=0, y=1.0, showarrow=False,
                               font=dict(size=11), xanchor="left", yanchor="bottom")
        cols[i % 2].plotly_chart(style(fig, title=title, showlegend=False, height=330),
                                 width='stretch')

# ---- tab 3: DCF --------------------------------------------------------------
with tab3:
    base = cfg["dcf"]
    if "dcf_init" not in st.session_state:
        st.session_state["dcf_init"] = True
        st.session_state["wacc"] = base["wacc"] * 100
        st.session_state["tg"] = base["terminal_growth"] * 100
        st.session_state["inv"] = base["include_investments"]
        for i in range(5):
            st.session_state[f"g{i}"] = base["revenue_growth"][i] * 100
            st.session_state[f"m{i}"] = base["fcf_margin"][i] * 100
    left, right = st.columns([1, 2])
    with left:
        st.subheader("Assumptions")
        wacc = st.slider("WACC (%)", 8.0, 20.0, step=0.1, key="wacc")
        tg = st.slider("Terminal growth (%)", 2.0, 8.0, step=0.1, key="tg")
        inv = st.checkbox("Add balance-sheet investments to net cash", key="inv")
        with st.expander("Yearly revenue growth and FCF margin", expanded=True):
            g = [st.slider(f"Year {i + 1} revenue growth (%)", 0.0, 40.0, step=0.5, key=f"g{i}") for i in range(5)]
            mg = [st.slider(f"Year {i + 1} FCF margin (%)", 0.0, 30.0, step=0.5, key=f"m{i}") for i in range(5)]
        b1, b2 = st.columns(2)
        if b1.button("Save to config.yaml"):
            cfg["dcf"] = {"revenue_growth": [round(x / 100, 4) for x in g],
                          "fcf_margin": [round(x / 100, 4) for x in mg],
                          "wacc": round(wacc / 100, 4), "terminal_growth": round(tg / 100, 4),
                          "include_investments": bool(inv)}
            refresh.save_config(cfg)
            st.cache_data.clear()
            st.success("Saved.")
        if b2.button("Reset to config"):
            st.session_state.pop("dcf_init", None)
            st.rerun()

    if wacc <= tg:
        right.error("WACC must be above terminal growth.")
    else:
        a = {"revenue_growth": [x / 100 for x in g], "fcf_margin": [x / 100 for x in mg],
             "wacc": wacc / 100, "terminal_growth": tg / 100, "include_investments": inv}
        sens = {"wacc": [w / 100 for w in (wacc - 1.5, wacc, wacc + 1.5)],
                "terminal_growth": [t / 100 for t in (tg - 1, tg, tg + 1)]}
        d = valuation.value_company(R["annual"][target], R["meta"][target], a, sens)
        with right:
            k = st.columns(4)
            k[0].metric("Enterprise value", f"Rs {d['enterprise_value']:,.0f} Cr")
            k[1].metric("Equity value", f"Rs {d['equity_value']:,.0f} Cr")
            k[2].metric("DCF value / share", f"Rs {d['value_per_share']:,.0f}")
            k[3].metric("Market price", f"Rs {d['market_price']:,.0f}", f"DCF {d['upside']:+.0%} vs market",
                        delta_color="off")
            fig = go.Figure(go.Bar(x=["DCF value", "Market price"],
                                   y=[d["value_per_share"], d["market_price"]],
                                   marker_color=[POS, MUTED],
                                   text=[f"Rs {d['value_per_share']:,.0f}", f"Rs {d['market_price']:,.0f}"],
                                   textposition="outside", hovertemplate="%{x}: %{text}<extra></extra>"))
            st.plotly_chart(style(fig, title="Value per share vs market (Rs)", showlegend=False, height=300),
                            width='stretch')
            grid = d["sensitivity"]
            fig = go.Figure(go.Heatmap(
                z=grid.values, x=list(grid.columns), y=list(grid.index), colorscale="Blues",
                text=np.round(grid.values, 0), texttemplate="Rs %{text:.0f}", showscale=False,
                hovertemplate="WACC %{y}, g %{x}: Rs %{z:.0f}<extra></extra>"))
            fig.update_xaxes(title="Terminal growth", side="bottom")
            fig.update_yaxes(title="WACC", autorange="reversed")
            st.plotly_chart(style(fig, title="Sensitivity: value per share", height=300),
                            width='stretch')
            with st.expander("Projection and bridge"):
                p = d["projection"].round(1)
                p.insert(0, "FY", [R["annual"][target].index[-1] + t for t in p["year"]])
                st.dataframe(p.drop(columns="year"), hide_index=True, width='stretch')
                st.write(f"PV of FCF Rs {d['pv_fcf']:,.0f} Cr + PV of terminal value Rs {d['pv_terminal']:,.0f} Cr "
                         f"= EV Rs {d['enterprise_value']:,.0f} Cr. Net cash Rs {d['net_cash']:,.0f} Cr. "
                         f"Shares {d['shares_cr']:.2f} Cr.")
    st.caption("Illustrative model. FCF margins are assumptions, not guidance; Paytm's free cash flow "
               "history is near zero, so most of the value sits in the terminal value.")

# ---- tab 4: data checks -------------------------------------------------------
with tab4:
    log = R["checks"]
    counts = log["status"].value_counts()
    st.write(f"**{len(log)} checks:** " + ", ".join(f"{counts.get(s, 0)} {s}" for s in ["PASS", "WARN", "FAIL"]))
    sel = st.multiselect("Status", ["FAIL", "WARN", "PASS"], default=["FAIL", "WARN"])
    st.dataframe(log[log["status"].isin(sel)], hide_index=True, width='stretch')
