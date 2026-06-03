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
                              confronto_bv_fv)
from modules.excel_writer import genera_excel, salva_excel
from modules.word_writer  import genera_word, salva_word
from config import INPUT_DIR, OUTPUT_DIR


# ---------------------------------------------------------------------------
# STEP 1: Leggi e pulisci il file Excel grezzo
# ---------------------------------------------------------------------------

def leggi_portafoglio(path: str) -> pd.DataFrame:
    print(f"[1/5] Lettura file: {path}")
    try:
        xls = pd.ExcelFile(path)
        foglio_scelto = xls.sheet_names[0]

        if len(xls.sheet_names) > 1:
            max_cols = 0
            for sheet in xls.sheet_names:
                df_temp = pd.read_excel(path, sheet_name=sheet, nrows=5)
                if len(df_temp.columns) > max_cols:
                    max_cols = len(df_temp.columns)
                    foglio_scelto = sheet
            print(f"    → Foglio selezionato: '{foglio_scelto}' (tra {xls.sheet_names})")

        df = pd.read_excel(path, sheet_name=foglio_scelto)
        df = df.dropna(how="all")
        df = df.dropna(axis=1, how="all")
        df.columns = df.columns.astype(str).str.strip()

        print(f"    → Righe: {len(df)}, Colonne: {len(df.columns)}")
        return df

    except Exception as e:
        print(f"[ERRORE] Impossibile leggere il file: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# STEP 2: Mapping colonne
# ---------------------------------------------------------------------------

def esegui_mapping(df: pd.DataFrame) -> pd.DataFrame:
    print(f"[2/5] Mapping colonne...")
    mapping = mappa_colonne(df.columns.tolist())
    info    = report_mapping(mapping)

    print(f"    → Colonne riconosciute: {info['riconosciute']}/{info['totale']}")
    if info["non_mappate"]:
        print(f"    → Non mappate: {info['non_mappate']}")

    df_mapped = applica_mapping(df, mapping)
    df_mapped = df_mapped.loc[:, ~df_mapped.columns.duplicated()]
    return df_mapped


# ---------------------------------------------------------------------------
# STEP 3: Calcola tutte le analisi disponibili
# ---------------------------------------------------------------------------

def calcola_analisi(df: pd.DataFrame) -> dict:
    print(f"[3/5] Calcolo analisi...")
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

    # Confronto BV vs FV — richiede entrambe le colonne
    if (disponibili.get("confronto_bv_fv") and
            "book_value" in df.columns and
            "fair_value" in df.columns and
            "asset_class" in df.columns):
        dati["confronto_bv_fv"] = confronto_bv_fv(df)

    dati["dettaglio"] = df

    print(f"    → Analisi calcolate: {len(dati) - 2}")
    return dati


# ---------------------------------------------------------------------------
# STEP 4 & 5: Genera Excel e Word
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
# ENTRY POINT
# ---------------------------------------------------------------------------

def genera_report(path_input: str,
                  nome_portafoglio: str = "Portafoglio",
                  output_dir: str = OUTPUT_DIR) -> tuple[str, str]:
    df_raw    = leggi_portafoglio(path_input)
    df_mapped = esegui_mapping(df_raw)
    dati      = calcola_analisi(df_mapped)
    return genera_output(dati, nome_portafoglio, output_dir)


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
