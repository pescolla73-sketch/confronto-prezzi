import io, re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Confronto Prezzi Fornitore vs Logistica", layout="wide")
st.title("💶 Confronto Prezzi Fornitore vs Logistica")

# ---------- utils ----------
def decimalize(x):
    if pd.isna(x): return None
    s = str(x).strip().replace(" ", "").replace("’","").replace("'","")
    if s == "": return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None

def round_money(d: Decimal, decimals=2):
    if d is None: return None
    q = Decimal(10) ** (-decimals)
    return d.quantize(q, rounding=ROUND_HALF_UP)

def to_excel_bytes(df, sheet="dati"):
    bio = io.BytesIO()
    try:
        with pd.ExcelWriter(bio, engine="xlsxwriter") as xl:
            df.to_excel(xl, index=False, sheet_name=sheet)
    except ModuleNotFoundError:
        with pd.ExcelWriter(bio, engine="openpyxl") as xl:
            df.to_excel(xl, index=False, sheet_name=sheet)
    bio.seek(0); return bio

def to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8-sig")

# normalizza stringhe intestazioni per match fuzzy
def _norm(s: str) -> str:
    s = str(s or "").lower().strip()
    s = re.sub(r"[\s\-_]+", " ", s)
    s = s.replace("’","").replace("'","")
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return s

def find_col(df: pd.DataFrame, candidates: list[str], required=True, label=""):
    norm_map = {_norm(c): c for c in df.columns}
    for cand in candidates:
        k = _norm(cand)
        if k in norm_map:
            return norm_map[k]
        # cerca substring
        for nk, orig in norm_map.items():
            if k and k in nk:
                return orig
    if required:
        raise KeyError(f"Colonna '{label}' non trovata. Cercate: {candidates}. Trovate: {list(df.columns)}")
    return None

# ---------- supplier ----------
def normalize_supplier(uploaded):
    xls = pd.ExcelFile(uploaded)
    if "Orders" not in xls.sheet_names:
        raise RuntimeError(f"Foglio 'Orders' non trovato. Fogli disponibili: {xls.sheet_names}")
    df = pd.read_excel(xls, sheet_name="Orders", dtype=str)

    col_order   = find_col(df, ["Orders Id","Order Id","OrderID","Order ID"], label="Order Id")
    col_nlmp    = find_col(df, ["Net Local Market Price","Net Local Market Price Total"], label="Net Local Market Price")
    col_supp    = find_col(df, ["Supplier's Price","Suppliers Price","Supplier Price","Supplier's Price Total"], label="Supplier's Price")

    out = pd.DataFrame()
    out["order_id"] = df[col_order].astype(str).str.replace("^BLL", "", regex=True).str.strip()
    out["nlmp"] = df[col_nlmp].apply(decimalize).apply(round_money)
    out["supplier_price"] = df[col_supp].apply(decimalize).apply(round_money)
    out = out.dropna(subset=["order_id"])
    return out

# ---------- logistics ----------
def normalize_logistics(uploaded):
    xls = pd.ExcelFile(uploaded)
    if "Sheet1" not in xls.sheet_names:
        raise RuntimeError(f"Foglio 'Sheet1' non trovato. Fogli disponibili: {xls.sheet_names}")
    df = pd.read_excel(xls, sheet_name="Sheet1", dtype=str)

    col_ord = find_col(df, ["TE_NDOC"], label="TE_NDOC")
    col_base = find_col(df, ["MM_PREZZO_BASE"], label="MM_PREZZO_BASE")
    col_netto = find_col(df, ["MM_PREZZO_NETTO"], label="MM_PREZZO_NETTO")

    out = pd.DataFrame()
    out["order_id"] = df[col_ord].astype(str).str.strip()
    out["prezzo_base"] = df[col_base].apply(decimalize).apply(round_money)
    out["prezzo_netto"] = df[col_netto].apply(decimalize).apply(round_money)
    out = out.dropna(subset=["order_id"])
    return out

# ---------- UI ----------
c1, c2 = st.columns(2)
with c1:
    f_sup = st.file_uploader("📤 File FORNITORE (.xlsx) — foglio Orders", type=["xlsx"], key="sup")
with c2:
    f_log = st.file_uploader("📥 File LOGISTICA (.xlsx) — foglio Sheet1", type=["xlsx"], key="log")

tol = st.number_input("Tolleranza confronto (euro)", min_value=0.00, max_value=10.00, value=0.01, step=0.01)

if st.button("▶️ Confronta", use_container_width=True):
    if not f_sup or not f_log:
        st.warning("Carica entrambi i file.")
        st.stop()

    sup = normalize_supplier(f_sup)
    log = normalize_logistics(f_log)

    merged = pd.merge(sup, log, on="order_id", how="outer", indicator=True)
    only_sup = merged[merged["_merge"]=="left_only"].copy()
    only_log = merged[merged["_merge"]=="right_only"].copy()
    both = merged[merged["_merge"]=="both"].copy()

    # differenze con tolleranza su entrambe le coppie di prezzi
    both["diff_base"] = (both["nlmp"] - both["prezzo_base"]).abs()
    both["diff_netto"] = (both["supplier_price"] - both["prezzo_netto"]).abs()
    diffs = both[(both["diff_base"] > tol) | (both["diff_netto"] > tol)].copy()
    simil = both[(both["diff_base"] <= tol) & (both["diff_netto"] <= tol)].copy()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Solo Fornitore", len(only_sup))
    m2.metric("Solo Logistica", len(only_log))
    m3.metric("Prezzi diversi", len(diffs))
    m4.metric("Prezzi uguali/simili", len(simil))

    st.subheader("📄 Prezzi diversi (oltre tolleranza)")
    st.dataframe(diffs.sort_values("order_id"), use_container_width=True, height=360)

    st.subheader("⬇️ Download")
    d1, d2, d3, d4 = st.columns(4)
    d1.download_button("prezzi_diversi.xlsx", to_excel_bytes(diffs), "prezzi_diversi.xlsx")
    d2.download_button("prezzi_diversi.csv",  to_csv_bytes(diffs),  "prezzi_diversi.csv")
    d3.download_button("solo_fornitore.csv",  to_csv_bytes(only_sup), "solo_fornitore.csv")
    d4.download_button("solo_logistica.csv",  to_csv_bytes(only_log), "solo_logistica.csv")
