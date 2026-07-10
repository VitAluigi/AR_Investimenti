# =============================================================================
# modules/mapper.py
# =============================================================================

import json
import os
import re
from pathlib import Path
from config import SCHEMA_CANONICO, MAPPING_FILE
from modules.ai_client import chiedi_ai

SINONIMI = {
    # ---- BOOK VALUE (valore contabile N) ----
    "valore carico lc finale": "book_value",
    "valore carico finale": "book_value",
    # SHIP — solo la colonna corretta
    "total book value lc": "book_value",

    # ---- FAIR VALUE (valore di mercato N) ----
    "valore lc mercato finale": "fair_value",
    "valore mercato finale": "fair_value",
    # SHIP — solo la colonna corretta
    "total market value lc": "fair_value",

    # ---- FAIR VALUE LEVEL ----
    "fair value level": "fair_value_level",
    "fv level": "fair_value_level",
    "level": "fair_value_level",

    # ---- ASSET CLASS ----
    "tipologia attivo classe d": "asset_class",
    "product type name": "asset_class",

    # ---- TIPO EMITTENTE ----
    "tipo emittente": "tipo_emittente",
    "issuer type name": "tipo_emittente",

    # ---- RATING (canonico "principale") ----
    "ifrs9 rating": "rating",
    "rating": "rating",

    # ---- RATING AGENZIA ----
    "rating s&p": "rating_agenzia",
    "rating moody": "rating_agenzia",
    "rating fitch": "rating_agenzia",
    "merito credito": "rating_agenzia",
    "axa rating": "rating_agenzia",
    "rating issue s&p": "rating_agenzia",
    "rating issuer s&p": "rating_agenzia",

    # ---- PAESE ----
    "paese emittente": "paese",
    "paese": "paese",
    "country": "paese",
    "nazione": "paese",
    "area geografica": "paese",
    "issuer country name": "paese",

    # ---- ISIN ----
    "codice isin": "isin",
    "security id": "isin",

    # ---- DESCRIZIONE ----
    "descrizione del titolo": "descrizione",
    "denominazione": "descrizione",
    "descrizione": "descrizione",
    "nome titolo": "descrizione",
    "security": "descrizione",
    "security id name": "descrizione",

    # ---- QUANTITA ----
    "nominale finale": "quantita",
    "nominal/units": "quantita",
    "units": "quantita",
    "quantit": "quantita",
    "qtà": "quantita",
    "pezzi": "quantita",

    # ---- PREZZO CARICO (solo SOFIA) ----
    "prezzo carico finale": "prezzo_carico",
    "prezzo storico": "prezzo_carico",
    "prezzo carico": "prezzo_carico",

    # ---- VALORE ACQUISTO ----
    "purchase value lc": "valore_acquisto",

    # ---- MARKET PRICE ----
    "market price pc": "market_price",

    # ---- CEDOLA / INTERESSI ----
    "competenza lorda cedole lc": "cedola",
    "total current income lc": "cedola",

    # ---- PL REALIZZO ----
    "p/m realizzo periodo": "pl_realizzo",
    "p/l realizzo": "pl_realizzo",
    "pl realizzo": "pl_realizzo",
    "total extra income lc": "pl_realizzo",

    # ---- PL VALUTAZIONE ----
    "p/m chiusure lc globali": "pl_valutazione",
    "stock revaluation lc ytd": "pl_valutazione",

    # ---- PL TOTALE ----
    "p/m totali lc": "pl_totale_db",

    # ---- VALUTA ----
    "valuta": "valuta",
    "currency": "valuta",
    "divisa": "valuta",
    "position currency": "valuta",

    # ---- SETTORE ----
    "settore": "settore",
    "issuer industry name": "settore",

    # ---- DATE ----
    "data acquisto": "data_acquisto",
    "acquisition date": "data_acquisto",
    "scadenza": "scadenza",
    "maturity": "scadenza",
    "maturity date ifrs9": "scadenza",

    # ---- PESO ----
    "peso": "peso_ptf",
    "% portafoglio": "peso_ptf",
    "% ptf": "peso_ptf",
    "weight": "peso_ptf",

    # ---- OCI ----
    "total oci lc ifrs9": "oci_lc",

    # ---- ECL / LOSS ----
    "total ecl lc": "ecl_lc",
    "loss allowance lc": "loss_allowance_lc",
    "w/b loss allowance lc": "wb_loss_allowance_lc",
    "w/b impairments lc ytd": "wb_impairments_lc",
    "impairments lc": "impairments_lc",

    # ---- DURATION ----
    "modified duration": "modified_duration",
    "mod duration": "modified_duration",
    "convexity": "convexity",

    # ---- CAMPI SHIP SPECIFICI ----
    "valuation area name": "valuation_area",
    "company code name": "company_name",
    "portfolio name": "portfolio_name",
    "valuation class name": "valuation_class",
    "bond classification name": "bond_classification",
    "security account group name": "security_account_group",

    # ---- PARTECIPAZIONI ----
    "tipo": "tipo_dettaglio",
    "sii mica account": "sii_mica_account",
}

