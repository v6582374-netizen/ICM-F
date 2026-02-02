import argparse
import json
import time
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
import zipfile

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


DESCRIPTOR_SPECS = [
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


DOMAIN_MAPPINGS = {
    "strict": {
        "S": {"15", "17", "19"},
        "T": {"47", "49", "51"},
        "A": {"27"},
    },
    "extended": {
        "S": {"11", "13", "15", "17", "19", "25", "29"},
        "T": {"45", "47", "49", "51", "53"},
        "A": {"27"},
    },
}
DEFAULT_MAPPING_MODE = "strict"


def assert_columns(df: pd.DataFrame, required: List[str], context: str) -> None:
    missing = [col for col in required if col not in df.columns]
    assert not missing, f"Missing columns in {context}: {missing}"


def load_table_from_source(source_path: Path, internal_path: str) -> pd.DataFrame:
    if source_path.is_dir():
        internal_parts = Path(internal_path).parts
        if internal_parts and internal_parts[0] == source_path.name:
            internal_path = str(Path(*internal_parts[1:]))
        file_path = source_path / internal_path
        assert file_path.exists(), f"Missing O*NET table file: {file_path}"
        df = pd.read_csv(file_path, sep="\t", dtype=str)
    else:
        assert source_path.exists(), f"Missing O*NET zip file: {source_path}"
        with zipfile.ZipFile(source_path) as zf:
            with zf.open(internal_path) as f:
                df = pd.read_csv(f, sep="\t", dtype=str)
    assert not df.empty, f"Loaded empty table: {internal_path}"
    return df


def load_onet_tables(source_path: Path) -> Dict[str, pd.DataFrame]:
    tables = {
        "occupation_data": "db_30_1_text/Occupation Data.txt",
        "work_activities": "db_30_1_text/Work Activities.txt",
        "work_context": "db_30_1_text/Work Context.txt",
        "abilities": "db_30_1_text/Abilities.txt",
        "scales": "db_30_1_text/Scales Reference.txt",
    }
    return {key: load_table_from_source(source_path, path) for key, path in tables.items()}


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


def extract_descriptor_frame(
    table_df: pd.DataFrame,
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

    df["Data Value"] = pd.to_numeric(df["Data Value"], errors="coerce")
    df = df[df["Data Value"].notna()].copy()
    assert not df.empty, f"No numeric values for {element_name} ({scale_id})"

    min_val, max_val = scale_bounds[scale_id]
    df["raw_0_100"] = (df["Data Value"] - min_val) / (max_val - min_val) * 100.0

    df = df.groupby("O*NET-SOC Code", as_index=False).agg({"raw_0_100": "mean"})
    raw_min, raw_max = df["raw_0_100"].min(), df["raw_0_100"].max()
    assert raw_max > raw_min, f"Invalid min-max for {element_name} ({scale_id})"
    df["norm_all"] = (df["raw_0_100"] - raw_min) / (raw_max - raw_min)
    return df[["O*NET-SOC Code", "raw_0_100", "norm_all"]]


def soc_major_group(code: str) -> str:
    if not isinstance(code, str) or "-" not in code:
        return ""
    return code.split("-")[0]


def get_mapping(mode: str) -> Dict[str, set]:
    assert mode in DOMAIN_MAPPINGS, f"Unknown mapping mode: {mode}"
    return DOMAIN_MAPPINGS[mode]


def map_domain(major_group: str, mapping: Dict[str, set] | None = None) -> str:
    mapping = mapping or get_mapping(DEFAULT_MAPPING_MODE)
    if major_group in mapping["S"]:
        return "S"
    if major_group in mapping["T"]:
        return "T"
    if major_group in mapping["A"]:
        return "A"
    return "Unknown"


def build_feature_table(
    tables: Dict[str, pd.DataFrame],
    scale_bounds: Dict[str, Tuple[float, float]],
    mapping: Dict[str, set],
) -> pd.DataFrame:
    occ_df = tables["occupation_data"][["O*NET-SOC Code", "Title"]].drop_duplicates()
    feature_df = occ_df.copy()

    for spec in DESCRIPTOR_SPECS:
        desc = extract_descriptor_frame(
            tables[spec["table"]],
            spec["element_name"],
            spec["scale_id"],
            scale_bounds,
        ).rename(
            columns={
                "raw_0_100": f"{spec['key']}_raw_0_100",
                "norm_all": f"{spec['key']}_norm",
            }
        )
        feature_df = feature_df.merge(desc, on="O*NET-SOC Code", how="left")

    descriptor_cols = [f"{spec['key']}_norm" for spec in DESCRIPTOR_SPECS]
    feature_df = feature_df.dropna(subset=descriptor_cols).copy()

    axis_map = {}
    for spec in DESCRIPTOR_SPECS:
        axis_map.setdefault(spec["axis"], []).append(f"{spec['key']}_norm")

    for axis, cols in axis_map.items():
        feature_df[axis] = feature_df[cols].mean(axis=1)

    feature_df["soc_major_group"] = feature_df["O*NET-SOC Code"].apply(soc_major_group)
    feature_df["domain"] = feature_df["soc_major_group"].apply(lambda g: map_domain(g, mapping))
    feature_df = feature_df[feature_df["domain"].isin(["S", "T", "A"])].copy()

    return feature_df


def select_candidates(df: pd.DataFrame, domain: str, top_m: int, top_k: int) -> pd.DataFrame:
    sub = df[df["domain"] == domain].copy()
    assert not sub.empty, f"No occupations found for domain {domain}"
    coords = sub[["digit", "physical", "iprisk"]].to_numpy()
    centroid = coords.mean(axis=0)
    sub["dist_to_centroid"] = np.linalg.norm(coords - centroid, axis=1)

    top_m = min(top_m, len(sub))
    top_m_df = sub.sort_values("dist_to_centroid", ascending=False).head(top_m).copy()

    extreme_codes: set[str] = set()
    for axis in ["digit", "physical", "iprisk"]:
        sorted_axis = sub.sort_values(axis, ascending=True)
        k = min(top_k, len(sorted_axis))
        bottom = sorted_axis.head(k)
        top = sorted_axis.tail(k)
        extreme_codes.update(bottom["O*NET-SOC Code"].tolist())
        extreme_codes.update(top["O*NET-SOC Code"].tolist())

    union_codes = set(top_m_df["O*NET-SOC Code"]).union(extreme_codes)
    candidates = sub[sub["O*NET-SOC Code"].isin(union_codes)].copy()
    candidates = candidates.sort_values("dist_to_centroid", ascending=False).reset_index(drop=True)
    candidates["rank_by_distance"] = np.arange(1, len(candidates) + 1)
    return candidates


@dataclass
class TriangleResult:
    area: float
    min_edge: float
    edge_lengths: Tuple[float, float, float]
    vector_ab: List[float]
    vector_ac: List[float]
    cross: List[float]
    cross_norm: float
    points: List[Dict[str, object]]


def compute_triangle_search(
    s_df: pd.DataFrame,
    t_df: pd.DataFrame,
    a_df: pd.DataFrame,
) -> TriangleResult:
    s_points = s_df[["digit", "physical", "iprisk"]].to_numpy()
    t_points = t_df[["digit", "physical", "iprisk"]].to_numpy()
    a_points = a_df[["digit", "physical", "iprisk"]].to_numpy()

    best: TriangleResult | None = None
    eps = 1e-12

    for i, s in enumerate(s_points):
        for j, t in enumerate(t_points):
            ab = t - s
            ab_len = float(np.linalg.norm(ab))
            for k, a in enumerate(a_points):
                ac = a - s
                cross = np.cross(ab, ac)
                cross_norm = float(np.linalg.norm(cross))
                area = 0.5 * cross_norm
                bc_len = float(np.linalg.norm(a - t))
                ac_len = float(np.linalg.norm(ac))
                min_edge = min(ab_len, ac_len, bc_len)

                if best is None or area > best.area + eps or (
                    abs(area - best.area) <= eps and min_edge > best.min_edge + eps
                ):
                    points = [
                        build_point_record(s_df.iloc[i]),
                        build_point_record(t_df.iloc[j]),
                        build_point_record(a_df.iloc[k]),
                    ]
                    best = TriangleResult(
                        area=area,
                        min_edge=min_edge,
                        edge_lengths=(ab_len, ac_len, bc_len),
                        vector_ab=ab.tolist(),
                        vector_ac=ac.tolist(),
                        cross=cross.tolist(),
                        cross_norm=cross_norm,
                        points=points,
                    )

    assert best is not None, "Triangle search failed to produce a result"
    return best


def build_point_record(row: pd.Series) -> Dict[str, object]:
    return {
        "onet_soc_code": row["O*NET-SOC Code"],
        "title": row["Title"],
        "domain": row["domain"],
        "digit": float(row["digit"]),
        "physical": float(row["physical"]),
        "iprisk": float(row["iprisk"]),
    }


def print_key_points_json(name: str, points: Dict[str, Dict[str, float]]) -> None:
    payload = {"figure": name, "points": points}
    print(json.dumps(payload, ensure_ascii=True))


def apply_plot_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#6b6b6b",
            "axes.labelcolor": "#4f4f4f",
            "xtick.color": "#4f4f4f",
            "ytick.color": "#4f4f4f",
            "grid.color": "#d9d9d9",
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "legend.fontsize": 9,
        }
    )


