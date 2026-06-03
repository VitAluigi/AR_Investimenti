# =============================================================================
# app.py — Interfaccia web Streamlit
# =============================================================================

import streamlit as st
import pandas as pd
import os
import tempfile
from pathlib import Path

from modules.mapper  import mappa_colonne, applica_mapping, report_mapping
from modules.analisi import scopri_analisi, kpi_portafoglio
from main            import leggi_portafoglio, calcola_analisi, genera_output

st.set_page_config(
    page_title="Report Portafoglio Titoli",
    layout="wide"
)

st.markdown("""
<style>
.ok  { color: #28a745; font-weight:bold; }
.no  { color: #dc3545; }
</style>
""", unsafe_allow_html=True)

st.title("Report Portafoglio Titoli")
st.caption("Carica il file Excel grezzo e genera automaticamente il report completo.")

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Configurazione")
    nome_portafoglio = st.text_input("Nome portafoglio", value="Portafoglio")

    st.divider()
    unita = st.selectbox(
        "Unità di misura",
        options=["€", "€ migliaia", "€ milioni"],
        index=0,
        help="Tutti i valori monetari verranno divisi di conseguenza in Excel e Word."
    )
    divisori = {"€": 1, "€ migliaia": 1_000, "€ milioni": 1_000_000}
    divisore = divisori[unita]

    st.divider()
    st.caption("Il sistema riconosce automaticamente le colonne e genera solo le analisi supportate dal tuo file.")

# ---------------------------------------------------------------------------
# UPLOAD FILE
# ---------------------------------------------------------------------------
uploaded_file = st.file_uploader(
    "Carica il file Excel del portafoglio",
    type=["xlsx", "xls"],
)

if not uploaded_file:
    st.info("Carica un file Excel per iniziare.")
    st.stop()

# ---------------------------------------------------------------------------
# LETTURA E MAPPING
# ---------------------------------------------------------------------------
with st.spinner("Analisi del file in corso..."):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    df_raw = leggi_portafoglio(tmp_path)
    mapping = mappa_colonne(df_raw.columns.tolist())
    info = report_mapping(mapping)
    df_mapped = applica_mapping(df_raw, mapping)
    df_mapped = df_mapped.loc[:, ~df_mapped.columns.duplicated()]

# ---------------------------------------------------------------------------
# SEZIONE 1: MAPPING
# ---------------------------------------------------------------------------
st.subheader("Riconoscimento colonne")

col1, col2 = st.columns(2)
with col1:
    st.metric("Colonne riconosciute", f"{info['riconosciute']}/{info['totale']}")
with col2:
    if info["non_mappate"]:
        st.warning(f"Non mappate: {', '.join(info['non_mappate'])}")
    else:
        st.success("Tutte le colonne riconosciute!")

with st.expander("Dettaglio mapping colonne"):
    mapping_display = [
        {"Colonna originale": k, "Campo canonico": v or "Non riconosciuta"}
        for k, v in mapping.items()
    ]
    st.dataframe(pd.DataFrame(mapping_display), use_container_width=True, hide_index=True)

with st.expander("Correggi mapping manuale (opzionale)"):
    from config import SCHEMA_CANONICO
    non_mappate = info["non_mappate"]
    if non_mappate:
        correzioni = {}
        for col in non_mappate:
            scelta = st.selectbox(
                f"'{col}' →",
                options=["(ignora)"] + list(SCHEMA_CANONICO.keys()),
                key=f"corr_{col}"
            )
            if scelta != "(ignora)":
                correzioni[col] = scelta
        if correzioni and st.button("Applica correzioni"):
            df_mapped = df_mapped.rename(columns=correzioni)
            st.success(f"Applicate {len(correzioni)} correzioni.")
    else:
        st.info("Nessuna colonna da correggere.")

# ---------------------------------------------------------------------------
# SEZIONE 2: ANALISI DISPONIBILI
# ---------------------------------------------------------------------------
st.subheader("Analisi disponibili")
disponibili = scopri_analisi(df_mapped)

cols = st.columns(3)
for i, (nome, attiva) in enumerate(disponibili.items()):
    with cols[i % 3]:
        stato  = "OK" if attiva else "KO"
        colore = "ok" if attiva else "no"
        st.markdown(
            f'<span class="{colore}">{stato} {nome.replace("_", " ").title()}</span>',
            unsafe_allow_html=True
        )

n_attive = sum(1 for v in disponibili.values() if v)
st.caption(f"**{n_attive}/{len(disponibili)}** analisi disponibili con i dati forniti.")

# ---------------------------------------------------------------------------
# SEZIONE 3: KPI
# ---------------------------------------------------------------------------
kpi = kpi_portafoglio(df_mapped)
st.subheader("KPI Portafoglio")

def fmt_val(v):
    if v is None:
        return "n.d."
    return f"{v / divisore:,.2f} {unita}"

def fmt_perc(v):
    return f"{v:.2f}%" if v is not None else "n.d."

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("NAV Totale",   fmt_val(kpi.get("nav")))
c2.metric("N° Titoli",    kpi.get("n_titoli", "n.d."))
c3.metric("P&L Totale",   fmt_val(kpi.get("pl_totale")))
c4.metric("Proventi",     fmt_val(kpi.get("proventi")))
c5.metric("Rendimento %", fmt_perc(kpi.get("rendimento_%")))

# ---------------------------------------------------------------------------
# SEZIONE 4: ANTEPRIMA
# ---------------------------------------------------------------------------
with st.expander("Anteprima dati"):
    st.dataframe(df_mapped.head(20), use_container_width=True)

# ---------------------------------------------------------------------------
# SEZIONE 5: GENERA
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Genera Report")

if st.button("Genera Excel + Word", type="primary", use_container_width=True):
    with st.spinner("Generazione report in corso..."):
        dati = calcola_analisi(df_mapped)
        output_dir = tempfile.mkdtemp()
        path_excel, path_word = genera_output(
            dati, nome_portafoglio, output_dir, unita=unita
        )

    st.success("Report generati con successo!")

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        with open(path_excel, "rb") as f:
            st.download_button(
                label="⬇Scarica Excel",
                data=f,
                file_name=os.path.basename(path_excel),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    with col_dl2:
        with open(path_word, "rb") as f:
            st.download_button(
                label="Scarica Word",
                data=f,
                file_name=os.path.basename(path_word),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
