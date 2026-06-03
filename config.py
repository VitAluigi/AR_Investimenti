import os

# =============================================================================
# config.py — Impostazioni centrali del sistema
# =============================================================================
# MODALITÀ AI:
#   "claude"  -> usa Anthropic Claude API (PC personale, test)
#   "azure"   -> usa Azure OpenAI (ambiente aziendale)
#   "none"    -> solo dizionario sinonimi, nessuna AI
# =============================================================================

AI_PROVIDER = "claude"

# --- Anthropic Claude (PC personale) ---
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
CLAUDE_MODEL   = "claude-opus-4-6"

# --- Azure OpenAI (azienda) ---
AZURE_OPENAI_ENDPOINT = "https://NOME-AZIENDA.openai.azure.com/"
AZURE_OPENAI_API_KEY  = "INSERISCI-API-KEY-AZURE"
AZURE_OPENAI_VERSION  = "2024-02-01"
AZURE_DEPLOYMENT_NAME = "gpt-4o"

# --- Percorsi ---
INPUT_DIR    = "input"
OUTPUT_DIR   = "output"
MAPPING_FILE = "modules/learned_mappings.json"

# --- Report ---
REPORT_LINGUA         = "italiano"
REPORT_VALUTA_SIMBOLO = "€"
REPORT_VALUTA_FORMATO = '#,##0.00 "€"'

# --- Schema canonico ---
# Nomenclatura chiara e non ambigua:
#   book_value     = valore di carico (contabile) N
#   book_value_prev= valore di carico (contabile) N-1
#   fair_value     = valore di mercato N
#   fair_value_prev= valore di mercato N-1
SCHEMA_CANONICO = {
    "isin":              "Codice ISIN",
    "descrizione":       "Descrizione titolo",
    "asset_class":       "Asset Class",
    "quantita":          "Quantità",
    "prezzo_carico":     "Prezzo di carico",
    # Book value (valore contabile)
    "book_value":        "Book Value N",
    "book_value_prev":   "Book Value N-1",
    # Fair value (valore di mercato)
    "fair_value":        "Fair Value N",
    "fair_value_prev":   "Fair Value N-1",
    "fair_value_level":  "Fair Value Level",
    # Classificazione
    "tipo_emittente":    "Tipo Emittente",
    "rating":            "Rating",
    "paese":             "Paese emittente",
    "valuta":            "Valuta",
    "settore":           "Settore",
    # Economica
    "cedola":            "Interessi/Cedole N",
    "cedola_prev":       "Interessi/Cedole N-1",
    "dividendi":         "Dividendi N",
    "dividendi_prev":    "Dividendi N-1",
    "pl_realizzo":       "PL Realizzo N",
    "pl_realizzo_prev":  "PL Realizzo N-1",
    "pl_valutazione":    "PL Valutazione N",
    "pl_valutazione_prev":"PL Valutazione N-1",
    "pl_totale_db":      "PL Totale N",
    "pl_totale_db_prev": "PL Totale N-1",
    # Date
    "data_acquisto":     "Data acquisto",
    "scadenza":          "Scadenza",
    "peso_ptf":          "Peso % portafoglio",
}

# --- Analisi disponibili: nome → colonne richieste ---
ANALISI_REQUISITI = {
    "patrimoniale_asset_class":      ["book_value", "asset_class"],
    "patrimoniale_fv_level":         ["book_value", "asset_class", "fair_value_level"],
    "rating_governativi":            ["book_value", "rating", "tipo_emittente"],
    "rating_non_governativi":        ["book_value", "rating", "tipo_emittente"],
    "geografia_governativi":         ["book_value", "paese", "tipo_emittente"],
    "economica_completa":            ["asset_class"],
    "economica_interessi_dividendi": ["cedola", "asset_class"],
    "economica_pl_realizzo":         ["pl_realizzo", "asset_class"],
    "economica_pl_valutazione":      ["pl_valutazione", "asset_class"],
    "concentrazione_top10":          ["book_value", "descrizione"],
    "esposizione_valutaria":         ["book_value", "valuta"],
    "esposizione_settoriale":        ["book_value", "settore"],
    "scadenze":                      ["book_value", "scadenza"],
    "confronto_bv_fv":               ["book_value", "fair_value", "asset_class"],
}

# --- Stile Excel ---
COLORI = {
    "header_bg": "1F3864",
    "header_fg": "FFFFFF",
    "totale_bg": "D9E1F2",
    "positivo":  "C6EFCE",
    "negativo":  "FFC7CE",
    "alternato": "EBF0FA",
}
