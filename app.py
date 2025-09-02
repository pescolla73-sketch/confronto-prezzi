import streamlit as st
import pandas as pd

st.title("🔍 Confronto Prezzi Ordini")

file_mio = st.file_uploader("📁 Carica il tuo file", type=["xlsx", "csv"])
file_fornitore = st.file_uploader("📁 Carica il file del fornitore", type=["xlsx", "csv"])

if file_mio and file_fornitore:
    df_mio = pd.read_excel(file_mio)
    df_fornitore = pd.read_excel(file_fornitore)

    st.success("✅ File caricati correttamente!")

    # Rinomina colonne per uniformare
    df_mio = df_mio.rename(columns={
        "TE_NDOC": "Numero ordine",
        "TE_DATA_EVA": "Data ordine",
        "MM_PREZZO_NETTO": "Prezzo mio"
    })

    df_fornitore = df_fornitore.rename(columns={
        "Order Id": "Numero ordine",
        "Order Date": "Data ordine",
        "Supplier's Price": "Prezzo fornitore"
    })

    # Confronto
    confronto = pd.merge(df_mio, df_fornitore, on=["Data ordine", "Numero ordine"], suffixes=("_mio", "_fornitore"))

    confronto["Esito"] = confronto.apply(
        lambda row: "✅ Uguale" if row["Prezzo mio"] == row["Prezzo fornitore"] else "❌ Diverso", axis=1
    )

    st.subheader("📊 Risultato del confronto")
    st.dataframe(confronto)
