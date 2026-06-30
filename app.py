# ==========================================================================
# app.py
# ==========================================================================

import streamlit as st
import pandas as pd
import os
import tempfile

from modules.mapper  import mappa_colonne, applica_mapping, report_mapping
from modules.analisi import (scopri_analisi, kpi_portafoglio,
                              unisci_ship_patrimoniale, unisci_ship_economico)
from main import leggi_portafoglio, calcola_analisi, genera_output, _merge_ptf_eco, applica_filtri
from modules.mapper import campi_canonici, salva_mapping_manuale

st.set_page_config(page_title="Report Automatico AR Investimenti", layout="wide")

# ---------------------------------------------------------------------------
# PASSWORD
# ---------------------------------------------------------------------------
def _check_password() -> bool:
    try:
        pwd_corretta = st.secrets["APP_PASSWORD"]
    except Exception:
        pwd_corretta = "arinvestimenti"

    if st.session_state.get("autenticato"):
        return True

    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("### Accesso riservato")
        pwd = st.text_input("Password", type="password", key="_pwd_input")
        if st.button("Accedi", use_container_width=True):
            if pwd == pwd_corretta:
                st.session_state["autenticato"] = True
                st.rerun()
            else:
                st.error("Password errata.")
    return False

if not _check_password():
    st.stop()

# ---------------------------------------------------------------------------
# STILE
# ---------------------------------------------------------------------------
st.markdown("""
<style>
.stApp { background-color: rgb(0, 51, 141); }
.stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3 { color: white; }
[data-testid="stSidebar"] { background-color: rgb(0, 40, 110); }
.stButton > button { background-color: white; color: rgb(0, 51, 141); font-weight: bold; }
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] { color: white; }
</style>
""", unsafe_allow_html=True)

st.title("Tool AI per AR Investimenti")
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
    )
    divisori = {"€": 1, "€ migliaia": 1_000, "€ milioni": 1_000_000}
    divisore = divisori[unita]

    st.divider()
    st.caption("Il sistema riconosce automaticamente le colonne e genera solo le analisi supportate.")

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
# LETTURA
# ---------------------------------------------------------------------------
with st.spinner("Lettura file in corso..."):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    tipo, df_ptf_n, df_ptf_n1, dfs_eco, df_tx = leggi_portafoglio(tmp_path)

# ---------------------------------------------------------------------------
# MAPPING E UNIONE N/N-1
# ---------------------------------------------------------------------------
with st.spinner("Mapping colonne..."):
    def _esegui_mapping(df):
        mapping  = mappa_colonne(df.columns.tolist())
        info = report_mapping(mapping)
        df_m = applica_mapping(df, mapping)
        return df_m.loc[:, ~df_m.columns.duplicated()], mapping, info

    if tipo == "ship":
        df_n,  mapping_n,  info_n  = _esegui_mapping(df_ptf_n)
        df_n1, mapping_n1, info_n1 = _esegui_mapping(df_ptf_n1)
        df_mapped = unisci_ship_patrimoniale(df_n, df_n1)
        mapping, info = mapping_n, info_n

        df_inc_n, df_inc_n1 = dfs_eco
        df_eco_n,  _, _ = _esegui_mapping(df_inc_n)
        df_eco_n1, _, _ = _esegui_mapping(df_inc_n1)
        df_eco = unisci_ship_economico(df_eco_n, df_eco_n1)
        df_mapped = _merge_ptf_eco(df_mapped, df_eco)

        st.info("DB SHIP rilevato (5 sheet: Inventory N+N-1, Income N+N-1, Transaction Report)")
    else:
        df_mapped, mapping, info = _esegui_mapping(df_ptf_n)
        st.info("DB SOFIA rilevato (2 sheet: Posizioni + Transaction Report)")

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

# ---------------------------------------------------------------------------
# SEZIONE 1b: MAPPATURA COLONNE
# ---------------------------------------------------------------------------

CAMPI = campi_canonici()
NESSUNO = "— Non mappare —"

canonico_to_orig = {can: orig for orig, can in mapping.items() if can}

opzioni = [NESSUNO] + list(CAMPI.keys())

def _fmt_opt(v):
    return v if v == NESSUNO else f"{CAMPI[v]}  ({v})"

with st.expander("Mappatura colonne (modifica le riconosciute o assegna le mancanti)",
                 expanded=False):
    st.caption("Puoi cambiare il campo canonico di qualsiasi colonna, anche di quelle "
               "già riconosciute. "
               "Le scelte vengono memorizzate e riusate nei prossimi caricamenti.")

    proposte = []

    for col in list(df_mapped.columns):
        is_canonica = col in CAMPI
        if is_canonica:
            etichetta = f"«{CAMPI[col]}»  -  riconosciuta"
            default = col
        else:
            etichetta = f"«{col}»  -  NON riconosciuta"
            default = NESSUNO

        idx = opzioni.index(default) if default in opzioni else 0
        scelta = st.selectbox(
            etichetta,
            options=opzioni,
            index=idx,
            key=f"map_edit_{col}",
            format_func=_fmt_opt,
        )

        nome_originale = canonico_to_orig.get(col, col) if is_canonica else col

        if scelta == NESSUNO:
            if is_canonica and nome_originale != col:
                proposte.append((col, nome_originale, None))
            continue

        if scelta == col:
            continue

        proposte.append((col, nome_originale, scelta))

    if proposte:
        rinomine = {}
        for col, orig, tgt_can in proposte:
            rinomine[col] = tgt_can if tgt_can is not None else orig

        colonne_invariate = [c for c in df_mapped.columns if c not in rinomine]
        target_count = {}
        for tgt in rinomine.values():
            target_count[tgt] = target_count.get(tgt, 0) + 1

        collisioni = {
            src: tgt for src, tgt in rinomine.items()
            if tgt in colonne_invariate or target_count[tgt] > 1
        }
        if collisioni:
            st.warning(
                "Queste riassegnazioni creano un conflitto (campo già presente o "
                "scelto più volte) e verranno ignorate: "
                + ", ".join(f"{s} → {CAMPI.get(t, t)}" for s, t in collisioni.items())
            )
            rinomine = {s: t for s, t in rinomine.items() if s not in collisioni}

        if rinomine:
            df_mapped = df_mapped.rename(columns=rinomine)
            df_mapped = df_mapped.loc[:, ~df_mapped.columns.duplicated()]

            for col, orig, tgt_can in proposte:
                if col in rinomine and tgt_can is not None and orig not in CAMPI:
                    salva_mapping_manuale(orig, tgt_can)

            st.success(
                "Mappatura aggiornata: "
                + ", ".join(f"{s} → {CAMPI.get(t, t)}" for s, t in rinomine.items())
            )

