import streamlit as st
import pandas as pd

# --- FUNZIONE DI CARICAMENTO INTELLIGENTE ---
def carica_file(uploaded_file, is_fornitore=False):
    """
    Legge un file CSV o Excel in base alla sua estensione.
    """
    try:
        nome_file = uploaded_file.name
        if nome_file.endswith('.csv'):
            skip = 10 if is_fornitore else 0
            return pd.read_csv(uploaded_file, skiprows=skip)
        else: # .xlsx
            if is_fornitore:
                return pd.read_excel(uploaded_file, sheet_name="Orders", skiprows=10)
            else:
                return pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Impossibile leggere il file {nome_file}. Assicurati che il formato sia corretto e, se è un file Excel, che il foglio 'Orders' esista. Dettagli: {e}")
        return None

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Confronto Prezzi", layout="wide")

# --- TITOLO ---
st.title("📊 Confronto Prezzi Ordini")
st.caption("Carica i due file per trovare le discrepanze di prezzo tra i tuoi movimenti e i dati del fornitore.")

# --- UI DI CARICAMENTO E IMPOSTAZIONI ---
col1, col2 = st.columns(2)
file_mio = col1.file_uploader("📁 Carica il tuo file Movimenti", type=["xlsx", "csv"])
file_fornitore = col2.file_uploader("📁 Carica il file del Fornitore", type=["xlsx", "csv"])
tolleranza = st.slider("Imposta la tolleranza per gli arrotondamenti (€)", 0.0, 1.0, 0.01, 0.01)

# --- LOGICA DI CONFRONTO ---
if file_mio and file_fornitore:
    
    df_mio = carica_file(file_mio)
    df_fornitore = carica_file(file_fornitore, is_fornitore=True)

    if df_mio is not None and df_fornitore is not None:
        try:
            with st.spinner("Elaborazione in corso..."):
                # SELEZIONE E PULIZIA DATI "MOVIMENTI"
                df_mio_subset = df_mio[['TE_NDOC', 'MM_PREZZO_NETTO']].rename(columns={
                    'TE_NDOC': 'Numero Ordine', 'MM_PREZZO_NETTO': 'Prezzo_Mio'
                })
                df_mio_subset['Numero Ordine'] = df_mio_subset['Numero Ordine'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                df_mio_subset['Prezzo_Mio'] = pd.to_numeric(df_mio_subset['Prezzo_Mio'], errors='coerce')
                
                # SELEZIONE E PULIZIA DATI "FORNITORE"
                df_fornitore_subset = df_fornitore[['Order Id', "Supplier's Price "]].rename(columns={
                    'Order Id': 'Numero Ordine', "Supplier's Price ": 'Prezzo_Fornitore'
                })
                df_fornitore_subset['Numero Ordine'] = df_fornitore_subset['Numero Ordine'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace("BLL", "").str.strip()
                df_fornitore_subset['Prezzo_Fornitore'] = pd.to_numeric(df_fornitore_subset['Prezzo_Fornitore'], errors='coerce')

                df_mio_subset.dropna(inplace=True)
                df_fornitore_subset.dropna(inplace=True)

                # MERGE E CONFRONTO
                confronto_df = pd.merge(df_mio_subset, df_fornitore_subset, on="Numero Ordine", how="inner")
                confronto_df['Differenza'] = (confronto_df['Prezzo_Mio'] - confronto_df['Prezzo_Fornitore']).abs()
                
                incongruenze_df = confronto_df[confronto_df['Differenza'] > tolleranza].copy()
                incongruenze_df['Prezzo_Mio'] = incongruenze_df['Prezzo_Mio'].round(2)
                incongruenze_df['Prezzo_Fornitore'] = incongruenze_df['Prezzo_Fornitore'].round(2)
                incongruenze_df['Differenza'] = incongruenze_df['Differenza'].round(2)

            # VISUALIZZAZIONE RISULTATI
            st.header("Risultati dell'Analisi")
            col_metrica1, col_metrica2 = st.columns(2)
            col_metrica1.metric("Ordini Corrispondenti", f"{len(confronto_df)}")
            col_metrica2.metric("Incongruenze Rilevate", f"{len(incongruenze_df)}")

            if not incongruenze_df.empty:
                st.subheader("⚠️ Dettaglio Incongruenze")
                st.dataframe(
                    incongruenze_df[['Numero Ordine', 'Prezzo_Mio', 'Prezzo_Fornitore', 'Differenza']],
                    use_container_width=True
                )
                st.download_button(
                    label="📥 Scarica Report Incongruenze (.csv)",
                    data=incongruenze_df.to_csv(index=False).encode('utf-8'),
                    file_name='report_incongruenze.csv',
                    mime='text/csv',
                )
            else:
                st.success("🎉 Ottime notizie! Nessuna incongruenza di prezzo trovata tra gli ordini abbinati.")

        except KeyError as e:
            st.error(f"❌ Errore: Colonna non trovata. Controlla che i nomi delle colonne nei file siano corretti. Colonna mancante: {e}")
        except Exception as e:
            st.error(f"❌ Si è verificato un errore durante l'elaborazione.")
            st.exception(e)
else:
    st.info("⬆️ Carica entrambi i file per avviare il confronto.")
