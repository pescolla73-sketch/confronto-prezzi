import streamlit as st
import pandas as pd

st.title("🔍 Confronto Prezzi Ordini")

file_mio = st.file_uploader("📁 Carica il tuo file", type=["xlsx", "csv"])
file_fornitore = st.file_uploader("📁 Carica il file del fornitore", type=["xlsx", "csv"])

if file_mio and file_fornitore:
    df_mio = pd.read_excel(file_mio) if file_mio.name.endswith(".xlsx") else pd.read_csv(file_mio)
    df_fornitore = pd.read_excel(file_fornitore) if file_fornitore.name.endswith(".xlsx") else pd.read_csv(file_fornitore)

    st.success("✅ File caricati correttamente!")

    # Unione basata su Data ordine e Numero ordine
    confronto = pd.merge(df_mio, df_fornitore, on=["Data ordine", "Numero ordine"], suffixes=("_mio", "_fornitore"))

    # Colonna differenza
    confronto["Esito"] = confronto.apply(
        lambda row: "✅ Uguale" if row["Prezzo mio"] == row["Prezzo fornitore"] else "❌ Diverso", axis=1
    )

    st.subheader("📊 Risultato del confronto")
    st.dataframe(confronto)
