import streamlit as st
import pandas as pd

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Diagnostica Confronto", layout="wide")

# --- TITOLO ---
st.title("🔬 Diagnostica Confronto Prezzi")
st.caption("Questa versione include dei pannelli di controllo per diagnosticare eventuali problemi.")

# --- UI DI CARICAMENTO E IMPOSTAZIONI ---
col1, col2 = st.columns(2)
file_mio = col1.file_uploader("📁 Carica il tuo file Movimenti", type=["xlsx", "csv"])
file_fornitore = col2.file_uploader("📁 Carica il file del Fornitore", type=["xlsx", "csv"])
tolleranza = st.slider("Imposta la tolleranza (€)", 0.0, 1.0, 0.01, 0.01)

# --- LOGICA DI CONFRONTO ---
if file_mio and file_fornitore:
    try:
        with st.spinner("Elaborazione in corso..."):
            # 1. CARICAMENTO E PREPARAZIONE DATI
            df_mio = pd.read_excel(file_mio)
            df_fornitore = pd.read_excel(file_fornitore, sheet_name="Orders", skiprows=10)

            df_mio_subset = df_mio[['TE_NDOC', 'MM_PREZZO_NETTO']].rename(columns={
                'TE_NDOC': 'Numero Ordine', 'MM_PREZZO_NETTO': 'Prezzo_Mio'
            })
            df_fornitore_subset = df_fornitore[['Order Id', "Supplier's Price "]].rename(columns={
                'Order Id': 'Numero Ordine', "Supplier's Price ": 'Prezzo_Fornitore'
            })

            # 2. PULIZIA DATI
            df_mio_subset['Numero Ordine'] = df_mio_subset['Numero Ordine'].astype(str).str.strip()
            df_fornitore_subset['Numero Ordine'] = df_fornitore_subset['Numero Ordine'].astype(str).str.replace("BLL", "").str.strip()
            
            # ATTENZIONE: Questa è una delle cause più comuni di errore.
            # Assicuriamoci che i prezzi siano letti correttamente. Pandas si aspetta il punto '.'
            # come separatore decimale. Se i tuoi file usano la virgola ',', la conversione fallirà.
            df_mio_subset['Prezzo_Mio'] = pd.to_numeric(df_mio_subset['Prezzo_Mio'], errors='coerce')
            df_fornitore_subset['Prezzo_Fornitore'] = pd.to_numeric(df_fornitore_subset['Prezzo_Fornitore'], errors='coerce')

            # Copia i dati puliti per la diagnostica prima di rimuovere le righe nulle
            df_mio_pulito = df_mio_subset.copy()
            df_fornitore_pulito = df_fornitore_subset.copy()
            
            # Rimuovi righe dove la conversione a numero è fallita (valori NaN)
            df_mio_subset.dropna(inplace=True)
            df_fornitore_subset.dropna(inplace=True)
            
            # 3. MERGE E CONFRONTO
            # Usiamo un merge "outer" per vedere TUTTI gli ordini, anche quelli non abbinati
            confronto_df = pd.merge(df_mio_subset, df_fornitore_subset, on="Numero Ordine", how="outer", indicator=True)
            
            # Calcolo differenza solo dove possibile (righe abbinate)
            confronto_df['Differenza'] = (confronto_df['Prezzo_Mio'] - confronto_df['Prezzo_Fornitore']).abs()
            incongruenze_df = confronto_df[(confronto_df['Differenza'] > tolleranza) & (confronto_df['_merge'] == 'both')]

        # --- PANNELLI DI DIAGNOSTICA ---
        st.divider()
        st.header("🔍 Pannelli di Diagnostica")

        with st.expander("🔬 Dati dopo la pulizia (prima di eliminare righe con errori)"):
            st.write("Controlla qui se il **Numero Ordine** che hai modificato è identico e se il **prezzo** è stato letto correttamente come numero. Se un prezzo appare come `NaN`, significa che la conversione è fallita (es. per una virgola).")
            col_diag1, col_diag2 = st.columns(2)
            with col_diag1:
                st.subheader("Tuo File (Movimenti)")
                st.dataframe(df_mio_pulito)
            with col_diag2:
                st.subheader("File Fornitore")
                st.dataframe(df_fornitore_pulito)

        with st.expander("🔗 Risultato dell'Unione (Merge)"):
            st.write("Questa tabella mostra il risultato completo dell'unione. La colonna `_merge` ti dice se un ordine era presente in entrambi i file (`both`), solo nel tuo (`left_only`) o solo in quello del fornitore (`right_only`). **L'ordine che hai modificato deve avere `both` per essere confrontato.**")
            st.dataframe(confronto_df)
        st.divider()

        # --- VISUALIZZAZIONE RISULTATI ---
        st.header("✅ Risultati Finali")
        if not incongruenze_df.empty:
            st.subheader("⚠️ Dettaglio Incongruenze")
            st.dataframe(incongruenze_df[['Numero Ordine', 'Prezzo_Mio', 'Prezzo_Fornitore', 'Differenza']], use_container_width=True)
        else:
            st.success("Nessuna incongruenza di prezzo trovata tra gli ordini abbinati.")

    except Exception as e:
        st.error(f"❌ Si è verificato un errore critico.")
        st.exception(e)
else:
    st.info("⬆️ Carica entrambi i file per avviare l'analisi.")
