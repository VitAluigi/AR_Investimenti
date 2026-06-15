# AR Investimenti

Sistema per generare report Excel e Word da database grezzo di portafoglio.

---

## Struttura progetto

```
portafoglio_ai/
- config.py                  <- Configura Azure OpenAI
- main.py                    <- Codice principale
- app.py                     <- Interfaccia web Streamlit
- requirements.txt
- modules/
   - mapper.py               <- Mapping intelligente colonne
   - analisi.py              <- Codice di calcoli
   - excel_writer.py         <- Generazione Excel
   - word_writer.py          <- Generazione Word + commenti AI (quando agente attivo)
   - learned_mappings.json   <- (creato automaticamente, impara nel tempo)
- input/                     <- Metti qui i file Excel grezzi
- output/                    <- Report generati
```

---

## Setup

### 1. Installare le librerie
```bash
pip install -r requirements.txt
```

### 2. Configurare Azure OpenAI quando disponibile
Aprire `config.py` e compilare:
```python
AZURE_OPENAI_ENDPOINT = "https://NOME-AZIENDA.openai.azure.com/"
AZURE_OPENAI_API_KEY  = "la-tua-api-key"
AZURE_DEPLOYMENT_NAME = "gpt-4o"
```

> Il sistema funziona anche senza Azure OpenAI configurato.
> In quel caso usa solo il dizionario di sinonimi per il mapping
> e genera i report senza i commenti narrativi AI.

---

## Utilizzo

### Interfaccia web (consigliata)
```bash
streamlit run app.py
```
Apri il browser su http://localhost:8501 se in locale

### Da riga di comando
```bash
python main.py --input input/portafoglio.xlsx -- nome "Fondo Alpha"
```

### Da codice Python
```python
from main import genera_report
genera_report("input/portafoglio.xlsx", nome_portafoglio="Fondo Alpha")
```

---

## Analisi generate automaticamente

| Analisi | Colonne richieste |
|---|---|
| Composizione per Asset Class | fair_value, asset_class |
| Asset Class × Fair Value Level | + fair_value_level |
| Rating Governativi | + rating, tipo_emittente |
| Rating Non Governativi | + rating, tipo_emittente |
| Geografia Governativi | + paese, tipo_emittente |
| Analisi Economica completa | asset_class + cedola/dividendi/PL |
| Top 10 Holdings | fair_value, descrizione |
| Esposizione Valutaria | fair_value, valuta |
| Esposizione Settoriale | fair_value, settore |

---

## Come funziona il mapping

Il sistema riconosce le colonne in 3 passi:
1. **Memoria**: controlla se ha già visto quella colonna (`learned_mappings.json`)
2. **Sinonimi**: confronta con ~60 termini noti del settore finanziario italiano
3. **AI**: chiede a Azure OpenAI per i casi ambigui (se configurato)

Ogni nuovo mapping viene salvato e riusato automaticamente.

---

## Aggiungere nuovi sinonimi

Apri `modules/mapper.py` e aggiungi nel dizionario `SINONIMI`:
```python
"mio termine custom": "campo_canonico",
```

---

## Output generati

- **Excel**: workbook multi-foglio con formattazione professionale, filtri, formattazione condizionale P&L
- **Word**: relazione strutturata con tabelle e commenti narrativi AI per ogni sezione

# Esecuzione

# Comandi da terminale
cd "/Users/vittorioaluigi/Desktop/Progetti 2026/portafoglio_ai" #**da pc**
cd "C:\Users\valuigi\OneDrive - KPMG\Audit and Assurance - Area 1 - AXA Assicurazioni SpA\Documenti\0_Permanent\AXAgpt\AR Investimenti\portafoglio_ai\portafoglio_ai" #**da aziendale**
pip install -r requirements.txt
streamlit run app.py
