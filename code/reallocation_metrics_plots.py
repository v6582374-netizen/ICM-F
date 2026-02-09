#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reallocation evidence suite: metrics + visuals.
Only uses existing model outputs and task DNA; no model changes.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Dict, List, Tuple

import importlib.util
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
module_path = ROOT / "code" / "adoption_task_share_forecast.py"
spec = importlib.util.spec_from_file_location("adoption_task_share_forecast", module_path)
if spec is None or spec.loader is None:
    raise ImportError("无法加载 adoption_task_share_forecast.py")
module = importlib.util.module_from_spec(spec)
sys.modules["adoption_task_share_forecast"] = module
spec.loader.exec_module(module)

build_time_grid = module.build_time_grid
load_adoption_anchors = module.load_adoption_anchors
load_scenario_config = module.load_scenario_config


STOPWORDS = {
    "the",
    "and",
    "or",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "by",
    "a",
    "an",
    "be",
    "is",
    "are",
    "as",
    "at",
    "from",
    "that",
    "this",
    "these",
    "those",
    "use",
    "using",
    "provide",
    "perform",
    "monitor",
    "prepare",
    "record",
    "review",
    "inspect",
    "determine",
    "ensure",
    "maintain",
    "analyze",
    "analyzing",
    "support",
}


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


def muted_palette() -> List[str]:
    return [
        "#5f7fa1",
        "#7b9b8a",
        "#b09b73",
        "#8f9aa6",
        "#7f8c99",
        "#9d8f7a",
        "#6f8f95",
        "#9aa3ad",
        "#5f6b75",
    ]


def normalize_word(token: str) -> str:
    return re.sub(r"[^a-z0-9]", "", token.lower())


def short_label(task_text: str, dims: str) -> str:
    tokens = re.split(r"[\\s,;:()\\-]+", task_text.strip())
    keyword = ""
    for tok in tokens:
        clean = normalize_word(tok)
        if not clean or clean in STOPWORDS:
            continue
        keyword = clean
        break
    if not keyword:
        keyword = normalize_word(tokens[0]) if tokens else "task"
    return f"{dims}:{keyword[:12]}"


