# app.py — Confronto prezzi robusto (fornitore 'Orders' + prezzo per lettera) vs logistica
import io, string, traceback
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Confronto Prezzi", layout="wide")
st.title("💶 Confronto Prezzi (Ordine + Data)")

# ====== Parametri di default ======
DECIMALS = 2                # arrotondamento a 2 decimali
DATE_DAYFIRST = True        # date italiane (GG/MM/AAAA)
DEFAULT_SUPPLIER_SHEET = "Orders"
DEFAULT_PRICE_LETTER = "Q"  # colonna prezzo nel fornitore (lettera Excel). Cambia se serve.

# ====== Utilità ======
def decimalize(x):
    """Converte stringhe con virgole/punti in Decimal."""
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
    q = Decimal(10) ** (-decimals)
    return d.quantize(q, rounding=ROUND_HALF_UP)

def letter_to_idx(s: str, default_idx: int = 16) -> int:
    """Converte 'A' -> 0, 'B' -> 1, ..., 'Z' -> 25, 'AA' -> 26, ..."""
    s = (s or "").strip().upper()
    if not s:
        return default_idx
    val = 0
    for ch in s:
        if not ("A" <= ch <= "Z"):
            return default_idx
        val = val * 26 + (ord(ch) - ord("A") + 1)
    return val - 1

def to_excel_bytes(df, sheet="dati"):
    """Genera XLSX. Usa XlsxWriter se disponibile, altrimenti openpyxl."""
    bio = io.BytesIO()
    try:
        with pd.ExcelWriter(bio, engine="xlsxwriter") as xl:
            df.to_excel(xl, index=False, sheet_name=sheet)
    except ModuleNotFoundError:
        with pd.ExcelWriter(bio, engine="openpyxl") as xl:
            df.to_excel(xl, index=False, sheet_name=sheet)
    bio.seek(0)
    return bio

def to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8-sig")

# ====== Lettura / normalizzazione FORNITORE ======
def read_supplier_df(uploaded, sheet_name=DEFAULT_SUPPLIER_SHEET, auto_header=True, header_idx=None):
    """
    Legge il file Excel del fornitore e restituisce un DataFrame con intestazioni corrette.
    - Se auto_header=True, cerca una riga che contenga 'Order Id' e 'Order Date'.
    - Altrimenti usa header_idx (0-based).
    """
    name = uploaded.name if hasattr(uploaded, "name") else "file"
    ext = Path(name).suffix.lower()
    if ext not in [".xlsx", ".xls"]:
        raise RuntimeError("Il file FORNITORE deve essere Excel (.xlsx/.xls).")
    xls = pd.ExcelFile(uploaded)
    if sheet_name not in xls.sheet_names:
        raise RuntimeError(f"Nel file '{name}' non trovo il foglio '{sheet_name}'. Fogli disponibili: {xls.sheet_names}")

    raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, dtype=str)

    # trova la riga header
    if auto_header:
        hdr_row = None
        for i in range(min(300, len(raw))):
            row_norm = [str(x or "").strip().lower() for x in raw.iloc[i].values]
            if "order id" in row_norm and "order date" in row_norm:
                hdr_row = i
                break
        if hdr_row is None:
            raise RuntimeError("Header non trovato automaticamente: manca 'Order Id'/'Order Date'. Imposta manualmente la riga intestazioni.")
    else:
        if header_idx is None:
            raise RuntimeError("Devi indicare la riga intestazioni (0-based) quando l'auto rilevazione è OFF.")
        hdr_row = header_idx

    df = raw.iloc[hdr_row + 1 :].copy()
    df.columns = [str(c) for c in raw.iloc[hdr_row].values]
    df = df.reset_index(drop=True)

    if "Order Id" not in df.columns or "Order Date" not in df.columns:
        raise RuntimeError("Nel foglio fornitore non trovo le colonne 'Order Id' e/o 'Order Date'.")
    return df

