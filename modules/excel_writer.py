# =============================================================================
# modules/excel_writer.py — Generazione Excel formattato (stile KPMG)
# =============================================================================

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import pandas as pd
from datetime import datetime

KPMG_BLU = "00338D"
BIANCO = "FFFFFF"
NERO = "000000"
ARIAL = "Arial"
FS = 8
FS_Titoli = 14

def _fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)

def _side(style="thin", color="CCCCCC"):
    return Side(style=style, color=color)

def _border():
    s = _side()
    return Border(left=s, right=s, top=s, bottom=s)

def _num_fmt(divisore):
    return '#,##0.0' if divisore > 1 else '#,##0.00'

def _div(val, divisore):
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return val / divisore
    return val

def _is_perc_col(col_name):
    n = str(col_name).lower()
    return "peso" in n or "var %" in n or col_name == "Var %"

# ---------------------------------------------------------------------------
# SCRIVI FOGLIO ANALISI
# ---------------------------------------------------------------------------

def _scrivi_foglio_analisi(ws, df: pd.DataFrame,
                            nome_analisi: str,
                            unita_label: str,
                            divisore: float):
    """
    Layout:
      B2 = "kpmg"
      B3 = nome analisi
      Riga 5: titolo blu (merge su colonne tabella), testo bianco, altezza 19.5
              contenuto: nome_analisi + \n + unita_label
      Riga 6: intestazioni Arial 8 bold nero no fill, altezza 12
      Riga 7+: dati Arial 8, altezza 12
    """
    ws.sheet_view.showGridLines = False
    n_cols     = len(df.columns)
    start_col  = 2
    end_col    = start_col + n_cols - 1

    # B2 KPMG
    ws.cell(row=2, column=2, value="kpmg").font = Font(
        name="KPMG Logo", size=FS_Titoli, color=KPMG_BLU)

    # B3 nome analisi
    ws.cell(row=3, column=2, value=nome_analisi).font = Font(
        name="KPMG Bold", size=FS_Titoli, color=KPMG_BLU)

    # Riga 5: titolo blu — merge esatto sulle colonne della tabella
    if end_col > start_col:
        ws.merge_cells(
            start_row=5, start_column=start_col,
            end_row=5,   end_column=end_col
        )
    cell_tit = ws.cell(row=5, column=start_col,
                        value=f"{nome_analisi}\n{unita_label}")
    cell_tit.font      = Font(name=ARIAL, size=FS, bold=True, color=BIANCO)
    cell_tit.fill      = _fill(KPMG_BLU)
    cell_tit.alignment = Alignment(horizontal="left", vertical="center",
                                    wrap_text=True)
    ws.row_dimensions[5].height = 19.5

    # Riga 6: intestazioni
    for c_idx, col_name in enumerate(df.columns, start_col):
        cell = ws.cell(row=6, column=c_idx, value=col_name)
        cell.font      = Font(name=ARIAL, size=FS, bold=True, color=NERO)
        cell.fill      = PatternFill(fill_type=None)
        cell.alignment = Alignment(horizontal="center", vertical="center",
                                    wrap_text=True)
        cell.border    = _border()
        ws.column_dimensions[get_column_letter(c_idx)].width = max(12, len(str(col_name)) + 2)
    ws.row_dimensions[6].height = 12

    # Righe dati
    num_fmt = _num_fmt(divisore)
    for r_idx, row in enumerate(df.itertuples(index=False), 7):
        is_tot = str(row[0]).strip().lower() == "totale"
        ws.row_dimensions[r_idx].height = 12

        for c_idx, val in enumerate(row, start_col):
            col_name = df.columns[c_idx - start_col]
            is_perc  = _is_perc_col(col_name)

            # Non dividere percentuali e variazioni %
            display_val = val if is_perc else _div(val, divisore)

            cell = ws.cell(row=r_idx, column=c_idx, value=display_val)
            cell.font   = Font(name=ARIAL, size=FS, bold=is_tot, color=NERO)
            cell.border = _border()

            if isinstance(display_val, (int, float)) and not isinstance(display_val, bool):
                if is_perc:
                    cell.number_format = '0.00'
                    cell.alignment     = Alignment(horizontal="right")
                else:
                    cell.number_format = num_fmt
                    cell.alignment     = Alignment(horizontal="right")
                # Colore P&L
                col_low = str(col_name).lower()
                if any(k in col_low for k in ["realizzo", "valutazione", "variazione", "var %"]):
                    if isinstance(display_val, (int, float)) and not isinstance(display_val, bool):
                        if display_val > 0:
                            cell.fill = _fill("C6EFCE")
                        elif display_val < 0:
                            cell.fill = _fill("FFC7CE")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    ws.column_dimensions["A"].width = 2
    ws.freeze_panes = ws.cell(row=7, column=start_col)


