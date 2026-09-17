#!/usr/bin/env python3
"""
Plot GenAI ability-to-task DNA mapping (D1-D9) for three occupations.
Outputs a single triptych PDF with three side-by-side panels.
"""
from __future__ import annotations

from argparse import ArgumentParser
import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"
FIG_DIR = ROOT / "figures"

OCCUPATIONS = [
    ("17-2199.08", "Robotics Engineers"),
    ("49-1011.00", "First-Line Supervisors (Mech/Install/Repair)"),
    ("27-3092.00", "Court Reporters and Captioners"),
]

DIMENSIONS = [f"D{i}" for i in range(1, 10)]
REQUIRED_COLUMNS = {"task_id", "w", "dims"}


def _ensure_schema(fieldnames: Iterable[str], path: Path) -> None:
    missing = REQUIRED_COLUMNS.difference(set(fieldnames))
    assert not missing, f"Missing columns in {path}: {sorted(missing)}"


def _split_dims(raw: str) -> List[str]:
    return [d.strip() for d in raw.split(",") if d.strip()]


def load_dim_weights(csv_path: Path) -> Dict[str, float]:
    weights = {d: 0.0 for d in DIMENSIONS}
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        _ensure_schema(reader.fieldnames or [], csv_path)
        for row in reader:
            w = float(row["w"])
            dims = _split_dims(row["dims"])
            if not dims:
                continue
            share = w / len(dims)
            for d in dims:
                if d in weights:
                    weights[d] += share
    return weights


def summarize_key_points(label: str, weights: Dict[str, float]) -> Dict[str, object]:
    max_dim = max(weights, key=weights.get)
    max_value = weights[max_dim]
    mean_value = float(np.mean(list(weights.values())))
    return {
        "occupation": label,
        "max_dim": max_dim,
        "max_value": round(max_value, 6),
        "mean_value": round(mean_value, 6),
    }


def plot_mapping_panel(ax: plt.Axes, title: str, weights: Dict[str, float]) -> None:
    dims = list(weights.keys())
    values = [weights[d] for d in dims]
    mean_value = float(np.mean(values))
    max_idx = int(np.argmax(values))

    bar_color = "#8FA3B8"
    line_color = "#B08A7A"
    edge_color = "#55606E"

    ax.bar(dims, values, color=bar_color, edgecolor=edge_color, linewidth=0.6, label="Weight share")
    ax.plot(dims, [mean_value] * len(dims), color=line_color, linewidth=1.2, label="Mean")

    ax.scatter(dims[max_idx], values[max_idx], color=edge_color, s=18, zorder=3)
    ax.annotate(
        f"{dims[max_idx]}={values[max_idx]:.2f}",
        xy=(dims[max_idx], values[max_idx]),
        xytext=(0, 8),
        textcoords="offset points",
        ha="center",
        fontsize=8,
        color=edge_color,
    )

    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Dimension (D1-D9)", fontsize=9)
    ax.set_ylabel("Weight share", fontsize=9)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_ylim(0, max(values) * 1.25 if values else 0.1)
    ax.tick_params(axis="x", labelsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.legend(loc="upper right", fontsize=7, frameon=False)


def build_demo_weights() -> Dict[str, float]:
    demo = {d: 0.02 for d in DIMENSIONS}
    demo["D1"] = 0.28
    demo["D3"] = 0.18
    demo["D8"] = 0.22
    demo["D9"] = 0.16
    return demo


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--output", default=str(FIG_DIR / "task_dna_genai_mapping_triptych.pdf"))
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    FIG_DIR.mkdir(parents=True, exist_ok=True)

    if args.demo:
        panel_data = [
            ("Demo A", build_demo_weights()),
            ("Demo B", build_demo_weights()),
            ("Demo C", build_demo_weights()),
        ]
    else:
        panel_data = []
        for soc_code, label in OCCUPATIONS:
            csv_path = DATA_DIR / f"task_dna_{soc_code}_authoritative_sc.csv"
            weights = load_dim_weights(csv_path)
            panel_data.append((f"{soc_code} {label}", weights))

    key_points = [summarize_key_points(title, weights) for title, weights in panel_data]
    print(json.dumps(key_points, indent=2))

    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.6), constrained_layout=True)
    for ax, (title, weights) in zip(axes, panel_data):
        plot_mapping_panel(ax, title, weights)

    fig.savefig(args.output, format="pdf")


if __name__ == "__main__":
    main()
