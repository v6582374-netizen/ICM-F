import json
from pathlib import Path
from typing import Dict, List, Tuple
import zipfile

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def assert_columns(df: pd.DataFrame, required: List[str], context: str) -> None:
    missing = [col for col in required if col not in df.columns]
    assert not missing, f"Missing columns in {context}: {missing}"


def load_table_from_zip(zip_path: Path, internal_path: str) -> pd.DataFrame:
    assert zip_path.exists(), f"Missing O*NET zip file: {zip_path}"
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(internal_path) as f:
            df = pd.read_csv(f, sep="\t", dtype=str)
    assert not df.empty, f"Loaded empty table: {internal_path}"
    return df


def load_onet_tables(zip_path: Path) -> Dict[str, pd.DataFrame]:
    tables = {
        "occupation_data": "db_30_1_text/Occupation Data.txt",
        "alternate_titles": "db_30_1_text/Alternate Titles.txt",
        "reported_titles": "db_30_1_text/Sample of Reported Titles.txt",
        "work_activities": "db_30_1_text/Work Activities.txt",
        "work_context": "db_30_1_text/Work Context.txt",
        "abilities": "db_30_1_text/Abilities.txt",
        "scales": "db_30_1_text/Scales Reference.txt",
    }
    return {key: load_table_from_zip(zip_path, path) for key, path in tables.items()}


def prepare_scale_bounds(scales_df: pd.DataFrame) -> Dict[str, Tuple[float, float]]:
    assert_columns(scales_df, ["Scale ID", "Minimum", "Maximum"], "Scales Reference")
    scales_df = scales_df.copy()
    scales_df["Minimum"] = pd.to_numeric(scales_df["Minimum"], errors="coerce")
    scales_df["Maximum"] = pd.to_numeric(scales_df["Maximum"], errors="coerce")
    scale_bounds = {}
    for _, row in scales_df.iterrows():
        if pd.notna(row["Minimum"]) and pd.notna(row["Maximum"]):
            scale_bounds[row["Scale ID"]] = (float(row["Minimum"]), float(row["Maximum"]))
    return scale_bounds


def normalize_to_0_100(value: float, scale_bounds: Tuple[float, float]) -> float:
    min_val, max_val = scale_bounds
    assert max_val > min_val, "Invalid scale bounds"
    return (value - min_val) / (max_val - min_val) * 100.0


def score_title_matches(
    label: str,
    occupation_df: pd.DataFrame,
    alternate_df: pd.DataFrame,
    reported_df: pd.DataFrame,
) -> Tuple[str, pd.DataFrame]:
    assert_columns(occupation_df, ["O*NET-SOC Code", "Title"], "Occupation Data")
    assert_columns(alternate_df, ["O*NET-SOC Code", "Alternate Title"], "Alternate Titles")
    assert_columns(reported_df, ["O*NET-SOC Code", "Reported Job Title"], "Reported Titles")

    queries = [q.strip() for q in label.split("/") if q.strip()]
    scores: Dict[str, int] = {}
    evidence_rows = []

    def add_score(code: str, weight: int, source: str, title: str) -> None:
        scores[code] = scores.get(code, 0) + weight
        evidence_rows.append({"label": label, "code": code, "source": source, "title": title})

    for q in queries:
        occ_match = occupation_df[occupation_df["Title"].str.contains(q, case=False, na=False)]
        for _, row in occ_match.iterrows():
            add_score(row["O*NET-SOC Code"], 3, "Occupation Data", row["Title"])

        alt_match = alternate_df[alternate_df["Alternate Title"].str.contains(q, case=False, na=False)]
        for _, row in alt_match.iterrows():
            add_score(row["O*NET-SOC Code"], 2, "Alternate Titles", row["Alternate Title"])

        rep_match = reported_df[reported_df["Reported Job Title"].str.contains(q, case=False, na=False)]
        for _, row in rep_match.iterrows():
            add_score(row["O*NET-SOC Code"], 1, "Reported Titles", row["Reported Job Title"])

    if not scores:
        raise ValueError(f"No O*NET-SOC matches found for label: {label}")

    score_df = pd.DataFrame(
        [{"code": code, "score": score} for code, score in scores.items()]
    ).sort_values(["score", "code"], ascending=[False, True])

    best_code = score_df.iloc[0]["code"]
    evidence_df = pd.DataFrame(evidence_rows)
    return best_code, score_df.merge(evidence_df, left_on="code", right_on="code", how="left")