def load_task_dna(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["task_id"] = df["task_id"].astype(str)
    if "mu_task" not in df.columns or df["mu_task"].isna().any():
        df["mu_task"] = df["c"].astype(float) - df["s"].astype(float)
    df["w"] = df["w"].astype(float)
    df["mu_task"] = df["mu_task"].astype(float)
    return df


def load_p_share(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["t"] = df["t"].astype(float)
    df["p_ij"] = df["p_ij"].astype(float)
    df["task_id"] = df["task_id"].astype(str)
    return df


def build_adoption_series(
    t_grid: np.ndarray,
    anchors: List[Dict],
    cfg: Dict,
    scenario: str,
) -> np.ndarray:
    anchor_map = {a["t_year"]: a["A_value"] for a in anchors}
    a_2024 = float(anchor_map[2024])
    a_2025 = float(anchor_map[2025])
    a_2026 = float(anchor_map.get(2026, 0.80))

    if scenario in {"Slow", "Baseline"}:
        post = cfg["piecewise_linear_params"][scenario]["post_2025_slope"]
        sat = cfg["piecewise_linear_params"][scenario]["saturation"]
        slope_2024_2025 = (a_2025 - a_2024) / (2025.0 - 2024.0)
        values = []
        for t in t_grid:
            if t <= 2025.0:
                values.append(a_2024 + slope_2024_2025 * (t - 2024.0))
            else:
                values.append(a_2025 + post * (t - 2025.0))
        return np.clip(np.array(values), 0.0, sat)
    if scenario == "Fast":
        target_2026 = max(a_2026, cfg["piecewise_linear_params"]["Fast"]["post_2025_target_2026"])
        post_2026 = cfg["piecewise_linear_params"]["Fast"]["post_2026_slope"]
        sat = cfg["piecewise_linear_params"]["Fast"]["saturation"]
        slope_2024_2025 = (a_2025 - a_2024) / (2025.0 - 2024.0)
        slope_2025_2026 = (target_2026 - a_2025) / (2026.0 - 2025.0)
        values = []
        for t in t_grid:
            if t <= 2025.0:
                values.append(a_2024 + slope_2024_2025 * (t - 2024.0))
            elif t <= 2026.0:
                values.append(a_2025 + slope_2025_2026 * (t - 2025.0))
            else:
                values.append(target_2026 + post_2026 * (t - 2026.0))
        return np.clip(np.array(values), 0.0, sat)
    raise ValueError(f"未知情景: {scenario}")


def compute_p_share_from_taskdna(
    t_grid: np.ndarray,
    a_values: np.ndarray,
    task_dna: pd.DataFrame,
    eta: float,
) -> pd.DataFrame:
    w = task_dna["w"].to_numpy().reshape(1, -1)
    mu = task_dna["mu_task"].to_numpy().reshape(1, -1)
    a_col = a_values.reshape(-1, 1)
    q = w * ((1.0 - a_col) + a_col * np.exp(eta * mu))
    p = q / q.sum(axis=1, keepdims=True)
    records = []
    task_ids = task_dna["task_id"].tolist()
    for ti, t in enumerate(t_grid):
        for j, tid in enumerate(task_ids):
            records.append({"t": float(t), "task_id": tid, "p_ij": float(p[ti, j])})
    return pd.DataFrame(records)


def ensure_p_share_files(
    processed: Path,
    soc: str,
    scenario: str,
    eta: float,
    t_grid: np.ndarray,
    a_values: np.ndarray,
    task_dna: pd.DataFrame,
) -> Path:
    path = processed / f"p_share_{soc}_{scenario}_eta{eta}.csv"
    if path.exists():
        return path
    df = compute_p_share_from_taskdna(t_grid, a_values, task_dna, eta)
    df.insert(0, "eta", eta)
    df.insert(0, "scenario", scenario)
    df.insert(0, "soc", soc)
    df.to_csv(path, index=False)
    return path


def compute_reallocation_metrics(
    p_share: pd.DataFrame,
    task_dna: pd.DataFrame,
    m_list: List[int],
) -> pd.DataFrame:
    w = task_dna.set_index("task_id")["w"]
    w_top = {}
    for m in m_list:
        w_top[m] = set(w.sort_values(ascending=False).head(m).index.astype(str))

    out = []
    for t, sub in p_share.groupby("t"):
        p = sub.set_index("task_id")["p_ij"]
        aligned = p.reindex(w.index).fillna(0.0)
        r = 0.5 * (aligned - w).abs()
        R = float(r.sum())
        row = {"t": float(t), "R": R}
        for m in m_list:
            p_top = set(aligned.sort_values(ascending=False).head(m).index.astype(str))
            overlap = len(p_top.intersection(w_top[m]))
            row[f"J_{m}"] = 1.0 - overlap / m
        out.append(row)
    return pd.DataFrame(out).sort_values("t")


def compute_top_contributors(
    p_share: pd.DataFrame,
    task_dna: pd.DataFrame,
    top_n: int,
) -> pd.DataFrame:
    t_start = p_share["t"].min()
    t_end = p_share["t"].max()
    start = p_share[p_share["t"] == t_start].set_index("task_id")["p_ij"]
    end = p_share[p_share["t"] == t_end].set_index("task_id")["p_ij"]
    w = task_dna.set_index("task_id")["w"]
    dims = task_dna.set_index("task_id")["dims"]
    delta = (end - start).fillna(0.0)
    r = 0.5 * (end.reindex(w.index).fillna(0.0) - w).abs()
    top_ids = r.sort_values(ascending=False).head(top_n).index.astype(str)
    rows = []
    for rank, tid in enumerate(top_ids, start=1):
        rows.append(
            {
                "rank": rank,
                "task_id": tid,
                "dims": dims.get(tid, ""),
                "w": float(w.get(tid, 0.0)),
                "p_start": float(start.get(tid, 0.0)),
                "p_end": float(end.get(tid, 0.0)),
                "Delta_p": float(delta.get(tid, 0.0)),
                "r": float(r.get(tid, 0.0)),
            }
        )
    return pd.DataFrame(rows)


def compute_top_rank_reversals(
    p_share: pd.DataFrame,
    task_dna: pd.DataFrame,
    top_n: int,
) -> pd.DataFrame:
    t_start = p_share["t"].min()
    t_end = p_share["t"].max()
    start = p_share[p_share["t"] == t_start].set_index("task_id")["p_ij"]
    end = p_share[p_share["t"] == t_end].set_index("task_id")["p_ij"]
    w = task_dna.set_index("task_id")["w"]
    dims = task_dna.set_index("task_id")["dims"]
    delta = (end - start).fillna(0.0)
    r = 0.5 * (end.reindex(w.index).fillna(0.0) - w).abs()

    w_rank = w.rank(ascending=False, method="min")
    p_rank = end.reindex(w.index).fillna(0.0).rank(ascending=False, method="min")
    rank_flip = (p_rank - w_rank).abs()

    top_ids = rank_flip.sort_values(ascending=False).head(top_n).index.astype(str)
    rows = []
    for rank, tid in enumerate(top_ids, start=1):
        rows.append(
            {
                "rank": rank,
                "task_id": tid,
                "dims": dims.get(tid, ""),
                "w": float(w.get(tid, 0.0)),
                "p_start": float(start.get(tid, 0.0)),
                "p_end": float(end.get(tid, 0.0)),
                "Delta_p": float(delta.get(tid, 0.0)),
                "r": float(r.get(tid, 0.0)),
                "rank_w": float(w_rank.get(tid, 0.0)),
                "rank_p_end": float(p_rank.get(tid, 0.0)),
                "rank_flip": float(rank_flip.get(tid, 0.0)),
            }
        )
    return pd.DataFrame(rows)


def plot_reallocation_mass(
    metrics: Dict[str, pd.DataFrame],
    t_grid: np.ndarray,
    a_values: Dict[str, np.ndarray],
    output_path: Path,
) -> None:
    apply_plot_style()
    fig, axes = plt.subplots(3, 1, figsize=(7.2, 7.6), dpi=300, sharex=True)
    colors = {"Slow": "#7f8c99", "Baseline": "#5f7fa1", "Fast": "#7b9b8a"}
    t_map = {t: i for i, t in enumerate(t_grid)}
    for ax, (soc, df) in zip(axes, metrics.items()):
        for scenario in ["Slow", "Baseline", "Fast"]:
            sub = df[df["scenario"] == scenario].sort_values("t")
            if sub.empty:
                continue
            a_map = {t: a_values[scenario][t_map[t]] for t in sub["t"].values}
            x = sub["t"].map(a_map).values
            ax.plot(
                x,
                sub["R"].values,
                color=colors[scenario],
                linewidth=2.0 if scenario == "Baseline" else 1.4,
                linestyle="-" if scenario == "Baseline" else "--",
                label=scenario,
            )
        ax.set_ylabel(f"{soc}\\nR(t)")
        ax.grid(True, alpha=0.3)
    axes[-1].set_xlabel("Adoption rate A(t)")
    axes[0].legend(frameon=False, fontsize=7, ncol=3)
    plt.tight_layout()
    plt.savefig(output_path, format="pdf")
    plt.close()


def plot_dumbbell_delta_p(
    p_share: pd.DataFrame,
    task_dna: pd.DataFrame,
    labels: Dict[str, str],
    output_path: Path,
    top_n: int = 10,
) -> None:
    apply_plot_style()
    t_start = p_share["t"].min()
    t_end = p_share["t"].max()
    start = p_share[p_share["t"] == t_start].set_index("task_id")["p_ij"]
    end = p_share[p_share["t"] == t_end].set_index("task_id")["p_ij"]
    delta = (end - start).abs().sort_values(ascending=False).head(top_n)
    rows = []
    for tid in delta.index.astype(str):
        rows.append(
            {
                "task_id": tid,
                "start": float(start.get(tid, 0.0)),
                "end": float(end.get(tid, 0.0)),
                "delta": float(end.get(tid, 0.0) - start.get(tid, 0.0)),
            }
        )
    df = pd.DataFrame(rows).sort_values("delta", ascending=True)
    y = np.arange(len(df))
    plt.figure(figsize=(7.2, 4.2), dpi=300)
    for i, row in df.iterrows():
        color = "#7b9b8a" if row["delta"] >= 0 else "#9d8f7a"
        plt.plot([row["start"], row["end"]], [y[df.index.get_loc(i)]] * 2, color=color, linewidth=1.6)
        plt.scatter([row["start"], row["end"]], [y[df.index.get_loc(i)]] * 2, color=color, s=28)
    plt.yticks(y, [labels[tid] for tid in df["task_id"]])
    plt.xlabel("Task share p_ij(t)")
    plt.title("STEM: start vs end shares (Top 10 by |Delta_p|)")
    plt.grid(True, axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, format="pdf")
    plt.close()


def plot_rankflip_and_contribution(
    rankflip: pd.DataFrame,
    contributors: pd.DataFrame,
    labels: Dict[str, str],
    output_path: Path,
) -> None:
    apply_plot_style()
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.6), dpi=300, gridspec_kw={"width_ratios": [1.05, 1.1]})

    left = rankflip.sort_values("rank_flip", ascending=False).reset_index(drop=True)
    y = np.arange(len(left))
    ax = axes[0]
    rank_min = float(left["rank_flip"].min()) if not left.empty else 0.0
    rank_max = float(left["rank_flip"].max()) if not left.empty else 1.0
    band_edges = np.linspace(rank_min, rank_max + 1e-9, 4)
    band_colors = ["#f4f6f8", "#eef2f5", "#e9eef2"]
    for i, row in left.iterrows():
        band_idx = int(np.digitize(row["rank_flip"], band_edges) - 1)
        band_idx = max(0, min(band_idx, len(band_colors) - 1))
        ax.axhspan(y[i] - 0.45, y[i] + 0.45, color=band_colors[band_idx], zorder=0)
        color = "#7b9b8a" if row["Delta_p"] >= 0 else "#9d8f7a"
        ax.plot([row["rank_w"], row["rank_p_end"]], [y[i], y[i]], color=color, linewidth=1.6)
        ax.scatter(row["rank_w"], y[i], color="#4f555c", s=24, zorder=3)
        ax.scatter(row["rank_p_end"], y[i], color=color, s=28, zorder=3)
        ax.annotate(
            f"{row['Delta_p']:+.3f}",
            (max(row["rank_w"], row["rank_p_end"]), y[i]),
            textcoords="offset points",
            xytext=(8, 0),
            va="center",
            fontsize=8,
            color="#6f7a86",
        )
        ax.annotate(
            f"{int(row['rank_w'])}",
            (row["rank_w"], y[i]),
            textcoords="offset points",
            xytext=(4, 6),
            fontsize=9,
            color="#2b2f33",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#b0b8c2", linewidth=0.5),
        )
        ax.annotate(
            f"{int(row['rank_p_end'])}",
            (row["rank_p_end"], y[i]),
            textcoords="offset points",
            xytext=(4, -12),
            fontsize=9,
            color="#2b2f33",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#b0b8c2", linewidth=0.5),
        )
    ax.set_yticks(y)
    ax.set_yticklabels([labels[tid] for tid in left["task_id"]])
    ax.set_xlabel("Rank (1 = highest share)")
    ax.set_title("Rank reversals from w to p(t_end)")
    ax.grid(True, axis="x", alpha=0.3)
    ax.invert_xaxis()
    ax.axvline(np.median(left["rank_w"]), color="#9aa3ad", linewidth=0.8, linestyle="--", zorder=0)

    right = contributors.sort_values("r", ascending=False).reset_index(drop=True)
    x = np.arange(len(right))
    r_vals = right["r"].values
    total_r = float(r_vals.sum())
    cumulative = np.cumsum(r_vals) / total_r if total_r > 0 else np.zeros_like(r_vals)
    ax2 = axes[1]
    bar_color = "#7b9b8a"
    ax2.bar(x, r_vals, color=bar_color, alpha=0.75, edgecolor="#6f7a86", linewidth=0.6, zorder=2)
    for xi, rv in zip(x, r_vals):
        ax2.annotate(
            f"{rv:.3f}",
            (xi, rv),
            textcoords="offset points",
            xytext=(0, 4),
            ha="center",
            fontsize=7,
            color="#5f6b75",
        )
    ax2.set_xticks(x)
    xlabels = [labels[tid] for tid in right["task_id"]]
    ax2.set_xticklabels(xlabels, rotation=30, ha="right")
    for idx, tick in enumerate(ax2.get_xticklabels()):
        if idx < 3:
            tick.set_fontweight("bold")
    ax2.set_ylabel("Contribution r_ij")
    ax2.set_xlabel("Top contributors (sorted by r_ij)")
    ax2.set_title("Cumulative contribution to total change")
    ax2.grid(True, axis="y", alpha=0.3, zorder=1)

    ax2b = ax2.twinx()
    ax2b.plot(x, cumulative, color="#5f7fa1", linewidth=1.8, marker="o", markersize=4, zorder=3)
    for xi, cv in zip(x, cumulative):
        ax2b.annotate(
            f"{cv*100:.1f}%",
            (xi, cv),
            textcoords="offset points",
            xytext=(3, -10),
            fontsize=7,
            color="#5f7fa1",
        )
    ax2b.fill_between(x, 0, cumulative, color="#5f7fa1", alpha=0.10, zorder=0)
    ax2b.set_ylabel("Cumulative share of total change")
    ax2b.set_ylim(0.0, 1.05)
    ax2b.grid(False)

    thresholds = [0.5, 0.8]
    threshold_indices = {}
    for th in thresholds:
        if len(cumulative) == 0:
            threshold_indices[th] = None
            continue
        idx = int(np.argmax(cumulative >= th))
        if cumulative[idx] >= th:
            threshold_indices[th] = idx
            ax2b.axhline(th, color="#9aa3ad", linewidth=0.8, linestyle="--")
            ax2b.annotate(
                f"{int(th*100)}%",
                (x[idx], th),
                textcoords="offset points",
                xytext=(6, 3),
                fontsize=8,
                color="#6f7a86",
            )
        else:
            threshold_indices[th] = None

    if len(r_vals) > 0:
        max_idx = int(np.argmax(r_vals))
        ax2.annotate(
            f"{r_vals[max_idx]:.3f}",
            (x[max_idx], r_vals[max_idx]),
            textcoords="offset points",
            xytext=(0, 6),
            ha="center",
            fontsize=8,
            color="#2b2f33",
        )
        elbow_idx = int(np.argmax(np.diff(cumulative, prepend=0.0)))
        ax2b.annotate(
            f"{cumulative[elbow_idx]*100:.1f}%",
            (x[elbow_idx], cumulative[elbow_idx]),
            textcoords="offset points",
            xytext=(6, -10),
            fontsize=8,
            color="#2b2f33",
        )
        ax2b.annotate(
            f"{cumulative[-1] * 100:.1f}%",
            (x[-1], cumulative[-1]),
            textcoords="offset points",
            xytext=(6, -2),
            fontsize=8,
            color="#2b2f33",
        )
        for idx in range(min(3, len(x))):
            ax2.patches[idx].set_linewidth(1.2)
            ax2.patches[idx].set_edgecolor("#2b2f33")

    keypoints = {
        "total_r": total_r,
        "top_r": float(r_vals[0]) if len(r_vals) > 0 else 0.0,
        "cumulative_share": [float(v) for v in cumulative.tolist()],
        "threshold_indices": {str(k): v for k, v in threshold_indices.items()},
        "task_order": [str(tid) for tid in right["task_id"]],
    }
    print(json.dumps(keypoints, ensure_ascii=False))

    plt.tight_layout()
    plt.savefig(output_path, format="pdf")
    plt.close()




