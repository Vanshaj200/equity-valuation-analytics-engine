"""Read the hidden "Data Sheet" tab of a Screener.in Excel export.

The visible P&L / Balance Sheet / Cash Flow tabs are formula views; the real
numbers sit in "Data Sheet" as blocks (PROFIT & LOSS, Quarters, BALANCE SHEET,
CASH FLOW, PRICE, DERIVED), one row per label, dates across columns.
"""
from pathlib import Path

import openpyxl
import pandas as pd

# Section header (column A) -> internal section key
SECTIONS = {
    "META": "meta",
    "PROFIT & LOSS": "pl",
    "QUARTERS": "q",
    "BALANCE SHEET": "bs",
    "CASH FLOW:": "cf",
    "PRICE:": "price",
    "DERIVED:": "derived",
}

# Screener label -> tidy column name. Duplicated labels ("Total") are handled
# by position in _snake().
LABELS = {
    "sales": "sales",
    "raw material cost": "raw_material",
    "change in inventory": "chg_inventory",
    "power and fuel": "power_fuel",
    "other mfr. exp": "other_mfr",
    "employee cost": "employee_cost",
    "selling and admin": "selling_admin",
    "other expenses": "other_expenses",
    "other income": "other_income",
    "depreciation": "depreciation",
    "interest": "interest",
    "profit before tax": "pbt",
    "tax": "tax",
    "net profit": "net_profit",
    "dividend amount": "dividend",
    "expenses": "expenses",
    "operating profit": "operating_profit",
    "equity share capital": "equity_capital",
    "reserves": "reserves",
    "borrowings": "borrowings",
    "other liabilities": "other_liabilities",
    "net block": "net_block",
    "capital work in progress": "cwip",
    "investments": "investments",
    "other assets": "other_assets",
    "receivables": "receivables",
    "inventory": "inventory",
    "cash & bank": "cash",
    "no. of equity shares": "shares",
    "new bonus shares": "bonus_shares",
    "face value": "face_value",
    "cash from operating activity": "cfo",
    "cash from investing activity": "cfi",
    "cash from financing activity": "cff",
    "net cash flow": "net_cash_flow",
    "adjusted equity shares in cr": "screener_adj_shares_cr",
}


def _fiscal_year(ts):
    """Indian fiscal year label: year in which the FY ends (Mar-2026 -> 2026)."""
    return ts.year if ts.month <= 3 else ts.year + 1


def read_data_sheet(path):
    """Parse one export. Returns dict with meta, annual, quarterly DataFrames."""
    wb = openpyxl.load_workbook(path, data_only=True)
    if "Data Sheet" not in wb.sheetnames:
        raise ValueError(f"{Path(path).name}: no 'Data Sheet' tab found")
    ws = wb["Data Sheet"]

    meta, blocks, dates = {}, {k: {} for k in SECTIONS.values()}, {}
    section, seen = None, {}
    name = None
    for row in ws.iter_rows(values_only=True):
        label = row[0]
        if label is None:
            continue
        label = str(label).strip()
        key = label.upper()
        if key == "COMPANY NAME":
            name = row[1]
            continue
        if key in SECTIONS:
            section = SECTIONS[key]
            seen = {}
            if section == "price":  # the PRICE row itself carries the values
                blocks["price"]["price"] = list(row[1:])
            continue
        if section is None:
            continue
        values = list(row[1:])
        if section == "meta":
            if values and values[0] is not None:
                meta[label] = values[0]
            continue
        if key == "REPORT DATE":
            dates[section] = [v for v in values if v is not None]
            continue
        # duplicated labels inside a section (e.g. the two "Total" rows)
        n = seen.get(label, 0)
        seen[label] = n + 1
        blocks[section][label if n == 0 else f"{label}#{n + 1}"] = values

    meta["company_name"] = name
    annual = _frame(blocks, dates, ["pl", "bs", "cf", "derived"], quarterly=False)
    quarterly = _frame(blocks, dates, ["q"], quarterly=True)
    # year-end price lives in its own row on the annual date axis
    px = blocks["price"].get("price")
    if px is not None and "bs" in dates:
        s = pd.Series(px[: len(dates["bs"])], index=[_fiscal_year(d) for d in dates["bs"]])
        annual["year_end_price"] = pd.to_numeric(s, errors="coerce").reindex(annual.index)
    return {"meta": meta, "annual": annual, "quarterly": quarterly}


def _frame(blocks, dates, sections, quarterly):
    """Assemble the sections into one DataFrame indexed by FY (or quarter end)."""
    cols = {}
    for sec in sections:
        dkey = "bs" if sec == "derived" else sec
        d = dates.get(dkey, [])
        for label, vals in blocks[sec].items():
            col = _snake(label, sec)
            if col is None:
                continue
            ser = pd.Series(vals[: len(d)], index=d)
            cols[col] = pd.to_numeric(ser, errors="coerce")
    df = pd.DataFrame(cols)
    if df.empty:
        return df
    df.index = pd.to_datetime(df.index)
    df = df[~df.index.duplicated()]
    if not quarterly:
        df.index = [_fiscal_year(t) for t in df.index]
        df.index.name = "fy"
    else:
        df.index.name = "quarter_end"
    return df


def _snake(label, section):
    base, _, dup = label.partition("#")
    if base.lower() == "total":  # first = liabilities, second = assets
        return "total_liabilities" if not dup else "total_assets"
    if section == "pl" and base.lower() == "other income":
        return "other_income"
    return LABELS.get(base.lower())


def ingest_all(companies, raw_dir):
    """companies: {display name: filename}. Returns {name: parsed export}."""
    out = {}
    for name, fname in companies.items():
        path = Path(raw_dir) / fname
        if not path.exists():
            raise FileNotFoundError(f"Missing export for {name}: {path}")
        out[name] = read_data_sheet(path)
    return out
