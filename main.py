# =============================================================================
# main.py — Orchestratore principale
# =============================================================================

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from modules.mapper  import mappa_colonne, applica_mapping, report_mapping
from modules.analisi import (scopri_analisi, report_analisi, kpi_portafoglio,
                              patrimoniale_asset_class, patrimoniale_fv_level,
                              rating_per_emittente, geografia_governativi,
                              economica_completa, top_holdings,
                              esposizione_valutaria, esposizione_settoriale,
                              confronto_bv_fv, top_operazioni,
                              scadenze_bucket, duration_ponderata, sensitivity_tassi,
                              unisci_ship_patrimoniale, unisci_ship_economico)
from modules.excel_writer import genera_excel, salva_excel
from modules.word_writer  import genera_word, salva_word
from config import INPUT_DIR, OUTPUT_DIR


# ---------------------------------------------------------------------------
# STEP 1: Leggi file Excel
# ---------------------------------------------------------------------------

def leggi_portafoglio(path: str):
    """
    Rileva il tipo di DB dal numero di sheet:
      2 sheet → SOFIA:  [Posizioni, Transaction Report]
      5 sheet → SHIP:   [Inventory N, Inventory N-1, Income N, Income N-1, Transaction Report]
      altri   → fallback SOFIA (primo sheet = posizioni, ultimo = tx)
    """
    print(f"[1/5] Lettura file: {path}")
    try:
        xls         = pd.ExcelFile(path)
        sheet_names = xls.sheet_names
        n_sheets    = len(sheet_names)

        def _leggi(sheet):
            df = pd.read_excel(path, sheet_name=sheet)
            df = df.dropna(how="all").dropna(axis=1, how="all")
            df.columns = df.columns.astype(str).str.strip()
            return df

        if n_sheets == 2:
            # ── SOFIA ──────────────────────────────────────────────────────
            print(f"    → DB SOFIA ({sheet_names})")
            df_ptf = _leggi(sheet_names[0])
            df_tx  = _leggi(sheet_names[1])
            print(f"    → Posizioni: {len(df_ptf)} righe | Transaction Report: {len(df_tx)} righe")
            return "sofia", df_ptf, None, None, df_tx

        elif n_sheets == 5:
            # ── SHIP ───────────────────────────────────────────────────────
            print(f"    → DB SHIP ({sheet_names})")
            df_inv_n  = _leggi(sheet_names[0])
            df_inv_n1 = _leggi(sheet_names[1])
            df_inc_n  = _leggi(sheet_names[2])
            df_inc_n1 = _leggi(sheet_names[3])
            df_tx     = _leggi(sheet_names[4])
            print(f"    → Inventory N: {len(df_inv_n)} | Inventory N-1: {len(df_inv_n1)} | "
                  f"Income N: {len(df_inc_n)} | Income N-1: {len(df_inc_n1)} | "
                  f"Transaction: {len(df_tx)} righe")
            return "ship", df_inv_n, df_inv_n1, (df_inc_n, df_inc_n1), df_tx

        else:
            # ── Fallback ───────────────────────────────────────────────────
            print(f"    → DB non riconosciuto ({n_sheets} sheet), tratto come SOFIA")
            df_ptf = _leggi(sheet_names[0])
            df_tx  = _leggi(sheet_names[-1]) if n_sheets > 1 else None
            return "sofia", df_ptf, None, None, df_tx

    except Exception as e:
        print(f"[ERRORE] Impossibile leggere il file: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# STEP 2: Mapping colonne
# ---------------------------------------------------------------------------

def esegui_mapping(df: pd.DataFrame) -> pd.DataFrame:
    mapping  = mappa_colonne(df.columns.tolist())
    info     = report_mapping(mapping)
    print(f"    → Colonne riconosciute: {info['riconosciute']}/{info['totale']}")
    if info["non_mappate"]:
        print(f"    → Non mappate: {info['non_mappate']}")
    df_mapped = applica_mapping(df, mapping)
    return df_mapped.loc[:, ~df_mapped.columns.duplicated()]


# ---------------------------------------------------------------------------
# STEP 3: Calcola analisi
# ---------------------------------------------------------------------------

def calcola_analisi(df: pd.DataFrame,
                    df_tx:    pd.DataFrame | None = None,
                    filtri:   dict | None = None) -> dict:
    """
    filtri: dict opzionale con chiavi 'valuation_area', 'company_name', 'portfolio_name'
    """
    print(f"[3/5] Calcolo analisi...")

    # Applica filtri se presenti
    if filtri:
        for col, valori in filtri.items():
            if col in df.columns and valori:
                df = df[df[col].isin(valori)]
                print(f"    → Filtro '{col}': {valori} → {len(df)} righe")

    disponibili = scopri_analisi(df)
    print(report_analisi(disponibili))

    dati = {}
    dati["kpi"] = kpi_portafoglio(df)

    if disponibili.get("patrimoniale_asset_class"):
        dati["patrimoniale_asset_class"] = patrimoniale_asset_class(df)

    if disponibili.get("patrimoniale_fv_level"):
        dati["patrimoniale_fv_level"] = patrimoniale_fv_level(df)

    if disponibili.get("rating_governativi"):
        dati["rating_governativi"] = rating_per_emittente(df, "gov")

    if disponibili.get("rating_non_governativi"):
        dati["rating_non_governativi"] = rating_per_emittente(df, "non_gov")

    if disponibili.get("geografia_governativi"):
        dati["geografia_governativi"] = geografia_governativi(df)

    if disponibili.get("economica_completa"):
        dati["economica_completa"] = economica_completa(df)

    if disponibili.get("concentrazione_top10"):
        dati["top_holdings"] = top_holdings(df, n=10)

    if disponibili.get("esposizione_valutaria"):
        dati["esposizione_valutaria"] = esposizione_valutaria(df)

    if disponibili.get("esposizione_settoriale"):
        dati["esposizione_settoriale"] = esposizione_settoriale(df)

    if disponibili.get("scadenze_bucket"):
        dati["scadenze_bucket"] = scadenze_bucket(df)

    if disponibili.get("duration_ponderata"):
        dati["duration_ponderata"] = duration_ponderata(df)

    if disponibili.get("sensitivity_tassi"):
        dati["sensitivity_tassi"] = sensitivity_tassi(df)

    if (disponibili.get("confronto_bv_fv") and
            "book_value" in df.columns and
            "fair_value" in df.columns and
            "asset_class" in df.columns):
        dati["confronto_bv_fv"] = confronto_bv_fv(df)

    # Transaction report
    if df_tx is not None and not df_tx.empty:
        dati["transaction_report"] = df_tx
        df_top_op = top_operazioni(df_tx, n=20)
        if df_top_op is not None and not df_top_op.empty:
            dati["top_operazioni"] = df_top_op
            print(f"    → Top operazioni: {len(df_top_op)} righe")

    dati["dettaglio"] = df

    print(f"    → Analisi calcolate: {len(dati) - 2}")
    return dati


# ---------------------------------------------------------------------------
# STEP 4 & 5: Genera output
# ---------------------------------------------------------------------------

def genera_output(dati: dict, nome_portafoglio: str,
                  output_dir: str, unita: str = "€") -> tuple[str, str]:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    data_str  = datetime.today().strftime("%Y%m%d")
    nome_safe = nome_portafoglio.replace(" ", "_").replace("/", "-")

    print(f"[4/5] Generazione Excel...")
    wb = genera_excel(dati, nome_portafoglio=nome_portafoglio, unita=unita)
    path_excel = os.path.join(output_dir, f"{nome_safe}_{data_str}.xlsx")
    salva_excel(wb, path_excel)

    print(f"[5/5] Generazione Word...")
    doc = genera_word(dati, kpi=dati["kpi"],
                      nome_portafoglio=nome_portafoglio, unita=unita)
    path_word = os.path.join(output_dir, f"{nome_safe}_{data_str}.docx")
    salva_word(doc, path_word)

    return path_excel, path_word


# ---------------------------------------------------------------------------
# ENTRY POINT alto livello
# ---------------------------------------------------------------------------

def genera_report(path_input: str,
                  nome_portafoglio: str = "Portafoglio",
                  output_dir: str = OUTPUT_DIR,
                  filtri: dict | None = None) -> tuple[str, str]:

    tipo, df_ptf_n, df_ptf_n1, dfs_eco, df_tx = leggi_portafoglio(path_input)

    print(f"[2/5] Mapping colonne...")
    if tipo == "ship":
        # Mappa e unisci Inventory N + N-1
        df_n  = esegui_mapping(df_ptf_n)
        df_n1 = esegui_mapping(df_ptf_n1)
        df_mapped = unisci_ship_patrimoniale(df_n, df_n1)
        # Mappa e unisci Income N + N-1 → aggiunge _prev alle colonne economiche
        df_inc_n, df_inc_n1 = dfs_eco
        df_eco_n  = esegui_mapping(df_inc_n)
        df_eco_n1 = esegui_mapping(df_inc_n1)
        df_eco    = unisci_ship_economico(df_eco_n, df_eco_n1)
        # Unisci patrimoni ale + economico sul portafoglio
        df_mapped = _merge_ptf_eco(df_mapped, df_eco)
    else:
        df_mapped = esegui_mapping(df_ptf_n)

    dati = calcola_analisi(df_mapped, df_tx, filtri)

    # Aggiungi i raw sheet di input per visualizzazione in fondo al report
    if tipo == "ship":
        # Inventory N + N-1 concatenati con colonna Anno
        inv_n_raw  = df_ptf_n.copy();  inv_n_raw.insert(0,  "Anno", df_ptf_n.get("Date",  pd.Series(["N"]*len(df_ptf_n))).iloc[0])
        inv_n1_raw = df_ptf_n1.copy(); inv_n1_raw.insert(0, "Anno", df_ptf_n1.get("Date", pd.Series(["N-1"]*len(df_ptf_n1))).iloc[0])
        dati["raw_inventory"] = pd.concat([inv_n_raw, inv_n1_raw], ignore_index=True)
        # Income N + N-1 concatenati
        df_inc_n, df_inc_n1 = dfs_eco
        inc_n_raw  = df_inc_n.copy();  inc_n_raw.insert(0,  "Anno", df_inc_n.get("Date To",  pd.Series(["N"]*len(df_inc_n))).iloc[0])
        inc_n1_raw = df_inc_n1.copy(); inc_n1_raw.insert(0, "Anno", df_inc_n1.get("Date To", pd.Series(["N-1"]*len(df_inc_n1))).iloc[0])
        dati["raw_income"] = pd.concat([inc_n_raw, inc_n1_raw], ignore_index=True)
    else:
        # SOFIA: foglio posizioni grezzo
        dati["raw_posizioni"] = df_ptf_n.copy()

    return genera_output(dati, nome_portafoglio, output_dir)


def _merge_ptf_eco(df_ptf: pd.DataFrame,
                   df_eco: pd.DataFrame) -> pd.DataFrame:
    """
    Aggiunge le colonne economiche (cedola, pl_realizzo, pl_valutazione
    e le rispettive _prev) al patrimoniale SHIP aggregandole per isin.
    """
    eco_cols = [c for c in df_eco.columns
                if c in ("isin", "cedola", "cedola_prev",
                         "pl_realizzo", "pl_realizzo_prev",
                         "pl_valutazione", "pl_valutazione_prev",
                         "pl_totale_db", "pl_totale_db_prev")]
    if "isin" not in df_ptf.columns or "isin" not in df_eco.columns:
        return df_ptf
    df_eco_agg = df_eco[eco_cols].groupby("isin", as_index=False).sum()
    return df_ptf.merge(df_eco_agg, on="isin", how="left")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera report portafoglio titoli")
    parser.add_argument("--input",  required=True,         help="Percorso file Excel input")
    parser.add_argument("--nome",   default="Portafoglio", help="Nome del portafoglio")
    parser.add_argument("--output", default=OUTPUT_DIR,    help="Cartella output")
    args = parser.parse_args()

    path_excel, path_word = genera_report(
        path_input=args.input,
        nome_portafoglio=args.nome,
        output_dir=args.output,
    )
    print(f"\nReport completati:")
    print(f"   Excel → {path_excel}")
    print(f"   Word  → {path_word}")
