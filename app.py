# app.py — Confronto prezzi minimale (Fornitore: Orders + colonna Q) vs Logistica
import io
import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Confronto Prezzi", layout="wide")
st.title("💶 Confronto Prezzi (Ordine + Data) — Setup fisso")

# ---- Parametri fissi ----
DECIMALS = 2               # confronta a 2 decimali
DATE_DAYFIRST = True       # date italiane GG/MM/AAAA
SUPPLIER_SHEET = "Orders"  # foglio da usare nel file fornitore
SUPPLIER_PRICE_POS = 16    # Q = 16 (0-based: A=0, B=1, ..., Q=16)

# ---- Utilità ----
def decimalize(x):
    """Converte '1.234,5678' -> Decimal('1234.5678') gestendo spazi e apostrofi."""
    if pd.isna(x): 
        return None
    s = str(x).strip().replace(" ", "").replace("’", "").replace("'", "")
    if s == "":
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")  # 1.234,56 -> 1234.56
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None

def round_money(d: Decimal, decimals=DECIMALS):
    if d is None:
        return None
    q = Decimal(10) ** (-decimals)   # es. 0.01
    return d.quantize(q, rounding=ROUND_HALF_UP)

def read_supplier_orders(uploaded):
    """
    Legge il file Excel del fornitore, foglio 'Orders'. 
    Individua automaticamente la riga intestazioni (cerca 'Order Id' e 'Order Date').
    Restituisce un DataFrame con le intestazioni corrette.
    """
    name = uploaded.name if hasattr(uploaded, "name") else "file"
    ext = Path(name).suffix.lower()
    if ext not in [".xlsx", ".xls"]:
        st.error("Il file FORNITORE deve essere Excel (.xlsx/.xls).")
        return None
    try:
        xls = pd.ExcelFile(uploaded)
        if SUPPLIER_SHEET not in xls.sheet_names:
            st.error(f"Nel file '{name}' non trovo il foglio '{SUPPLIER_SHEET}'. I fogli disponibili sono: {xls.sheet_names}")
            return None

        raw = pd.read_excel(xls, sheet_name=SUPPLIER_SHEET, header=None, dtype=str)

        # Trova la riga header: contiene 'Order Id' e 'Order Date' (case-insensitive)
        def norm(s): 
            return str(s or "").strip().lower()
        hdr_row = None
        for i in range(min(200, len(raw))):  # controlla le prime 200 righe
            row_norm = [norm(x) for x in raw.iloc[i].values]
            if ("order id" in row_norm) and ("order date" in row_norm):
                hdr_row = i
                break
        if hdr_row is None:
            st.error("Non riesco a individuare la riga intestazioni nel foglio 'Orders' (mancano 'Order Id' e/o 'Order Date').")
            return None

        df = raw.iloc[hdr_row+1:].copy()
        df.columns = [str(c) for c in raw.iloc[hdr_row].values]
        df = df.reset_index(drop=True)

        # Controlli minimi
        if "Order Id" not in df.columns or "Order Date" not in df.columns:
            st.error("Nel foglio 'Orders' non trovo le colonne 'Order Id' e 'Order Date'.")
            return None
        if SUPPLIER_PRICE_POS >= df.shape[1]:
            st.error(f"La colonna prezzo Q (posizione {SUPPLIER_PRICE_POS}) non esiste (il foglio ha solo {df.shape[1]} colonne).")
            return None

        return df
    except Exception as e:
        st.error(f"Errore leggendo il foglio 'Orders': {e}")
        return None

def normalize_supplier(df):
    """
    Costruisce un dataframe con: order_id, order_date, price
    - order_id: df['Order Id']
    - order_date: df['Order Date'] (parse GG/MM/AAAA), senza orario
    - price: colonna alla posizione Q (indice 16) arrotondata a 2 decimali
    """
    # prende la colonna Q per il prezzo per posizione
    price_series = df.iloc[:, SUPPLIER_PRICE_POS]

    out = pd.DataFrame({
        "order_id": df["Order Id"].astype(str).str.strip(),
        "order_date": pd.to_datetime(df["Order Date"], dayfirst=DATE_DAYFIRST, errors="coerce").dt.date,
        "price_raw": price_series
    })
    out["price_dec"] = out["price_raw"].apply(decimalize)
    out["price"] = out["price_dec"].apply(round_money)
    out = out.dropna(subset=["order_id", "order_date", "price"]).copy()
    return out[["order_id", "order_date", "price"]]