# ---------------------------------------------------------------------------
# GENERAZIONE WORKBOOK
# ---------------------------------------------------------------------------

def genera_excel(dati: dict,
                 nome_portafoglio: str = "Portafoglio",
                 data_report: str = None,
                 unita: str = "€") -> Workbook:

    wb          = Workbook()
    data_report = data_report or datetime.today().strftime("%d/%m/%Y")
    divisori    = {"€": 1, "€ migliaia": 1_000, "€ milioni": 1_000_000}
    divisore    = divisori.get(unita, 1)
    unita_label = f"({unita})"

    # ------------------------------------------------------------------ #
    # 00 SUMMARY                                                         #
    # ------------------------------------------------------------------ #
    ws_r = wb.active
    ws_r.title = "Summary"
    ws_r.sheet_view.showGridLines = False

    ws_r.cell(row=2, column=2, value="kpmg").font = Font(
        name="KPMG Logo", size=FS_Titoli, color=KPMG_BLU)
    ws_r.cell(row=3, column=2, value=nome_portafoglio).font = Font(
        name="KPMG Bold", size=FS_Titoli, color=KPMG_BLU)

    ws_r.merge_cells("B5:E5")
    c = ws_r.cell(row=5, column=2,
                  value=f"Riepilogo Portafoglio\n{data_report} — {unita_label}")
    c.font      = Font(name=ARIAL, size=FS, bold=True, color=BIANCO)
    c.fill      = _fill(KPMG_BLU)
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    ws_r.row_dimensions[5].height = 19.5

    # Intestazioni KPI
    hdrs = ["Indicatore", "N", "N-1", "Variazione"]
    for i, h in enumerate(hdrs, 2):
        cell = ws_r.cell(row=6, column=i, value=h)
        cell.font   = Font(name=ARIAL, size=FS, bold=True, color=NERO)
        cell.border = _border()
    ws_r.row_dimensions[6].height = 12

    if "kpi" in dati and dati["kpi"]:
        kpi = dati["kpi"]
        num_fmt = _num_fmt(divisore)
        rows_kpi = [
            ("NAV Totale", kpi.get("nav"), kpi.get("nav_prev"), kpi.get("var_nav")),
            ("N° Titoli", kpi.get("n_titoli"), None, None),
            ("P&L Totale", kpi.get("pl_totale"), None, None),
            ("Proventi", kpi.get("proventi"), None, None),
            ("Rendimento %", kpi.get("rendimento_%"), None, None),
        ]
        for i, (label, n, n1, var) in enumerate(rows_kpi, 7):
            ws_r.row_dimensions[i].height = 12
            ws_r.cell(row=i, column=2, value=label).font = Font(name=ARIAL, size=FS)
            ws_r.cell(row=i, column=2).border = _border()
            for col_idx, val in enumerate([n, n1, var], 3):
                display = None
                if val is not None:
                    if label in ("N° Titoli", "Rendimento %"):
                        display = val
                    else:
                        display = _div(val, divisore)
                cell = ws_r.cell(row=i, column=col_idx, value=display)
                cell.font = Font(name=ARIAL, size=FS)
                cell.border = _border()
                cell.alignment = Alignment(horizontal="right")
                if label == "N° Titoli":
                    cell.number_format = '0'
                elif label == "Rendimento %":
                    cell.number_format = '0.00"%"'
                else:
                    cell.number_format = num_fmt

    for col, w in [("A",2),("B",26),("C",16),("D",16),("E",16)]:
        ws_r.column_dimensions[col].width = w

    # ------------------------------------------------------------------ #
    # FOGLI ANALISI                                                        #
    # ------------------------------------------------------------------ #
    config_fogli = [
        ("patrimoniale_asset_class", "AssetClass", "Composizione per Asset Class"),
        ("patrimoniale_fv_level", "FVLevel", "Asset Class per Fair Value Level"),
        ("rating_governativi", "Rating_Gov", "Rating – Titoli Governativi"),
        ("rating_non_governativi", "Rating_NonGov", "Rating – Titoli Non Governativi"),
        ("geografia_governativi", "Geografia_Gov", "Distribuzione Geografica Governativi"),
        ("economica_completa", "Economica", "Analisi Economica per Asset Class"),
        ("top_holdings", "Top10_Holdings", "Top 10 Holdings per Fair Value"),
        ("esposizione_valutaria", "Valute", "Esposizione Valutaria"),
        ("esposizione_settoriale", "Settori", "Esposizione Settoriale"),
    ]

    for chiave, nome_foglio, nome_analisi in config_fogli:
        if chiave not in dati or dati[chiave] is None:
            continue
        df = dati[chiave]
        if isinstance(df, pd.DataFrame) and df.empty:
            continue
        ws = wb.create_sheet(title=nome_foglio)
        _scrivi_foglio_analisi(ws, df,
                                nome_analisi=nome_analisi,
                                unita_label=unita_label,
                                divisore=divisore)

    # ------------------------------------------------------------------ #
    # 99 DETTAGLIO COMPLETO (invariato)                                    #
    # ------------------------------------------------------------------ #
    if "dettaglio" in dati and dati["dettaglio"] is not None:
        ws_det = wb.create_sheet(title="99_Dettaglio")
        ws_det.sheet_view.showGridLines = False

        ETICHETTE = {
            "isin": "ISIN", "descrizione": "Descrizione", "asset_class": "Asset Class",
            "quantita": "Quantità", "prezzo_carico": "Prezzo Carico",
            "fair_value": "Fair Value N", "fair_value_prev": "Fair Value N-1",
            "tipo_emittente": "Tipo Emittente", "rating": "Rating",
            "paese": "Paese", "valuta": "Valuta", "settore": "Settore",
            "cedola": "Interessi N", "cedola_prev": "Interessi N-1",
            "dividendi": "Dividendi N", "dividendi_prev": "Dividendi N-1",
            "pl_realizzo": "PL Realizzo N", "pl_realizzo_prev": "PL Realizzo N-1",
            "pl_valutazione": "PL Valutazione N", "pl_valutazione_prev": "PL Valutazione N-1",
            "data_acquisto": "Data Acquisto", "scadenza": "Scadenza",
        }
        df_det = dati["dettaglio"].rename(columns=ETICHETTE)

        for c_idx, col_name in enumerate(df_det.columns, 1):
            cell = ws_det.cell(row=1, column=c_idx, value=col_name)
            cell.font      = Font(name=ARIAL, size=FS, bold=True)
            cell.border    = _border()
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
            ws_det.column_dimensions[get_column_letter(c_idx)].width = 16
        ws_det.row_dimensions[1].height = 12
        ws_det.auto_filter.ref = f"A1:{get_column_letter(len(df_det.columns))}1"
        ws_det.freeze_panes    = "A2"

        for r_idx, row in enumerate(df_det.itertuples(index=False), 2):
            ws_det.row_dimensions[r_idx].height = 12
            for c_idx, val in enumerate(row, 1):
                cell        = ws_det.cell(row=r_idx, column=c_idx, value=val)
                cell.font   = Font(name=ARIAL, size=FS)
                cell.border = _border()

    return wb


def salva_excel(wb: Workbook, path: str):
    wb.save(path)
    print(f"[OK] Excel salvato: {path}")
