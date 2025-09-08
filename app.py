# app.py — Riconciliazione Fornitore vs Logistica (robusto)
import io, re, zipfile
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Riconciliazione Fornitore vs Logistica", layout="wide")
st.title("🔗 Riconciliazione Fornitore vs Logistica")
st.caption("Carica due file, scegli foglio se serve, controlla mappatura, e scarica i report.")

# ---------- Helpers ----------
def normalize_name(s: str) -> str:
    s = str(s or "").strip().lower()
    s = re.sub(r'[\s\-_]+', ' ', s)
    return (s
        .replace("à","a").replace("è","e").replace("é","e")
        .replace("ì","i").replace("ò","o").replace("ù","u")
    )

ORDER_KEYS = ["order id","orderid","id ordine","numero ordine","num ordine","n ordine","n. ordine",
              "order number","order no","order_no","orderno","order","ordine","numero","id transazione","id"]
DATE_KEYS  = ["order date","data ordine","data","date","transaction date","trans date",
              "created at","placed at","data documento","data operazione"]
AMNT_KEYS  = ["amount","total","totale","grand total","importo","importo totale","valore",
              "price","net amount","tot ordine","totale ordine","netto"]

def score_columns(cols):
    norm = [normalize_name(c) for c in cols]
    def pick(keys):
        best_idx, best_score = None, -1
        for i, h in enumerate(norm):
            sc = 0
            for k in keys:
                if h == k: sc = max(sc, 3)
                elif k in h: sc = max(sc, 2)
            if sc > best_score:
                best_idx, best_score = i, sc
        return best_idx
    oi = pick(ORDER_KEYS)
    di = pick(DATE_KEYS)
    ai = pick(AMNT_KEYS)
    return {
        "order": cols[oi] if oi is not None else cols[0],
        "date":  cols[di] if di is not None else cols[1 if len(cols)>1 else 0],
        "amount":cols[ai] if ai is not None else cols[2 if len(cols)>2 else 0],
    }

def read_table_with_sheet_picker(uploaded, key_prefix=""):
    name = uploaded.name if hasattr(uploaded, "name") else "file"
    suffix = Path(name).suffix.lower()
    if suffix in [".xlsx", ".xls"]:
        try:
            xls = pd.ExcelFile(uploaded)
            sheet = st.selectbox(f"Scegli foglio per **{name}**", xls.sheet_names, key=f"{key_prefix}_sheet_{name}")
            return pd.read_excel(xls, sheet_name=sheet, dtype=str)
        except Exception as e:
            st.error(f"Errore leggendo {name}: {e}. Se è un vecchio .xls, salvalo come .xlsx.")
            return None
    elif suffix == ".csv":
        try:
            return pd.read_csv(uploaded, dtype=str, sep=None, engine="python")
        except Exception as e:
            st.error(f"Errore leggendo {name}: {e}")
            return None
    else:
        st.error(f"Formato non supportato: {suffix}")
        return None