def apply_axis_trim(ax, coords: np.ndarray, pad_ratio: float = 0.03) -> None:
    mins = coords.min(axis=0)
    maxs = coords.max(axis=0)
    ranges = maxs - mins
    pad = np.where(ranges > 0, ranges * pad_ratio, 0.02)
    ax.set_xlim(mins[0] - pad[0], maxs[0] + pad[0])
    ax.set_ylim(mins[1] - pad[1], maxs[1] + pad[1])
    ax.set_zlim(mins[2] - pad[2], maxs[2] + pad[2])


def wrap_annotation_text(text: str, width: int = 26) -> str:
    cleaned = " ".join(str(text).split())
    return textwrap.fill(cleaned, width=width, break_long_words=False, break_on_hyphens=False)


def plot_trendline(ax, x: np.ndarray, y: np.ndarray, color: str, label: str) -> None:
    if len(x) < 2:
        return
    coeff = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 100)
    ys = coeff[0] * xs + coeff[1]
    ax.plot(xs, ys, color=color, linestyle="--", linewidth=1.2, label=label)


def plot_3d_all_points(
    all_df: pd.DataFrame,
    triangle_df: pd.DataFrame,
    output_path: Path,
) -> None:
    apply_plot_style()
    fig = plt.figure(figsize=(8.2, 6.6))
    ax = fig.add_subplot(111, projection="3d")

    colors = {"S": "#2C7BB6", "T": "#D7191C", "A": "#31A354"}
    for domain, group in all_df.groupby("domain"):
        ax.scatter(
            group["digit"],
            group["physical"],
            group["iprisk"],
            color=colors.get(domain, "#9e9e9e"),
            s=10,
            alpha=0.35,
            edgecolor="none",
            label=f"{domain} domain",
        )

    points = triangle_df[["digit", "physical", "iprisk"]].to_numpy()
    tri_colors = ["#0C2C84", "#99000D", "#006D2C"]
    for i, (_, row) in enumerate(triangle_df.iterrows()):
        ax.scatter(
            row["digit"],
            row["physical"],
            row["iprisk"],
            color=tri_colors[i],
            s=90,
            edgecolor="#4f4f4f",
            label=f"Triangle {row['domain']}",
        )
        label_text = f"{row['title']} ({row['onet_soc_code']})"
        z_offset = 0.01
        if str(row["title"]).startswith("First-Line Supervisors of Mechanics"):
            z_offset = -0.1
        ax.text(
            row["digit"] + 0.01,
            row["physical"] + 0.01,
            row["iprisk"] + z_offset,
            wrap_annotation_text(label_text, width=28),
            fontsize=9,
            color="#2f2f2f",
            linespacing=1.05,
            clip_on=True,
        )

    triangle = Poly3DCollection([points], alpha=0.2, facecolor="#A7B3BD", edgecolor="#7A8C99")
    ax.add_collection3d(triangle)

    coords = all_df[["digit", "physical", "iprisk"]].to_numpy()
    centroid = coords.mean(axis=0)
    centered = coords - centroid
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    direction = vt[0]
    projections = centered @ direction
    line_min = centroid + direction * projections.min()
    line_max = centroid + direction * projections.max()
    ax.plot(
        [line_min[0], line_max[0]],
        [line_min[1], line_max[1]],
        [line_min[2], line_max[2]],
        color="#7A7A7A",
        linewidth=1.5,
        linestyle="--",
        label="Trendline (PC1)",
    )

    ax.set_xlabel("Digitization (normalized)")
    ax.set_ylabel("Physicality (normalized)", labelpad=10)
    ax.set_zlabel("IP Risk (normalized)")
    ax.set_title("All Occupations: 3D Heterogeneity Cloud")
    ax.grid(True)
    apply_axis_trim(ax, coords)

    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.02), ncol=2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)

    print_key_points_json(
        "fig_heterogeneity_3d_all_points",
        {row["title"]: {"digit": row["digit"], "physical": row["physical"], "iprisk": row["iprisk"]} for _, row in triangle_df.iterrows()},
    )


