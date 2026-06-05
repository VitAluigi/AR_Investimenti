# =============================================================================
# modules/analisi.py
# =============================================================================

import pandas as pd
import numpy as np
from config import ANALISI_REQUISITI

# 1. Capability Discovery
def scopri_analisi(df: pd.DataFrame) -> dict:
    colonne = set(df.columns.tolist())
    risultato = {}
    for nome, requisiti in ANALISI_REQUISITI.items():
        if nome == "economica_completa":
            voci = ["cedola", "dividendi", "pl_realizzo", "pl_valutazione", "pl_totale_db"]
            risultato[nome] = (
                "asset_class" in colonne and any(v in colonne for v in voci)
            )
        elif nome == "effetti_tx_top20":
            risultato[nome] = (
                "fair_value" in colonne and "asset_class" in colonne
            )
        elif nome == "oci_per_asset_class":
            risultato[nome] = (
                "oci_lc" in colonne and
                "asset_class" in colonne and
                df["oci_lc"].notna().any() and
                df["oci_lc"].abs().sum() > 0
            )
        else:
            risultato[nome] = all(r in colonne for r in requisiti)
    return risultato

def report_analisi(disponibili: dict) -> str:
    attive   = [n for n, v in disponibili.items() if v]
    inattive = [n for n, v in disponibili.items() if not v]
    lines = [f"Analisi disponibili ({len(attive)}/{len(disponibili)}):"]
    for a in attive: lines.append(f" OK {a}")
    for i in inattive: lines.append(f" KO {i}")
    return "\n".join(lines)

# 2. Helpers
def _sum(df, col):
    if col in df.columns:
        return float(np.nansum(df[col].values))
    return 0.0

def _var_pct(n, n1):
    """
    Calcola variazione % con gestione casi speciali:
    - N esiste, N-1 assente/zero  -> "+100%"
    - N-1 esiste, N assente/zero  -> "-100%"
    - Variazione > +100%          -> ">100%"
    - Variazione < -100%          -> "<-100%"
    """
    import math
    n_ok  = n  is not None and not (isinstance(n, float) and math.isnan(n))  and n  != 0
    n1_ok = n1 is not None and not (isinstance(n1, float) and math.isnan(n1)) and n1 != 0

    if n_ok and not n1_ok:
        return "+100%"
    if n1_ok and not n_ok:
        return "-100%"
    if not n_ok and not n1_ok:
        return None

    var = round((n - n1) / abs(n1) * 100, 2)
    if var > 100:
        return ">100%"
    if var < -100:
        return "<-100%"
    return var

def _build_confronto(df_base: pd.DataFrame,
                     col_label: str,
                     col_n: str,
                     col_n1: str = None) -> pd.DataFrame:
    label_display = col_label.replace("_", " ").title()

    agg = df_base.groupby(col_label, dropna=False)[col_n].sum().reset_index()
    agg.columns = [label_display, "N"]
    tot_n = agg["N"].sum()
    agg["Peso %"] = (agg["N"] / tot_n * 100).round(2) if tot_n else 0

    if col_n1 and col_n1 in df_base.columns:
        agg_prev = df_base.groupby(col_label, dropna=False)[col_n1].sum().reset_index()
        agg_prev.columns = [label_display, "N-1"]
        agg = agg.merge(agg_prev, on=label_display, how="left")
        agg["Variazione"] = (agg["N"] - agg["N-1"]).round(2)
        agg["Var %"] = agg.apply(lambda r: _var_pct(r["N"], r["N-1"]), axis=1)
        tot_n1 = agg["N-1"].sum()
    else:
        agg["N-1"] = agg["Variazione"] = agg["Var %"] = None
        tot_n1 = None

    agg = agg.sort_values("N", ascending=False)
    totale = {
        label_display: "Totale",
        "N": tot_n,
        "Peso %": 100.0,
        "N-1": tot_n1,
        "Variazione": round(tot_n - tot_n1, 2) if tot_n1 is not None else None,
        "Var %": _var_pct(tot_n, tot_n1),
    }
    return pd.concat([agg, pd.DataFrame([totale])], ignore_index=True)

# 3. Analisi Patrimoniale
def patrimoniale_asset_class(df: pd.DataFrame) -> pd.DataFrame:
    return _build_confronto(df, "asset_class", "book_value", "book_value_prev")

def patrimoniale_fv_level(df: pd.DataFrame) -> pd.DataFrame:
    def _pivot(col_val, suffix):
        p = df.pivot_table(
            index="asset_class", columns="fair_value_level",
            values=col_val, aggfunc="sum", fill_value=0,
        )
        p.columns = [f"Level {c} {suffix}" for c in p.columns]
        return p

    pivot_n = _pivot("book_value", "N")
    result  = pivot_n.copy()
    if "book_value_prev" in df.columns:
        result = pd.concat([pivot_n, _pivot("book_value_prev", "N-1")], axis=1)

    result["Totale N"] = pivot_n.sum(axis=1)
    result.index.name  = "Asset Class"
    result = result.reset_index()
    tot = result.select_dtypes("number").sum()
    tot["Asset Class"] = "Totale"
    return pd.concat([result, pd.DataFrame([tot])], ignore_index=True)


def rating_per_emittente(df: pd.DataFrame, tipo: str) -> pd.DataFrame:
    if tipo == "gov":
        mask = df["tipo_emittente"].str.lower().str.startswith("gov")
    else:
        mask = df["tipo_emittente"].str.lower().str.contains("non_gov", na=False)
    sub = df[mask]
    if sub.empty:
        return pd.DataFrame(columns=["rating", "N", "Peso %", "N-1", "Variazione", "Var %"])

    result = _build_confronto(sub, "rating", "book_value", "book_value_prev")

    ordine = ["AAA","AA+","AA","AA-","A+","A","A-","BBB+","BBB","BBB-",
              "BB+","BB","BB-","B+","B","B-","NR","N.R.","n.r."]
    label_col = result.columns[0]
    non_tot = result[result[label_col] != "Totale"].copy()
    tot_row = result[result[label_col] == "Totale"]
    non_tot["_ord"] = non_tot[label_col].apply(
        lambda x: ordine.index(str(x)) if str(x) in ordine else 999)
    non_tot = non_tot.sort_values("_ord").drop(columns=["_ord"])
    return pd.concat([non_tot, tot_row], ignore_index=True)

def geografia_governativi(df: pd.DataFrame) -> pd.DataFrame:
    mask = df["tipo_emittente"].str.lower().str.startswith("gov")
    return _build_confronto(df[mask], "paese", "book_value", "book_value_prev")

