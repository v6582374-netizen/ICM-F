#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Adoption-anchored A(t) scenarios + task-share forecasting (mixture reweighting).
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


REQUIRED_COLUMNS = [
    "task_id",
    "task_text",
    "w",
    "s",
    "c",
    "mu_task",
    "dims",
    "evidence_note",
]


def apply_plot_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#6f7a86",
            "axes.labelcolor": "#2b2f33",
            "xtick.color": "#2b2f33",
            "ytick.color": "#2b2f33",
            "grid.color": "#c7cdd3",
            "grid.alpha": 0.35,
            "grid.linestyle": "-",
            "font.size": 10,
        }
    )


def muted_palette() -> Dict[str, str]:
    return {
        "Slow": "#7f8c99",
        "Baseline": "#5f7fa1",
        "Fast": "#7b9b8a",
        "Other": "#4f555c",
    }


def _safe_float(x) -> float:
    try:
        return float(x)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"无法转换为 float: {x}") from exc


def load_adoption_anchors(path: Path) -> List[Dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    anchors = payload.get("values", [])
    if len(anchors) < 2:
        raise ValueError("adoption_anchors.json 至少需要 2 个锚点")
    return anchors


def load_scenario_config(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_task_dna(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    validate_schema_with_dictionary(df, path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path} 缺失列: {missing}")
    if "mu_task" not in df.columns or df["mu_task"].isna().any():
        df["mu_task"] = df["c"].astype(float) - df["s"].astype(float)
    df["w"] = df["w"].astype(float)
    df["s"] = df["s"].astype(float)
    df["c"] = df["c"].astype(float)
    df["mu_task"] = df["mu_task"].astype(float)
    return df


def validate_schema_with_dictionary(df: pd.DataFrame, path: Path) -> None:
    dict_path = Path("data_dictionary.md")
    if not dict_path.exists():
        return
    lines = dict_path.read_text(encoding="utf-8").splitlines()
    match_line = None
    for line in lines:
        if str(path) in line:
            match_line = line
            break
    if match_line is None:
        return
    parts = [p.strip() for p in match_line.split("|")]
    if len(parts) < 5:
        return
    cols_segment = parts[4]
    if cols_segment:
        cols = [c.strip() for c in cols_segment.split(",")]
        cols = [c for c in cols if c]
        missing_cols = [c for c in REQUIRED_COLUMNS if c not in cols]
        assert not missing_cols, f"数据字典未包含必需列: {missing_cols}"


def build_time_grid(cfg: Dict) -> np.ndarray:
    grid = cfg["time_grid"]
    t_start = _safe_float(grid["t_start_year"])
    t_end = _safe_float(grid["t_end_year"])
    step = _safe_float(grid["step_year"])
    n = int(round((t_end - t_start) / step)) + 1
    return t_start + step * np.arange(n)


def piecewise_linear_scenario(
    t_grid: np.ndarray,
    anchor_2024: Tuple[float, float],
    anchor_2025: Tuple[float, float],
    post_2025_slope: float,
    saturation: float,
) -> np.ndarray:
    t0, a0 = anchor_2024
    t1, a1 = anchor_2025
    slope_2024_2025 = (a1 - a0) / (t1 - t0)
    values = np.zeros_like(t_grid, dtype=float)
    for i, t in enumerate(t_grid):
        if t <= t0:
            values[i] = a0 + slope_2024_2025 * (t - t0)
        elif t <= t1:
            values[i] = a0 + slope_2024_2025 * (t - t0)
        else:
            values[i] = a1 + post_2025_slope * (t - t1)
    return np.clip(values, 0.0, saturation)


def fast_piecewise_scenario(
    t_grid: np.ndarray,
    anchor_2024: Tuple[float, float],
    anchor_2025: Tuple[float, float],
    target_2026: float,
    post_2026_slope: float,
    saturation: float,
) -> np.ndarray:
    t0, a0 = anchor_2024
    t1, a1 = anchor_2025
    t2 = 2026.0
    slope_2024_2025 = (a1 - a0) / (t1 - t0)
    slope_2025_2026 = (target_2026 - a1) / (t2 - t1)
    values = np.zeros_like(t_grid, dtype=float)
    for i, t in enumerate(t_grid):
        if t <= t0:
            values[i] = a0 + slope_2024_2025 * (t - t0)
        elif t <= t1:
            values[i] = a0 + slope_2024_2025 * (t - t0)
        elif t <= t2:
            values[i] = a1 + slope_2025_2026 * (t - t1)
        else:
            values[i] = target_2026 + post_2026_slope * (t - t2)
    return np.clip(values, 0.0, saturation)


def logistic_params_from_anchors(
    t1: float,
    a1: float,
    t2: float,
    a2: float,
    a_min: float,
    a_max: float,
    k_range: Tuple[float, float],
) -> Tuple[float, float]:
    def logit(a: float) -> float:
        return math.log((a - a_min) / (a_max - a))

    raw_k = (logit(a2) - logit(a1)) / (t2 - t1)
    k = min(max(raw_k, k_range[0]), k_range[1])
    t_mid = t1 - (1.0 / k) * logit(a1)
    return k, t_mid


def logistic_scenario(
    t_grid: np.ndarray,
    anchor_2024: Tuple[float, float],
    anchor_2025: Tuple[float, float],
    a_min: float,
    a_max: float,
    k_range: Tuple[float, float],
) -> np.ndarray:
    t1, a1 = anchor_2024
    t2, a2 = anchor_2025
    k, t_mid = logistic_params_from_anchors(t1, a1, t2, a2, a_min, a_max, k_range)
    values = a_min + (a_max - a_min) / (1.0 + np.exp(-k * (t_grid - t_mid)))
    return np.clip(values, 0.0, a_max)


def build_adoption_scenarios(
    t_grid: np.ndarray,
    anchors: List[Dict],
    cfg: Dict,
) -> Dict[str, Dict[str, np.ndarray]]:
    anchor_map = {a["t_year"]: a["A_value"] for a in anchors}
    anchor_2024 = (2024.0, float(anchor_map[2024]))
    anchor_2025 = (2025.0, float(anchor_map[2025]))
    anchor_2026 = float(anchor_map.get(2026, 0.80))

    pw = cfg["piecewise_linear_params"]
    scenarios_pw = {
        "Baseline": piecewise_linear_scenario(
            t_grid,
            anchor_2024,
            anchor_2025,
            post_2025_slope=pw["Baseline"]["post_2025_slope"],
            saturation=pw["Baseline"]["saturation"],
        ),
        "Slow": piecewise_linear_scenario(
            t_grid,
            anchor_2024,
            anchor_2025,
            post_2025_slope=pw["Slow"]["post_2025_slope"],
            saturation=pw["Slow"]["saturation"],
        ),
        "Fast": fast_piecewise_scenario(
            t_grid,
            anchor_2024,
            anchor_2025,
            target_2026=max(anchor_2026, pw["Fast"]["post_2025_target_2026"]),
            post_2026_slope=pw["Fast"]["post_2026_slope"],
            saturation=pw["Fast"]["saturation"],
        ),
    }

    lr = cfg["logistic_param_ranges"]
    scenarios_logistic = {}
    for name, params in lr.items():
        scenarios_logistic[name] = logistic_scenario(
            t_grid,
            anchor_2024,
            anchor_2025,
            a_min=params["A_min"],
            a_max=params["A_max"],
            k_range=tuple(params["k_range"]),
        )
    return {"piecewise_linear_saturation": scenarios_pw, "logistic": scenarios_logistic}


def compute_q_p(
    weights: np.ndarray,
    mu_task: np.ndarray,
    a_values: np.ndarray,
    eta: float,
) -> np.ndarray:
    weights = weights.reshape(1, -1)
    mu_task = mu_task.reshape(1, -1)
    a_values = a_values.reshape(-1, 1)
    q = weights * ((1.0 - a_values) + a_values * np.exp(eta * mu_task))
    denom = q.sum(axis=1, keepdims=True)
    p = q / denom
    return p


def compute_t_star(
    t_grid: np.ndarray,
    p_values: np.ndarray,
    eps: float,
) -> List[float | None]:
    t_star = []
    for j in range(p_values.shape[1]):
        idx = np.where(p_values[:, j] <= eps)[0]
        if idx.size == 0:
            t_star.append(None)
        else:
            t_star.append(float(t_grid[idx[0]]))
    return t_star


def compute_summary(
    t_grid: np.ndarray,
    p_values: np.ndarray,
    task_ids: Iterable,
    top_n: int = 5,
) -> Dict:
    p_start = p_values[0, :]
    p_end = p_values[-1, :]
    delta = p_end - p_start
    order = np.argsort(delta)
    losers = [(str(task_ids[i]), float(delta[i])) for i in order[:top_n]]
    gainers = [(str(task_ids[i]), float(delta[i])) for i in order[-top_n:][::-1]]
    reallocation_mass = 0.5 * float(np.abs(delta).sum())
    hhi_start = float(np.sum(p_start ** 2))
    hhi_end = float(np.sum(p_end ** 2))
    return {
        "top_gainers": gainers,
        "top_losers": losers,
        "reallocation_mass": reallocation_mass,
        "hhi_start": hhi_start,
        "hhi_end": hhi_end,
    }


def latex_escape(text: str) -> str:
    mapping = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "\\": r"\textbackslash{}",
    }
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text


def write_appendix_table(
    df: pd.DataFrame,
    output_path: Path,
    max_evidence_len: int = 80,
) -> None:
    header = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Task DNA summary for SOC occupation.}",
        r"\label{tab:appendix_taskdna}",
        r"\begin{tabular}{@{}lllllll@{}}",
        r"\toprule",
        r"Task ID & Dims & $w$ & $s$ & $c$ & $\mu_{task}$ & Evidence (short) \\",
        r"\midrule",
    ]
    rows = []
    for _, row in df.iterrows():
        evidence = str(row.get("evidence_note", ""))[:max_evidence_len]
        rows.append(
            " & ".join(
                [
                    latex_escape(str(row["task_id"])),
                    latex_escape(str(row["dims"])),
                    f"{float(row['w']):.4f}",
                    f"{float(row['s']):.2f}",
                    f"{float(row['c']):.2f}",
                    f"{float(row['mu_task']):.2f}",
                    latex_escape(evidence),
                ]
            )
            + r" \\"
        )
    footer = [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    content = "\n".join(header + rows + footer)
    output_path.write_text(content, encoding="utf-8")


def plot_adoption_scenarios(
    t_grid: np.ndarray,
    scenarios: Dict[str, np.ndarray],
    anchors: List[Dict],
    output_path: Path,
) -> None:
    apply_plot_style()
    colors = muted_palette()
    linestyles = {"Slow": "--", "Baseline": "-", "Fast": "-."}
    plt.figure(figsize=(7.2, 4.2), dpi=300)
    for name, values in scenarios.items():
        plt.plot(
            t_grid,
            values,
            label=name,
            color=colors.get(name, "#888888"),
            linewidth=1.8,
            linestyle=linestyles.get(name, "-"),
        )
    for a in anchors:
        plt.scatter(a["t_year"], a["A_value"], color="#555555", s=18, zorder=3)
        plt.annotate(
            f"{a['t_year']}: {a['A_value']:.2f}",
            (a["t_year"], a["A_value"]),
            textcoords="offset points",
            xytext=(4, 6),
            fontsize=8,
            color="#444444",
        )
    plt.xlabel("Year")
    plt.ylabel("Adoption rate A(t)")
    plt.title("Adoption scenarios A(t)")
    plt.grid(True, alpha=0.3)
    plt.legend(frameon=False, fontsize=8)
    plt.tight_layout()
    plt.savefig(output_path, format="pdf")
    plt.close()
    key_points = {
        "anchors": anchors,
        "scenario_endpoints": {k: float(v[-1]) for k, v in scenarios.items()},
    }
    print(json.dumps({"fig_A_t_scenarios": key_points}, ensure_ascii=False))


def plot_task_share_topk(
    t_grid: np.ndarray,
    p_values: np.ndarray,
    task_ids: List,
    top_k: int,
    output_path: Path,
) -> None:
    apply_plot_style()
    avg_share = p_values.mean(axis=0)
    top_idx = np.argsort(avg_share)[-top_k:][::-1]
    other_idx = [i for i in range(len(task_ids)) if i not in top_idx]
    plt.figure(figsize=(7.2, 4.2), dpi=300)
    palette = [
        "#5f7fa1",
        "#7b9b8a",
        "#b09b73",
        "#8f9aa6",
        "#7f8c99",
        "#9d8f7a",
        "#6f8f95",
        "#9aa3ad",
    ]
    markers = ["o", "s", "D", "^", "v", "P", "X", "h"]
    for i, idx in enumerate(top_idx):
        plt.plot(
            t_grid,
            p_values[:, idx],
            label=f"{task_ids[idx]}",
            linewidth=1.4,
            color=palette[i % len(palette)],
            marker=markers[i % len(markers)],
            markevery=max(int(len(t_grid) / 10), 1),
            markersize=3,
            markerfacecolor="white",
            markeredgewidth=0.6,
        )
    if other_idx:
        other_share = p_values[:, other_idx].sum(axis=1)
        plt.plot(t_grid, other_share, label="Other", linewidth=1.8, color=muted_palette()["Other"])
    plt.xlabel("Year")
    plt.ylabel("Task share p_ij(t)")
    plt.title("Top task shares (baseline, eta=1)")
    plt.grid(True, alpha=0.3)
    plt.legend(frameon=False, fontsize=7)
    plt.tight_layout()
    plt.savefig(output_path, format="pdf")
    plt.close()
    key_points = {"top_tasks": [str(task_ids[i]) for i in top_idx], "other_count": len(other_idx)}
    print(json.dumps({"fig_task_share_topk": key_points}, ensure_ascii=False))


def plot_task_share_all(
    t_grid: np.ndarray,
    p_values: np.ndarray,
    output_path: Path,
) -> None:
    apply_plot_style()
    plt.figure(figsize=(7.2, 4.2), dpi=300)
    cmap = plt.get_cmap("cividis")
    n_tasks = p_values.shape[1]
    for j in range(n_tasks):
        plt.plot(
            t_grid,
            p_values[:, j],
            color=cmap(0.15 + 0.7 * j / max(n_tasks - 1, 1)),
            linewidth=0.8,
            alpha=0.35,
        )
    p_med = np.median(p_values, axis=1)
    p_lo = np.quantile(p_values, 0.10, axis=1)
    p_hi = np.quantile(p_values, 0.90, axis=1)
    plt.fill_between(t_grid, p_lo, p_hi, color="#cfd5db", alpha=0.35, label="10–90% band")
    plt.plot(t_grid, p_med, color="#4f555c", linewidth=1.6, label="Median")
    plt.xlabel("Year")
    plt.ylabel("Task share p_ij(t)")
    plt.title("All task shares (baseline, eta=1)")
    plt.grid(True, alpha=0.3)
    plt.legend(frameon=False, fontsize=7)
    plt.tight_layout()
    plt.savefig(output_path, format="pdf")
    plt.close()
    print(json.dumps({"fig_task_share_all": {"tasks": int(p_values.shape[1])}}, ensure_ascii=False))


def plot_tstar_distribution(
    t_star_1: List[float | None],
    t_star_5: List[float | None],
    output_path: Path,
) -> None:
    apply_plot_style()
    t1 = [t for t in t_star_1 if t is not None]
    t5 = [t for t in t_star_5 if t is not None]
    bins = np.arange(2024, 2036, 1)
    plt.figure(figsize=(7.2, 4.2), dpi=300)
    plt.hist(t1, bins=bins, alpha=0.55, label="eps=1%", color="#5f7fa1", edgecolor="#3f4a55")
    plt.hist(t5, bins=bins, alpha=0.55, label="eps=5%", color="#7b9b8a", edgecolor="#3f4a55")
    plt.xlabel("t* year")
    plt.ylabel("Count of tasks")
    plt.title("Distribution of t*")
    plt.grid(True, alpha=0.3)
    plt.legend(frameon=False, fontsize=8)
    plt.tight_layout()
    plt.savefig(output_path, format="pdf")
    plt.close()
    key_points = {"eps_1_count": len(t1), "eps_5_count": len(t5)}
    print(json.dumps({"fig_tstar_distribution": key_points}, ensure_ascii=False))


def ensure_probabilities(p_values: np.ndarray) -> None:
    row_sums = p_values.sum(axis=1)
    assert np.allclose(row_sums, 1.0, atol=1e-8), "p_ij 行和不为 1"
    assert np.all(p_values >= 0.0), "p_ij 存在负值"


def build_pipeline_summary(
    output_path: Path,
    inputs: Dict,
    outputs: Dict,
    notes: List[str],
) -> None:
    from xml.etree.ElementTree import Element, SubElement, tostring

    root = Element("pipeline_run_summary")
    SubElement(root, "timestamp_utc").text = datetime.now(timezone.utc).isoformat(timespec="seconds")

    inputs_node = SubElement(root, "inputs")
    for k, v in inputs.items():
        item = SubElement(inputs_node, "item", key=str(k))
        item.text = json.dumps(v, ensure_ascii=False)

    outputs_node = SubElement(root, "outputs")
    for k, v in outputs.items():
        item = SubElement(outputs_node, "item", key=str(k))
        item.text = str(v)

    notes_node = SubElement(root, "notes")
    for note in notes:
        SubElement(notes_node, "note").text = note

    output_path.write_text(tostring(root, encoding="unicode"), encoding="utf-8")


def run_pipeline(
    task_dna_files: Dict[str, Path],
    anchors_path: Path,
    scenario_path: Path,
    output_dir: Path,
    figures_dir: Path,
    tables_dir: Path,
    eta_grid: List[float],
    eps_grid: List[float],
    top_k: int,
) -> None:
    anchors = load_adoption_anchors(anchors_path)
    cfg = load_scenario_config(scenario_path)
    t_grid = build_time_grid(cfg)
    scenarios = build_adoption_scenarios(t_grid, anchors, cfg)
    primary_family = cfg["A_family_primary"]
    a_scenarios = scenarios[primary_family]

    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    for soc, path in task_dna_files.items():
        df = load_task_dna(path)
        task_ids = df["task_id"].tolist()
        weights = df["w"].to_numpy()
        mu_task = df["mu_task"].to_numpy()

        summary = {}
        t_star_records = []
        for scenario_name, a_values in a_scenarios.items():
            for eta in eta_grid:
                p_values = compute_q_p(weights, mu_task, a_values, eta)
                ensure_probabilities(p_values)
                summary_key = f"{scenario_name}_eta{eta}"
                summary[summary_key] = compute_summary(t_grid, p_values, task_ids)
                share_records = [
                    {
                        "soc": soc,
                        "scenario": scenario_name,
                        "eta": eta,
                        "t": float(t),
                        "task_id": task_id,
                        "p_ij": float(p_values[ti, j]),
                    }
                    for ti, t in enumerate(t_grid)
                    for j, task_id in enumerate(task_ids)
                ]
                share_path = output_dir / f"p_share_{soc}_{scenario_name}_eta{eta}.csv"
                pd.DataFrame(share_records).to_csv(share_path, index=False)
                for eps in eps_grid:
                    t_star_vals = compute_t_star(t_grid, p_values, eps)
                    for task_id, t_star in zip(task_ids, t_star_vals):
                        t_star_records.append(
                            {
                                "soc": soc,
                                "scenario": scenario_name,
                                "eta": eta,
                                "eps": eps,
                                "task_id": task_id,
                                "t_star": t_star,
                            }
                        )

        summary_path = output_dir / f"task_shift_summary_{soc}.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        t_star_path = output_dir / f"t_star_table_{soc}.csv"
        pd.DataFrame(t_star_records).to_csv(t_star_path, index=False)

        appendix_path = tables_dir / f"appendix_taskdna_{soc}.tex"
        write_appendix_table(df, appendix_path)

        if soc == "17-2199.08":
            plot_adoption_scenarios(
                t_grid,
                a_scenarios,
                anchors,
                figures_dir / "fig_A_t_scenarios.pdf",
            )
            baseline_p = compute_q_p(weights, mu_task, a_scenarios["Baseline"], 1.0)
            plot_task_share_topk(
                t_grid,
                baseline_p,
                task_ids,
                top_k,
                figures_dir / "fig_STEM_task_share_topK.pdf",
            )
            plot_task_share_all(
                t_grid,
                baseline_p,
                figures_dir / "fig_STEM_task_share_all_tasks_appendix.pdf",
            )
            t_star_1 = compute_t_star(t_grid, baseline_p, 0.01)
            t_star_5 = compute_t_star(t_grid, baseline_p, 0.05)
            plot_tstar_distribution(
                t_star_1,
                t_star_5,
                figures_dir / "fig_STEM_tstar_bar.pdf",
            )
        elif soc == "49-1011.00":
            baseline_p = compute_q_p(weights, mu_task, a_scenarios["Baseline"], 1.0)
            plot_task_share_all(
                t_grid,
                baseline_p,
                figures_dir / "fig_task_share_all_49-1011.00.pdf",
            )
        elif soc == "27-3092.00":
            baseline_p = compute_q_p(weights, mu_task, a_scenarios["Baseline"], 1.0)
            plot_task_share_all(
                t_grid,
                baseline_p,
                figures_dir / "fig_task_share_all_27-3092.00.pdf",
            )

    build_pipeline_summary(
        output_dir / "pipeline_run_summary.xml",
        inputs={
            "task_dna_files": {k: str(v) for k, v in task_dna_files.items()},
            "anchors_path": str(anchors_path),
            "scenario_path": str(scenario_path),
            "eta_grid": eta_grid,
            "eps_grid": eps_grid,
        },
        outputs={
            "p_share": "data/processed/p_share_{soc}_{scenario}_eta{eta}.csv",
            "task_shift_summary": "data/processed/task_shift_summary_{soc}.json",
            "t_star_table": "data/processed/t_star_table_{soc}.csv",
        },
        notes=[
            "A_family_primary=piecewise_linear_saturation",
            "A_family_secondary=logistic",
            "source_url 需与 PDF 中 URL 完全一致",
        ],
    )


def demo_run() -> None:
    dummy = pd.DataFrame(
        {
            "task_id": ["T1", "T2", "T3", "T4", "T5"],
            "task_text": ["A", "B", "C", "D", "E"],
            "w": [0.2, 0.2, 0.2, 0.2, 0.2],
            "s": [0.3, 0.6, 0.4, 0.2, 0.5],
            "c": [0.5, 0.7, 0.6, 0.3, 0.7],
            "mu_task": [0.2, 0.1, 0.2, 0.1, 0.2],
            "dims": ["D1", "D2", "D3", "D4", "D5"],
            "evidence_note": ["demo"] * 5,
        }
    )
    anchors = [
        {"t_year": 2024, "A_value": 0.65},
        {"t_year": 2025, "A_value": 0.71},
        {"t_year": 2026, "A_value": 0.80},
    ]
    cfg = load_scenario_config(Path("data/processed/adoption_scenarios.json"))
    t_grid = build_time_grid(cfg)
    scenarios = build_adoption_scenarios(t_grid, anchors, cfg)["piecewise_linear_saturation"]
    baseline = scenarios["Baseline"]
    p_values = compute_q_p(dummy["w"].to_numpy(), dummy["mu_task"].to_numpy(), baseline, 1.0)
    ensure_probabilities(p_values)
    print(json.dumps({"demo_summary": compute_summary(t_grid, p_values, dummy["task_id"])}, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Adoption-anchored task share forecasting.")
    parser.add_argument("--demo", action="store_true", help="运行内置 Dummy Data 演示")
    parser.add_argument("--anchors", default="data/processed/adoption_anchors.json")
    parser.add_argument("--scenarios", default="data/processed/adoption_scenarios.json")
    parser.add_argument("--output_dir", default="data/processed")
    parser.add_argument("--figures_dir", default="figures")
    parser.add_argument("--tables_dir", default="tables")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.demo:
        demo_run()
        return

    task_dna_files = {
        "17-2199.08": Path("data/processed/task_dna_17-2199.08_authoritative_sc.csv"),
        "49-1011.00": Path("data/processed/task_dna_49-1011.00_authoritative_sc.csv"),
        "27-3092.00": Path("data/processed/task_dna_27-3092.00_authoritative_sc.csv"),
    }
    run_pipeline(
        task_dna_files=task_dna_files,
        anchors_path=Path(args.anchors),
        scenario_path=Path(args.scenarios),
        output_dir=Path(args.output_dir),
        figures_dir=Path(args.figures_dir),
        tables_dir=Path(args.tables_dir),
        eta_grid=[0.5, 1.0, 2.0],
        eps_grid=[0.01, 0.05],
        top_k=8,
    )


if __name__ == "__main__":
    main()
