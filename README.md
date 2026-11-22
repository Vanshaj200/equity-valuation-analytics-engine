# Equity Valuation & Analytics Engine: Paytm vs fintech peers

Values Paytm (One 97 Communications) against Angel One, CAMS and PB Fintech from
Screener.in exports, and serves an interactive Streamlit dashboard.

## Setup

```powershell
pip install -r requirements.txt
python -m src.refresh      # run the pipeline, print DCF + comps, write data/processed/
streamlit run app.py       # dashboard
```

## Data

Four Screener.in Excel exports live in `data/raw/` (`One_97`, `Angel_One`,
`Cams_Services`, `PB_Fintech`). The visible P&L / Balance Sheet / Cash Flow
tabs are formula views, so `ingest.py` reads the hidden **Data Sheet** tab.
Figures are consolidated, Rs Cr, FY2017-FY2026, plus a quarterly block.

To update: replace a file in `data/raw/` with a newer export (same filename)
and press **Refresh data** in the sidebar. It is a re-ingest of a downloaded
export, not live scraping.

## Pipeline (`src/`)

| Module | Job |
|---|---|
| `ingest.py` | Parse each Data Sheet into tidy annual and quarterly tables |
| `clean.py` | Fill blanks, rescale share counts across face-value splits, run due-diligence checks |
| `analytics.py` | Growth, 3y/5y CAGR, net margin, ROE, EPS, P/E, P/B |
| `valuation.py` | 5-year DCF and WACC x terminal-growth grid |
| `comps.py` | Peer table and peer median |
| `refresh.py` | Orchestrates everything; `python -m src.refresh` prints results |

## Due-diligence checks

Logged per company (PASS / WARN / FAIL) and shown in the dashboard's *Data checks* tab:
missing core fields, imputations, face-value splits, share-count jumps without a split,
P&L to PBT reconciliation, PBT - tax = net profit, balance-sheet balance, quarters
summing to annual, market cap vs price x shares, and a standalone-vs-consolidated
revenue test. **PB Fintech fails the last one** (other income exceeds sales, market cap
is ~230x sales, latest quarter jumps ~7x): its annual revenue is on a holding-company
basis, so it is shown but excluded from the peer median.

## DCF

Assumptions live in `config.yaml` (defaults: growth 16/15/14/12/10%, FCF margin
4/7/10/13/15%, WACC 13.5%, terminal growth 5%). Net cash = cash & bank - borrowings
(set `include_investments: true` to add balance-sheet investments). Default output is
about Rs 272/share against a Rs 1,675 market price. Most of that value is terminal value
because Paytm's historical free cash flow is near zero. The dashboard sliders update the
valuation live, and **Save to config.yaml** writes them back.