def plot_2d_projections_all_points(
    all_df: pd.DataFrame,
    triangle_df: pd.DataFrame,
    output_path: Path,
) -> None:
    apply_plot_style()
    fig, axes = plt.subplots(1, 3, figsize=(15.8, 5.0))
    colors = {"S": "#2C7BB6", "T": "#D7191C", "A": "#31A354"}

    projections = [
        ("digit", "physical", "Digitization vs Physicality"),
        ("digit", "iprisk", "Digitization vs IP Risk"),
        ("physical", "iprisk", "Physicality vs IP Risk"),
    ]

    for ax, (x_col, y_col, title) in zip(axes, projections):
        for domain, group in all_df.groupby("domain"):
            ax.scatter(
                group[x_col],
                group[y_col],
                color=colors.get(domain, "#9e9e9e"),
                s=12,
                alpha=0.35,
                edgecolor="none",
                label=f"{domain} domain",
            )
        tri_points = triangle_df[[x_col, y_col]].to_numpy()
        ax.plot(tri_points[:, 0], tri_points[:, 1], color="#4f4f4f", linewidth=1.0, alpha=0.8)
        ax.scatter(
            tri_points[:, 0],
            tri_points[:, 1],
            color="#FFD700",
            s=90,
            edgecolor="#4f4f4f",
            label="Triangle points",
        )
        for _, row in triangle_df.iterrows():
            label_with_code = f"{row['title']} ({row['onet_soc_code']})"
            x_pos = float(row[x_col]) + 0.01
            y_pos = float(row[y_col]) + 0.01
            x_pos = min(max(x_pos, -0.02), 1.02)
            y_pos = min(max(y_pos, -0.02), 1.02)
            ax.text(
                x_pos,
                y_pos,
                wrap_annotation_text(label_with_code, width=30),
                fontsize=8,
                color="#2f2f2f",
                linespacing=1.05,
                clip_on=True,
            )

        plot_trendline(ax, all_df[x_col].to_numpy(), all_df[y_col].to_numpy(), "#7A7A7A", "Trendline")
        ax.set_xlabel(f"{x_col.capitalize()} (normalized)")
        ax.set_ylabel(f"{y_col.capitalize()} (normalized)")
        ax.set_title(title)
        ax.grid(True)
        ax.set_xlim(-0.05, 1.05)
        ax.set_ylim(-0.05, 1.05)

    for ax in axes:
        ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.0), fontsize=8, ncol=2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)

    print_key_points_json(
        "fig_heterogeneity_2d_projections_all_points",
        {row["title"]: {"digit": row["digit"], "physical": row["physical"], "iprisk": row["iprisk"]} for _, row in triangle_df.iterrows()},
    )


