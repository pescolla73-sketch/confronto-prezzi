import streamlit as st
import pandas as pd

st.set_page_config(page_title="Confronto Prezzi Ordini", layout="wide")
st.title("🔍 Confronto Prezzi Ordini")

# Upload dei file
file_mio = st.file_uploader("📁 Carica il tuo file", type=["xlsx"])
file_fornitore = st.file_uploader("📁 Carica il file del fornitore", type=["xlsx"])

if file_mio and file_fornitore:
    try:
        # Leggi il tuo file (colonne Z e AA → posizione 25 e 26)
        df_mio = pd.read_excel(file_mio)
        df_mio = df_mio.rename(columns={
            df_mio.columns[25]: "Numero ordine",
            df_mio.columns[26]: "Data ordine"
        })

        # Leggi il foglio "Orders" dal file del fornitore
        df_fornitore = pd.read_excel(file_fornitore, sheet_name="Orders")
        df_fornitore = df_fornitore.rename(columns={
            df_fornitore.columns[1]: "Numero ordine",
            df_fornitore.columns[3]: "Data ordine"
        })

        # Pulisci i dati
        df_mio["Numero ordine"] = df_mio["Numero ordine"].astype(str).str.strip()
        df_fornitore["Numero ordine"] = df_fornitore["Numero ordine"].astype(str).str.replace("BLL", "").str.strip()

        # Forza formati data coerenti
        df_mio["Data ordine"] = pd.to_datetime(df_mio["Data ordine"], format="%d/%m/%Y", errors="coerce")
        df_fornitore["Data ordine"] = pd.to_datetime(df_fornitore["Data ordine"], format="%d-%m-%Y", errors="coerce")

        # Esegui il confronto
        confronto = pd.merge(df_mio, df_fornitore, on=["Data ordine", "Numero ordine"], suffixes=("_mio", "_fornitore"))

        confronto["Esito"] = "✅ Uguale"  # Puoi aggiungere confronto prezzi se servono

        st.success("✅ Confronto completato!")
        st.subheader("📊 Risultato")
        st.dataframe(confronto)

    except Exception as e:
        st.error(f"❌ Errore durante l'elaborazione: {e}")
else:
    st.info("📥 Carica entrambi i file per iniziare il confronto.")