def confronto_bv_fv(df: pd.DataFrame) -> pd.DataFrame:
    """Confronto Book Value vs Fair Value di mercato per asset class."""
    result = df.groupby("asset_class", dropna=False).agg(
        bv=("book_value", "sum"),
        fv=("fair_value",  "sum"),
    ).reset_index()
    result.columns = ["Asset Class", "Book Value N", "Fair Value N"]
    result["Differenza"] = (result["Fair Value N"] - result["Book Value N"]).round(2)
    result["Diff %"] = result.apply(
        lambda r: _var_pct(r["Fair Value N"], r["Book Value N"]), axis=1)
    result = result.sort_values("Book Value N", ascending=False)
    tot = result.select_dtypes("number").sum()
    tot["Asset Class"] = "Totale"
    tot["Diff %"] = _var_pct(tot["Fair Value N"], tot["Book Value N"])
    return pd.concat([result, pd.DataFrame([tot])], ignore_index=True)

# 4. Analisi Economica
def economica_completa(df: pd.DataFrame) -> pd.DataFrame:
    voci = [
        ("Cedole/Int. N", "cedola"),
        ("Dividendi N", "dividendi"),
        ("PL Realizzo N", "pl_realizzo"),
        ("PL Valutazione N", "pl_valutazione"),
        ("ECL N", "ecl_lc"),
    ]
    voci_prev = [
        ("Cedole/Int. N-1", "cedola_prev"),
        ("Dividendi N-1", "dividendi_prev"),
        ("PL Realizzo N-1", "pl_realizzo_prev"),
        ("PL Valutazione N-1", "pl_valutazione_prev"),
        ("ECL N-1", "ecl_lc_prev"),
    ]

    agg_n = {label: pd.NamedAgg(column=col, aggfunc="sum")
             for label, col in voci if col in df.columns}
    agg_p = {label: pd.NamedAgg(column=col, aggfunc="sum")
             for label, col in voci_prev if col in df.columns}

    if "pl_totale_db" in df.columns:
        agg_n["PL Totale N"] = pd.NamedAgg(column="pl_totale_db", aggfunc="sum")
    if "pl_totale_db_prev" in df.columns:
        agg_p["PL Totale N-1"] = pd.NamedAgg(column="pl_totale_db_prev", aggfunc="sum")

    result = df.groupby("asset_class", dropna=False).agg(**{**agg_n, **agg_p}).reset_index()
    result = result.rename(columns={"asset_class": "Asset Class"})

    cols_n  = [l for l, _ in voci if l in result.columns]
    cols_n1 = [l for l, _ in voci_prev if l in result.columns]

    if "PL Totale N" in result.columns:
        result["Totale N"] = result["PL Totale N"]
    elif cols_n:
        result["Totale N"] = result[cols_n].sum(axis=1)

    if "PL Totale N-1" in result.columns:
        result["Totale N-1"] = result["PL Totale N-1"]
    elif cols_n1:
        result["Totale N-1"] = result[cols_n1].sum(axis=1)

    if "Totale N-1" in result.columns:
        result["Variazione"] = result["Totale N"] - result["Totale N-1"]
        result["Var %"] = result.apply(
            lambda r: _var_pct(r["Totale N"], r["Totale N-1"]), axis=1)

    num_cols = result.select_dtypes("number").columns.tolist()
    tot = result[num_cols].sum()
    tot["Asset Class"] = "Totale"
    if "Totale N-1" in result.columns:
        tot["Var %"] = _var_pct(tot["Totale N"], tot.get("Totale N-1"))
    return pd.concat([result, pd.DataFrame([tot])], ignore_index=True)