def plot_sensitivity_candidate_scale(sensitivity: Dict[str, object], output_path: Path) -> None:
    apply_plot_style()
    results = sensitivity.get("results", [])
    if not results:
        return
    ms = np.array([r["top_m"] for r in results], dtype=float)
    areas = np.array([r["area3d"] for r in results], dtype=float)

    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.plot(ms, areas, marker="o", color="#6C8EBF", linewidth=1.4, markersize=5, label="Area3D")

    coeff = np.polyfit(ms, areas, 1)
    xs = np.linspace(ms.min(), ms.max(), 100)
    ys = coeff[0] * xs + coeff[1]
    ax.plot(xs, ys, color="#9E9E9E", linestyle="--", linewidth=1.1, label="Trendline")

    ax.set_xlabel("Candidate pool size M")
    ax.set_ylabel("Triangle area (normalized)")
    ax.set_title("Sensitivity to Candidate Pool Size")
    ax.grid(True)
    ax.set_xlim(ms.min() - 20, ms.max() + 20)

    for m, a in zip(ms, areas):
        ax.text(m, a + 0.005, f"{a:.4f}", ha="center", fontsize=9, color="#4f4f4f")

    ax.legend(loc="upper left")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)

    print_key_points_json(
        "fig_sensitivity_candidate_scale",
        {str(int(m)): {"area3d": float(a)} for m, a in zip(ms, areas)},
    )


