#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Revise visualization suite for task-share forecasting (readability-first).
Only plotting and TopK selection rules are modified.
"""

from __future__ import annotations

import argparse
import json
import re
import importlib.util
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

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

build_adoption_scenarios = module.build_adoption_scenarios
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


def select_topk_tasks(
    p_share: pd.DataFrame,
    task_dna: pd.DataFrame,
    top_k: int,
) -> Tuple[List[str], Dict[str, str]]:
    t_start = p_share["t"].min()
    t_end = p_share["t"].max()
    start = p_share[p_share["t"] == t_start].set_index("task_id")["p_ij"]
    end = p_share[p_share["t"] == t_end].set_index("task_id")["p_ij"]
    delta = (end - start).fillna(0.0)
    delta_abs = delta.abs().sort_values(ascending=False)

    top_by_delta = list(delta_abs.index[:top_k])
    top_by_w = task_dna.set_index("task_id")["w"].sort_values(ascending=False).head(2).index.tolist()
    selected = []
    for tid in top_by_w + top_by_delta:
        if tid not in selected:
            selected.append(tid)
    selected = selected[:top_k]

    rule_meta = {
        "rule": "TopK by |delta_p| between t_start and t_end (Baseline, eta=1)",
        "guardrail": "force-include top-2 by w",
    }
    return selected, rule_meta


def build_shortlabels(task_dna: pd.DataFrame) -> Dict[str, str]:
    labels = {}
    for _, row in task_dna.iterrows():
        labels[str(row["task_id"])] = short_label(str(row["task_text"]), str(row["dims"]))
    return labels


def latex_escape(text: str) -> str:
    mapping = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
    }
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text


def plot_adoption_scenarios_v2(
    t_grid: np.ndarray,
    scenarios: Dict[str, np.ndarray],
    anchors: List[Dict],
    output_path: Path,
) -> None:
    apply_plot_style()
    colors = {"Slow": "#7f8c99", "Baseline": "#5f7fa1", "Fast": "#7b9b8a"}
    linestyles = {"Slow": "--", "Baseline": "-", "Fast": "-."}
    plt.figure(figsize=(7.2, 4.2), dpi=300)
    plt.fill_between(
        t_grid,
        scenarios["Slow"],
        scenarios["Fast"],
        color="#d5dbe0",
        alpha=0.35,
        label="Slow–Fast band",
    )
    for name, values in scenarios.items():
        plt.plot(
            t_grid,
            values,
            label=name,
            color=colors.get(name, "#888888"),
            linewidth=2.0,
            linestyle=linestyles.get(name, "-"),
        )
    for a in anchors:
        plt.scatter(a["t_year"], a["A_value"], color="#3f4a55", s=52, zorder=3)
        plt.annotate(
            f"{a['t_year']}: {a['A_value']:.2f}",
            (a["t_year"], a["A_value"]),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=8,
            color="#2b2f33",
        )
    plt.xlabel("Year")
    plt.ylabel("Adoption rate A(t)")
    plt.title("Adoption scenarios A(t)")
    plt.text(
        0.5,
        1.02,
        "A(t): organizations regularly using GenAI; sources McKinsey 2024/2025, Gartner 2023",
        ha="center",
        transform=plt.gca().transAxes,
        fontsize=8,
        color="#4f555c",
    )
    plt.grid(True, alpha=0.3)
    plt.legend(frameon=False, fontsize=7, ncol=2)
    plt.tight_layout()
    plt.savefig(output_path, format="pdf")
    plt.close()


def plot_stacked_area_topk(
    t_grid: np.ndarray,
    p_share: pd.DataFrame,
    topk: List[str],
    labels: Dict[str, str],
    output_path: Path,
) -> None:
    apply_plot_style()
    palette = muted_palette()
    topk = [tid for tid in topk if tid in set(p_share["task_id"])]
    pivot = p_share.pivot(index="t", columns="task_id", values="p_ij").reindex(columns=topk)
    other = 1.0 - pivot.sum(axis=1)
    data = [pivot[tid].values for tid in topk] + [other.values]
    lab = [labels[tid] for tid in topk] + ["Other"]
    colors = palette[: len(topk)] + ["#4f555c"]
    plt.figure(figsize=(7.2, 4.2), dpi=300)
    plt.stackplot(t_grid, data, labels=lab, colors=colors, alpha=0.85)
    plt.xlabel("Year")
    plt.ylabel("Task share p_ij(t)")
    plt.title("TopK task shares (stacked area, baseline, eta=1)")
    plt.grid(True, alpha=0.25)
    plt.legend(frameon=False, fontsize=7, ncol=2)
    plt.tight_layout()
    plt.savefig(output_path, format="pdf")
    plt.close()


def plot_dumbbell_topk(
    t_grid: np.ndarray,
    p_share: pd.DataFrame,
    topk: List[str],
    labels: Dict[str, str],
    output_path: Path,
) -> None:
    apply_plot_style()
    t_start = t_grid.min()
    t_end = t_grid.max()
    start = p_share[p_share["t"] == t_start].set_index("task_id")["p_ij"]
    end = p_share[p_share["t"] == t_end].set_index("task_id")["p_ij"]
    rows = []
    for tid in topk:
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
    plt.title("Start vs end shares (TopK, baseline, eta=1)")
    plt.grid(True, axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, format="pdf")
    plt.close()


def plot_heatmap_tasks(
    t_grid: np.ndarray,
    p_share: pd.DataFrame,
    task_dna: pd.DataFrame,
    output_path: Path,
    sort_by: str = "delta",
) -> None:
    apply_plot_style()
    pivot = p_share.pivot(index="task_id", columns="t", values="p_ij").fillna(0.0)
    t_start = t_grid.min()
    t_end = t_grid.max()
    start = pivot[t_start]
    end = pivot[t_end]
    delta = (end - start).fillna(0.0)
    info = task_dna.set_index("task_id")[["dims", "mu_task"]]
    info["delta"] = delta

    def sort_key(row):
        if sort_by == "mu":
            return row["mu_task"]
        return row["delta"]

    grouped = defaultdict(list)
    for tid, row in info.iterrows():
        grouped[str(row["dims"])].append((str(tid), sort_key(row)))

    order = []
    for dims in sorted(grouped.keys()):
        items = sorted(grouped[dims], key=lambda x: x[1], reverse=True)
        order.extend([tid for tid, _ in items])

    order = [str(tid) for tid in order]
    matrix = pivot.loc[order].values
    plt.figure(figsize=(7.2, 5.2), dpi=300)
    im = plt.imshow(matrix, aspect="auto", cmap="cividis")
    plt.colorbar(im, fraction=0.03, pad=0.02, label="p_ij(t)")
    plt.yticks(range(len(order)), order, fontsize=6)
    plt.xticks(
        np.linspace(0, len(t_grid) - 1, 6),
        [f"{t_grid[int(i)]:.0f}" for i in np.linspace(0, len(t_grid) - 1, 6)],
    )
    plt.xlabel("Year")
    plt.ylabel("Task ID")
    plt.title("Task share heatmap (sorted by dims, within-dims by delta_p)")

    # dims block separators
    idx = 0
    for dims in sorted(grouped.keys()):
        idx += len(grouped[dims])
        plt.axhline(idx - 0.5, color="white", linewidth=0.6, alpha=0.6)
    plt.tight_layout()
    plt.savefig(output_path, format="pdf")
    plt.close()


def plot_tstar_facet(
    t_star: pd.DataFrame,
    output_path: Path,
) -> None:
    apply_plot_style()
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.6), dpi=300, sharey=True)
    eps_list = [0.05, 0.01]
    bins = np.arange(2024, 2036, 1)
    for ax, eps in zip(axes, eps_list):
        vals = t_star[(t_star["eps"] == eps) & (~t_star["t_star"].isna())]["t_star"].values
        if len(vals) == 0:
            ax.text(0.5, 0.5, "No crossings", ha="center", va="center", color="#4f555c")
        else:
            ax.hist(vals, bins=bins, color="#5f7fa1" if eps == 0.05 else "#7b9b8a", alpha=0.65)
        ax.set_title(f"eps={eps:.0%}")
        ax.set_xlabel("t* year")
        ax.grid(True, axis="y", alpha=0.25)
    axes[0].set_ylabel("Count of tasks")
    plt.tight_layout()
    plt.savefig(output_path, format="pdf")
    plt.close()


def write_shortlabel_table(task_dna: pd.DataFrame, output_path: Path) -> None:
    labels = build_shortlabels(task_dna)
    header = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Task DNA summary with short labels for plots.}",
        r"\label{tab:appendix_taskdna_shortlabel}",
        r"\begin{tabular}{@{}lllllllc@{}}",
        r"\toprule",
        r"Task ID & Dims & Shortlabel & $w$ & $s$ & $c$ & $\mu_{task}$ & Evidence (short) \\",
        r"\midrule",
    ]
    rows = []
    for _, row in task_dna.iterrows():
        evidence = latex_escape(str(row.get("evidence_note", ""))[:60])
        rows.append(
            " & ".join(
                [
                    latex_escape(str(row["task_id"])),
                    latex_escape(str(row["dims"])),
                    latex_escape(labels[str(row["task_id"])]),
                    f"{float(row['w']):.4f}",
                    f"{float(row['s']):.2f}",
                    f"{float(row['c']):.2f}",
                    f"{float(row['mu_task']):.2f}",
                    evidence,
                ]
            )
            + r" \\"
        )
    footer = [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    output_path.write_text("\n".join(header + rows + footer), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot task share v2.")
    parser.add_argument("--output_dir", default="figures")
    parser.add_argument("--tables_dir", default="tables")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(".")
    processed = root / "data" / "processed"

    soc_list = ["17-2199.08", "49-1011.00", "27-3092.00"]
    scenario_main = "Baseline"
    eta_main = 1.0
    top_k = 8

    anchors = load_adoption_anchors(processed / "adoption_anchors.json")
    cfg = load_scenario_config(processed / "adoption_scenarios.json")
    t_grid = build_time_grid(cfg)
    scenarios = build_adoption_scenarios(t_grid, anchors, cfg)["piecewise_linear_saturation"]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = Path(args.tables_dir)
    tables_dir.mkdir(parents=True, exist_ok=True)

    plot_adoption_scenarios_v2(
        t_grid,
        scenarios,
        anchors,
        output_dir / "fig_A_t_scenarios_v2.pdf",
    )

    plot_config = {
        "soc_list": soc_list,
        "scenario_main": scenario_main,
        "eta_main": eta_main,
        "time_grid": {"t_start": float(t_grid.min()), "t_end": float(t_grid.max()), "step": float(t_grid[1] - t_grid[0])},
        "topK": top_k,
        "topK_rule": "TopK by |delta_p| between t_start and t_end under (Baseline, eta=1) with top-2 by w guardrail",
        "other_bucket": True,
        "scenario_plot_mode": "overlay",
        "topK_by_soc": {},
    }

    for soc in soc_list:
        task_dna_path = processed / f"task_dna_{soc}_authoritative_sc.csv"
        task_dna = load_task_dna(task_dna_path)
        labels = build_shortlabels(task_dna)

        p_share_path = processed / f"p_share_{soc}_{scenario_main}_eta{eta_main}.csv"
        p_share = load_p_share(p_share_path)

        topk, rule_meta = select_topk_tasks(p_share, task_dna, top_k)
        plot_config["topK_by_soc"][soc] = {
            "task_id": topk,
            "rule": rule_meta["rule"],
            "guardrail": rule_meta["guardrail"],
        }

        write_shortlabel_table(task_dna, tables_dir / f"appendix_taskdna_{soc}_shortlabels.tex")

        if soc == "17-2199.08":
            plot_stacked_area_topk(
                t_grid,
                p_share,
                topk,
                labels,
                output_dir / "fig_STEM_task_share_area_topK_v2.pdf",
            )
            plot_dumbbell_topk(
                t_grid,
                p_share,
                topk,
                labels,
                output_dir / "fig_STEM_task_share_dumbbell_v2.pdf",
            )

        plot_heatmap_tasks(
            t_grid,
            p_share,
            task_dna,
            output_dir / f"fig_task_share_heatmap_{soc}_v2.pdf",
            sort_by="delta",
        )

    t_star = pd.read_csv(processed / "t_star_table_17-2199.08.csv")
    t_star = t_star[(t_star["scenario"] == scenario_main) & (t_star["eta"] == eta_main)].copy()
    plot_tstar_facet(
        t_star,
        output_dir / "fig_STEM_tstar_facet_or_ecdf_v2.pdf",
    )

    (processed / "plot_config_v2.json").write_text(
        json.dumps(plot_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
