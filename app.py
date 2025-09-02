import streamlit as st
import pandas as pd

st.set_page_config(page_title="Investigatore di Riga", layout="wide")
st.title("🕵️ Investigatore di Ordine Specifico")
st.caption("Questo strumento analizza un singolo ordine per capire perché non viene confrontato.")

# --- UI DI CARICAMENTO ---
col1, col2 = st.columns(2)
file_mio = col1.file_uploader("1️⃣ Carica il tuo file Movimenti (.xls)", type=["xls"])
file_fornitore = col2.file_uploader("2️⃣ Carica il file Breakdown (.xlsx)", type=["xlsx"])

if file_mio and file_fornitore:
    # Input per l'ordine da investigare
    ordine_da_cercare = st.text_input("Inserisci qui il Numero Ordine ESATTO che hai modificato (es. 178999699)", "")

    if ordine_da_cercare:
        try:
            with st.spinner("Sto analizzando la riga dell'ordine..."):
                # --- LETTURA FILE ---
                df_mio = pd.read_excel(file_mio, header=None)
                df_fornitore_raw = pd.read_excel(file_fornitore, sheet_name="Orders", header=None)
                df_fornitore = df_fornitore_raw.iloc[10:].copy()

                # --- ESTRAZIONE DATI PER POSIZIONE ---
                df_mio_subset = df_mio[[25, 51, 52]].copy()
                df_mio_subset.columns = ['Numero Ordine', 'Prezzo_AZ_Mio', 'Prezzo_BA_Mio']
                df_fornitore_subset = df_fornitore[[1, 14, 16]].copy()
                df_fornitore_subset.columns = ['Numero Ordine', 'Prezzo_O_Fornitore', 'Prezzo_Q_Fornitore']

                # --- PULIZIA NUMERO ORDINE ---
                df_mio_subset['Numero Ordine'] = df_mio_subset['Numero Ordine'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                df_fornitore_subset['Numero Ordine'] = df_fornitore_subset['Numero Ordine'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace("BLL", "").str.strip()

                # --- TROVA LA RIGA PRIMA DELLA CONVERSIONE ---
                riga_mio = df_mio_subset[df_mio_subset['Numero Ordine'] == ordine_da_cercare]
                riga_fornitore = df_fornitore_subset[df_fornitore_subset['Numero Ordine'] == ordine_da_cercare]

                st.header("🔬 Risultati dell'Investigazione")

                if riga_mio.empty or riga_fornitore.empty:
                    st.error(f"ATTENZIONE: L'ordine '{ordine_da_cercare}' non è stato trovato in entrambi i file dopo la pulizia iniziale del numero d'ordine.")
                else:
                    st.subheader("Passo 1: Valori letti dalle colonne")
                    st.write("Questi sono i valori originali nelle colonne AZ, BA, O, Q per l'ordine specificato.")
                    st.table(riga_mio)
                    st.table(riga_fornitore)

                    # --- CONVERSIONE PREZZI ---
                    for col in ['Prezzo_AZ_Mio', 'Prezzo_BA_Mio']:
                        prezzi = df_mio_subset[col].astype(str).str.replace(',', '.', regex=False)
                        df_mio_subset[col] = pd.to_numeric(prezzi, errors='coerce')
                    for col in ['Prezzo_O_Fornitore', 'Prezzo_Q_Fornitore']:
                        prezzi = df_fornitore_subset[col].astype(str).str.replace(',', '.', regex=False)
                        df_fornitore_subset[col] = pd.to_numeric(prezzi, errors='coerce')

                    # --- TROVA LA RIGA DOPO LA CONVERSIONE ---
                    riga_mio_convertita = df_mio_subset[df_mio_subset['Numero Ordine'] == ordine_da_cercare]
                    riga_fornitore_convertita = df_fornitore_subset[df_fornitore_subset['Numero Ordine'] == ordine_da_cercare]
                    
                    st.subheader("Passo 2: Valori dopo la conversione in numero")
                    st.write("Qui vedi i valori dopo aver tentato di convertirli in numeri. Controlla se qualche cella è diventata 'NaN' (vuota).")
                    st.table(riga_mio_convertita)
                    st.table(riga_fornitore_convertita)

                    # --- VERIFICA FINALE ---
                    st.subheader("Passo 3: Diagnosi Finale")
                    riga_unita = pd.merge(riga_mio_convertita.dropna(), riga_fornitore_convertita.dropna(), on="Numero Ordine")
                    
                    if riga_unita.empty:
                        st.error("CONCLUSIONE: La riga di questo ordine viene scartata! Questo succede perché almeno uno dei valori di prezzo non è stato riconosciuto come un numero valido ed è diventato 'NaN' (vuoto) dopo la conversione.")
                        st.write("Controlla i valori originali nel tuo file Excel per quella specifica cella: potrebbe contenere testo, spazi o simboli di valuta.")
                    else:
                        st.success("CONCLUSIONE: La riga di questo ordine è valida e dovrebbe essere confrontata correttamente. Se non vedi differenze, è probabile che i valori rientrino nella tolleranza impostata.")
                        st.write("Dati finali che verrebbero confrontati:")
                        st.table(riga_unita)

        except Exception as e:
            st.error("Si è verificato un errore durante l'investigazione.")
            st.exception(e)
else:
    st.info("⬆️ Carica entrambi i file e inserisci un numero d'ordine per avviare l'investigazione.")