def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reallocation metrics and plots.")
    parser.add_argument("--output_dir", default="figures")
    parser.add_argument("--processed_dir", default="data/processed")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(".")
    processed = root / args.processed_dir
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    soc_list = ["17-2199.08", "49-1011.00", "27-3092.00"]
    scenario_list = ["Slow", "Baseline", "Fast"]
    eta_grid = [0.5, 1.0, 2.0, 4.0, 8.0]
    m_list = [5, 8, 10]
    top_k = 10

    anchors = load_adoption_anchors(processed / "adoption_anchors.json")
    cfg = load_scenario_config(processed / "adoption_scenarios.json")
    t_grid = build_time_grid(cfg)
    a_by_scenario = {s: build_adoption_series(t_grid, anchors, cfg, s) for s in scenario_list}

    plot_config = {
        "t_start": float(t_grid.min()),
        "t_end": float(t_grid.max()),
        "m_list": m_list,
        "eta_grid": eta_grid,
        "scenario_list": scenario_list,
        "label_rule": "dims + keyword from task_text; task_id only in appendix table",
        "topK_rule": "TopK by |Delta_p| between t_start and t_end with top-2 by w guardrail",
        "monotone_check_R_vs_A": {},
    }

    metrics_by_soc = {}

    for soc in soc_list:
        task_dna_path = processed / f"task_dna_{soc}_authoritative_sc.csv"
        task_dna = load_task_dna(task_dna_path)
        labels = {tid: short_label(txt, dims) for tid, txt, dims in zip(task_dna["task_id"], task_dna["task_text"], task_dna["dims"])}

        metrics_rows = []
        top_contrib_rows = []
        monotone_report = {}

        for scenario in scenario_list:
            a_values = a_by_scenario[scenario]
            for eta in eta_grid:
                p_share_path = ensure_p_share_files(processed, soc, scenario, eta, t_grid, a_values, task_dna)
                p_share = load_p_share(p_share_path)
                re_metrics = compute_reallocation_metrics(p_share, task_dna, m_list)
                re_metrics.insert(0, "eta", eta)
                re_metrics.insert(0, "scenario", scenario)
                re_metrics.insert(0, "soc", soc)
                re_metrics["A"] = a_values
                metrics_rows.append(re_metrics)

                contributors = compute_top_contributors(p_share, task_dna, top_n=top_k)
                contributors.insert(0, "eta", eta)
                contributors.insert(0, "scenario", scenario)
                contributors.insert(0, "t_end", float(p_share["t"].max()))
                contributors.insert(0, "t_start", float(p_share["t"].min()))
                contributors.insert(0, "soc", soc)
                top_contrib_rows.append(contributors)

                r_vals = re_metrics["R"].values
                monotone = bool(np.all(np.diff(r_vals) >= -1e-8))
                monotone_report[f"{scenario}_eta{eta}"] = monotone


        metrics_df = pd.concat(metrics_rows, ignore_index=True)
        metrics_df.to_csv(processed / f"reallocation_metrics_{soc}.csv", index=False)
        top_contrib_df = pd.concat(top_contrib_rows, ignore_index=True)
        top_contrib_df.to_csv(processed / f"top_contributors_{soc}.csv", index=False)
        plot_config["monotone_check_R_vs_A"][soc] = monotone_report

        metrics_by_soc[soc] = metrics_df[metrics_df["eta"] == 1.0].copy()

        p_share_base = load_p_share(processed / f"p_share_{soc}_Baseline_eta1.0.csv")
        if soc == "17-2199.08":
            plot_dumbbell_delta_p(
                p_share_base,
                task_dna,
                labels,
                output_dir / "fig_STEM_dumbbell_delta_p.pdf",
                top_n=10,
            )
            rankflip = compute_top_rank_reversals(p_share_base, task_dna, top_n=10)
            contrib = compute_top_contributors(p_share_base, task_dna, top_n=10)
            plot_rankflip_and_contribution(
                rankflip,
                contrib,
                labels,
                output_dir / "fig_STEM_rankflip_contribution_v2.pdf",
            )

    plot_reallocation_mass(
        metrics_by_soc,
        t_grid,
        a_by_scenario,
        output_dir / "fig_reallocation_mass_vs_A_or_t.pdf",
    )

    (processed / "reallocation_plot_config.json").write_text(
        json.dumps(plot_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
