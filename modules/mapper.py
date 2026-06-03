# =============================================================================
# modules/mapper.py — Mapping intelligente delle colonne
# =============================================================================

import json
import os
import re
from pathlib import Path
from config import SCHEMA_CANONICO, MAPPING_FILE
from modules.ai_client import chiedi_ai

# ---------------------------------------------------------------------------
# Dizionario sinonimi — CAMPI STANDARD (non N-1)
# ---------------------------------------------------------------------------
SINONIMI = {
    # fair_value (book value N nel db reale)
    "fair value level":          "fair_value_level",   # PRIMA di "fair value"
    "fair value":                "fair_value",
    "valore carico lc finale":   "fair_value",
    "valore carico finale":      "fair_value",
    "valore di mercato":         "fair_value",
    "controvalore":              "fair_value",
    "mtm":                       "fair_value",
    "mark to market":            "fair_value",
    "valore corrente":           "fair_value",
    "market value":              "fair_value",
    # fair_value_mercato (valore di mercato effettivo)
    "valore lc mercato finale":  "fair_value_mercato",
    "valore mercato finale":     "fair_value_mercato",
    "prezzo finale":             "fair_value_mercato",
    # fair_value_level
    "fv level":                  "fair_value_level",
    "level":                     "fair_value_level",
    # asset_class
    "tipo asset sofia":          "asset_class",
    "tipologia attivo classe d": "asset_class",
    "asset class":               "asset_class",
    "tipologia":                 "asset_class",
    "categoria":                 "asset_class",
    "tipo strumento":            "asset_class",
    # tipo_emittente
    "tipo emittente":            "tipo_emittente",
    "issuer type":               "tipo_emittente",
    # rating
    "rating s&p":                "rating",
    "rating moody":              "rating",
    "rating fitch":              "rating",
    "merito credito":            "rating",
    "rating":                    "rating",
    # paese
    "paese emittente":           "paese",
    "paese":                     "paese",
    "country":                   "paese",
    "nazione":                   "paese",
    "area geografica":           "paese",
    # isin
    "codice isin":               "isin",
    "isin":                      "isin",
    # descrizione
    "descrizione del titolo":    "descrizione",
    "denominazione":             "descrizione",
    "descrizione":               "descrizione",
    "nome titolo":               "descrizione",
    "security":                  "descrizione",
    # quantita
    "nominale finale":           "quantita",
    "quantit":                   "quantita",
    "qtà":                       "quantita",
    "pezzi":                     "quantita",
    # prezzo_carico
    "prezzo carico finale":      "prezzo_carico",
    "prezzo storico":            "prezzo_carico",
    "prezzo carico":             "prezzo_carico",
    "costo medio":               "prezzo_carico",
    "prezzo medio":              "prezzo_carico",
    "book value":                "prezzo_carico",
    # cedola (include dividendi nel db reale)
    "competenza lorda cedole lc":    "cedola",
    "rateo cedole lordo lc periodo": "cedola",
    "cedola/interessi":              "cedola",
    "cedola":                        "cedola",
    "interessi":                     "cedola",
    "proventi":                      "cedola",
    "coupon":                        "cedola",
    # dividendi
    "dividendi incassati":       "dividendi",
    "dividendi":                 "dividendi",
    "dividend":                  "dividendi",
    # pl_realizzo
    "p/m realizzo periodo":      "pl_realizzo",
    "plus realizzo periodo":     "pl_realizzo",
    "minus realizzo periodo":    "pl_realizzo",
    "p/l realizzo":              "pl_realizzo",
    "pl realizzo":               "pl_realizzo",
    "realizz":                   "pl_realizzo",
    "plus/minus real":           "pl_realizzo",
    # pl_valutazione
    "p/m prezzo mercato fine":   "pl_valutazione",
    "plus prezzo mercato fine":  "pl_valutazione",
    "minus prezzo mercato fine": "pl_valutazione",
    "p/l valutazione":           "pl_valutazione",
    "pl valutazione":            "pl_valutazione",
    "valutat":                   "pl_valutazione",
    "plus/minus val":            "pl_valutazione",
    "unrealized":                "pl_valutazione",
    # pl_totale_db (precalcolato nel db)
    "p/m totali lc":             "pl_totale_db",
    "p/m totale lc":             "pl_totale_db",
    # valuta
    "valuta":                    "valuta",
    "currency":                  "valuta",
    "divisa":                    "valuta",
    # settore
    "settore":                   "settore",
    "sector":                    "settore",
    "industria":                 "settore",
    # date
    "data acquisto":             "data_acquisto",
    "data operaz":               "data_acquisto",
    "scadenza":                  "scadenza",
    "maturity":                  "scadenza",
    # peso
    "peso":                      "peso_ptf",
    "% portafoglio":             "peso_ptf",
    "% ptf":                     "peso_ptf",
    "weight":                    "peso_ptf",
}

# ---------------------------------------------------------------------------
# Dizionario sinonimi — CAMPI N-1 (anno precedente)
# ---------------------------------------------------------------------------
SINONIMI_PREV = {
    # fair_value_prev (book value N-1)
    "valore carico lc iniziale":     "fair_value_prev",
    "valore carico iniziale":        "fair_value_prev",
    "mtm n-1":                       "fair_value_prev",
    "fair value n-1":                "fair_value_prev",
    "valore di mercato n-1":         "fair_value_prev",
    "controvalore n-1":              "fair_value_prev",
    # cedola_prev
    "cedola/interessi n-1":          "cedola_prev",
    "cedola n-1":                    "cedola_prev",
    "interessi n-1":                 "cedola_prev",
    "competenza lorda cedole n-1":   "cedola_prev",
    # dividendi_prev
    "dividendi incassati n-1":       "dividendi_prev",
    "dividendi n-1":                 "dividendi_prev",
    # pl_realizzo_prev
    "p/m realizzo periodo n-1":      "pl_realizzo_prev",
    "p/l realizzo n-1":              "pl_realizzo_prev",
    "pl realizzo n-1":               "pl_realizzo_prev",
    "plus/minus realizzo n-1":       "pl_realizzo_prev",
    # pl_valutazione_prev
    "p/m prezzo mercato fine n-1":   "pl_valutazione_prev",
    "p/l valutazione n-1":           "pl_valutazione_prev",
    "pl valutazione n-1":            "pl_valutazione_prev",
    "plus/minus valutazione n-1":    "pl_valutazione_prev",
    # pl_totale_db_prev
    "p/m totali lc n-1":             "pl_totale_db_prev",
    "p/m totale lc n-1":             "pl_totale_db_prev",
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

    # Se contiene "n-1" → cerca SOLO nei sinonimi prev
    if "n-1" in col_lower:
        for pattern, canonico in SINONIMI_PREV.items():
            if pattern in col_lower:
                return canonico
        return None

    # Match esatto prima
    for pattern, canonico in SINONIMI.items():
        if col_lower == pattern:
            return canonico

    # Match parziale: pattern più lunghi prima per evitare ambiguità
    # (es. "fair value level" prima di "fair value")
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


def mappa_colonne(raw_columns: list[str]) -> dict:
    mapping_appreso = _carica_mapping_appreso()
    risultato       = {}
    da_chiedere_ai  = []

    for col in raw_columns:
        col_key = col.strip().lower()

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
        "mappate":      mappate,
        "non_mappate":  non_mappate,
        "totale":       len(mapping),
        "riconosciute": len(mappate),
    }
