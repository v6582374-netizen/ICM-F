#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scheme A pipeline (ARCHIVED - DATA SOURCES REMOVED):

This pipeline was originally designed for EuRepoC/WDI/STIP analysis.
Data sources have been removed per project requirements.
Kept for reference only - DO NOT USE.

Original inputs (no longer available):
  1) Event-level dataset (EuRepoC): eurepoc_global_dataset_1_3.csv
  2) Exposure (population): World Bank WDI
  3) Policy initiatives (P dimension): OECD STIP
"""

import os
import re
import json
from difflib import get_close_matches

import numpy as np
import pandas as pd


# -----------------------
# Utils
# -----------------------
NA_TOKENS = {"not available", "na", "n/a", "nan", "none", ""}


def clean_na(x):
    if pd.isna(x):
        return np.nan
    s = str(x).strip()
    if s.lower() in NA_TOKENS:
        return np.nan
    return s


def norm_country(s):
    if pd.isna(s):
        return None
    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("&", "and")
    s = re.sub(r"[,\.()]", "", s)
    return s.lower()


def split_multilabel(x, sep=";"):
    x = clean_na(x)
    if pd.isna(x):
        return []
    parts = [p.strip() for p in str(x).split(sep)]
    parts = [p for p in parts if p and p.lower() not in NA_TOKENS]
    return parts


def parse_year_from_date(d):
    d = clean_na(d)
    if pd.isna(d):
        return np.nan
    m = re.search(r"(\d{4})", str(d))
    return int(m.group(1)) if m else np.nan


def build_country_name_map(ev_countries, wb_countries, cutoff=0.88):
    wb_set = set(wb_countries)
    mapping = {}
    for c in ev_countries:
        if c in wb_set:
            mapping[c] = c
        else:
            cand = get_close_matches(c, wb_countries, n=1, cutoff=cutoff)
            mapping[c] = cand[0] if cand else None
    return mapping


def rank_and_stats(df, col):
    r = df[["country_norm", col]].dropna().sort_values(col, ascending=False).copy()
    r["rank"] = np.arange(1, len(r) + 1)
    stats = {
        "mean": float(r[col].mean()),
        "median": float(r[col].median()),
        "p25": float(r[col].quantile(0.25)),
        "p75": float(r[col].quantile(0.75)),
        "n": int(r.shape[0]),
    }
    return r, stats


# -----------------------
# Loaders
# -----------------------
def load_population_long(pop_path, year_min=2000, year_max=2024):
    # World Bank format: first 4 rows are metadata headers
    df = pd.read_csv(pop_path, skiprows=4)
    year_cols = [c for c in df.columns if re.fullmatch(r"\d{4}", str(c))]
    year_cols = [c for c in year_cols if year_min <= int(c) <= year_max]

    long_df = df[["Country Name", "Country Code"] + year_cols].melt(
        id_vars=["Country Name", "Country Code"], var_name="year", value_name="population"
    )
    long_df["year"] = long_df["year"].astype(int)
    long_df["country_norm"] = long_df["Country Name"].map(norm_country)
    return long_df


def load_eurepoc_events(event_path):
    ev = pd.read_csv(event_path)
    ev["year"] = ev["start_date"].apply(parse_year_from_date)

    # receiver_country can be multi-country; expand first
    ev["receiver_country_list"] = ev["receiver_country"].apply(split_multilabel)
    ev = ev.explode("receiver_country_list")
    ev["country"] = ev["receiver_country_list"].apply(clean_na)
    ev["country_norm"] = ev["country"].map(norm_country)
    ev.drop(columns=["receiver_country_list"], inplace=True)

    return ev


def load_stip(stip_path):
    stip = pd.read_csv(stip_path)
    stip["country_norm"] = stip["Country"].map(norm_country)
    stip["start_year"] = pd.to_numeric(stip.get("Start date"), errors="coerce")
    stip["end_year"] = pd.to_numeric(stip.get("End date"), errors="coerce")

    # fallback: if start_year missing, use creation year (YYYY-..)
    if "Creation date in the survey" in stip.columns:
        creation_year = pd.to_numeric(stip["Creation date in the survey"].astype(str).str[:4], errors="coerce")
        stip["start_year"] = stip["start_year"].fillna(creation_year)

    return stip


# -----------------------
# Core computation
# -----------------------
def build_panel(event_df, pop_long, stip_df, year_min=2000, year_max=2024):
    # map event country names -> WB country names (normed) by fuzzy matching
    wb_unique = [c for c in pop_long["country_norm"].dropna().unique()]
    ev_unique = [c for c in event_df["country_norm"].dropna().unique()]
    name_map = build_country_name_map(ev_unique, wb_unique, cutoff=0.88)

    event_df["wb_country_norm"] = event_df["country_norm"].map(name_map)

    # keep usable events (have year and country matched)
    ev = event_df.dropna(subset=["year", "wb_country_norm"]).copy()
    ev["year"] = ev["year"].astype(int)
    ev = ev[(ev["year"] >= year_min) & (ev["year"] <= year_max)].copy()
    ev["country_norm"] = ev["wb_country_norm"]
    ev.drop(columns=["wb_country_norm"], inplace=True)

    # merge population as exposure E_it
    panel = ev[
        [
            "incident_id",
            "year",
            "country_norm",
            "incident_type",
            "receiver_category",
            "mitre_initial_access",
            "response_indicator",
            "weighted_intensity",
        ]
    ].copy()
    panel = panel.merge(pop_long[["country_norm", "year", "population"]], on=["country_norm", "year"], how="left")
    panel["E_it"] = panel["population"]

    # parse multilabel lists
    panel["T_list"] = panel["incident_type"].apply(split_multilabel)
    panel["S_list"] = panel["receiver_category"].apply(split_multilabel)
    panel["F_list"] = panel["mitre_initial_access"].apply(split_multilabel)
    panel["R_list"] = panel["response_indicator"].apply(split_multilabel)

    # country-year aggregation for Y_T,Y_S,Y_F,Y_R
    def uniq_count(series):
        return len(set([i for sub in series for i in sub]))

    cy = panel.groupby(["country_norm", "year"], as_index=False).agg(
        incidents=("incident_id", "nunique"),
        Y_S=("S_list", uniq_count),
        Y_F=("F_list", uniq_count),
        Y_R=("R_list", uniq_count),
        avg_intensity=("weighted_intensity", lambda s: pd.to_numeric(s, errors="coerce").mean()),
        population=("population", "first"),
    )
    cy["Y_T"] = cy["incidents"]

    # P dimension from STIP: count active initiatives per country-year
    years = np.arange(year_min, year_max + 1)
    records = []
    for c, sub in stip_df.groupby("country_norm"):
        syrs = sub["start_year"]
        eyrs = sub["end_year"]
        for y in years:
            active = ((syrs <= y) & ((eyrs.isna()) | (eyrs >= y))).sum()
            if active > 0:
                records.append((c, y, int(active)))
    stip_cy = pd.DataFrame(records, columns=["country_norm", "year", "Y_P"])

    cy = cy.merge(stip_cy, on=["country_norm", "year"], how="left")
    cy["Y_P"] = cy["Y_P"].fillna(0).astype(int)
    cy["E_it"] = cy["population"]

    return panel, cy


def build_rate_table(panel, dim_col, dim_name, pop_col="population"):
    tmp = panel[["country_norm", "year", pop_col, dim_col, "incident_id"]].copy()
    tmp = tmp.explode(dim_col)
    tmp = tmp.dropna(subset=[dim_col])
    tmp = tmp[tmp[dim_col].astype(str).str.len() > 0]
    g = tmp.groupby(["country_norm", "year", dim_col], as_index=False).agg(
        n_events=("incident_id", "nunique"),
        population=(pop_col, "first"),
    )
    g["rate_per_million"] = g["n_events"] / (g["population"] / 1e6)
    g.rename(columns={dim_col: dim_name}, inplace=True)
    return g


def compute_country_scores(panel, cy_panel):
    # H_i: intensity per million population (summed over all event rows)
    wi = pd.to_numeric(panel["weighted_intensity"], errors="coerce")
    hi = panel.assign(wi=wi).groupby("country_norm", as_index=False).agg(
        total_intensity=("wi", "sum"),
        total_pop=("population", "sum"),
        n_incidents=("incident_id", "nunique"),
    )
    hi["H_i"] = hi["total_intensity"] / (hi["total_pop"] / 1e6)
    hi_top20 = hi.sort_values("H_i", ascending=False).head(20)

    # SR/FR/RR/PR:
    # SR_i: mean incident rate per million pop across years
    # FR_i: mean avg_intensity across years
    # RR_i: mean response diversity across years
    # PR_i: mean policy initiatives rate per million pop across years
    cy = cy_panel.copy()
    cy["inc_rate_pm"] = cy["Y_T"] / (cy["population"] / 1e6)
    cy["P_rate_pm"] = cy["Y_P"] / (cy["population"] / 1e6)

    summ = cy.groupby("country_norm", as_index=False).agg(
        SR_i=("inc_rate_pm", "mean"),
        FR_i=("avg_intensity", "mean"),
        RR_i=("Y_R", "mean"),
        PR_i=("P_rate_pm", "mean"),
        years=("year", "nunique"),
    )

    SR_rank, SR_stats = rank_and_stats(summ, "SR_i")
    FR_rank, FR_stats = rank_and_stats(summ, "FR_i")
    RR_rank, RR_stats = rank_and_stats(summ, "RR_i")
    PR_rank, PR_stats = rank_and_stats(summ, "PR_i")

    return hi_top20, (SR_rank, FR_rank, RR_rank, PR_rank), (SR_stats, FR_stats, RR_stats, PR_stats)


def compute_missingness(event_raw_df, event_expanded_df, panel):
    t_missing = float(pd.Series([len(x) == 0 for x in panel["T_list"]]).mean())
    s_missing = float(pd.Series([len(x) == 0 for x in panel["S_list"]]).mean())
    f_missing = float(pd.Series([len(x) == 0 for x in panel["F_list"]]).mean())
    r_missing = float(pd.Series([len(x) == 0 for x in panel["R_list"]]).mean())

    rep = {
        "event_rows_raw": int(event_raw_df.shape[0]),
        "event_rows_expanded": int(event_expanded_df.shape[0]),
        "event_rows_used_unique_incidents": int(panel["incident_id"].nunique()),
        "T_missing_rate_after_parse": t_missing,
        "S_missing_rate_after_parse": s_missing,
        "F_missing_rate_after_parse": f_missing,
        "R_missing_rate_after_parse": r_missing,
        "panel_pop_missing_rate": float(panel["population"].isna().mean()),
        "events_year_range": [int(panel["year"].min()), int(panel["year"].max())],
    }
    return rep


# -----------------------
# Main
# -----------------------
def main():
    # Configure paths (edit if needed)
    EVENT_PATH = "data/eurepoc_global_dataset_1_3.csv"
    POP_PATH = "data/API_SP.POP.TOTL_DS2_en_csv_v2_174326/API_SP.POP.TOTL_DS2_en_csv_v2_174326.csv"
    STIP_PATH = "data/STIP_COMPASS_Policy_Initiatives_Export.csv"
    OUT_DIR = "outputs_schemeA"

    assert os.path.exists(EVENT_PATH), f"Missing {EVENT_PATH}"
    assert os.path.exists(POP_PATH), f"Missing {POP_PATH}"
    assert os.path.exists(STIP_PATH), f"Missing {STIP_PATH}"

    os.makedirs(OUT_DIR, exist_ok=True)

    pop_long = load_population_long(POP_PATH, year_min=2000, year_max=2024)

    event_raw = pd.read_csv(EVENT_PATH)
    event_expanded = load_eurepoc_events(EVENT_PATH)

    stip = load_stip(STIP_PATH)

    panel, cy_panel = build_panel(event_expanded, pop_long, stip, year_min=2000, year_max=2024)

    # outputs
    cy_panel.to_csv(os.path.join(OUT_DIR, "panel_country_year.csv"), index=False)

    textRate_T = build_rate_table(panel, "T_list", "T")
    textRate_T.to_csv(os.path.join(OUT_DIR, "textRate_T_country_year.csv"), index=False)

    hi_top20, ranks, stats = compute_country_scores(panel, cy_panel)
    hi_top20.to_csv(os.path.join(OUT_DIR, "H_i_top20.csv"), index=False)

    SR_rank, FR_rank, RR_rank, PR_rank = ranks
    SR_rank.to_csv(os.path.join(OUT_DIR, "SR_rank.csv"), index=False)
    FR_rank.to_csv(os.path.join(OUT_DIR, "FR_rank.csv"), index=False)
    RR_rank.to_csv(os.path.join(OUT_DIR, "RR_rank.csv"), index=False)
    PR_rank.to_csv(os.path.join(OUT_DIR, "PR_rank.csv"), index=False)

    missing = compute_missingness(event_raw, event_expanded, panel)
    report = {
        "field_mapping_rules": {
            "T": {"field": "incident_type", "source": "EuRepoC"},
            "S": {"field": "receiver_category", "source": "EuRepoC"},
            "F": {"field": "mitre_initial_access", "source": "EuRepoC"},
            "R": {"field": "response_indicator", "source": "EuRepoC"},
            "P": {"rule": "count active STIP initiatives per (country,year)", "source": "STIP"},
            "E_it": {"field": "population", "source": "WorldBank SP.POP.TOTL"},
        },
        "missingness": missing,
        "distribution_stats": {"SR": stats[0], "FR": stats[1], "RR": stats[2], "PR": stats[3]},
    }

    with open(os.path.join(OUT_DIR, "missingness_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # minimal console JSON for quick copy into paper
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # Dummy data fallback: if user runs in a clean folder without files, we create tiny demo files.
    # In your actual project, keep the real files in the same folder and this dummy block will be skipped.
    required = [
        "data/eurepoc_global_dataset_1_3.csv",
        "data/API_SP.POP.TOTL_DS2_en_csv_v2_174326/API_SP.POP.TOTL_DS2_en_csv_v2_174326.csv",
        "data/STIP_COMPASS_Policy_Initiatives_Export.csv",
    ]
    if not all(os.path.exists(p) for p in required):
        # Create minimal dummy files
        pd.DataFrame(
            {
                "incident_id": [1, 2],
                "start_date": ["01.01.2020", "02.02.2020"],
                "receiver_country": ["France", "France"],
                "incident_type": ["Data theft", "Disruption"],
                "receiver_category": ["Critical infrastructure", "State institutions / political system"],
                "mitre_initial_access": ["Exploit Public-Facing Application", "Not available"],
                "response_indicator": ["Unfriendly acts/retorsions justified", "Not available"],
                "weighted_intensity": [2.0, 1.0],
            }
        ).to_csv("data/eurepoc_global_dataset_1_3.csv", index=False)

        # WB pop format with 4 header rows + data
        os.makedirs("data/API_SP.POP.TOTL_DS2_en_csv_v2_174326", exist_ok=True)
        with open("data/API_SP.POP.TOTL_DS2_en_csv_v2_174326/API_SP.POP.TOTL_DS2_en_csv_v2_174326.csv", "w", encoding="utf-8") as f:
            f.write("dummy\n" * 4)
        pd.DataFrame(
            {
                "Country Name": ["France"],
                "Country Code": ["FRA"],
                "Indicator Name": ["Population, total"],
                "Indicator Code": ["SP.POP.TOTL"],
                "2020": [67000000],
                "2021": [67500000],
                "2022": [68000000],
                "2023": [68500000],
                "2024": [69000000],
            }
        ).to_csv("data/API_SP.POP.TOTL_DS2_en_csv_v2_174326/API_SP.POP.TOTL_DS2_en_csv_v2_174326.csv", mode="a", index=False)

        pd.DataFrame(
            {
                "Policy initiative ID": [100],
                "Country": ["France"],
                "Creation date in the survey": ["2020-01-01T00:00:00Z"],
                "Last modification date in the survey": ["2025-01-01T00:00:00Z"],
                "English name": ["Dummy policy"],
                "Start date": [2020],
                "End date": [np.nan],
            }
        ).to_csv("data/STIP_COMPASS_Policy_Initiatives_Export.csv", index=False)

    main()