def map_occupation_codes(
    labels: List[str],
    occupation_df: pd.DataFrame,
    alternate_df: pd.DataFrame,
    reported_df: pd.DataFrame,
) -> Tuple[Dict[str, str], pd.DataFrame]:
    mapping = {}
    evidence_list = []
    for label in labels:
        code, evidence = score_title_matches(label, occupation_df, alternate_df, reported_df)
        mapping[label] = code
        evidence_list.append(evidence)
    evidence_df = pd.concat(evidence_list, ignore_index=True)
    return mapping, evidence_df


def extract_descriptor_values(
    table_df: pd.DataFrame,
    occupation_codes: List[str],
    element_name: str,
    scale_id: str,
    scale_bounds: Dict[str, Tuple[float, float]],
) -> pd.DataFrame:
    assert_columns(table_df, ["O*NET-SOC Code", "Element Name", "Scale ID", "Data Value"], "Descriptor Table")
    assert scale_id in scale_bounds, f"Missing scale bounds for {scale_id}"

    df = table_df[
        (table_df["Element Name"].str.contains(element_name, case=False, na=False))
        & (table_df["Scale ID"] == scale_id)
    ].copy()
    assert not df.empty, f"No descriptor data found: {element_name} ({scale_id})"

    df = df[df["O*NET-SOC Code"].isin(occupation_codes)].copy()
    assert not df.empty, f"No descriptor data for selected occupations: {element_name} ({scale_id})"

    df["Data Value"] = pd.to_numeric(df["Data Value"], errors="coerce")
    assert df["Data Value"].notna().all(), f"Non-numeric values in {element_name} ({scale_id})"

    min_val, max_val = scale_bounds[scale_id]
    df["Raw 0-100"] = (df["Data Value"] - min_val) / (max_val - min_val) * 100.0
    return df[["O*NET-SOC Code", "Element Name", "Scale ID", "Data Value", "Raw 0-100"]]


def compute_minmax(
    table_df: pd.DataFrame,
    element_name: str,
    scale_id: str,
    scale_bounds: Dict[str, Tuple[float, float]],
    eligible_codes: List[str],
) -> Tuple[float, float]:
    df = table_df[
        (table_df["Element Name"].str.contains(element_name, case=False, na=False))
        & (table_df["Scale ID"] == scale_id)
        & (table_df["O*NET-SOC Code"].isin(eligible_codes))
    ].copy()
    df["Data Value"] = pd.to_numeric(df["Data Value"], errors="coerce")
    df = df[df["Data Value"].notna()]
    assert not df.empty, f"No data for min-max: {element_name} ({scale_id})"
    min_val, max_val = scale_bounds[scale_id]
    raw_0_100 = (df["Data Value"] - min_val) / (max_val - min_val) * 100.0
    return float(raw_0_100.min()), float(raw_0_100.max())


def normalize_scores(value: float, min_val: float, max_val: float) -> float:
    assert max_val > min_val, "Invalid min-max for normalization"
    return (value - min_val) / (max_val - min_val)


def build_descriptor_specs() -> List[Dict[str, str]]:
    return [
        {
            "axis": "digit",
            "table": "work_activities",
            "element_name": "Working with Computers",
            "scale_id": "IM",
            "key": "working_with_computers",
        },
        {
            "axis": "digit",
            "table": "work_context",
            "element_name": "E-Mail",
            "scale_id": "CXP",
            "key": "e_mail",
        },
        {
            "axis": "physical",
            "table": "work_context",
            "element_name": "Spend Time Using Your Hands to Handle, Control, or Feel Objects, Tools, or Controls",
            "scale_id": "CXP",
            "key": "using_hands",
        },
        {
            "axis": "physical",
            "table": "work_context",
            "element_name": "Spend Time Kneeling, Crouching, Stooping, or Crawling",
            "scale_id": "CXP",
            "key": "kneeling",
        },
        {
            "axis": "iprisk",
            "table": "abilities",
            "element_name": "Originality",
            "scale_id": "IM",
            "key": "originality",
        },
        {
            "axis": "iprisk",
            "table": "work_activities",
            "element_name": "Thinking Creatively",
            "scale_id": "IM",
            "key": "thinking_creatively",
        },
    ]