def normalize_supplier(df, price_col_idx, strip_leading_zeros=False):
    if price_col_idx >= df.shape[1]:
        raise RuntimeError(
            f"La colonna prezzo (indice {price_col_idx}) non esiste; il foglio ha {df.shape[1]} colonne."
        )
    price_series = df.iloc[:, price_col_idx]

    out = pd.DataFrame(
        {
            "order_id": df["Order Id"].astype(str).str.strip(),
            "order_date": pd.to_datetime(df["Order Date"], dayfirst=DATE_DAYFIRST, errors="coerce").dt.date,
            "price_raw": price_series,
        }
    )
    if strip_leading_zeros:
        mask_num = out["order_id"].str.fullmatch(r"\d+")
        out.loc[mask_num, "order_id"] = out.loc[mask_num, "order_id"].str.lstrip("0").replace({"": "0"})

    out["price_dec"] = out["price_raw"].apply(decimalize)
    out["price"] = out["price_dec"].apply(round_money)
    out = out.dropna(subset=["order_id", "order_date", "price"]).copy()
    return out[["order_id", "order_date", "price"]]

# ====== Lettura / normalizzazione LOGISTICA ======
def read_logistics_df(uploaded):
    name = uploaded.name if hasattr(uploaded, "name") else "file"
    ext = Path(name).suffix.lower()
    if ext in [".xlsx", ".xls"]:
        df = pd.read_excel(uploaded, dtype=str)
    elif ext == ".csv":
        df = pd.read_csv(uploaded, dtype=str, sep=None, engine="python")
    else:
        raise RuntimeError("Il file LOGISTICA deve essere .xlsx/.xls/.csv")
    return df

def normalize_logistics(df, col_order, col_date, col_price, strip_leading_zeros=False):
    missing = [c for c in [col_order, col_date, col_price] if c not in df.columns]
    if missing:
        raise RuntimeError(f"Mancano colonne in logistica: {missing}\nColonne trovate: {list(df.columns)}")

    out = pd.DataFrame(
        {
            "order_id": df[col_order].astype(str).str.strip(),
            "order_date": pd.to_datetime(df[col_date], dayfirst=DATE_DAYFIRST, errors="coerce").dt.date,
            "price_raw": df[col_price],
        }
    )
    if strip_leading_zeros:
        mask_num = out["order_id"].str.fullmatch(r"\d+")
        out.loc[mask_num, "order_id"] = out.loc[mask_num, "order_id"].str.lstrip("0").replace({"": "0"})

    out["price_dec"] = out["price_raw"].apply(decimalize)
    out["price"] = out["price_dec"].apply(round_money)
    out = out.dropna(subset=["order_id", "order_date", "price"]).copy()
    return out[["order_id", "order_date", "price"]]

# ====== UI ======
st.subheader("1) Carica i file")
left, right = st.columns(2)
with left:
    f_sup = st.file_uploader("📤 FORNITORE (.xlsx/.xls) — foglio 'Orders'", type=["xlsx", "xls"], key="sup")
with right:
    f_log = st.file_uploader("📥 LOGISTICA (.xlsx/.xls/.csv)", type=["xlsx", "xls", "csv"], key="log")

st.subheader("2) Impostazioni fornitore")
c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    supplier_sheet = st.text_input("Foglio", value=DEFAULT_SUPPLIER_SHEET)
with c2:
    auto_header = st.checkbox("Auto-rileva intestazioni", value=True)
with c3:
    header_idx_txt = st.text_input("Riga intestazioni (0-based se auto OFF)", value="")

c4, c5 = st.columns([1, 1])
with c4:
    price_letter = st.text_input("Colonna prezzo (lettera Excel)", value=DEFAULT_PRICE_LETTER).strip().upper() or DEFAULT_PRICE_LETTER
with c5:
    strip_zeros = st.checkbox("Rimuovi zeri iniziali in Order Id (se numerici)", value=False)

st.subheader("3) Impostazioni logistica")
log_cols = []
if f_log:
    try:
        _tmp = read_logistics_df(f_log)
        log_cols = list(_tmp.columns)
    except Exception:
        log_cols = []
col_order = st.selectbox("Ordine (logistica)", log_cols or ["MM_ORDINE_TAGLIA"], index=(log_cols.index("MM_ORDINE_TAGLIA") if "MM_ORDINE_TAGLIA" in log_cols else 0))
col_date = st.selectbox("Data (logistica)", log_cols or ["TE_DATA"], index=(log_cols.index("TE_DATA") if "TE_DATA" in log_cols else 0))
col_price = st.selectbox("Prezzo (logistica)", log_cols or ["MM_PREZZO_BASE"], index=(log_cols.index("MM_PREZZO_BASE") if "MM_PREZZO_BASE" in log_cols else 0))

st.subheader("4) Opzioni di confronto")
o1, o2 = st.columns(2)
with o1:
    ignore_date = st.checkbox("Ignora data (confronta solo per Order Id)", value=False)