def write_triangle_json(result: TriangleResult, output_path: Path) -> None:
    payload = {
        "triangle": result.points,
        "area3d": result.area,
        "edge_lengths": {"ab": result.edge_lengths[0], "ac": result.edge_lengths[1], "bc": result.edge_lengths[2]},
        "min_edge_length": result.min_edge,
        "tie_break": "maximize area; if tie, maximize min_edge_length",
        "vector_ab": result.vector_ab,
        "vector_ac": result.vector_ac,
        "cross": result.cross,
        "cross_norm": result.cross_norm,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def write_search_report(
    output_path: Path,
    total_count: int,
    filtered_count: int,
    domain_counts: Dict[str, int],
    candidate_counts: Dict[str, int],
    loops: int,
    result: TriangleResult,
    top_m: int,
    top_k: int,
    mapping_mode: str,
) -> None:
    lines = [
        "# Max-Area Triangle Search Report (All Occupations)",
        "",
        f"- Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Mapping mode: {mapping_mode}",
        f"- Total occupations (raw): {total_count}",
        f"- After descriptor completeness filter: {filtered_count}",
        f"- Domain counts (S/T/A): {domain_counts}",
        "",
        "## Descriptor Specs (2 per axis)",
    ]
    for spec in DESCRIPTOR_SPECS:
        lines.append(
            f"- {spec['axis']} | {spec['key']} | {spec['element_name']} | {spec['scale_id']} | {spec['table']}"
        )
    lines += [
        "",
        "## Domain Mapping (SOC Major Groups)",
        f"- S groups: {sorted(DOMAIN_MAPPINGS[mapping_mode]['S'])}",
        f"- T groups: {sorted(DOMAIN_MAPPINGS[mapping_mode]['T'])}",
        f"- A groups: {sorted(DOMAIN_MAPPINGS[mapping_mode]['A'])}",
        "",
        "## Candidate Selection",
        f"- Method: top {top_m} farthest from domain centroid + extremes_per_axis (top/bottom {top_k})",
        f"- Candidate counts: {candidate_counts}",
        f"- Triple-loop combinations evaluated: {loops}",
        "",
        "## Best Triangle",
        f"- Area3D: {result.area:.6f}",
        f"- Min edge length: {result.min_edge:.6f}",
        f"- Edge lengths (ab, ac, bc): {result.edge_lengths}",
        "",
        "### Points",
    ]
    for point in result.points:
        lines.append(f"- {point['domain']} | {point['onet_soc_code']} | {point['title']}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_dummy_demo() -> None:
    dummy = pd.DataFrame(
        [
            {"O*NET-SOC Code": "00-0000.00", "Title": "Dummy S", "digit": 0.1, "physical": 0.9, "iprisk": 0.2, "domain": "S"},
            {"O*NET-SOC Code": "00-0001.00", "Title": "Dummy T", "digit": 0.8, "physical": 0.2, "iprisk": 0.4, "domain": "T"},
            {"O*NET-SOC Code": "00-0002.00", "Title": "Dummy A", "digit": 0.4, "physical": 0.3, "iprisk": 0.9, "domain": "A"},
        ]
    )
    result = compute_triangle_search(dummy[dummy["domain"] == "S"], dummy[dummy["domain"] == "T"], dummy[dummy["domain"] == "A"])
    print(json.dumps({"dummy_area": result.area}, ensure_ascii=True))


def write_domain_mapping_used(output_path: Path) -> None:
    lines = [
        "# Domain Mapping Used (SOC 2018 Major Groups)",
        "",
        "This file documents the SOC major-group mapping used for S/T/A classification.",
        "",
        "## Scope",
        "- SOC 2018 major groups (two-digit prefixes from O*NET-SOC codes).",
        "- Local O*NET source: `data/raw/onet/db_30_1_text/Occupation Data.txt`.",
        "- Authoritative SOC major-group list: https://www.bls.gov/soc/2018/major_groups.htm",
        "",
        "## strict (default in code)",
        "```",
        f"STEM  = {sorted(DOMAIN_MAPPINGS['strict']['S'])}",
        f"TRADE = {sorted(DOMAIN_MAPPINGS['strict']['T'])}",
        f"ARTS  = {sorted(DOMAIN_MAPPINGS['strict']['A'])}",
        "```",
        "",
        "## extended (optional)",
        "```",
        f"STEM  = {sorted(DOMAIN_MAPPINGS['extended']['S'])}",
        f"TRADE = {sorted(DOMAIN_MAPPINGS['extended']['T'])}",
        f"ARTS  = {sorted(DOMAIN_MAPPINGS['extended']['A'])}",
        "```",
        "",
        "## Notes",
        "- The code defaults to strict mapping unless --mapping extended is passed.",
        "- Keep SOC major groups aligned to the BLS SOC 2018 list.",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_sensitivity(
    feature_df: pd.DataFrame,
    mapping_mode: str,
    top_m_values: List[int],
    top_k: int,
) -> Dict[str, object]:
    results = []
    baseline_codes: set[str] | None = None
    baseline_area: float | None = None

    for top_m in top_m_values:
        s_candidates = select_candidates(feature_df, "S", top_m, top_k)
        t_candidates = select_candidates(feature_df, "T", top_m, top_k)
        a_candidates = select_candidates(feature_df, "A", top_m, top_k)
        result = compute_triangle_search(s_candidates, t_candidates, a_candidates)
        codes = {point["onet_soc_code"] for point in result.points}
        if baseline_codes is None:
            baseline_codes = codes
            baseline_area = result.area
        results.append(
            {
                "top_m": top_m,
                "area3d": result.area,
                "min_edge_length": result.min_edge,
                "triangle": result.points,
                "edge_lengths": {
                    "ab": result.edge_lengths[0],
                    "ac": result.edge_lengths[1],
                    "bc": result.edge_lengths[2],
                },
                "vector_ab": result.vector_ab,
                "vector_ac": result.vector_ac,
                "cross_norm": result.cross_norm,
                "same_points_as_baseline": codes == baseline_codes,
            }
        )

    max_diff_pct = None
    if baseline_area is not None:
        diffs = [abs(r["area3d"] - baseline_area) / baseline_area for r in results]
        max_diff_pct = max(diffs) * 100.0 if diffs else None

    return {
        "mapping_mode": mapping_mode,
        "top_k": top_k,
        "results": results,
        "max_area_diff_pct_vs_baseline": max_diff_pct,
        "baseline_top_m": top_m_values[0] if top_m_values else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Search max-area triangle across all occupations.")
    parser.add_argument("--mapping", choices=["strict", "extended"], default=DEFAULT_MAPPING_MODE)
    parser.add_argument("--top-m", type=int, default=200)
    parser.add_argument("--top-k", type=int, default=50)
    args = parser.parse_args()

    mapping_mode = args.mapping
    top_m = args.top_m
    top_k = args.top_k
    suffix = mapping_mode

    zip_path = Path("data/raw/onet/db_30_1_text.zip")
    dir_path = Path("data/raw/onet/db_30_1_text")
    if zip_path.exists():
        source_path = zip_path
    else:
        assert dir_path.exists(), f"Missing O*NET data: {zip_path} or {dir_path}"
        source_path = dir_path
    output_csv = Path("data/processed/career_features_all.csv")
    output_triangle = Path(f"data/processed/max_area_triangle_{suffix}.json")
    output_triangle_sensitivity = Path(f"data/processed/max_area_triangle_{suffix}_sensitivity.json")
    output_report = Path(f"data/processed/max_area_triangle_{suffix}_search_report.md")
    output_mapping_used = Path("data/processed/domain_mapping_used.md")
    fig_3d = Path(f"figures/fig_heterogeneity_3d_all_points_{suffix}_tight.pdf")
    fig_2d = Path(f"figures/fig_heterogeneity_2d_projections_all_points_{suffix}.pdf")
    fig_sensitivity = Path(f"figures/fig_sensitivity_candidate_scale_{suffix}.pdf")

    run_dummy_demo()
    tables = load_onet_tables(source_path)
    scale_bounds = prepare_scale_bounds(tables["scales"])
    mapping = get_mapping(mapping_mode)
    feature_df = build_feature_table(tables, scale_bounds, mapping)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    feature_df.to_csv(output_csv, index=False)

    total_count = len(tables["occupation_data"]["O*NET-SOC Code"].unique())
    filtered_count = len(feature_df)
    domain_counts = feature_df["domain"].value_counts().to_dict()

    s_candidates = select_candidates(feature_df, "S", top_m, top_k)
    t_candidates = select_candidates(feature_df, "T", top_m, top_k)
    a_candidates = select_candidates(feature_df, "A", top_m, top_k)

    loops = len(s_candidates) * len(t_candidates) * len(a_candidates)
    result = compute_triangle_search(s_candidates, t_candidates, a_candidates)

    write_triangle_json(result, output_triangle)
    write_search_report(
        output_report,
        total_count,
        filtered_count,
        domain_counts,
        {"S": len(s_candidates), "T": len(t_candidates), "A": len(a_candidates)},
        loops,
        result,
        top_m,
        top_k,
        mapping_mode,
    )

    triangle_df = pd.DataFrame(result.points)
    plot_3d_all_points(feature_df, triangle_df, fig_3d)
    plot_2d_projections_all_points(feature_df, triangle_df, fig_2d)

    sensitivity = run_sensitivity(feature_df, mapping_mode, [200, 400, 800], top_k)
    output_triangle_sensitivity.parent.mkdir(parents=True, exist_ok=True)
    output_triangle_sensitivity.write_text(
        json.dumps(sensitivity, ensure_ascii=True, indent=2), encoding="utf-8"
    )
    plot_sensitivity_candidate_scale(sensitivity, fig_sensitivity)

    write_domain_mapping_used(output_mapping_used)


if __name__ == "__main__":
    main()