def compute_descriptor_weight(
    table_df: pd.DataFrame,
    element_name: str,
    scale_id: str,
    scale_bounds: Dict[str, Tuple[float, float]],
    eligible_codes: List[str],
) -> float:
    df = table_df[
        (table_df["Element Name"].str.contains(element_name, case=False, na=False))
        & (table_df["Scale ID"] == scale_id)
        & (table_df["O*NET-SOC Code"].isin(eligible_codes))
    ].copy()
    df["Data Value"] = pd.to_numeric(df["Data Value"], errors="coerce")
    df = df[df["Data Value"].notna()]
    assert not df.empty, f"No data for weight: {element_name} ({scale_id})"
    min_val, max_val = scale_bounds[scale_id]
    raw_0_100 = (df["Data Value"] - min_val) / (max_val - min_val) * 100.0
    return float(raw_0_100.mean())


def collect_descriptor_matrix(
    tables: Dict[str, pd.DataFrame],
    mapping: Dict[str, str],
    scale_bounds: Dict[str, Tuple[float, float]],
    major_group_codes: List[str],
) -> Tuple[pd.DataFrame, Dict[str, float], Dict[str, float]]:
    specs = build_descriptor_specs()
    occupation_codes = list(mapping.values())
    rows = []

    for spec in specs:
        table_df = tables[spec["table"]]
        desc_df = extract_descriptor_values(
            table_df,
            occupation_codes,
            spec["element_name"],
            spec["scale_id"],
            scale_bounds,
        )

        all_min, all_max = compute_minmax(
            table_df,
            spec["element_name"],
            spec["scale_id"],
            scale_bounds,
            table_df["O*NET-SOC Code"].unique().tolist(),
        )
        group_min, group_max = compute_minmax(
            table_df, spec["element_name"], spec["scale_id"], scale_bounds, major_group_codes
        )

        for _, row in desc_df.iterrows():
            raw_0_100 = float(row["Raw 0-100"])
            rows.append(
                {
                    "occupation_code": row["O*NET-SOC Code"],
                    "descriptor_key": spec["key"],
                    "descriptor_name": spec["element_name"],
                    "axis": spec["axis"],
                    "scale_id": spec["scale_id"],
                    "raw_value": float(row["Data Value"]),
                    "raw_0_100": raw_0_100,
                    "norm_all": normalize_scores(raw_0_100, all_min, all_max),
                    "norm_group": normalize_scores(raw_0_100, group_min, group_max),
                }
            )

    desc_df = pd.DataFrame(rows)

    weight_all = {}
    weight_group = {}
    for spec in specs:
        table_df = tables[spec["table"]]
        all_codes = table_df["O*NET-SOC Code"].unique().tolist()
        weight_all[spec["key"]] = compute_descriptor_weight(
            table_df, spec["element_name"], spec["scale_id"], scale_bounds, all_codes
        )
        weight_group[spec["key"]] = compute_descriptor_weight(
            table_df, spec["element_name"], spec["scale_id"], scale_bounds, major_group_codes
        )

    return desc_df, weight_all, weight_group


def aggregate_axes(
    desc_df: pd.DataFrame,
    weights: Dict[str, float],
    norm_col: str,
) -> pd.DataFrame:
    rows = []
    for code, sub in desc_df.groupby("occupation_code"):
        for axis, axis_df in sub.groupby("axis"):
            values = axis_df[norm_col].values
            keys = axis_df["descriptor_key"].tolist()
            assert all(k in weights for k in keys), "Missing weights for descriptor keys"
            w = np.array([weights[k] for k in keys], dtype=float)
            w = w / w.sum()
            rows.append(
                {
                    "occupation_code": code,
                    "axis": axis,
                    f"{norm_col}_equal": float(np.mean(values)),
                    f"{norm_col}_weighted": float(np.sum(values * w)),
                }
            )
    return pd.DataFrame(rows)


def to_wide_table(
    labels: List[str],
    mapping: Dict[str, str],
    desc_df: pd.DataFrame,
    agg_all: pd.DataFrame,
    agg_group: pd.DataFrame,
) -> pd.DataFrame:
    records = []
    for label in labels:
        code = mapping[label]
        record = {"occupation_label": label, "onet_soc_code": code}
        sub = desc_df[desc_df["occupation_code"] == code].copy()
        for _, row in sub.iterrows():
            key = row["descriptor_key"]
            record[f"{key}_raw"] = row["raw_value"]
            record[f"{key}_raw_0_100"] = row["raw_0_100"]
            record[f"{key}_norm_all"] = row["norm_all"]
            record[f"{key}_norm_group"] = row["norm_group"]
        agg_sub_all = agg_all[agg_all["occupation_code"] == code]
        for _, row in agg_sub_all.iterrows():
            axis = row["axis"]
            record[f"{axis}_equal_all"] = row["norm_all_equal"]
            record[f"{axis}_weighted_all"] = row["norm_all_weighted"]
        agg_sub_group = agg_group[agg_group["occupation_code"] == code]
        for _, row in agg_sub_group.iterrows():
            axis = row["axis"]
            record[f"{axis}_equal_group"] = row["norm_group_equal"]
            record[f"{axis}_weighted_group"] = row["norm_group_weighted"]
        records.append(record)
    return pd.DataFrame(records)