with o2:
    pass

run = st.button("▶️ Confronta prezzi", use_container_width=True)
st.divider()

# ====== LOGICA PRINCIPALE ======
if run:
    try:
        if not f_sup or not f_log:
            st.warning("Carica entrambi i file.")
            st.stop()

        # Fornitore
        header_idx = None
        if not auto_header and header_idx_txt.strip() != "":
            header_idx = int(header_idx_txt)
        df_sup_raw = read_supplier_df(f_sup, sheet_name=supplier_sheet, auto_header=auto_header, header_idx=header_idx)
        price_idx = letter_to_idx(price_letter, default_idx=letter_to_idx(DEFAULT_PRICE_LETTER))
        sup_n = normalize_supplier(df_sup_raw, price_idx, strip_leading_zeros=strip_zeros)

        # Logistica
        df_log_raw = read_logistics_df(f_log)
        log_n = normalize_logistics(df_log_raw, col_order, col_date, col_price, strip_leading_zeros=strip_zeros)

        # Merge
        if ignore_date:
            sup_k = sup_n.groupby("order_id", as_index=False)["price"].mean().rename(columns={"price": "price_supplier"})
            log_k = log_n.groupby("order_id", as_index=False)["price"].mean().rename(columns={"price": "price_logistics"})
            merged = pd.merge(sup_k, log_k, on="order_id", how="outer", indicator=True)
        else:
            merged = pd.merge(
                sup_n.rename(columns={"price": "price_supplier"}),
                log_n.rename(columns={"price": "price_logistics"}),
                on=["order_id", "order_date"],
                how="outer",
                indicator=True,
            )

        only_sup = merged[merged["_merge"] == "left_only"].copy()
        only_log = merged[merged["_merge"] == "right_only"].copy()
        both = merged[merged["_merge"] == "both"].copy()

        # Differenze di prezzo
        if "price_supplier" in both.columns and "price_logistics" in both.columns:
            both["price_diff"] = (both["price_supplier"] - both["price_logistics"]).astype(float)
            diffs = both[both["price_diff"] != 0].copy()
        else:
            diffs = pd.DataFrame(columns=["order_id", "order_date", "price_supplier", "price_logistics", "price_diff"])

        # Metriche
        m1, m2, m3 = st.columns(3)
        m1.metric("Solo fornitore", len(only_sup))
        m2.metric("Solo logistica", len(only_log))
        m3.metric("Prezzi diversi", len(diffs))

        st.subheader(f"📄 Prezzi diversi (arrotondati a {DECIMALS} decimali)")
        order_cols = [c for c in ["order_date", "order_id"] if c in diffs.columns]
        st.dataframe(diffs.sort_values(order_cols), use_container_width=True, height=360)

        st.subheader("⬇️ Download")
        d1, d2, d3, d4, d5, d6 = st.columns(6)
        d1.download_button("prezzi_diversi.xlsx", to_excel_bytes(diffs), "prezzi_diversi.xlsx")
        d2.download_button("prezzi_diversi.csv", to_csv_bytes(diffs), "prezzi_diversi.csv")
        d3.download_button("solo_fornitore.xlsx", to_excel_bytes(only_sup), "solo_fornitore.xlsx")
        d4.download_button("solo_fornitore.csv", to_csv_bytes(only_sup), "solo_fornitore.csv")
        d5.download_button("solo_logistica.xlsx", to_excel_bytes(only_log), "solo_logistica.xlsx")
        d6.download_button("solo_logistica.csv", to_csv_bytes(only_log), "solo_logistica.csv")

        with st.expander("🔍 Diagnostica"):
            st.write("Fornitore (prime 5 righe normalizzate):")
            st.write(sup_n.head(5))
            st.write("Logistica (prime 5 righe normalizzate):")
            st.write(log_n.head(5))
            if not ignore_date:
                st.write("Esempi chiavi SUP:", (sup_n["order_id"].astype(str) + "|" + sup_n["order_date"].astype(str)).head(10).tolist())
                st.write("Esempi chiavi LOG:", (log_n["order_id"].astype(str) + "|" + log_n["order_date"].astype(str)).head(10).tolist())

    except Exception as e:
        st.error("Si è verificato un errore. Apri 'Dettagli errore' per il trace.")
        with st.expander("❗ Dettagli errore (stack trace)"):
            st.text(f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")
