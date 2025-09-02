import streamlit as st
import pandas as pd

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Diagnostica Finale", layout="wide")
st.title("🔬 Diagnostica Finale del Confronto Prezzi")

# --- UI DI CARICAMENTO ---
col1, col2 = st.columns(2)
file_mio = col1.file_uploader("1️⃣ Carica il tuo file Movimenti (.xls)", type=["xls"])
file_fornitore = col2.file_uploader("2️⃣ Carica il file Breakdown (.xlsx)", type=["xlsx"])
tolleranza = st.slider("Imposta la tolleranza (€)", 0.0, 1.0, 0.01, 0.01)

# --- LOGICA DI CONFRONTO ---
if file_mio and file_fornitore:
    try:
        # --- 1. LETTURA GREZZA ---
        df_mio_raw = pd.read_excel(file_mio, header=None)
        df_fornitore_raw = pd.read_excel(file_fornitore, sheet_name="Orders", skiprows=10, header=None)

        with st.expander("🔬 PASSO 1: Dati Grezzi Letti dai File"):
            st.write("Controlla qui se le colonne (identificate da numeri) contengono i dati che ti aspetti.")
            c1, c2 = st.columns(2)
            c1.subheader("Tuo File (Grezzo)")
            c1.dataframe(df_mio_raw)
            c2.subheader("File Fornitore (Grezzo)")
            c2.dataframe(df_fornitore_raw)

        # --- 2. SELEZIONE E PULIZIA ---
        # Seleziona le colonne per posizione
        df_mio_subset = df_mio_raw[[25, 51, 52]].copy()
        df_mio_subset.columns = ['Numero Ordine', 'Prezzo_AZ_Mio', 'Prezzo_BA_Mio']

        df_fornitore_subset = df_fornitore_raw[[1, 14, 16]].copy()
        df_fornitore_subset.columns = ['Numero Ordine', 'Prezzo_O_Fornitore', 'Prezzo_Q_Fornitore']

        # Pulisci e converti i dati
        df_mio_subset['Numero Ordine'] = df_mio_subset['Numero Ordine'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        df_fornitore_subset['Numero Ordine'] = df_fornitore_subset['Numero Ordine'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace("BLL", "").str.strip()

        for col in ['Prezzo_AZ_Mio', 'Prezzo_BA_Mio']:
            prezzi = df_mio_subset[col].astype(str).str.replace(',', '.', regex=False)
            df_mio_subset[col] = pd.to_numeric(prezzi, errors='coerce')
        
        for col in ['Prezzo_O_Fornitore', 'Prezzo_Q_Fornitore']:
            prezzi = df_fornitore_subset[col].astype(str).str.replace(',', '.', regex=False)
            df_fornitore_subset[col] = pd.to_numeric(prezzi, errors='coerce')

        with st.expander("🔬 PASSO 2: Dati Dopo la Pulizia (Prima di Scartare le Righe Invalide)"):
            st.warning("CERCA QUI IL TUO ORDINE MODIFICATO! Controlla se i prezzi appaiono come numeri corretti. Se una cella del prezzo è vuota (NaN), significa che non è stato possibile leggerla come numero e la riga verrà scartata.")
            c1, c2 = st.columns(2)
            c1.subheader("Tuo File (Pulito)")
            c1.dataframe(df_mio_subset)
            c2.subheader("File Fornitore (Pulito)")
            c2.dataframe(df_fornitore_subset)

        # Scarta le righe con dati mancanti
        df_mio_subset.dropna(inplace=True)
        df_fornitore_subset.dropna(inplace=True)

        # --- 3. UNIONE E CONFRONTO ---
        confronto_df = pd.merge(df_mio_subset, df_fornitore_subset, on="Numero Ordine", how="inner")
        
        with st.expander("🔬 PASSO 3: Ordini Abbinati Correttamente"):
            st.write("Questi sono gli unici ordini che vengono effettivamente confrontati. Se il tuo ordine non è qui, non è stato abbinato.")
            st.dataframe(confronto_df)

        # Calcolo finale
        confronto_df['Differenza_AZ_vs_O'] = (confronto_df['Prezzo_AZ_Mio'] - confronto_df['Prezzo_O_Fornitore']).abs()
        confronto_df['Differenza_BA_vs_Q'] = (confronto_df['Prezzo_BA_Mio'] - confronto_df['Prezzo_Q_Fornitore']).abs()
        
        incongruenze_df = confronto_df[
            (confronto_df['Differenza_AZ_vs_O'] > tolleranza) | 
            (confronto_df['Differenza_BA_vs_Q'] > tolleranza)
        ].copy()

        # --- RISULTATI FINALI ---
        st.header("✅ Risultati Finali del Confronto")
        if incongruenze_df.empty:
            st.info(f"Confrontati {len(confronto_df)} ordini. Nessuna incongruenza trovata con la tolleranza impostata.")
        else:
            st.success(f"🎉 Trovate {len(incongruenze_df)} incongruenze!")
            st.dataframe(incongruenze_df.round(2))

    except Exception as e:
        st.error("Si è verificato un errore.")
        st.exception(e)
else:
    st.info("⬆️ Carica entrambi i file per avviare la diagnostica.")
