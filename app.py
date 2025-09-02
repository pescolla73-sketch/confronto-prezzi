import streamlit as st
import pandas as pd

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Confronto Prezzi Excel", layout="wide")
st.title("📊 Confronto Prezzi da File Excel (Versione Finale)")
st.caption("Questa versione gestisce differenze di formato, caratteri invisibili e arrotondamenti.")

# --- UI DI CARICAMENTO ---
col1, col2 = st.columns(2)
file_mio = col1.file_uploader("1️⃣ Carica il tuo file Movimenti (.xls)", type=["xls"])
file_fornitore = col2.file_uploader("2️⃣ Carica il file Breakdown del Fornitore (.xlsx)", type=["xlsx"])
tolleranza = st.slider("Imposta la tolleranza per gli arrotondamenti (€)", 0.0, 1.0, 0.01, 0.01)

# --- LOGICA DI CONFRONTO ---
if file_mio and file_fornitore:
    try:
        with st.spinner("Elaborazione dei file Excel..."):
            df_mio = pd.read_excel(file_mio)
            df_fornitore = pd.read_excel(file_fornitore, sheet_name="Orders", header=7)

        with st.spinner("Confronto in corso..."):
            # --- SELEZIONE COLONNE PER NOME ---
            cols_mio = {'TE_NDOC': 'Numero Ordine', 'MM_PREZZO_BASE': 'Prezzo_Base_Mio', 'MM_PREZZO_NETTO': 'Prezzo_Netto_Mio'}
            df_mio_subset = df_mio[list(cols_mio.keys())].rename(columns=cols_mio)

            cols_fornitore = {'Order Id': 'Numero Ordine', 'Net Local Market Price': 'Prezzo_Base_Fornitore', "Supplier's Price ": 'Prezzo_Netto_Fornitore'}
            df_fornitore_subset = df_fornitore[list(cols_fornitore.keys())].rename(columns=cols_fornitore)

            # --- PULIZIA NUMERO ORDINE (Metodo di Estrazione Forzata) ---
            df_mio_subset['Numero Ordine'] = df_mio_subset['Numero Ordine'].astype(str).str.extract(r'(\d+)').fillna('')
            df_fornitore_subset['Numero Ordine'] = df_fornitore_subset['Numero Ordine'].astype(str).str.extract(r'(\d+)').fillna('')

            # --- PULIZIA PREZZI (con gestione virgola/punto) ---
            for col in ['Prezzo_Base_Mio', 'Prezzo_Netto_Mio']:
                prezzi = df_mio_subset[col].astype(str).str.replace(',', '.', regex=False)
                df_mio_subset[col] = pd.to_numeric(prezzi, errors='coerce')
            
            for col in ['Prezzo_Base_Fornitore', 'Prezzo_Netto_Fornitore']:
                prezzi = df_fornitore_subset[col].astype(str).str.replace(',', '.', regex=False)
                df_fornitore_subset[col] = pd.to_numeric(prezzi, errors='coerce')

            df_mio_subset.dropna(inplace=True)
            df_fornitore_subset.dropna(inplace=True)

            # --- MERGE E CONFRONTO ---
            confronto_df = pd.merge(df_mio_subset, df_fornitore_subset, on="Numero Ordine", how="inner")
            confronto_df['Differenza_Base'] = (confronto_df['Prezzo_Base_Mio'] - confronto_df['Prezzo_Base_Fornitore']).abs()
            confronto_df['Differenza_Netto'] = (confronto_df['Prezzo_Netto_Mio'] - confronto_df['Prezzo_Netto_Fornitore']).abs()
            
            incongruenze_df = confronto_df[
                (confronto_df['Differenza_Base'] > tolleranza) | 
                (confronto_df['Differenza_Netto'] > tolleranza)
            ].copy()

        # --- VISUALIZZAZIONE RISULTATI ---
        st.header("Risultati dell'Analisi")
        if incongruenze_df.empty:
            st.success(f"🎉 Nessuna incongruenza trovata su {len(confronto_df)} ordini confrontati.")
        else:
            st.warning(f"⚠️ Trovate {len(incongruenze_df)} incongruenze:")
            st.dataframe(incongruenze_df.round(2))

    except Exception as e:
        st.error("Si è verificato un errore.")
        st.exception(e)
else:
    st.info("⬆️ Carica entrambi i file Excel per avviare il confronto.")