# ---------------------------------------------------------------------------
# FILTRI
# ---------------------------------------------------------------------------
filtri = {}

with st.sidebar:
    st.divider()
    st.header("Filtri analisi")

    if "valuation_area" in df_mapped.columns:
        opzioni_va = sorted(df_mapped["valuation_area"].dropna().unique().tolist())
        sel_va = st.multiselect("Valuation Area", options=opzioni_va, default=opzioni_va)
        if sel_va and set(sel_va) != set(opzioni_va):
            filtri["valuation_area"] = sel_va

    if "company_name" in df_mapped.columns:
        opzioni_co = sorted(df_mapped["company_name"].dropna().unique().tolist())
        sel_co = st.multiselect("Società", options=opzioni_co, default=opzioni_co)
        if sel_co and set(sel_co) != set(opzioni_co):
            filtri["company_name"] = sel_co

    if "portfolio_name" in df_mapped.columns:
        opzioni_pf = sorted(df_mapped["portfolio_name"].dropna().unique().tolist())
        sel_pf = st.multiselect("Portafoglio", options=opzioni_pf, default=opzioni_pf)
        if sel_pf and set(sel_pf) != set(opzioni_pf):
            filtri["portfolio_name"] = sel_pf
          
df_filtered = applica_filtri(df_mapped, filtri)

if len(df_filtered) < len(df_mapped):
    st.caption(f"Filtri attivi: {len(df_filtered)}/{len(df_mapped)} righe selezionate.")

# ---------------------------------------------------------------------------
# SEZIONE 2: ANALISI DISPONIBILI
# ---------------------------------------------------------------------------
st.subheader("Analisi disponibili")
disponibili = scopri_analisi(df_filtered)

cols = st.columns(3)
for i, (nome, attiva) in enumerate(disponibili.items()):
    with cols[i % 3]:
        colore_bg  = "#ffffff" if attiva else "#ffeaea"
        colore_txt = "rgb(0,51,141)" if attiva else "#dc3545"
        icona = "OK" if attiva else "KO"
        st.markdown(
            f"""<div style="background-color:{colore_bg};color:{colore_txt};
            padding:8px 12px;margin-bottom:6px;border-radius:6px;
            font-size:13px;font-weight:600;">
            {icona} {nome.replace("_", " ").title()}</div>""",
            unsafe_allow_html=True
        )

n_attive = sum(1 for v in disponibili.values() if v)
st.caption(f"**{n_attive}/{len(disponibili)}** analisi disponibili con i dati forniti.")

if df_tx is not None and not df_tx.empty:
    st.success("Transaction Report rilevato - sheet Top 20 Operazioni disponibile.")
else:
    st.info("Nessun Transaction Report - sheet Top 20 Operazioni non disponibile.")

# ---------------------------------------------------------------------------
# SEZIONE 3: KPI
# ---------------------------------------------------------------------------
kpi = kpi_portafoglio(df_filtered)
st.subheader("KPI Portafoglio")

def fmt_val(v):
    return "n.d." if v is None else f"{v / divisore:,.2f} {unita}"

def fmt_perc(v):
    return f"{v:.2f}%" if v is not None else "n.d."

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Book Value", fmt_val(kpi.get("nav")))
c2.metric("N° Titoli", kpi.get("n_titoli", "n.d."))
c3.metric("P/M Totali", fmt_val(kpi.get("pl_totale")))
c4.metric("Proventi", fmt_val(kpi.get("proventi")))
c5.metric("Rendimento %", fmt_perc(kpi.get("rendimento_%")))

# ---------------------------------------------------------------------------
# SEZIONE 4: ANTEPRIMA
# ---------------------------------------------------------------------------
with st.expander("Anteprima dati"):
    st.dataframe(df_filtered.head(20), use_container_width=True)

# ---------------------------------------------------------------------------
# SEZIONE 5: GENERA
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Genera Report")

if st.button("Genera Excel + Word", type="primary", use_container_width=True):
    with st.spinner("Generazione report in corso..."):
        dati = calcola_analisi(df_mapped, df_tx, filtri)
        output_dir = tempfile.mkdtemp()
        path_excel, path_word = genera_output(
            dati, nome_portafoglio, output_dir, unita=unita
        )
    st.session_state["path_excel"] = path_excel
    st.session_state["path_word"]  = path_word
    st.success("Report generati con successo!")

if "path_excel" in st.session_state and "path_word" in st.session_state:
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        with open(st.session_state["path_excel"], "rb") as f:
            st.download_button(
                label="Scarica Excel",
                data=f,
                file_name=os.path.basename(st.session_state["path_excel"]),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    with col_dl2:
        with open(st.session_state["path_word"], "rb") as f:
            st.download_button(
                label="Scarica Word",
                data=f,
                file_name=os.path.basename(st.session_state["path_word"]),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
