# =============================================================================
# config.py — Impostazioni centrali del sistema
# =============================================================================
# MODALITÀ AI:
#   "claude"  → usa Anthropic Claude API (PC personale, test)
#   "azure"   → usa Azure OpenAI (ambiente aziendale)
#   "none"    → solo dizionario sinonimi, nessuna AI
# =============================================================================

AI_PROVIDER = "claude"   # ← cambia in "azure" quando sei in azienda

# --- Anthropic Claude (PC personale) ---
CLAUDE_API_KEY   = "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"
CLAUDE_MODEL     = "claude-opus-4-6"

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
REPORT_VALUTA_FORMATO = '#.##0,00 "€"'

# --- Schema canonico ---
SCHEMA_CANONICO = {
    "isin":             "Codice ISIN",
    "descrizione":      "Descrizione titolo",
    "asset_class":      "Asset Class",
    "quantita":         "Quantità",
    "prezzo_carico":    "Prezzo di carico",
    "fair_value":       "Fair Value (€)",
    "fair_value_level": "Fair Value Level",
    "tipo_emittente":   "Tipo Emittente",
    "rating":           "Rating",
    "paese":            "Paese emittente",
    "valuta":           "Valuta",
    "settore":          "Settore",
    "cedola":           "Interessi/Cedole (€)",
    "dividendi":        "Dividendi (€)",
    "pl_realizzo":      "Plus/Minus da realizzo (€)",
    "pl_valutazione":   "Plus/Minus da valutazione (€)",
    "data_acquisto":    "Data acquisto",
    "scadenza":         "Scadenza",
    "peso_ptf":         "Peso % portafoglio",
}

# --- Analisi disponibili: nome → colonne richieste ---
ANALISI_REQUISITI = {
    "patrimoniale_asset_class":      ["fair_value", "asset_class"],
    "patrimoniale_fv_level":         ["fair_value", "asset_class", "fair_value_level"],
    "rating_governativi":            ["fair_value", "rating", "tipo_emittente"],
    "rating_non_governativi":        ["fair_value", "rating", "tipo_emittente"],
    "geografia_governativi":         ["fair_value", "paese", "tipo_emittente"],
    "economica_completa":            ["asset_class"],
    "economica_interessi_dividendi": ["cedola", "asset_class"],
    "economica_pl_realizzo":         ["pl_realizzo", "asset_class"],
    "economica_pl_valutazione":      ["pl_valutazione", "asset_class"],
    "concentrazione_top10":          ["fair_value", "descrizione"],
    "esposizione_valutaria":         ["fair_value", "valuta"],
    "esposizione_settoriale":        ["fair_value", "settore"],
    "scadenze":                      ["fair_value", "scadenza"],
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