def print_key_points_json(name: str, data: Dict[str, Dict[str, float]]) -> None:
    payload = {"figure": name, "points": data}
    print(json.dumps(payload, ensure_ascii=True))


def apply_plot_style():
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#6b6b6b",
            "axes.labelcolor": "#4f4f4f",
            "xtick.color": "#4f4f4f",
            "ytick.color": "#4f4f4f",
            "grid.color": "#d9d9d9",
            "font.size": 12,
            "axes.titlesize": 13,
            "axes.labelsize": 12,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 10,
        }
    )


def plot_3d_scatter(df: pd.DataFrame, output_path: Path) -> None:
    apply_plot_style()
    fig = plt.figure(figsize=(7.6, 6.4))
    ax = fig.add_subplot(111, projection="3d")
    colors = ["#2C7BB6", "#D7191C", "#31A354"]

    points = []
    for i, (_, row) in enumerate(df.iterrows()):
        ax.scatter(row["digit"], row["physical"], row["iprisk"], color=colors[i], s=90, edgecolor="#4f4f4f")
        points.append([row["digit"], row["physical"], row["iprisk"]])

    triangle = Poly3DCollection([points], alpha=0.18, facecolor="#A7B3BD", edgecolor="#7A8C99")
    ax.add_collection3d(triangle)

    centroid = df[["digit", "physical", "iprisk"]].mean()
    ax.scatter(centroid["digit"], centroid["physical"], centroid["iprisk"], color="#4f4f4f", s=40, marker="x")
    ax.text(
        centroid["digit"] + 0.015,
        centroid["physical"] + 0.015,
        centroid["iprisk"] + 0.015,
        "Centroid",
        color="#4f4f4f",
    )

    ax.set_xlabel("Digitization (normalized)")
    ax.set_ylabel("Physicality (0-1)", labelpad=12)
    ax.set_zlabel("IP Risk (normalized)")
    ax.set_title("Occupation Heterogeneity: 3D Scatter")
    ax.grid(True)

    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=colors[i], markeredgecolor="#4f4f4f", markersize=8)
        for i in range(len(df))
    ]
    ax.legend(handles, df["label"].tolist(), loc="upper left", bbox_to_anchor=(0.0, 1.05))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)

    print_key_points_json(
        "fig1_heterogeneity_3d",
        {row["label"]: {"digit": row["digit"], "physical": row["physical"], "iprisk": row["iprisk"]} for _, row in df.iterrows()},
    )


def plot_2d_projections(df: pd.DataFrame, output_path: Path) -> None:
    apply_plot_style()
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.4))
    colors = ["#2C7BB6", "#D7191C", "#31A354"]

    for i, (_, row) in enumerate(df.iterrows()):
        axes[0].scatter(row["digit"], row["physical"], color=colors[i], s=90, edgecolor="#4f4f4f")
        axes[0].text(
            row["digit"] + 0.012,
            row["physical"] - 0.04,
            f"iprisk={row['iprisk']:.2f}",
            color="#3f3f3f",
            fontsize=11,
        )

        axes[1].scatter(row["digit"], row["iprisk"], color=colors[i], s=90, edgecolor="#4f4f4f")

    for ax in axes:
        ax.grid(True)
        ax.set_xlim(-0.05, 1.05)
        ax.set_ylim(-0.05, 1.05)

    axes[0].set_xlabel("Digitization (normalized)")
    axes[0].set_ylabel("Physicality (normalized)")
    axes[0].set_title("Digitization vs Physicality")

    axes[1].set_xlabel("Digitization (normalized)")
    axes[1].set_ylabel("IP Risk (normalized)")
    axes[1].set_title("Digitization vs IP Risk")

    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=colors[i], markeredgecolor="#4f4f4f", markersize=8)
        for i in range(len(df))
    ]
    axes[0].legend(handles, df["label"].tolist(), loc="upper left", bbox_to_anchor=(0.0, 1.0))
    axes[1].legend(handles, df["label"].tolist(), loc="upper left", bbox_to_anchor=(0.0, 1.0))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)

    print_key_points_json(
        "fig2_projections",
        {row["label"]: {"digit": row["digit"], "physical": row["physical"], "iprisk": row["iprisk"]} for _, row in df.iterrows()},
    )




