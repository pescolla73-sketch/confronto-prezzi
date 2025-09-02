import streamlit as st
import pandas as pd

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Confronto Prezzi Excel", layout="wide")
st.title("📊 Confronto Prezzi (Basato su Posizioni AZ, BA, O, Q)")

# --- UI DI CARICAMENTO ---
col1, col2 = st.columns(2)
file_mio = col1.file_uploader("1️⃣ Carica il tuo file Movimenti (.xls)", type=["xls"])
file_fornitore = col2.file_uploader("2️⃣ Carica il file Breakdown del Fornitore (.xlsx)", type=["xlsx"])
tolleranza = st.slider("Imposta la tolleranza (€)", 0.0, 1.0, 0.01, 0.01)

# --- LOGICA DI CONFRONTO ---
if file_mio and file_fornitore:
    try:
        with st.spinner("Elaborazione..."):
            # Legge i file senza intestazione per usare gli indici di colonna
            df_mio = pd.read_excel(file_mio, header=None)
            df_fornitore = pd.read_excel(file_fornitore, sheet_name="Orders", skiprows=10, header=None)

            # --- SELEZIONE COLONNE PER POSIZIONE ---
            # Z->25, AZ->51, BA->52
            df_mio_subset = df_mio[[25, 51, 52]].copy()
            df_mio_subset.columns = ['Numero Ordine', 'Prezzo_AZ_Mio', 'Prezzo_BA_Mio']

            # B->1, O->14, Q->16
            df_fornitore_subset = df_fornitore[[1, 14, 16]].copy()
            df_fornitore_subset.columns = ['Numero Ordine', 'Prezzo_O_Fornitore', 'Prezzo_Q_Fornitore']

            # --- PULIZIA DATI ---
            df_mio_subset['Numero Ordine'] = df_mio_subset['Numero Ordine'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            df_fornitore_subset['Numero Ordine'] = df_fornitore_subset['Numero Ordine'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace("BLL", "").str.strip()

            for col in ['Prezzo_AZ_Mio', 'Prezzo_BA_Mio']:
                prezzi = df_mio_subset[col].astype(str).str.replace(',', '.', regex=False)
                df_mio_subset[col] = pd.to_numeric(prezzi, errors='coerce')
            
            for col in ['Prezzo_O_Fornitore', 'Prezzo_Q_Fornitore']:
                prezzi = df_fornitore_subset[col].astype(str).str.replace(',', '.', regex=False)
                df_fornitore_subset[col] = pd.to_numeric(prezzi, errors='coerce')

            df_mio_subset.dropna(inplace=True)
            df_fornitore_subset.dropna(inplace=True)

            # --- MERGE E CONFRONTO ---
            confronto_df = pd.merge(df_mio_subset, df_fornitore_subset, on="Numero Ordine", how="inner")
            
            confronto_df['Differenza_AZ_vs_O'] = (confronto_df['Prezzo_AZ_Mio'] - confronto_df['Prezzo_O_Fornitore']).abs()
            confronto_df['Differenza_BA_vs_Q'] = (confronto_df['Prezzo_BA_Mio'] - confronto_df['Prezzo_Q_Fornitore']).abs()
            
            incongruenze_df = confronto_df[
                (confronto_df['Differenza_AZ_vs_O'] > tolleranza) | 
                (confronto_df['Differenza_BA_vs_Q'] > tolleranza)
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
    st.info("⬆️ Carica entrambi i file per avviare il confronto.")