def read_logistics(uploaded):
    """
    Legge il file di logistica (Excel o CSV) e restituisce un DF con colonne attese:
    - MM_ORDINE_TAGLIA (ordine)
    - TE_DATA         (data)
    - MM_PREZZO_BASE  (prezzo)
    """
    name = uploaded.name if hasattr(uploaded, "name") else "file"
    ext = Path(name).suffix.lower()
    try:
        if ext in [".xlsx", ".xls"]:
            # prende il primo foglio
            df = pd.read_excel(uploaded, dtype=str)
        elif ext == ".csv":
            df = pd.read_csv(uploaded, dtype=str, sep=None, engine="python")
        else:
            st.error("Il file LOGISTICA deve essere .xlsx/.xls/.csv")
            return None
    except Exception as e:
        st.error(f"Errore leggendo '{name}': {e}")
        return None

    expected = ["MM_ORDINE_TAGLIA", "TE_DATA", "MM_PREZZO_BASE"]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        st.error(f"Mancano colonne nel file LOGISTICA: {missing}\nColonne trovate: {list(df.columns)}")
        return None
    return df

def normalize_logistics(df):
    out = pd.DataFrame({
        "order_id": df["MM_ORDINE_TAGLIA"].astype(str).str.strip(),
        "order_date": pd.to_datetime(df["TE_DATA"], dayfirst=DATE_DAYFIRST, errors="coerce").dt.date,
        "price_raw": df["MM_PREZZO_BASE"]
    })
    out["price_dec"] = out["price_raw"].apply(decimalize)
    out["price"] = out["price_dec"].apply(round_money)
    out = out.dropna(subset=["order_id", "order_date", "price"]).copy()
    return out[["order_id", "order_date", "price"]]

def to_excel_bytes(df, sheet="dati"):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as xl:
        df.to_excel(xl, index=False, sheet_name=sheet)
    bio.seek(0)
    return bio

# ---- UI ----
c1, c2 = st.columns(2)
with c1:
    f_sup = st.file_uploader("📤 File FORNITORE (.xlsx/.xls) — usa foglio 'Orders'", type=["xlsx", "xls"], key="sup")
with c2:
    f_log = st.file_uploader("📥 File LOGISTICA (.xlsx/.xls/.csv)", type=["xlsx", "xls", "csv"], key="log")

run = st.button("▶️ Confronta prezzi", use_container_width=True)

if run:
    if not f_sup or not f_log:
        st.warning("Carica entrambi i file.")
        st.stop()

    # Fornitore
    df_sup_raw = read_supplier_orders(f_sup)
    if df_sup_raw is None or df_sup_raw.empty:
        st.stop()
    sup_n = normalize_supplier(df_sup_raw)

    # Logistica
    df_log_raw = read_logistics(f_log)
    if df_log_raw is None or df_log_raw.empty:
        st.stop()
    log_n = normalize_logistics(df_log_raw)

    # Merge su (order_id + order_date)
    merged = pd.merge(
        sup_n.rename(columns={"price": "price_supplier"}),
        log_n.rename(columns={"price": "price_logistics"}),
        on=["order_id", "order_date"], how="outer", indicator=True
    )

    only_sup = merged[merged["_merge"] == "left_only"].copy()
    only_log = merged[merged["_merge"] == "right_only"].copy()
    both = merged[merged["_merge"] == "both"].copy()

    # Differenze (dopo arrotondamento a 2 decimali)
    both["price_diff"] = (both["price_supplier"] - both["price_logistics"]).astype(float)
    diffs = both[both["price_diff"] != 0].copy()

    # Metriche
    m1, m2, m3 = st.columns(3)
    m1.metric("Solo fornitore", len(only_sup))
    m2.metric("Solo logistica", len(only_log))
    m3.metric("Prezzi diversi", len(diffs))

    st.subheader(f"📄 Prezzi diversi (arrotondati a {DECIMALS} decimali)")
    st.dataframe(diffs.sort_values(["order_date", "order_id"]), use_container_width=True, height=360)

    st.subheader("⬇️ Download")
    d1, d2, d3 = st.columns(3)
    d1.download_button("prezzi_diversi.xlsx", to_excel_bytes(diffs), "prezzi_diversi.xlsx")
    d2.download_button("solo_fornitore.xlsx", to_excel_bytes(only_sup), "solo_fornitore.xlsx")
    d3.download_button("solo_logistica.xlsx", to_excel_bytes(only_log), "solo_logistica.xlsx")

    with st.expander("🔍 Diagnostica (rapida)"):
        st.write("Fornitore:", sup_n.head(5))
        st.write("Logistica:", log_n.head(5))
