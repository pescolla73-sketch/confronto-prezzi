import streamlit as st
import pandas as pd

st.set_page_config(page_title="Investigatore Colonne", layout="wide")
st.title("🕵️ Investigatore Nomi Colonne")
st.caption("Questo strumento serve solo a scoprire i nomi esatti delle colonne nel file del fornitore.")

# Carica solo il file del fornitore
file_fornitore = st.file_uploader("Carica qui solo il file Breakdown del Fornitore (.xlsx)", type=["xlsx"])

if file_fornitore:
    try:
        st.info("Sto leggendo il file con l'intestazione alla riga 8...")
        
        # Legge il file esattamente come farebbe lo script principale
        df_fornitore = pd.read_excel(file_fornitore, sheet_name="Orders", header=7)

        st.success("File letto con successo! Ecco i nomi delle colonne che ho trovato:")
        
        # Mostra i nomi delle colonne ESATTI, inclusi eventuali spazi
        st.write(df_fornitore.columns.to_list())

        st.warning("Per favore, copia e incolla la lista di nomi che vedi qui sopra nella nostra conversazione.")

    except Exception as e:
        st.error("Si è verificato un errore durante la lettura del file.")
        st.exception(e)
