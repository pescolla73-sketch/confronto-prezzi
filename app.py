import streamlit as st
import pandas as pd

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Confronto Prezzi Excel", layout="wide")
st.title("📊 Confronto Automatico da File Originali")
st.info("Carica i file .xls e .xlsx originali. Lo script eseguirà la pulizia e il confronto in automatico.")

# --- UI DI CARICAMENTO ---
col1, col2 = st.columns(2)
file_mio = col1.file_uploader("1️⃣ Carica il tuo file Movimenti (.xls)", type=["xls"])
file_fornitore = col2.file_uploader("2️⃣ Carica il file Breakdown del Fornitore (.xlsx)", type=["xlsx"])

# --- LOGICA DI CONFRONTO ---
if file_mio and file_fornitore:
    try:
        with st.spinner("Elaborazione e pulizia automatica dei file..."):
            # --- LETTURA FILE ---
            # Legge i file SENZA intestazione per poter usare gli indici e saltare le righe corrette
            df_mio_raw = pd.read_excel(file_mio, header=None)
            df_fornitore_raw = pd.read_excel(file_fornitore, sheet_name="Orders", header=None)

            # Salta le righe iniziali per arrivare ai dati, come da tue istruzioni
            df_mio = df_mio_raw.iloc[1:].copy() # I dati iniziano dalla riga 2 (indice 1)
            df_fornitore = df_fornitore_raw.iloc[11:].copy() # I dati iniziano dalla riga 12 (indice 11)

        with st.spinner("Confronto in corso..."):
            # --- SELEZIONE COLONNE PER POSIZIONE ---
            # Il tuo file: Z(25), AA(26), AZ(51), BA(52)
            df_mio_subset = df_mio[[25, 26, 51, 52]].copy()
            df_mio_subset.columns = ['Numero Ordine', 'Data Ordine', 'Prezzo_1_Mio', 'Prezzo_2_Mio']

            # File fornitore: B(1), D(3), O(14), Q(16)
            df_fornitore_subset = df_fornitore[[1, 3, 14, 16]].copy()
            df_fornitore_subset.columns = ['Numero Ordine', 'Data Ordine', 'Prezzo_1_Fornitore', 'Prezzo_2_Fornitore']

            # --- PULIZIA DATI ---
            # Pulisce i numeri ordine estraendo solo la parte numerica
            df_mio_subset['Numero Ordine'] = df_mio_subset['Numero Ordine'].astype(str).str.extract(r'(\d+)').fillna('')
            df_fornitore_subset['Numero Ordine'] = df_fornitore_subset['Numero Ordine'].astype(str).str.extract(r'(\d+)').fillna('')
            
            # Converte le date in un formato standard per il confronto
            df_mio_subset['Data Ordine'] = pd.to_datetime(df_mio_subset['Data Ordine'], errors='coerce').dt.date
            df_fornitore_subset['Data Ordine'] = pd.to_datetime(df_fornitore_subset['Data Ordine'], errors='coerce').dt.date

            # Pulisce i prezzi, gestisce la virgola e arrotonda a 2 decimali
            for col in ['Prezzo_1_Mio', 'Prezzo_2_Mio']:
                prezzi = pd.to_numeric(df_mio_subset[col].astype(str).str.replace(',', '.', regex=False), errors='coerce')
                df_mio_subset[col] = prezzi.round(2)
            
            for col in ['Prezzo_1_Fornitore', 'Prezzo_2_Fornitore']:
                prezzi = pd.to_numeric(df_fornitore_subset[col].astype(str).str.replace(',', '.', regex=False), errors='coerce')
                df_fornitore_subset[col] = prezzi.round(2)

            # Rimuove le righe con dati invalidi (es. date o prezzi non leggibili)
            df_mio_subset.dropna(inplace=True)
            df_fornitore_subset.dropna(inplace=True)

            # --- MERGE E CONFRONTO ---
            # Unisce usando SIA Numero Ordine SIA Data Ordine per la massima precisione
            confronto_df = pd.merge(df_mio_subset, df_fornitore_subset, on=["Numero Ordine", "Data Ordine"], how="inner")
            
            # Confronta i prezzi già arrotondati per trovare le differenze
            incongruenze_df = confronto_df[
                (confronto_df['Prezzo_1_Mio'] != confronto_df['Prezzo_1_Fornitore']) | 
                (confronto_df['Prezzo_2_Mio'] != confronto_df['Prezzo_2_Fornitore'])
            ].copy()

        # --- VISUALIZZAZIONE RISULTATI ---
        st.header("Risultati dell'Analisi")
        if incongruenze_df.empty:
            st.success(f"🎉 Nessuna incongruenza trovata su {len(confronto_df)} ordini confrontati.")
        else:
            st.warning(f"⚠️ Trovate {len(incongruenze_df)} incongruenze:")
            st.dataframe(incongruenze_df)

    except Exception as e:
        st.error("Si è verificato un errore. Assicurati che le colonne nei file originali siano sempre nelle stesse posizioni.")
        st.exception(e)
else:
    st.info("⬆️ Carica i due file Excel originali per avviare il confronto automatico.")