# ---------------------------------------------------------------------------
# Dizionario sinonimi — CAMPI N-1 (anno precedente)
# ---------------------------------------------------------------------------
SINONIMI_PREV = {
    # SOFIA: book_value_prev
    "valore carico lc iniziale": "book_value_prev",
    "valore carico iniziale": "book_value_prev",
    "book value iniziale": "book_value_prev",
    "nominale iniziale": "book_value_prev",
    # SOFIA: fair_value_prev
    "valore lc mercato iniziale": "fair_value_prev",
    # Generici N-1
    "book value n-1": "book_value_prev",
    "valore carico n-1": "book_value_prev",
    "fair value n-1": "fair_value_prev",
    "valore mercato n-1": "fair_value_prev",
    "valore lc mercato n-1": "fair_value_prev",
    "controvalore n-1": "fair_value_prev",
    "valore di mercato n-1": "fair_value_prev",
    "mtm n-1": "book_value_prev",
    # cedola_prev
    "cedola/interessi n-1": "cedola_prev",
    "cedola n-1": "cedola_prev",
    "interessi n-1": "cedola_prev",
    "competenza lorda cedole n-1":"cedola_prev",
    # dividendi_prev
    "dividendi incassati n-1": "dividendi_prev",
    "dividendi n-1": "dividendi_prev",
    # pl_realizzo_prev
    "p/m realizzo periodo n-1": "pl_realizzo_prev",
    "p/l realizzo n-1": "pl_realizzo_prev",
    "pl realizzo n-1": "pl_realizzo_prev",
    "plus/minus realizzo n-1": "pl_realizzo_prev",
    # pl_valutazione_prev
    "p/m prezzo mercato n-1": "pl_valutazione_prev",
    "p/l valutazione n-1": "pl_valutazione_prev",
    "pl valutazione n-1": "pl_valutazione_prev",
    "plus/minus valutazione n-1": "pl_valutazione_prev",
    # oci_prev
    "val oci lc n-1": "oci_lc_prev",
    "total oci lc n-1": "oci_lc_prev",
    # ecl_prev
    "total ecl lc n-1": "ecl_lc_prev",
    "loss allowance lc n-1": "ecl_lc_prev",
    # pl_totale_db_prev
    "p/m totali lc n-1": "pl_totale_db_prev",
    "p/m totale lc n-1": "pl_totale_db_prev",
}


