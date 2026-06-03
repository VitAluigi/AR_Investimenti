# =============================================================================
# modules/analisi.py - Capability discovery e calcoli finanziari
# =============================================================================

import pandas as pd
import numpy as np
from config import ANALISI_REQUISITI


# ---------------------------------------------------------------------------
# 1. CAPABILITY DISCOVERY
# ---------------------------------------------------------------------------

def scopri_analisi(df: pd.DataFrame) -> dict:
    colonne = set(df.columns.tolist())
    risultato = {}
    for nome, requisiti in ANALISI_REQUISITI.items():
        if nome == "economica_completa":
            voci = ["cedola", "dividendi", "pl_realizzo", "pl_valutazione", "pl_totale_db"]
            risultato[nome] = (
                "asset_class" in colonne and any(v in colonne for v in voci)
            )
        else:
            risultato[nome] = all(r in colonne for r in requisiti)
    return risultato


def report_analisi(disponibili: dict) -> str:
    attive   = [n for n, v in disponibili.items() if v]
    inattive = [n for n, v in disponibili.items() if not v]
    lines = [f"Analisi disponibili ({len(attive)}/{len(disponibili)}):"]
    for a in attive:   lines.append(f"  OK {a}")
    for i in inattive: lines.append(f"  KO {i}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. HELPERS
# ---------------------------------------------------------------------------

def _sum(df, col):
    if col in df.columns:
        return float(np.nansum(df[col].values))
    return 0.0

def _var_pct(n, n1):
    if n1 and n1 != 0:
        return round((n - n1) / abs(n1) * 100, 2)
    return None

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
        "N":           tot_n,
        "Peso %":      100.0,
        "N-1":         tot_n1,
        "Variazione":  round(tot_n - tot_n1, 2) if tot_n1 is not None else None,
        "Var %":       _var_pct(tot_n, tot_n1),
    }
    return pd.concat([agg, pd.DataFrame([totale])], ignore_index=True)


# ---------------------------------------------------------------------------
# 3. ANALISI PATRIMONIALE
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 4. ANALISI ECONOMICA
# ---------------------------------------------------------------------------

def economica_completa(df: pd.DataFrame) -> pd.DataFrame:
    voci = [
        ("Cedole/Int. N",    "cedola"),
        ("Dividendi N",      "dividendi"),
        ("PL Realizzo N",    "pl_realizzo"),
        ("PL Valutazione N", "pl_valutazione"),
    ]
    voci_prev = [
        ("Cedole/Int. N-1",    "cedola_prev"),
        ("Dividendi N-1",      "dividendi_prev"),
        ("PL Realizzo N-1",    "pl_realizzo_prev"),
        ("PL Valutazione N-1", "pl_valutazione_prev"),
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


# ---------------------------------------------------------------------------
# 5. ANALISI AGGIUNTIVE
# ---------------------------------------------------------------------------

def top_holdings(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    cols = ["descrizione", "book_value"]
    if "asset_class"     in df.columns: cols.insert(1, "asset_class")
    if "isin"            in df.columns: cols.insert(0, "isin")
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


def kpi_portafoglio(df: pd.DataFrame) -> dict:
    nav      = _sum(df, "book_value")
    nav_prev = _sum(df, "book_value_prev")
    n_titoli = int(df["isin"].nunique()) if "isin" in df.columns else len(df)

    if "pl_totale_db" in df.columns:
        pl_tot = _sum(df, "pl_totale_db")
    else:
        pl_tot = _sum(df, "pl_realizzo") + _sum(df, "pl_valutazione")

    proventi = _sum(df, "cedola") + _sum(df, "dividendi")

    return {
        "nav":          nav,
        "nav_prev":     nav_prev,
        "n_titoli":     n_titoli,
        "pl_totale":    pl_tot,
        "proventi":     proventi,
        "rendimento_%": round(pl_tot / nav * 100, 2) if nav > 0 else None,
        "var_nav":      round(nav - nav_prev, 2) if nav_prev else None,
        "var_nav_%":    _var_pct(nav, nav_prev),
    }
