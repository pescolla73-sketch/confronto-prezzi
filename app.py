import streamlit as st
import pandas as pd

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Confronto Prezzi",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- TITOLO ---
st.title("📊 Confronto Prezzi Ordini")
st.caption("Carica i due file per trovare le discrepanze di prezzo tra i tuoi movimenti e i dati del fornitore.")

# --- UI DI CARICAMENTO E IMPOSTAZIONI ---
col1, col2 = st.columns(2)
with col1:
    file_mio = st.file_uploader("📁 Carica il tuo file Movimenti", type=["xlsx", "csv"])
with col2:
    file_fornitore = st.file_uploader("📁 Carica il file del Fornitore", type=["xlsx", "csv"])

# Slider per la tolleranza in una posizione centrale e meno invasiva
tolleranza = st.slider(
    "Imposta la tolleranza per gli arrotondamenti (€)", 
    min_value=0.0, max_value=1.0, value=0.01, step=0.01
)

# --- LOGICA DI CONFRONTO ---
if file_mio and file_fornitore:
    try:
        # Mostra uno stato di avanzamento per un feedback moderno
        with st.spinner("Elaborazione in corso..."):
            
            # 1. CARICAMENTO DATI
            df_mio = pd.read_excel(file_mio)
            # Legge il foglio 'Orders', saltando le prime 10 righe di intestazione
            df_fornitore = pd.read_excel(file_fornitore, sheet_name="Orders", skiprows=10)

            # 2. SELEZIONE E PULIZIA DATI "MOVIMENTI"
            df_mio_subset = df_mio[['TE_NDOC', 'MM_PREZZO_NETTO']].rename(columns={
                'TE_NDOC': 'Numero Ordine', 'MM_PREZZO_NETTO': 'Prezzo_Mio'
            })
            df_mio_subset['Numero Ordine'] = df_mio_subset['Numero Ordine'].astype(str).str.strip()
            df_mio_subset['Prezzo_Mio'] = pd.to_numeric(df_mio_subset['Prezzo_Mio'], errors='coerce')
            
            # 3. SELEZIONE E PULIZIA DATI "FORNITORE"
            df_fornitore_subset = df_fornitore[['Order Id', "Supplier's Price "]].rename(columns={
                'Order Id': 'Numero Ordine', "Supplier's Price ": 'Prezzo_Fornitore'
            })
            df_fornitore_subset['Numero Ordine'] = df_fornitore_subset['Numero Ordine'].astype(str).str.replace("BLL", "").str.strip()
            df_fornitore_subset['Prezzo_Fornitore'] = pd.to_numeric(df_fornitore_subset['Prezzo_Fornitore'], errors='coerce')

            # 4. RIMozione righe non valide
            df_mio_subset.dropna(inplace=True)
            df_fornitore_subset.dropna(inplace=True)

            # 5. MERGE E CONFRONTO
            confronto_df = pd.merge(df_mio_subset, df_fornitore_subset, on="Numero Ordine", how="inner")
            confronto_df['Differenza'] = (confronto_df['Prezzo_Mio'] - confronto_df['Prezzo_Fornitore']).abs()
            
            # 6. FILTRO INCONGRUENZE
            incongruenze_df = confronto_df[confronto_df['Differenza'] > tolleranza].copy()
            # Arrotonda i valori per una migliore visualizzazione
            incongruenze_df['Prezzo_Mio'] = incongruenze_df['Prezzo_Mio'].round(2)
            incongruenze_df['Prezzo_Fornitore'] = incongruenze_df['Prezzo_Fornitore'].round(2)
            incongruenze_df['Differenza'] = incongruenze_df['Differenza'].round(2)


        # --- VISUALIZZAZIONE RISULTATI ---
        st.header("Risultati dell'Analisi")
        
        # Riepilogo con metriche
        col_metrica1, col_metrica2 = st.columns(2)
        col_metrica1.metric("Ordini Corrispondenti", f"{len(confronto_df)}")
        col_metrica2.metric("Incongruenze Rilevate", f"{len(incongruenze_df)}", delta=f"-{len(incongruenze_df)}", delta_color="inverse")

        if not incongruenze_df.empty:
            st.subheader("⚠️ Dettaglio Incongruenze")
            
            # Mostra solo le colonne essenziali
            st.dataframe(
                incongruenze_df[['Numero Ordine', 'Prezzo_Mio', 'Prezzo_Fornitore', 'Differenza']],
                use_container_width=True
            )
            
            # Opzione per scaricare il report
            st.download_button(
                label="📥 Scarica Report Incongruenze (.csv)",
                data=incongruenze_df.to_csv(index=False).encode('utf-8'),
                file_name='report_incongruenze.csv',
                mime='text/csv',
            )
        else:
            st.success("🎉 Ottime notizie! Nessuna incongruenza di prezzo trovata con la tolleranza impostata.")

    except Exception as e:
        st.error(f"❌ Si è verificato un errore durante l'elaborazione.")
        st.exception(e) # Mostra i dettagli tecnici dell'errore
else:
    st.info("⬆️ Carica entrambi i file per avviare il confronto.")