def run_dummy_demo() -> None:
    dummy_rows = []
    for code in ["00-0000.00", "00-0001.00"]:
        for axis, key in [
            ("digit", "working_with_computers"),
            ("digit", "e_mail"),
            ("physical", "using_hands"),
            ("physical", "kneeling"),
            ("iprisk", "originality"),
            ("iprisk", "thinking_creatively"),
        ]:
            dummy_rows.append(
                {
                    "occupation_code": code,
                    "descriptor_key": key,
                    "descriptor_name": key,
                    "axis": axis,
                    "scale_id": "IM",
                    "raw_value": 3.0,
                    "raw_0_100": 50.0,
                    "norm_all": 0.5,
                    "norm_group": 0.5,
                }
            )
    dummy_df = pd.DataFrame(dummy_rows)
    dummy_weights = {key: 1.0 for key in dummy_df["descriptor_key"].unique().tolist()}
    agg_dummy = aggregate_axes(dummy_df, dummy_weights, "norm_all")
    print(json.dumps({"dummy_demo": agg_dummy.to_dict(orient="records")}, ensure_ascii=True))


def build_mapping_notes(
    mapping: Dict[str, str],
    evidence_df: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# O*NET-SOC Mapping Notes",
        "",
        "## Data Source",
        "- O*NET 30.1 Text Database (`data/raw/onet/db_30_1_text.zip`)",
        "- Official download page: https://www.onetcenter.org/database.html",
        "",
        "## Mapping Rationale",
    ]
    for label, code in mapping.items():
        lines.append(f"### {label}")
        lines.append(f"- Selected code: {code}")
        candidates = evidence_df[evidence_df["label"] == label][["code", "score"]].drop_duplicates()
        top_candidates = candidates.sort_values(["score", "code"], ascending=[False, True]).head(5)
        lines.append(
            "- Candidate codes (score): "
            + ", ".join(f"{r['code']} ({r['score']})" for _, r in top_candidates.iterrows())
        )
        lines.append("- Evidence examples:")
        examples = evidence_df[(evidence_df["label"] == label) & (evidence_df["code"] == code)].head(3)
        for _, row in examples.iterrows():
            lines.append(f"  - {row['source']}: {row['title']}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\\n".join(lines), encoding="utf-8")


def main() -> None:
    zip_path = Path("data/raw/onet/db_30_1_text.zip")
    output_csv = Path("data/processed/career_features.csv")
    fig1 = Path("figures/fig1_heterogeneity_3d.pdf")
    fig2 = Path("figures/fig2_projections.pdf")
    mapping_notes_path = Path("data/mapping_notes.md")

    labels = [
        "Software Developer / Software Engineer",
        "Electrician",
        "Illustrator / Graphic Designer",
    ]

    run_dummy_demo()
    tables = load_onet_tables(zip_path)
    scale_bounds = prepare_scale_bounds(tables["scales"])

    mapping, evidence_df = map_occupation_codes(
        labels, tables["occupation_data"], tables["alternate_titles"], tables["reported_titles"]
    )

    major_groups = {code.split("-")[0] for code in mapping.values()}
    all_codes = tables["occupation_data"]["O*NET-SOC Code"].unique().tolist()
    group_codes = [code for code in all_codes if code.split("-")[0] in major_groups]

    desc_df, weights_all, weights_group = collect_descriptor_matrix(
        tables, mapping, scale_bounds, group_codes
    )

    agg_all = aggregate_axes(desc_df, weights_all, "norm_all")
    agg_group = aggregate_axes(desc_df, weights_group, "norm_group")

    wide = to_wide_table(labels, mapping, desc_df, agg_all, agg_group)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(output_csv, index=False)

    plot_df = wide[["occupation_label", "digit_equal_all", "physical_equal_all", "iprisk_equal_all"]].copy()
    plot_df.columns = ["label", "digit", "physical", "iprisk"]
    plot_3d_scatter(plot_df, fig1)
    plot_2d_projections(plot_df, fig2)

    build_mapping_notes(mapping, evidence_df, mapping_notes_path)


if __name__ == "__main__":
    main()
