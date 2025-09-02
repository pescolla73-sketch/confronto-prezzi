import streamlit as st
import pandas as pd

st.title("🔍 Confronto Prezzi Ordini")

file_mio = st.file_uploader("📁 Carica il tuo file", type=["xlsx"])
file_fornitore = st.file_uploader("📁 Carica il file del fornitore", type=["xlsx"])

if file_mio and file_fornitore:
    # Leggi il tuo file
    df_mio = pd.read_excel(file_mio)
    # Leggi il foglio "Orders" dal file del fornitore
    df_fornitore = pd.read_excel(file_fornitore, sheet_name="Orders")

    st.success("✅ File caricati correttamente!")

    # Rinomina le colonne
    df_mio = df_mio.rename(columns={
        df_mio.columns[25]: "Numero ordine",   # Colonna Z
        df_mio.columns[26]: "Data ordine"      # Colonna AA
    })

    df_fornitore = df_fornitore.rename(columns={
        df_fornitore.columns[1]: "Numero ordine",  # Colonna B
        df_fornitore.columns[3]: "Data ordine"     # Colonna D
    })

    # Pulisci il prefisso "BLL" nei numeri ordine del fornitore
    df_fornitore["Numero ordine"] = df_fornitore["Numero ordine"].astype(str).str.replace("BLL", "").str.strip()

    # Assicurati che i numeri ordine siano stringhe
    df_mio["Numero ordine"] = df_mio["Numero ordine"].astype(str).str.strip()

    # Confronto
    confronto = pd.merge(df_mio, df_fornitore, on=["Data ordine", "Numero ordine"], suffixes=("_mio", "_fornitore"))

    confronto["Esito"] = "✅ Uguale"  # Puoi aggiungere confronto prezzi se servono

    st.subheader("📊 Risultato del confronto")
    st.dataframe(confronto)
