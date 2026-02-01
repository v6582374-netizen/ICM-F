#!/usr/bin/env python3
"""
Generate a maximalist circular heatmap ("task DNA") for Robotics Engineers.
Outputs a single PDF under figures/.
"""
from __future__ import annotations

from argparse import ArgumentParser
import json
from math import pi
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "figures"


def _soft_clip(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    return np.clip(values, 0.0, 1.0)


def build_dummy_tasks() -> List[str]:
    return [
        "Perception Fusion",
        "Sensor Calibration",
        "SLAM Mapping",
        "Path Planning",
        "Motion Control",
        "Trajectory Optimization",
        "System Integration",
        "ROS Middleware",
        "Safety Validation",
        "Simulation Design",
        "Testing Automation",
        "Fault Diagnosis",
        "Edge Deployment",
        "Embedded Firmware",
        "Hardware Bring-up",
        "Actuator Tuning",
        "Vision Pipeline",
        "Localization",
        "Behavior Design",
        "Human-Robot Interaction",
        "Data Logging",
        "Performance Profiling",
        "Reliability Engineering",
        "Field Support",
    ]


def synthesize_ring_data(n_tasks: int, seed: int = 42) -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 2 * np.pi, n_tasks, endpoint=False)
    importance = 0.55 + 0.25 * np.sin(x * 1.3 + 0.4) + 0.1 * rng.normal(size=n_tasks)
    frequency = 0.45 + 0.28 * np.cos(x * 1.1 - 0.3) + 0.12 * rng.normal(size=n_tasks)
    complexity = 0.5 + 0.3 * np.sin(x * 1.7 + 1.1) + 0.08 * rng.normal(size=n_tasks)
    impact = 0.5 + 0.22 * np.cos(x * 1.9 + 0.8) + 0.1 * rng.normal(size=n_tasks)

    return {
        "Importance": _soft_clip(importance),
        "Frequency": _soft_clip(frequency),
        "Complexity": _soft_clip(complexity),
        "Impact": _soft_clip(impact),
    }


def compute_key_points(tasks: List[str], values: np.ndarray) -> Dict[str, object]:
    assert len(tasks) == len(values), "Task list length mismatch."
    max_idx = int(np.argmax(values))
    min_idx = int(np.argmin(values))
    return {
        "max": {
            "task": tasks[max_idx],
            "value": round(float(values[max_idx]), 4),
            "index": max_idx,
        },
        "min": {
            "task": tasks[min_idx],
            "value": round(float(values[min_idx]), 4),
            "index": min_idx,
        },
        "mean": round(float(np.mean(values)), 4),
    }


def moving_average(values: np.ndarray, window: int = 5) -> np.ndarray:
    assert window >= 3, "Window must be >= 3."
    pad = window // 2
    padded = np.r_[values[-pad:], values, values[:pad]]
    kernel = np.ones(window) / window
    smoothed = np.convolve(padded, kernel, mode="valid")
    return smoothed[: len(values)]


def plot_circular_heatmap(
    tasks: List[str],
    rings: Dict[str, np.ndarray],
    output_path: Path,
) -> Dict[str, object]:
    assert len(tasks) > 0, "Empty task list."
    n_tasks = len(tasks)
    for name, values in rings.items():
        assert len(values) == n_tasks, f"Ring {name} length mismatch."

    mpl.rcParams.update(
        {
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
        }
    )

    angles = np.linspace(0, 2 * np.pi, n_tasks + 1)
    ring_names = list(rings.keys())
    ring_values = np.vstack([rings[name] for name in ring_names])

    r_start = 0.75
    r_gap = 0.08
    r_width = 0.12
    ring_bounds = []
    r = r_start
    for _ in ring_names:
        ring_bounds.append((r, r + r_width))
        r += r_width + r_gap

    fig = plt.figure(figsize=(7.4, 7.4), dpi=300)
    ax = fig.add_subplot(111, projection="polar")
    ax.set_theta_direction(-1)
    ax.set_theta_offset(pi / 2.0)
    ax.set_facecolor("white")

    cmap = mpl.colormaps.get_cmap("BuPu")
    norm = mpl.colors.Normalize(vmin=0.0, vmax=1.0)

    for idx, (name, (r_inner, r_outer)) in enumerate(zip(ring_names, ring_bounds)):
        r_edges = np.linspace(r_inner, r_outer, 2)
        theta_edges, r_edges = np.meshgrid(angles, r_edges)
        values = ring_values[idx][np.newaxis, :]
        ax.pcolormesh(
            theta_edges,
            r_edges,
            values,
            cmap=cmap,
            norm=norm,
            shading="flat",
            edgecolors="white",
            linewidth=0.25,
            alpha=0.9,
        )

    importance = rings["Importance"]
    smoothed = moving_average(importance, window=5)
    trend_r = ring_bounds[-1][1] + 0.08 + 0.08 * smoothed
    ax.plot(angles[:-1], trend_r, color="#6B7A8F", linewidth=1.1, label="Trend")

    max_idx = int(np.argmax(importance))
    min_idx = int(np.argmin(importance))
    marker_r = ring_bounds[-1][1] + 0.05
    ax.scatter(
        angles[max_idx],
        marker_r,
        s=28,
        color="#7A6C5D",
        marker="*",
        zorder=5,
        label="Max",
    )
    ax.scatter(
        angles[min_idx],
        marker_r,
        s=24,
        color="#8C8FA3",
        marker="o",
        zorder=5,
        label="Min",
    )

    ax.set_xlabel("Task Index", labelpad=12)
    ax.set_ylabel("Intensity", labelpad=20)
    ax.set_xticks(np.linspace(0, 2 * np.pi, 12, endpoint=False))
    ax.set_xticklabels([str(i) for i in range(1, 13)])
    ax.set_yticklabels([])
    ax.grid(color="#E0E0E0", linewidth=0.5, alpha=0.8)

    legend = ax.legend(loc="lower left", bbox_to_anchor=(1.05, 0.2), frameon=False)
    for text in legend.get_texts():
        text.set_color("#4C566A")

    cbar = fig.colorbar(
        mpl.cm.ScalarMappable(norm=norm, cmap=cmap),
        ax=ax,
        pad=0.1,
        fraction=0.04,
    )
    cbar.set_label("Ring Intensity")

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format="pdf")
    plt.close(fig)

    return compute_key_points(tasks, importance)


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(FIG_DIR / "fig_robotics_task_dna_circos.pdf"),
    )
    args = parser.parse_args()

    tasks = build_dummy_tasks()
    rings = synthesize_ring_data(len(tasks))
    key_points = plot_circular_heatmap(tasks, rings, Path(args.output))
    print(json.dumps(key_points, indent=2))


if __name__ == "__main__":
    main()