def to_float(x):
    if pd.isna(x): return None
    s = str(x).strip()
    if s == "": return None
    s = s.replace(" ", "").replace("’", "").replace("'", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")  # 1.234,56 -> 1234.56
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return None

def normalize_df(df, order_col, date_col, amount_col, *, dayfirst=True, aggregate=False, strip_leading_zeros=False):
    out = df[[order_col, date_col, amount_col]].copy()
    out.columns = ["order_id", "order_date", "amount"]

    # ID ordine pulito
    out["order_id"] = out["order_id"].astype(str).str.strip()
    if strip_leading_zeros:
        # rimuove zeri iniziali solo se tutto numerico
        mask_num = out["order_id"].str.fullmatch(r"\d+")
        out.loc[mask_num, "order_id"] = out.loc[mask_num, "order_id"].str.lstrip("0").replace({"": "0"})

    # Date
    out["order_date"] = pd.to_datetime(out["order_date"], dayfirst=dayfirst, errors="coerce").dt.date

    # Importi
    out["amount"] = out["amount"].apply(to_float)

    # Scarta righe senza ID o data
    out = out.dropna(subset=["order_id", "order_date"]).copy()

    # Aggrega duplicati
    if aggregate:
        out = out.groupby(["order_id", "order_date"], as_index=False)["amount"].sum()

    return out

def to_excel_bytes(df):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as xl:
        df.to_excel(xl, index=False, sheet_name="dati")
    bio.seek(0)
    return bio

# ---------- UI ----------
col1, col2 = st.columns(2)
with col1:
    supplier_file = st.file_uploader("📤 Carica **Fornitore** (.xlsx, .xls, .csv)", type=["xlsx","xls","csv"], key="sup")
with col2:
    logistics_file = st.file_uploader("📥 Carica **Logistica** (.xlsx, .xls, .csv)", type=["xlsx","xls","csv"], key="log")

with st.expander("Opzioni avanzate", expanded=False):
    dayfirst = st.checkbox("Date italiane (GG/MM/AAAA)", value=True)
    aggregate = st.checkbox("Aggrega righe duplicate (Ordine+Data)", value=False)
    strip_zeros = st.checkbox("Rimuovi zeri iniziali in Numero Ordine (solo ID numerici)", value=False)
    ignore_date = st.checkbox("Ignora data (confronta solo per Numero Ordine)", value=False)

if supplier_file and logistics_file:
    df_sup = read_table_with_sheet_picker(supplier_file, key_prefix="sup")
    df_log = read_table_with_sheet_picker(logistics_file, key_prefix="log")

    if df_sup is not None and df_log is not None and not df_sup.empty and not df_log.empty:
        sup_map = score_columns(df_sup.columns.tolist())
        log_map = score_columns(df_log.columns.tolist())

        st.subheader("Mappatura colonne")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Fornitore**")
            sup_order = st.selectbox("Numero Ordine (Fornitore)", list(df_sup.columns),
                                     index=list(df_sup.columns).index(sup_map["order"]))
            sup_date  = st.selectbox("Data Ordine (Fornitore)", list(df_sup.columns),
                                     index=list(df_sup.columns).index(sup_map["date"]))
            sup_amt   = st.selectbox("Importo (Fornitore)", list(df_sup.columns),
                                     index=list(df_sup.columns).index(sup_map["amount"]))
        with c2:
            st.markdown("**Logistica**")
            log_order = st.selectbox("Numero Ordine (Logistica)", list(df_log.columns),
                                     index=list(df_log.columns).index(log_map["order"]))
            log_date  = st.selectbox("Data Ordine (Logistica)", list(df_log.columns),
                                     index=list(df_log.columns).index(log_map["date"]))
            log_amt   = st.selectbox("Importo (Logistica)", list(df_log.columns),
                                     index=list(df_log.columns).index(log_map["amount"]))

        run = st.button("▶️ Confronta ora", use_container_width=True)

        if run:
            sup_norm = normalize_df(df_sup, sup_order, sup_date, sup_amt,
                                    dayfirst=dayfirst, aggregate=aggregate, strip_leading_zeros=strip_zeros)
            log_norm = normalize_df(df_log, log_order, log_date, log_amt,
                                    dayfirst=dayfirst, aggregate=aggregate, strip_leading_zeros=strip_zeros)

            # Merge
            if ignore_date:
                sup_k = sup_norm.groupby("order_id", as_index=False)["amount"].sum().rename(columns={"amount":"amount_supplier"})
                log_k = log_norm.groupby("order_id", as_index=False)["amount"].sum().rename(columns={"amount":"amount_logistics"})
                merged = pd.merge(sup_k, log_k, on="order_id", how="outer", indicator=True)
                merged["order_date"] = pd.NaT
            else:
                merged = pd.merge(
                    sup_norm.rename(columns={"amount":"amount_supplier"}),
                    log_norm.rename(columns={"amount":"amount_logistics"}),
                    on=["order_id", "order_date"], how="outer", indicator=True
                )

            only_sup = merged[merged["_merge"]=="left_only"].copy()
            only_log = merged[merged["_merge"]=="right_only"].copy()
            both = merged[merged["_merge"]=="both"].copy()

            both["amount_diff"] = (both["amount_supplier"].fillna(0) - both["amount_logistics"].fillna(0)).round(2)
            mismatches = both[both["amount_diff"].abs() > 0.01].copy()
            matches = both[both["amount_diff"].abs() <= 0.01].copy()

            # Totali
            tot_sup = sup_norm["amount"].sum(skipna=True)
            tot_log = log_norm["amount"].sum(skipna=True)
            delta = round((tot_sup or 0) - (tot_log or 0), 2)

            # Metriche
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Solo Fornitore", len(only_sup))
            m2.metric("Solo Logistica", len(only_log))
            m3.metric("Differenze importo", len(mismatches))
            m4.metric("Corrispondenze", len(matches))
            n1, n2, n3 = st.columns(3)
            n1.metric("Totale Fornitore", f"{tot_sup:,.2f}")
            n2.metric("Totale Logistica", f"{tot_log:,.2f}")
            n3.metric("Delta (F-L)", f"{delta:,.2f}")

            # Tabelle
            st.subheader("📄 Differenze importo")
            st.dataframe(mismatches.sort_values(by=["order_date","order_id"], na_position="first"), use_container_width=True, height=260)
            st.subheader("📄 Solo Fornitore / Solo Logistica")
            colA, colB = st.columns(2)
            with colA:
                st.dataframe(only_sup.sort_values(by=["order_date","order_id"], na_position="first"), use_container_width=True, height=240)
            with colB:
                st.dataframe(only_log.sort_values(by=["order_date","order_id"], na_position="first"), use_container_width=True, height=240)

            # Download singoli
            st.subheader("⬇️ Scarica report")
            d1, d2, d3, d4 = st.columns(4)
            d1.download_button("differenze_importo.xlsx", data=to_excel_bytes(mismatches), file_name="differenze_importo.xlsx")
            d2.download_button("solo_fornitore.xlsx", data=to_excel_bytes(only_sup), file_name="solo_fornitore.xlsx")
            d3.download_button("solo_logistica.xlsx", data=to_excel_bytes(only_log), file_name="solo_logistica.xlsx")
            d4.download_button("corrispondenze_ok.xlsx", data=to_excel_bytes(matches), file_name="corrispondenze_ok.xlsx")

            # Download ZIP
            zbuf = io.BytesIO()
            with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
                for nm, df in {
                    "differenze_importo": mismatches.sort_values(by=["order_date","order_id"], na_position="first"),
                    "solo_fornitore": only_sup.sort_values(by=["order_date","order_id"], na_position="first"),
                    "solo_logistica": only_log.sort_values(by=["order_date","order_id"], na_position="first"),
                    "corrispondenze_ok": matches.sort_values(by=["order_date","order_id"], na_position="first"),
                }.items():
                    z.writestr(f"{nm}.xlsx", to_excel_bytes(df).getvalue())
                summary = f"""RIEPILOGO
Totale Fornitore: {tot_sup:.2f}
Totale Logistica: {tot_log:.2f}
Delta (F-L): {delta:.2f}

Solo fornitore: {len(only_sup)}
Solo logistica: {len(only_log)}
Corrispondenze: {len(matches)}
Differenze importo: {len(mismatches)}
"""
                z.writestr("RIEPILOGO.txt", summary)
            zbuf.seek(0)
            st.download_button("Scarica tutto (ZIP)", data=zbuf, file_name="report_riconciliazione.zip", mime="application/zip")

            # Diagnostica
            with st.expander("🔍 Diagnostica"):
                st.write("**Fornitore (post-normalizzazione)**", {
                    "righe_valide": len(sup_norm),
                    "importi_non_numerici": int(sup_norm["amount"].isna().sum()),
                })
                st.write("**Logistica (post-normalizzazione)**", {
                    "righe_valide": len(log_norm),
                    "importi_non_numerici": int(log_norm["amount"].isna().sum()),
                })
                if not ignore_date:
                    st.write("Esempi chiavi SUP:", (sup_norm["order_id"].astype(str) + "|" + sup_norm["order_date"].astype(str)).head(10).tolist())
                    st.write("Esempi chiavi LOG:", (log_norm["order_id"].astype(str) + "|" + log_norm["order_date"].astype(str)).head(10).tolist())
                st.write({
                    "solo_fornitore": len(only_sup),
                    "solo_logistica": len(only_log),
                    "differenze": len(mismatches),
                    "corrispondenze": len(matches)
                })
    else:
        st.info("Controlla che i fogli non siano vuoti e che la riga 1 contenga le intestazioni.")
else:
    st.info("Carica i due file per iniziare. Formati supportati: .xlsx, .xls, .csv")