# 5. Analisi Aggiuntive
def top_holdings(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    cols = ["descrizione", "book_value"]
    if "asset_class" in df.columns: cols.insert(1, "asset_class")
    if "isin"  in df.columns: cols.insert(0, "isin")
    if "book_value_prev" in df.columns: cols.append("book_value_prev")

    result = (df[cols].copy()
              .sort_values("book_value", ascending=False)
              .head(n).reset_index(drop=True))

    tot = df["book_value"].sum()
    result["Peso %"] = (result["book_value"] / tot * 100).round(2)

    if "book_value_prev" in result.columns:
        result["Variazione"] = result["book_value"] - result["book_value_prev"]
        result["Var %"] = result.apply(
            lambda r: _var_pct(r["book_value"], r["book_value_prev"]), axis=1)
        result = result.rename(columns={"book_value": "N", "book_value_prev": "N-1"})
    else:
        result = result.rename(columns={"book_value": "N"})

    result.index = result.index + 1
    result.index.name = "Rank"
    return result.rename(columns={
        "isin": "ISIN", "descrizione": "Descrizione", "asset_class": "Asset Class"})

def esposizione_valutaria(df: pd.DataFrame) -> pd.DataFrame:
    return _build_confronto(df, "valuta", "book_value", "book_value_prev")

def esposizione_settoriale(df: pd.DataFrame) -> pd.DataFrame:
    return _build_confronto(df, "settore", "book_value", "book_value_prev")

def oci_per_asset_class(df: pd.DataFrame) -> pd.DataFrame:
    """
    Analisi Riserva OCI per asset class.
    Fonte: colonna oci_lc dall'Inventory.
    OCI N, OCI N-1 e variazione per asset class.
    """
    result = _build_confronto(df, "asset_class", "oci_lc", "oci_lc_prev")

    # OCI w/o Recycling se disponibile
    if "oci_no_recycling_lc" in df.columns:
        agg_no_rec = df.groupby("asset_class", dropna=False)[
            "oci_no_recycling_lc"].sum().reset_index()
        agg_no_rec.columns = ["Asset Class", "OCI w/o Recycl. N"]
        label_col = result.columns[0]
        result = result.rename(columns={label_col: "Asset Class"})
        result = result.merge(agg_no_rec, on="Asset Class", how="left")

    return result

def composizione_valuation_class(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot asset_class * valuation_class -> Book Value N.
    """
    if "valuation_class" not in df.columns or "asset_class" not in df.columns:
        return pd.DataFrame()

    # Pivot: righe = asset_class, colonne = valuation_class
    pivot = df.pivot_table(
        index="asset_class",
        columns="valuation_class",
        values="book_value",
        aggfunc="sum",
        fill_value=0,
    )
    pivot.index.name = "Asset Class"
    pivot.columns.name = None

    # Colonna totale
    pivot["Totale"] = pivot.sum(axis=1)

    # Riga totale
    tot = pivot.sum(axis=0)
    tot.name = "Totale"
    pivot = pd.concat([pivot, tot.to_frame().T])

    # Peso % su totale portafoglio
    tot_ptf = pivot.loc["Totale", "Totale"]
    pivot["Peso %"] = (pivot["Totale"] / tot_ptf * 100).round(2) if tot_ptf else 0

    return pivot.reset_index()

def scadenze_bucket(df: pd.DataFrame) -> pd.DataFrame:
    """
    Distribuzione del Book Value per bucket di scadenza.
    Considera solo i titoli con scadenza valorizzata (esclusione di Azioni, Fondi ecc.).
    Bucket: 0-1, 1-3, 3-5, 5-10, 10-20, 20-30, >30 anni.
    """
    BUCKET_ORDER = ["0-1 anni", "1-3 anni", "3-5 anni",
                    "5-10 anni", "10-20 anni", "20-30 anni", ">30 anni"]
    PERPETUAL = "Perpetual"

    oggi = pd.Timestamp.today().normalize()

    def _bucket(scad):
        if pd.isna(scad):
            return None
        try:
            scad = pd.Timestamp(scad)
        except Exception:
            return None
        anni = (scad - oggi).days / 365.25
        if anni < 0: return "Scaduto"
        if anni <= 1: return "0-1 anni"
        if anni <= 3: return "1-3 anni"
        if anni <= 5: return "3-5 anni"
        if anni <= 10: return "5-10 anni"
        if anni <= 20: return "10-20 anni"
        if anni <= 30: return "20-30 anni"
        return ">30 anni"

    df = df.copy()
    df["_bucket"] = df["scadenza"].apply(_bucket)

    df_filt = df[df["_bucket"].notna()].copy()
    if df_filt.empty:
        return pd.DataFrame(columns=["Bucket", "N", "Peso %", "N-1", "Variazione", "Var %"])

    agg = df_filt.groupby("_bucket")["book_value"].sum().reset_index()
    agg.columns = ["Bucket", "N"]
    tot_n = agg["N"].sum()
    agg["Peso %"] = (agg["N"] / tot_n * 100).round(2) if tot_n else 0

    # N-1
    if "book_value_prev" in df.columns:
        agg_prev = df_filt.groupby("_bucket")["book_value_prev"].sum().reset_index()
        agg_prev.columns = ["Bucket", "N-1"]
        agg = agg.merge(agg_prev, on="Bucket", how="left")
        agg["Variazione"] = (agg["N"] - agg["N-1"]).round(2)
        agg["Var %"] = agg.apply(lambda r: _var_pct(r["N"], r["N-1"]), axis=1)
        tot_n1 = agg["N-1"].sum()
    else:
        agg["N-1"] = agg["Variazione"] = agg["Var %"] = None
        tot_n1 = None

    # Ordina per bucket logico
    order_map = {b: i for i, b in enumerate(BUCKET_ORDER)}
    agg["_ord"] = agg["Bucket"].map(lambda x: order_map.get(x, 99))
    agg = agg.sort_values("_ord").drop(columns=["_ord"])

    totale = {
        "Bucket": "Totale",
        "N": tot_n,
        "Peso %": 100.0,
        "N-1": tot_n1,
        "Variazione": round(tot_n - tot_n1, 2) if tot_n1 is not None else None,
        "Var %": _var_pct(tot_n, tot_n1),
    }
    return pd.concat([agg, pd.DataFrame([totale])], ignore_index=True)


def duration_ponderata(df: pd.DataFrame) -> pd.DataFrame:
    """
    Duration media ponderata per Book Value, aggregata per asset class.
    Duration ponderata = sum(BV_i * dur_i) / sum(BV_i)
    """
    df = df.copy()
    df_filt = df[df["modified_duration"].notna() & df["book_value"].notna()].copy()
    if df_filt.empty:
        return pd.DataFrame(columns=["Asset Class", "Dur. Ponderata N",
                                      "Book Value N", "Dur. Ponderata N-1"])

    df_filt["_bv_dur"] = df_filt["book_value"] * df_filt["modified_duration"]

    agg = df_filt.groupby("asset_class", dropna=False).agg(
        bv_sum =("book_value", "sum"),
        bv_dur =("_bv_dur", "sum"),
    ).reset_index()
    agg.columns = ["Asset Class", "Book Value N", "_bv_dur"]
    agg["Dur. Ponderata N"] = (agg["_bv_dur"] / agg["Book Value N"]).round(3)
    agg = agg.drop(columns=["_bv_dur"])

    # N-1
    if "book_value_prev" in df.columns and "modified_duration" in df.columns:
        df_filt_n1 = df[df["modified_duration"].notna() & df["book_value_prev"].notna()].copy()
        if not df_filt_n1.empty:
            df_filt_n1["_bv_dur_prev"] = df_filt_n1["book_value_prev"] * df_filt_n1["modified_duration"]
            agg_prev = df_filt_n1.groupby("asset_class", dropna=False).agg(
                bv_prev=("book_value_prev", "sum"),
                bv_dur_prev=("_bv_dur_prev", "sum"),
            ).reset_index()
            agg_prev.columns = ["Asset Class", "_bv_prev", "_bv_dur_prev"]
            agg_prev["Dur. Ponderata N-1"] = (agg_prev["_bv_dur_prev"] / agg_prev["_bv_prev"]).round(3)
            agg_prev = agg_prev[["Asset Class", "Dur. Ponderata N-1"]]
            agg = agg.merge(agg_prev, on="Asset Class", how="left")

    agg = agg.sort_values("Book Value N", ascending=False)

    # Riga totale - duration ponderata sull'intero portafoglio
    tot_bv  = df_filt["book_value"].sum()
    tot_dur = df_filt["_bv_dur"].sum()
    tot_row = {"Asset Class": "Totale", "Book Value N": tot_bv,
               "Dur. Ponderata N": round(tot_dur / tot_bv, 3) if tot_bv else None}
    if "Dur. Ponderata N-1" in agg.columns:
        if not df_filt_n1.empty:
            tot_bv_n1  = df_filt_n1["book_value_prev"].sum()
            tot_dur_n1 = df_filt_n1["_bv_dur_prev"].sum()
            tot_row["Dur. Ponderata N-1"] = round(tot_dur_n1 / tot_bv_n1, 3) if tot_bv_n1 else None

    return pd.concat([agg, pd.DataFrame([tot_row])], ignore_index=True)

def sensitivity_tassi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Stress test tasso di interesse con approssimazione di Taylor al 2° ordine.

    Formula:
        Delta_P = BV * (−D_mod × Delta_y + ½ * C * Delta_y^2)

    dove Delta_y è lo shift parallelo della curva dei tassi.
    D_mod e C sono pesati per Book Value per asset class.

    Shift testati: −200bp, −100bp, −50bp, +50bp, +100bp, +200bp
    """
    SHIFTS_BP  = [-200, -100, -50, +50, +100, +200]
    SHIFTS_DY  = [s / 10000 for s in SHIFTS_BP]
    SHIFT_LBLS = [f"{'+' if s>0 else ''}{s}bp" for s in SHIFTS_BP]

    # Filtra solo titoli con duration e book_value valorizzati
    df = df.copy()
    mask = df["modified_duration"].notna() & df["book_value"].notna()
    df_filt = df[mask].copy()

    if df_filt.empty:
        return pd.DataFrame()

    # Convexity: se disponibile, altrimenti stima D^2 + D (appross. bond bullet)
    if "convexity" in df_filt.columns and df_filt["convexity"].notna().any():
        df_filt["_conv"] = df_filt["convexity"].fillna(
            df_filt["modified_duration"]**2 + df_filt["modified_duration"]
        )
    else:
        df_filt["_conv"] = (df_filt["modified_duration"]**2 +
                            df_filt["modified_duration"])

    # Duration e Convexity ponderate per asset class
    agg = df_filt.groupby("asset_class", dropna=False).apply(
        lambda g: pd.Series({
            "BV":       g["book_value"].sum(),
            "D_pond":   (g["book_value"] * g["modified_duration"]).sum() / g["book_value"].sum(),
            "C_pond":   (g["book_value"] * g["_conv"]).sum() / g["book_value"].sum(),
        })
    ).reset_index()

    # Totale portafoglio
    tot_bv   = df_filt["book_value"].sum()
    tot_dpond = (df_filt["book_value"] * df_filt["modified_duration"]).sum() / tot_bv
    tot_cpond = (df_filt["book_value"] * df_filt["_conv"]).sum() / tot_bv
    tot_row  = pd.DataFrame([{
        "asset_class": "Totale",
        "BV": tot_bv,
        "D_pond": tot_dpond,
        "C_pond": tot_cpond,
    }])
    agg = pd.concat([agg, tot_row], ignore_index=True)

    # Calcola Delta_P per ogni shift
    for lbl, dy in zip(SHIFT_LBLS, SHIFTS_DY):
        agg[f"Delta_P {lbl} (€)"] = (
            agg["BV"] * (-agg["D_pond"] * dy + 0.5 * agg["C_pond"] * dy**2)
        ).round(2)
        agg[f"Delta_P {lbl} (%)"] = (
            (-agg["D_pond"] * dy + 0.5 * agg["C_pond"] * dy**2) * 100
        ).round(4)

    # Rinomina colonne espositive
    agg = agg.rename(columns={
        "asset_class": "Asset Class",
        "BV":          "Book Value",
        "D_pond":      "Dur. Pond.",
        "C_pond":      "Conv. Pond.",
    })

    # Arrotonda duration e convexity
    agg["Dur. Pond."]  = agg["Dur. Pond."].round(3)
    agg["Conv. Pond."] = agg["Conv. Pond."].round(3)

    return agg

def kpi_portafoglio(df: pd.DataFrame) -> dict:
    # N
    nav = _sum(df, "book_value")
    nav_prev = _sum(df, "book_value_prev")
    n_titoli = int(df["isin"].nunique()) if "isin" in df.columns else len(df)

    if "pl_totale_db" in df.columns:
        pl_tot = _sum(df, "pl_totale_db")
    else:
        pl_tot = _sum(df, "pl_realizzo") + _sum(df, "pl_valutazione")

    proventi = _sum(df, "cedola") + _sum(df, "dividendi")
    pl_realizzo = _sum(df, "pl_realizzo")

    # N-1
    if "book_value_prev" in df.columns and "isin" in df.columns:
        n_titoli_prev = int(df[df["book_value_prev"].notna()]["isin"].nunique())
    else:
        n_titoli_prev = None

    if "pl_totale_db_prev" in df.columns:
        pl_tot_prev = _sum(df, "pl_totale_db_prev") or None
    else:
        v = _sum(df, "pl_realizzo_prev") + _sum(df, "pl_valutazione_prev")
        pl_tot_prev = v if v != 0 else None

    proventi_prev = _sum(df, "cedola_prev") + _sum(df, "dividendi_prev")
    pl_rea_prev = _sum(df, "pl_realizzo_prev")
    rend_prev  = round((proventi_prev + pl_rea_prev) / nav_prev * 100, 2) if nav_prev and nav_prev > 0 else None

    return {
        "nav": nav,
        "nav_prev": nav_prev,
        "n_titoli": n_titoli,
        "n_titoli_prev": n_titoli_prev,
        "pl_totale": pl_tot,
        "pl_totale_prev": pl_tot_prev,
        "proventi": proventi,
        "proventi_prev": proventi_prev if proventi_prev else None,
        "rendimento_%": round((proventi + pl_realizzo) / nav * 100, 2) if nav > 0 else None,
        "rendimento_%_prev": rend_prev,
        "var_nav": round(nav - nav_prev, 2) if nav_prev else None,
        "var_nav_%": _var_pct(nav, nav_prev),
    }

# 6. Top Operazioni da Transaction Report
_TX_COL_MAP = {
    "position value date":"data",
    "business transaction category name": "tipo",
    "isin code": "isin",
    "security id name": "descrizione",
    "product category name": "asset_class",
    "nominal/units": "nominale",
    "transaction amount lc": "importo_lc",
    "transaction amount pc": "importo_pc",
    "realised gain loss security lc": "pl_titolo_lc",
    "realised gain loss security pc": "pl_titolo_pc",
    "realised gain loss fx lc": "pl_cambio_lc",
    "realised gain loss lc": "pl_totale_lc",
    "issue currency": "valuta",
    "counterparty name": "controparte",
    "operation price pc": "prezzo",
}

_TX_TIPI_RILEVANTI = {"sale", "purchase"}

def top_operazioni(df_tx: pd.DataFrame, n: int = 20) -> pd.DataFrame | None:
    if df_tx is None or df_tx.empty:
        return None

    df = df_tx.copy()
    df.columns = df.columns.str.strip().str.lower()
    rename = {k: v for k, v in _TX_COL_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    if "tipo" not in df.columns:
        return None
    df = df[df["tipo"].str.strip().str.lower().isin(_TX_TIPI_RILEVANTI)].copy()
    if df.empty:
        return None

    if "importo_lc" in df.columns:
        df["_abs"] = df["importo_lc"].abs()
        df = df.sort_values("_abs", ascending=False).drop(columns=["_abs"])

    df = df.head(n).reset_index(drop=True)
    df.index = df.index + 1
    df.index.name = "Rank"

    cols_out = [c for c in [
        "data", "tipo", "isin", "descrizione", "asset_class",
        "valuta", "nominale", "prezzo",
        "importo_lc", "importo_pc",
        "pl_titolo_lc", "pl_titolo_pc",
        "pl_cambio_lc", "pl_totale_lc",
        "controparte",
    ] if c in df.columns]
    df = df[cols_out]

    etichette = {
        "data": "Data",
        "tipo": "Tipo",
        "isin": "ISIN",
        "descrizione": "Titolo",
        "asset_class": "Asset Class",
        "valuta": "Valuta",
        "nominale": "Nominale",
        "prezzo": "Prezzo",
        "importo_lc": "Importo LC",
        "importo_pc": "Importo PC",
        "pl_titolo_lc":"P/L Titolo LC",
        "pl_titolo_pc":"P/L Titolo PC",
        "pl_cambio_lc":"P/L Cambio LC",
        "pl_totale_lc":"P/L Totale LC",
        "controparte": "Controparte",
    }
    return df.rename(columns=etichette)

# Analisi Effetti da Inventory e Transaction Report Top 20
def analisi_effetti_inventory(df: pd.DataFrame) -> pd.DataFrame:
    """
    Decomposizione esatta FV_N − FV_N1 per asset class usando Inventory n ed Inventory n-1.

    Chiave: (valuation_area, company_name, portfolio_name, security_account_group, isin)

    Per ogni riga:
      P_FV_N1 = fair_value_prev / quantita_prev (prezzo FV unitario N-1)
      P_FV_N = fair_value / quantita (prezzo FV unitario N)
      Eff_Nom = Delta_Q × P_FV_N1 (variazione esposizione a prezzi N-1)
      Eff_Mkt = Q_N × (P_FV_N − P_FV_N1) (rivalutazione sulla posizione finale)
      Check: Eff_Nom + Eff_Mkt = FV_N − FV_N1

    Aggregato per asset class con totali e check.
    """
    if "fair_value" not in df.columns or "quantita" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    has_prev = ("fair_value_prev" in df.columns and "quantita_prev" in df.columns)

    if not has_prev:
        return pd.DataFrame()

    # Prezzi unitari FV
    df["_p_fv_n"] = (df["fair_value"] / df["quantita"].replace(0, np.nan)).fillna(0)
    df["_p_fv_n1"] = (df["fair_value_prev"] / df["quantita_prev"].replace(0, np.nan)).fillna(0)

    # Quantità
    df["_q_n"] = df["quantita"].fillna(0)
    df["_q_n1"] = df["quantita_prev"].fillna(0)
    df["_fv_n"] = df["fair_value"].fillna(0)
    df["_fv_n1"] = df["fair_value_prev"].fillna(0)

    # Effetti a livello riga
    df["_delta_q"] = df["_q_n"] - df["_q_n1"]
    df["_eff_nom"] = df["_delta_q"] * df["_p_fv_n1"]
    df["_eff_mkt"] = df["_q_n"] * (df["_p_fv_n"] - df["_p_fv_n1"])
    df["_delta_fv"] = df["_fv_n"] - df["_fv_n1"]

    # Aggrega per asset class
    agg = df.groupby("asset_class", dropna=False).agg(
        fv_n1 = ("_fv_n1",   "sum"),
        fv_n = ("_fv_n",    "sum"),
        eff_nom = ("_eff_nom", "sum"),
        eff_mkt = ("_eff_mkt", "sum"),
        delta_fv = ("_delta_fv","sum"),
    ).reset_index()

    agg = agg.rename(columns={"asset_class": "Asset Class"})
    agg["Somma Effetti"] = agg["eff_nom"] + agg["eff_mkt"]
    agg["Check (Somma−Delta FV)"]  = (agg["Somma Effetti"] - agg["delta_fv"]).round(0)

    agg = agg.rename(columns={
        "fv_n1": "FV N-1",
        "fv_n": "FV N",
        "eff_nom": "Eff. Nominale",
        "eff_mkt": "Eff. Mercato",
        "delta_fv": "Delta FV (N−N1)",
    })
    agg = agg.sort_values("FV N", ascending=False)

    # Riga totale
    tot = agg.select_dtypes("number").sum()
    tot["Asset Class"] = "Totale"
    tot["Check (Somma−Delta FV)"] = round(tot["Somma Effetti"] - tot["Delta FV (N−N1)"], 0)
    result = pd.concat([agg, pd.DataFrame([tot])], ignore_index=True)

    # Drop colonne interne
    for col in ["_p_fv_n","_p_fv_n1","_q_n","_q_n1","_fv_n","_fv_n1",
                "_delta_q","_eff_nom","_eff_mkt","_delta_fv"]:
        if col in df.columns: df.drop(columns=[col], inplace=True)

    return result[["Asset Class","FV N-1","FV N","Delta FV (N−N1)",
                   "Eff. Nominale","Eff. Mercato","Somma Effetti","Check (Somma−Delta FV)"]]


def analisi_effetti_tx_top20(df_tx: pd.DataFrame,
                              df_ptf: pd.DataFrame,
                              n: int = 20) -> pd.DataFrame | None:
    """
    Top N operazioni per effetto totale |Eff_Nom + Eff_Mkt| con decomposizione
    attributiva per singola transazione.

    P_prev per la prima operazione dell'ISIN = P_FV_N1 (fair value unitario N-1)
    P_prev per operazioni successive = P_tx dell'operazione precedente

    Eff_Nom_tx = Delta Q × P_prev (esposizione aggiunta/rimossa a prezzi precedenti)
    Eff_Mkt_tx = Delta Q × (P_FV_N − P_tx) (rivalutazione di mercato sulle unità dell'op.)
    """
    if df_tx is None or df_tx.empty or df_ptf is None or df_ptf.empty:
        return None

    # Prezzi di riferimento da df_ptf
    ptf = df_ptf.copy()
    has_fv_prev = "fair_value_prev" in ptf.columns
    has_q_prev = "quantita_prev" in ptf.columns
    has_fv_n = "fair_value" in ptf.columns
    has_q_n = "quantita" in ptf.columns

    if not (has_fv_n and has_q_n and "isin" in ptf.columns):
        return None

    agg_cols = {}
    if has_fv_prev and has_q_prev:
        agg_cols.update({"fair_value_prev":"sum","quantita_prev":"sum"})
    if has_fv_n and has_q_n:
        agg_cols.update({"fair_value":"sum","quantita":"sum"})

    ref = ptf.groupby("isin").agg(agg_cols).reset_index()

    if has_fv_prev and has_q_prev:
        ref["p_fv_n1"] = (ref["fair_value_prev"] /
                          ref["quantita_prev"].replace(0,np.nan)).fillna(0)
    else:
        ref["p_fv_n1"] = 0.0

    ref["p_fv_n"] = (ref["fair_value"] /
                     ref["quantita"].replace(0,np.nan)).fillna(0)

    ref_idx = ref.set_index("isin")
    isins_ptf = set(ref["isin"])

    # Prepara TX
    df = df_tx.copy()
    df.columns = df.columns.str.strip().str.lower()
    col_map = {k: v for k, v in _TX_COL_MAP.items() if k in df.columns}
    # Aggiungi mapping SAG
    for c in df.columns:
        if "security account group" in c:
            col_map[c] = "security_account_group"
    df = df.rename(columns=col_map)

    if "tipo" not in df.columns or "isin" not in df.columns:
        return None

    df = df[df["tipo"].str.strip().str.lower().isin({"purchase","sale"}) &
            df["isin"].isin(isins_ptf)].copy()

    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df = df.sort_values("data").reset_index(drop=True)

    # Calcolo effetti rolling
    stato = {}  # isin -> p_prev (ultimo prezzo usato)

    rows = []
    for _, row in df.iterrows():
        isin = row["isin"]
        tipo = str(row["tipo"]).lower()
        nom_tx = float(row.get("nominale", 0) or 0)
        p_tx = float(row.get("prezzo",   np.nan) or np.nan)

        # Inizializza con P_FV_N1
        if isin not in stato:
            stato[isin] = float(ref_idx.at[isin,"p_fv_n1"]) if isin in ref_idx.index else np.nan

        p_prev = stato[isin]
        p_fv_n = float(ref_idx.at[isin,"p_fv_n"]) if isin in ref_idx.index else np.nan
        delta_q = abs(nom_tx) if tipo=="purchase" else -abs(nom_tx)

        if not (np.isnan(p_tx) or np.isnan(p_prev)):
            eff_nom = round(delta_q * p_prev, 0)
            eff_mkt = round(delta_q * (p_fv_n - p_tx), 0) if not np.isnan(p_fv_n) else np.nan
        elif not np.isnan(p_tx):
            # Posizione nuova (nessun N-1): eff_nom = importo, eff_mkt vs FV
            eff_nom = round(delta_q * p_tx, 0)
            eff_mkt = round(delta_q * (p_fv_n - p_tx), 0) if not np.isnan(p_fv_n) else np.nan
        else:
            eff_nom = np.nan
            eff_mkt = np.nan

        eff_tot = (eff_nom or 0) + (eff_mkt or 0) if not (np.isnan(eff_nom if eff_nom else np.nan)) else np.nan

        rows.append({
            "Data": row.get("data",""),
            "Tipo": tipo.capitalize(),
            "ISIN": isin,
            "Titolo": row.get("descrizione",""),
            "Asset Class": row.get("asset_class",""),
            "SAG": row.get("security_account_group",""),
            "ΔNominale": delta_q,
            "Prezzo Tx": round(p_tx,4)   if not np.isnan(p_tx)   else np.nan,
            "Prezzo FV N-1": round(p_prev,4)  if not np.isnan(p_prev) else np.nan,
            "Prezzo FV N": round(p_fv_n,4) if not np.isnan(p_fv_n) else np.nan,
            "Eff. Nominale": eff_nom,
            "Eff. Mercato": eff_mkt,
            "Eff. Totale": round(eff_tot, 0) if eff_tot and not np.isnan(eff_tot) else np.nan,
            "Importo LC": row.get("importo_lc", np.nan),
            "P/L Realizzo LC": row.get("pl_titolo_lc", np.nan),
        })

        # Aggiorna p_prev per operazioni successive
        if not np.isnan(p_tx):
            stato[isin] = p_tx

    df_all = pd.DataFrame(rows)

    # Top N per |Eff. Totale|
    df_top = (df_all[df_all["Eff. Totale"].notna()]
              .assign(_abs=lambda x: x["Eff. Totale"].abs())
              .sort_values("_abs", ascending=False)
              .drop(columns=["_abs"])
              .head(n)
              .reset_index(drop=True))
    df_top.index = df_top.index + 1
    df_top.index.name = "Rank"
    return df_top

def analisi_effetti_operazioni(df_tx: pd.DataFrame,
                                df_ptf: pd.DataFrame) -> dict | None:
    """
    Decomposizione della variazione di portafoglio in 3 effetti.

    Input:
      df_tx : Transaction Report (grezzo, tutti i portafogli)
      df_ptf : DataFrame già filtrato e mappato (output di calcola_analisi)
               contiene entrambi N e N-1 con chiave composita:
               (valuation_area, company_name, portfolio_name, isin)

    Chiave: solo ISIN (il TX non ha VA/Company/Portfolio, ma df_ptf è già
    filtrato dalla VA selezionata nell'app -> nessun incrocio tra portafogli).
    Il TX viene filtrato agli ISIN presenti in df_ptf per isolare la VA corretta.

    Effetto Nominale = Delta Q × P_rif
    Effetto Prezzo = (P_tx − P_rif) × Q_rif
    Effetto Mercato = FV_N − Q_N × P_last

    P_rif rolling:
    - 1ª op ISIN -> P_N1 = BV_N1 / Nom_N1
    - Purchase -> P_rif aggiornato come media ponderata dopo l'acquisto
    - Sale -> P_rif invariato (costo storico residuo)

    Check per ISIN:
      Somma Eff_Nom + Somma Eff_Pre + Eff_Mercato ≈ FV_N − BV_N1

    Check portafoglio totale:
      Somma Eff_Mercato + Somma Eff_Prezzo + Somma Eff_Nominale = FV_N_tot − BV_N1_tot
    """
    if df_tx is None or df_tx.empty or df_ptf is None or df_ptf.empty:
        return None

    # ── Estrai prezzi di riferimento da df_ptf (già filtrato per VA) ─────
    ptf = df_ptf.copy()

    # Colonne necessarie
    has_bv_prev = "book_value_prev" in ptf.columns
    has_fv = "fair_value" in ptf.columns
    has_nom = "quantita" in ptf.columns
    has_nom_prev = "quantita_prev" in ptf.columns

    if not ("isin" in ptf.columns and "book_value" in ptf.columns):
        return None

    # Aggrega per ISIN (somma su VA/Company/Portfolio se più righe)
    has_fv_prev = "fair_value_prev" in ptf.columns
    agg_cols = {"book_value": "sum"}
    if has_bv_prev: agg_cols["book_value_prev"] = "sum"
    if has_fv: agg_cols["fair_value"] = "sum"
    if has_fv_prev: agg_cols["fair_value_prev"] = "sum"
    if has_nom: agg_cols["quantita"] = "sum"
    if has_nom_prev: agg_cols["quantita_prev"] = "sum"

    ref = ptf.groupby("isin").agg(agg_cols).reset_index()

    # Prezzi unitari - usa FV per allineare il check a FV_N - FV_N1
    if has_fv_prev and has_nom_prev:
        ref["p_n1"] = (ref["fair_value_prev"] /
                       ref["quantita_prev"].replace(0, np.nan)).round(6)
    elif has_nom_prev and has_bv_prev:
        ref["p_n1"] = (ref["book_value_prev"] /
                       ref["quantita_prev"].replace(0, np.nan)).round(6)
    else:
        ref["p_n1"] = np.nan

    if has_nom:
        ref["p_n"] = (ref["book_value"] /
                      ref["quantita"].replace(0, np.nan)).round(6)
    else:
        ref["p_n"] = np.nan

    ref_idx = ref.set_index("isin")

    # ISINs nel portafoglio filtrato
    isins_ptf = set(ref["isin"])

    # Preparazione TX e filtra agli ISIN del portafoglio corrente
    df = df_tx.copy()
    df.columns = df.columns.str.strip().str.lower()
    col_map = {k: v for k, v in _TX_COL_MAP.items() if k in df.columns}
    df = df.rename(columns=col_map)

    if "tipo" not in df.columns or "isin" not in df.columns:
        return None

    df = df[df["tipo"].str.strip().str.lower().isin({"purchase","sale"}) &
            df["isin"].isin(isins_ptf)].copy()

    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df = df.sort_values("data").reset_index(drop=True)

    # Calcolo effetti rolling per operazione
    stato = {}  # isin -> {p_rif, q_rif}

    det_rows = []
    for _, row in df.iterrows():
        isin = row.get("isin","")
        tipo = str(row.get("tipo","")).lower()
        nom_tx = float(row.get("nominale", 0) or 0)
        p_tx = float(row.get("prezzo",   np.nan) or np.nan)

        if isin not in stato:
            p_ref = float(ref_idx.at[isin,"p_n1"]) if isin in ref_idx.index else np.nan
            q_ref = float(ref_idx.at[isin,"quantita_prev"]) if (isin in ref_idx.index and has_nom_prev) else 0.0
            stato[isin] = {"p_rif": p_ref, "q_rif": q_ref}

        p_rif = stato[isin]["p_rif"]
        q_rif = stato[isin]["q_rif"]

        if not np.isnan(p_tx):
            delta_q = abs(nom_tx) if tipo=="purchase" else -abs(nom_tx)
            if not np.isnan(p_rif):
                # Posizione esistente in N-1: Laspeyres standard
                eff_nom = round(delta_q * p_rif, 0)
                eff_pre = round((p_tx - p_rif) * q_rif, 0)
            else:
                # Posizione nuova (nessun riferimento N-1):
                # Eff_Nom = intero importo acquisto (pura variazione quantità)
                # Eff_Pre = 0 (non c'è prezzo precedente da confrontare)
                eff_nom = round(abs(nom_tx) * p_tx, 0) if tipo=="purchase" else np.nan
                eff_pre = 0.0 if tipo=="purchase" else np.nan
        else:
            eff_nom = np.nan
            eff_pre = np.nan

        det_rows.append({
            "Data": row.get("data",""),
            "Tipo": tipo.capitalize(),
            "ISIN": isin,
            "Titolo": row.get("descrizione",""),
            "Asset Class": row.get("asset_class",""),
            "Delta Nominale": nom_tx,
            "Prezzo Tx": round(p_tx, 4) if not np.isnan(p_tx) else np.nan,
            "Prezzo Rif.": round(p_rif,4) if not np.isnan(p_rif) else np.nan,
            "Effetto Nominale": eff_nom,
            "Effetto Prezzo": eff_pre,
            "Importo LC": row.get("importo_lc", np.nan),
            "P/L Realizzo LC": row.get("pl_titolo_lc", np.nan),
        })

        # Aggiorna stato rolling
        if not np.isnan(p_tx):
            q_new = q_rif + (abs(nom_tx) if tipo=="purchase" else -abs(nom_tx))
            if tipo == "purchase":
                if not np.isnan(p_rif) and q_rif > 0:
                    # Media ponderata su posizione esistente
                    p_new = (q_rif * p_rif + abs(nom_tx) * p_tx) / q_new if q_new > 0 else p_tx
                else:
                    # Posizione nuova: il prezzo di acquisto diventa il riferimento
                    p_new = p_tx
                stato[isin] = {"p_rif": round(p_new,6), "q_rif": max(q_new, 0)}
            elif tipo == "sale":
                stato[isin] = {"p_rif": p_rif, "q_rif": max(q_new, 0)}

    df_det = pd.DataFrame(det_rows)

    # Riepilogo per ISIN + Effetto Mercato
    rie_rows = []

    has_fv_prev_rie = "fair_value_prev" in ref_idx.columns

    for isin, row_ref in ref_idx.iterrows():
        bv_n1 = float(row_ref.get("book_value_prev", 0) or 0) if has_bv_prev else 0.0
        fv_n1 = float(row_ref.get("fair_value_prev", 0) or 0) if has_fv_prev_rie else bv_n1
        bv_n = float(row_ref.get("book_value", 0) or 0)
        fv_n = float(row_ref.get("fair_value", np.nan)) if has_fv else np.nan
        nom_n = float(row_ref.get("quantita", 0) or 0) if has_nom else 0.0

        # Totali effetti da transazioni
        sub = df_det[df_det["ISIN"]==isin]
        tot_nom = sub["Effetto Nominale"].sum() if len(sub) else 0.0
        tot_pre = sub["Effetto Prezzo"].sum() if len(sub) else 0.0

        # Effetto Mercato: FV_N vs Q_N × P_last
        p_last  = stato.get(isin,{}).get("p_rif", float(row_ref.get("p_n1", np.nan)))
        eff_mkt = round(fv_n - nom_n * p_last, 0) if (not np.isnan(fv_n) and not np.isnan(p_last) and nom_n > 0) else np.nan

        # Check ISIN: Somma effetti vs FV_N − FV_N1
        sigma = (tot_nom or 0) + (tot_pre or 0) + (eff_mkt or 0)
        delta_fv = (fv_n - fv_n1) if (not np.isnan(fv_n)) else np.nan
        check = round(sigma - delta_fv, 0) if not np.isnan(delta_fv) else np.nan

        rie_rows.append({
            "ISIN": isin,
            "FV N-1": fv_n1,
            "BV N-1": bv_n1,
            "BV N": bv_n,
            "FV N": fv_n,
            "Somma Eff. Nominale": tot_nom,
            "Somma Eff. Prezzo": tot_pre,
            "Effetto Mercato": eff_mkt,
            "Somma Totale": round(sigma, 0),
            "FV N − FV N-1": round(delta_fv, 0) if not np.isnan(delta_fv) else np.nan,
            "Check": check,
        })

    df_rie = pd.DataFrame(rie_rows)

    # Check portafoglio totale (base: FV_N − FV_N1)
    tot_fv_n1 = df_rie["FV N-1"].sum()  if "FV N-1" in df_rie.columns else df_rie["BV N-1"].sum()
    tot_bv_n1 = df_rie["BV N-1"].sum()
    tot_fv_n = df_rie["FV N"].dropna().sum()
    tot_eff_nom = df_rie["Somma Eff. Nominale"].sum()
    tot_eff_pre = df_rie["Somma Eff. Prezzo"].sum()
    tot_eff_mkt = df_rie["Effetto Mercato"].dropna().sum()
    tot_sigma = tot_eff_nom + tot_eff_pre + tot_eff_mkt
    delta_fv = tot_fv_n - tot_fv_n1
    check_ptf = round(tot_sigma - delta_fv, 0)

    # Laspeyres cross-term = residuo dopo aver escluso RGL titoli venduti
    rgl_venduti = df_rie[df_rie["FV N"].isna() | (df_rie["FV N"] == 0)]["Somma Eff. Prezzo"].sum()
    cross_term  = round(check_ptf - rgl_venduti, 0)

    check_summary = {
        "FV N-1 totale": round(tot_fv_n1, 0),
        "FV N totale": round(tot_fv_n, 0),
        "Effetti": "",
        "Somma Eff. Nominale": round(tot_eff_nom, 0),
        "Somma Eff. Prezzo": round(tot_eff_pre, 0),
        "Somma Eff. Mercato": round(tot_eff_mkt, 0),
        "Somma Totale Effetti": round(tot_sigma, 0),
        "Rico": "",
        "FV N - FV N-1": round(delta_fv, 0),
        "RGL titoli venduti": round(rgl_venduti, 0),
        "Cross-term Laspeyres": cross_term,
        "Check Portafoglio": check_ptf,
    }

    return {
        "dettaglio": df_det,
        "riepilogo": df_rie,
        "check_ptf": check_summary,
    }

# 7. Funzioni SHIP - unione N / N-1
def _data_sheet(df: pd.DataFrame, col_data: str) -> pd.Timestamp | None:
    if col_data not in df.columns:
        return None
    try:
        return pd.to_datetime(df[col_data], dayfirst=True, errors="coerce").dropna().mode()[0]
    except Exception:
        return None

def unisci_ship_patrimoniale(df_n: pd.DataFrame,
                              df_n1: pd.DataFrame) -> pd.DataFrame:
    """
    Unione dei due Inventory SHIP (N e N-1) con outer join su isin.
    Nel DB SHIP ogni ISIN appare una sola volta per sheet, ma la
    Valuation Area e Valuation Class possono cambiare tra N e N-1
    per lo stesso titolo - quindi la chiave è solo isin.

    Casistiche gestite:
    - Titoli in entrambi gli anni: book_value e book_value_prev valorizzati
    - Titoli solo in N (acquistati): book_value_prev = NaN
    - Titoli solo in N-1 (venduti): book_value = NaN, book_value_prev valorizzato
    """
    # Determina quale sheet è N e quale N-1 dalla colonna Date
    col_data = next((c for c in df_n.columns if c.lower() == "date"), None)
    data_a = _data_sheet(df_n,  col_data) if col_data else None
    data_b = _data_sheet(df_n1, col_data) if col_data else None
    if data_a and data_b and data_b > data_a:
        df_n, df_n1 = df_n1, df_n

    # Chiave primaria SHIP: Valuation Area + Company + Portfolio + ISIN
    # (ogni titolo può apparire più volte con VA/Company/Portfolio diversi,
    # ma la combinazione è unica per riga e stabile tra N e N-1)
    chiavi_ship = ["valuation_area", "company_name", "portfolio_name",
                   "security_account_group", "isin"]
    merge_on = [c for c in chiavi_ship
                if c in df_n.columns and c in df_n1.columns]
    if not merge_on:
        merge_on = [c for c in ["isin"]
                    if c in df_n.columns and c in df_n1.columns]
    if not merge_on:
        return df_n

    # Colonne numeriche di N-1 -> rinominate _prev
    cols_numeriche = [c for c in df_n1.columns
                      if pd.api.types.is_numeric_dtype(df_n1[c])
                      and c in df_n.columns
                      and c not in merge_on]

    # Colonne anagrafiche (stringa) di N-1 → incluse in _prev per recupero titoli venduti
    COLS_ANA = ["asset_class", "tipo_emittente", "rating", "paese", "valuta",
                "settore", "descrizione", "valuation_class", "bond_classification",
                "company_name", "portfolio_name", "security_account_group",
                "scadenza", "data_acquisto"]
    cols_anagrafica = [c for c in COLS_ANA
                       if c in df_n1.columns and c not in merge_on]

    cols_da_prev = cols_numeriche + cols_anagrafica
    df_prev = df_n1[merge_on + cols_da_prev].copy()
    df_prev = df_prev.rename(columns={c: f"{c}_prev" for c in cols_da_prev})

    # outer join: titoli in entrambi, solo N (acquistati), solo N-1 (venduti)
    result = df_n.merge(df_prev, on=merge_on, how="outer")

    # Per i titoli venduti (solo N-1): recupera colonne anagrafiche da _prev
    for col in cols_anagrafica:
        if col in result.columns and f"{col}_prev" in result.columns:
            result[col] = result[col].combine_first(result[f"{col}_prev"])
            result.drop(columns=[f"{col}_prev"], inplace=True, errors="ignore")

    return result

def unisci_ship_economico(df_eco_n: pd.DataFrame,
                           df_eco_n1: pd.DataFrame) -> pd.DataFrame:
    """
    Unisce i due Income SHIP (N e N-1).
    Chiave: (valuation_area, company_name, portfolio_name, isin) - stessa chiave del patrimoniale.
    """
    col_data = next((c for c in df_eco_n.columns
                     if c.lower() in ("date to", "dateto", "date_to")), None)
    data_a = _data_sheet(df_eco_n,  col_data) if col_data else None
    data_b = _data_sheet(df_eco_n1, col_data) if col_data else None
    if data_a and data_b and data_b > data_a:
        df_eco_n, df_eco_n1 = df_eco_n1, df_eco_n

    # Stessa chiave del patrimoniale
    chiavi_ship = ["valuation_area", "company_name", "portfolio_name",
                   "security_account_group", "isin"]
    merge_on = [c for c in chiavi_ship
                if c in df_eco_n.columns and c in df_eco_n1.columns]
    if not merge_on:
        merge_on = [c for c in ["isin"]
                    if c in df_eco_n.columns and c in df_eco_n1.columns]
    if not merge_on:
        return df_eco_n

    eco_canonici = ["cedola", "dividendi", "pl_realizzo",
                    "pl_valutazione", "pl_totale_db"]
    cols_n1 = [c for c in eco_canonici
               if c in df_eco_n1.columns and c not in merge_on]

    df_prev = df_eco_n1[merge_on + cols_n1].copy()
    df_prev = df_prev.rename(columns={c: f"{c}_prev" for c in cols_n1})

    return df_eco_n.merge(df_prev, on=merge_on, how="outer")
