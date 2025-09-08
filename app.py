import io, zipfile, re
from datetime import date
import pandas as pd
from dash import Dash, dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# --- Helpers ---
def to_float(x):
    if pd.isna(x): return None
    s = str(x).strip().replace(" ", "").replace("’", "").replace("'", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return None

def clean_order_id(x):
    s = str(x).strip()
    m = re.findall(r"\d+", s)
    return "".join(m) if m else s

def normalize_df(df, order_col, date_col, amount_cols, dayfirst=True):
    out = df[[order_col, date_col] + amount_cols].copy()
    out.columns = ["order_id", "order_date"] + [f"amount_{i}" for i in range(len(amount_cols))]
    out["order_id"] = out["order_id"].apply(clean_order_id)
    out["order_date"] = pd.to_datetime(out["order_date"], dayfirst=dayfirst, errors="coerce").dt.date
    for c in [c for c in out.columns if c.startswith("amount")]:
        out[c] = out[c].apply(to_float)
    return out.dropna(subset=["order_id","order_date"])

def reconcile(df1, df2, tol=0.01):
    merged = pd.merge(df1, df2, on=["order_id","order_date"], how="outer", suffixes=("_mio","_for"), indicator=True)
    only_mio = merged[merged["_merge"]=="left_only"]
    only_for = merged[merged["_merge"]=="right_only"]
    both = merged[merged["_merge"]=="both"].copy()
    diffs = []
    if not both.empty:
        for c in [c for c in both.columns if c.startswith("amount_mio")]:
            c_for = c.replace("_mio","_for")
            both[f"diff_{c}"] = (both[c].fillna(0) - both[c_for].fillna(0)).round(2)
        diffs = both.loc[(both.filter(like="diff_").abs() > tol).any(axis=1)]
    matches = both.loc[(both.filter(like="diff_").abs() <= tol).all(axis=1)]
    return only_mio, only_for, diffs, matches

# --- Layout ---
app.layout = dbc.Container([
    html.H2("🔗 Riconciliazione Fornitore vs Logistica (Dash)"),
    dcc.Upload(id="upload-mio", children=html.Div(["📂 Trascina o seleziona il tuo file Movimenti"]),
               style={"border":"1px dashed grey","padding":"20px","margin":"10px"}, multiple=False),
    dcc.Upload(id="upload-for", children=html.Div(["📂 Trascina o seleziona il file Fornitore"]),
               style={"border":"1px dashed grey","padding":"20px","margin":"10px"}, multiple=False),
    html.Button("▶️ Confronta", id="btn-run", n_clicks=0, className="btn btn-primary"),
    html.Div(id="output")
], fluid=True)

# --- Callback ---
@app.callback(
    Output("output","children"),
    Input("btn-run","n_clicks"),
    State("upload-mio","contents"), State("upload-mio","filename"),
    State("upload-for","contents"), State("upload-for","filename")
)
def run_compare(n, c1, f1, c2, f2):
    if n==0 or not c1 or not c2:
        return dbc.Alert("Carica entrambi i file e premi Confronta.", color="info")

    import base64
    def parse(contents, filename):
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string)
        if filename.endswith(".csv"):
            return pd.read_csv(io.BytesIO(decoded), dtype=str)
        else:
            return pd.read_excel(io.BytesIO(decoded), dtype=str)

    df_mio = parse(c1,f1)
    df_for = parse(c2,f2)

    # 🔧 qui setta i nomi/indici colonne giuste in base ai tuoi file
    mio_norm = normalize_df(df_mio, df_mio.columns[0], df_mio.columns[1], [df_mio.columns[2], df_mio.columns[3]])
    for_norm = normalize_df(df_for, df_for.columns[0], df_for.columns[1], [df_for.columns[2], df_for.columns[3]])

    only_mio, only_for, diffs, matches = reconcile(mio_norm, for_norm)

    return html.Div([
        html.H4("📄 Differenze"),
        dash_table.DataTable(data=diffs.to_dict("records"), page_size=10, style_table={"overflowX":"auto"}),
        html.H4("📄 Solo Movimenti"),
        dash_table.DataTable(data=only_mio.to_dict("records"), page_size=5, style_table={"overflowX":"auto"}),
        html.H4("📄 Solo Fornitore"),
        dash_table.DataTable(data=only_for.to_dict("records"), page_size=5, style_table={"overflowX":"auto"}),
        html.H4("✅ Corrispondenze"),
        dash_table.DataTable(data=matches.to_dict("records"), page_size=5, style_table={"overflowX":"auto"}),
    ])

if __name__ == "__main__":
    app.run_server(debug=True)
