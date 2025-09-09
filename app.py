# app.py - confronto prezzi semplice (Ordine+Data), normalizza decimali
import io, re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Confronto Prezzi", layout="wide")
st.title("💶 Confronto Prezzi (Ordine + Data)")

DECIMALS = 2  # cambia a 4 se vuoi confrontare a 4 decimali
DATE_DAYFIRST = True  # True per date italiane GG/MM/AAAA

def read_table(uploaded):
    name = uploaded.name if hasattr(uploaded, "name") else "file"
    ext = Path(name).suffix.lower()
    if ext in [".xlsx", ".xls"]:
        xls = pd.ExcelFile(uploaded)
        sheet = st.selectbox(f"Scegli foglio per {name}", xls.sheet_names, key=f"sheet_{name}")
        return pd.read_excel(xls, sheet_name=sheet, dtype=str)
    elif ext == ".csv":
        return pd.read_csv(uploaded, dtype=str, sep=None, engine="python")
    else:
        st.error(f"Formato non supportato: {ext}")
        return None

def decimalize(x):
    """Converte '1.234,5678' -> Decimal('1234.5678') gestendo spazi/apostrofi."""
    if pd.isna(x): return None
    s = str(x).strip().replace(" ", "").replace("’","").replace("'","")
    if s == "": return None
    # 1.234,56 -> 1234.56 ; 1234,5 -> 1234.5
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None

def normalize_df(df, col_ord, col_date, col_price):
    out = df[[col_ord, col_date, col_price]].copy()
    out.columns = ["order_id", "order_date", "price_raw"]
    out["order_id"] = out["order_id"].astype(str).str.strip()
    out["order_date"] = pd.to_datetime(out["order_date"], dayfirst=DATE_DAYFIRST, errors="coerce").dt.date
    out["price_dec"] = out["price_raw"].apply(decimalize)

    # arrotonda a DECIMALS con HALF_UP (classico finanziario)
    q = Decimal(10) ** -DECIMALS  # es. 0.01
    out["price"] = out["price_dec"].apply(lambda d: d.quantize(q, rounding=ROUND_HALF_UP) if d is not None else None)

    out = out.dropna(subset=["order_id","order_date","price"])
    return out[["order_id","order_date","price"]]

# Upload
c1, c2 = st.columns(2)
with c1:
    f_sup = st.file_uploader("📤 File FORNITORE (.xlsx/.xls/.csv)", type=["xlsx","xls","csv"], key="sup")
with c2:
    f_log = st.file_uploader("📥 File LOGISTICA (.xlsx/.xls/.csv)", type=["xlsx","xls","csv"], key="log")

if f_sup is not None and f_log is not None:
    df_sup = read_table(f_sup)
    df_log = read_table(f_log)

    if df_sup is not None and df_log is not None and not df_sup.empty and not df_log.empty:
        st.subheader("Mappatura colonne (scegli le 3 colonne)")
        # pick intelligenti di default
        def guess(cols, keys):
            cols_norm = [re.sub(r'[\s\-_]+',' ', c.lower()) for c in cols]
            for k in keys:
                for i, h in enumerate(cols_norm):
                    if h == k or k in h:
                        return i
            return 0

        ord_keys = ["numero ordine","order id","order number","ordine","order"]
        date_keys = ["data ordine","order date","date","data","data operazione","data documento"]
        price_keys = ["prezzo","price","amount","importo","totale","total"]

        c3, c4 = st.columns(2)
        with c3:
            sup_ord = st.selectbox("Fornitore - Numero Ordine", list(df_sup.columns),
                                   index=guess(df_sup.columns, ord_keys))
            sup_date = st.selectbox("Fornitore - Data Ordine", list(df_sup.columns),
                                    index=guess(df_sup.columns, date_keys))
            sup_price = st.selectbox("Fornitore - Prezzo", list(df_sup.columns),
                                     index=guess(df_sup.columns, price_keys))
        with c4:
            log_ord = st.selectbox("Logistica - Numero Ordine", list(df_log.columns),
                                   index=guess(df_log.columns, ord_keys))
            log_date = st.selectbox("Logistica - Data Ordine", list(df_log.columns),
                                    index=guess(df_log.columns, date_keys))
            log_price = st.selectbox("Logistica - Prezzo", list(df_log.columns),
                                     index=guess(df_log.columns, price_keys))

        run = st.button("▶️ Confronta prezzi", use_container_width=True)
        if run:
            sup_n = normalize_df(df_sup, sup_ord, sup_date, sup_price)
            log_n = normalize_df(df_log, log_ord, log_date, log_price)

            merged = pd.merge(
                sup_n.rename(columns={"price":"price_supplier"}),
                log_n.rename(columns={"price":"price_logistics"}),
                on=["order_id","order_date"], how="outer", indicator=True
            )

            only_sup = merged[merged["_merge"]=="left_only"].copy()
            only_log = merged[merged["_merge"]=="right_only"].copy()
            both = merged[merged["_merge"]=="both"].copy()

            both["price_diff"] = both["price_supplier"] - both["price_logistics"]
            diffs = both[both["price_diff"] != 0].copy()

            # metriche
            m1, m2, m3 = st.columns(3)
            m1.metric("Solo fornitore", len(only_sup))
            m2.metric("Solo logistica", len(only_log))
            m3.metric("Prezzi diversi", len(diffs))

            st.subheader(f"📄 Prezzi diversi (arrotondati a {DECIMALS} decimali)")
            st.dataframe(
                diffs.sort_values(["order_date","order_id"]),
                use_container_width=True, height=320
            )

            # download excel
            def to_excel_bytes(df, sheet="dati"):
                bio = io.BytesIO()
                with pd.ExcelWriter(bio, engine="xlsxwriter") as xl:
                    df.to_excel(xl, index=False, sheet_name=sheet)
                bio.seek(0); return bio

            d1, d2, d3 = st.columns(3)
            d1.download_button("Scarica prezzi_diversi.xlsx", to_excel_bytes(diffs), "prezzi_diversi.xlsx")
            d2.download_button("Scarica solo_fornitore.xlsx", to_excel_bytes(only_sup), "solo_fornitore.xlsx")
            d3.download_button("Scarica solo_logistica.xlsx", to_excel_bytes(only_log), "solo_logistica.xlsx")

    else:
        st.info("Controlla che i fogli non siano vuoti e che la riga 1 contenga le intestazioni.")
else:
    st.info("Carica i due file per iniziare.")
