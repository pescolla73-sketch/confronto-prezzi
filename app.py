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