def _carica_mapping_appreso() -> dict:
    if os.path.exists(MAPPING_FILE):
        with open(MAPPING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _salva_mapping_appreso(mapping: dict):
    Path(MAPPING_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


def _match_sinonimo(col: str) -> str | None:
    col_lower = col.lower().strip()

    # 1. Match esatto in SINONIMI_PREV
    if col_lower in SINONIMI_PREV:
        return SINONIMI_PREV[col_lower]

    # 2. Match parziale in SINONIMI_PREV
    for pattern, canonico in sorted(SINONIMI_PREV.items(), key=lambda x: -len(x[0])):
        if re.search(r'\b' + re.escape(pattern) + r'\b', col_lower):
            return canonico

    # 3. Match esatto in SINONIMI
    if col_lower in SINONIMI:
        return SINONIMI[col_lower]

    # 4. Match parziale in SINONIMI
    for pattern, canonico in sorted(SINONIMI.items(), key=lambda x: -len(x[0])):
        if re.search(r'\b' + re.escape(pattern) + r'\b', col_lower):
            return canonico

    return None

def _chiedi_ai_mapping(colonne_sconosciute: list[str]) -> dict:
    schema_keys = list(SCHEMA_CANONICO.keys())
    prompt = f"""Sei un esperto di portafogli finanziari italiani.
Hai queste colonne non riconosciute di un file Excel di portafoglio titoli:
{colonne_sconosciute}

Mappale su uno di questi campi canonici (usa null se nessuno è appropriato):
{schema_keys}

Rispondi SOLO con un oggetto JSON valido nel formato:
{{"colonna_originale": "campo_canonico_o_null"}}

Nessun testo aggiuntivo, nessun markdown, solo JSON puro."""

    testo = chiedi_ai(prompt, max_tokens=500)
    if not testo:
        return {col: None for col in colonne_sconosciute}
    try:
        testo = re.sub(r"```json|```", "", testo).strip()
        return json.loads(testo)
    except Exception:
        return {col: None for col in colonne_sconosciute}

# Colonne da non mappare
COLONNE_ESCLUSE = {"date", "date from", "date to", "dateto", "datefrom"}


def mappa_colonne(raw_columns: list[str]) -> dict:
    mapping_appreso = _carica_mapping_appreso()
    risultato = {}
    da_chiedere_ai = []

    for col in raw_columns:
        col_key = col.strip().lower()

        if col_key in COLONNE_ESCLUSE:
            risultato[col] = None
            continue

        if col_key in mapping_appreso:
            risultato[col] = mapping_appreso[col_key]
            continue

        match = _match_sinonimo(col)
        if match:
            risultato[col] = match
            mapping_appreso[col_key] = match
            continue

        da_chiedere_ai.append(col)

    if da_chiedere_ai:
        ai_mapping = _chiedi_ai_mapping(da_chiedere_ai)
        for col, canonico in ai_mapping.items():
            valore = canonico if (canonico and canonico != "null") else None
            risultato[col] = valore
            if valore:
                mapping_appreso[col.strip().lower()] = valore

    _salva_mapping_appreso(mapping_appreso)
    return risultato


def applica_mapping(df, mapping: dict):
    rename_dict = {k: v for k, v in mapping.items() if v is not None}
    return df.rename(columns=rename_dict)


def report_mapping(mapping: dict) -> dict:
    mappate     = {k: v for k, v in mapping.items() if v is not None}
    non_mappate = [k for k, v in mapping.items() if v is None]
    return {
        "mappate": mappate,
        "non_mappate": non_mappate,
        "totale": len(mapping),
        "riconosciute": len(mappate),
    }

def campi_canonici() -> dict:
    """Ritorna {campo_canonico: etichetta} per i menu a tendina, inclusi gli N-1."""
    campi = dict(SCHEMA_CANONICO)
    campi.update({
        "book_value_prev": "Book Value N-1",
        "fair_value_prev": "Fair Value N-1",
        "quantita_prev": "Quantità N-1",
        "fair_value_level_prev": "Fair Value Level N-1",
        "cedola_prev": "Interessi/Cedole N-1",
        "dividendi_prev": "Dividendi N-1",
        "pl_realizzo_prev": "PL Realizzo N-1",
        "pl_valutazione_prev": "PL Valutazione N-1",
        "pl_totale_db_prev": "PL Totale N-1",
        "oci_lc_prev": "OCI LC N-1",
        "ecl_lc_prev": "ECL LC N-1",
        "modified_duration_prev": "Modified Duration N-1",
    })
    return campi


def salva_mapping_manuale(col: str, canonico: str):
    """Memorizza una scelta manuale così da riconoscerla in automatico la prossima volta."""
    if not canonico:
        return
    mapping = _carica_mapping_appreso()
    mapping[col.strip().lower()] = canonico
    _salva_mapping_appreso(mapping)
    if canonico:
        return
    mapping = _carica_mapping_appreso()
    mapping[col.strip().lower()] = canonico
    _salva_mapping_appreso(mapping)
