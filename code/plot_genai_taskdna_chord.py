#!/usr/bin/env python3
"""
Draw a chord-style GenAI capability -> Task DNA mapping for each occupation.
Outputs one PDF per SOC code under figures/ and XML summaries under data/processed/.
"""
from __future__ import annotations

from argparse import ArgumentParser
import csv
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib.pyplot as plt
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"
FIG_DIR = ROOT / "figures"

DIM_ORDER = [f"D{i}" for i in range(1, 10)]
OCCUPATIONS = [
    ("17-2199.08", "Robotics Engineers"),
    ("49-1011.00", "First-Line Supervisors (Mech/Install/Repair)"),
    ("27-3092.00", "Court Reporters and Captioners"),
]

PALETTE = {
    "neutral_dark": "#3C4046",
    "neutral": "#6B7077",
    "neutral_light": "#C7CCD2",
    "warm_brown": "#8E7648",
    "warm_brown_light": "#C9BBA4",
    "sage": "#7A8C76",
    "sage_light": "#BCC7BC",
    "blue_gray": "#7A8CA2",
}

DIM_LABELS = {
    "D1": "D1 Eng. problem solving",
    "D2": "D2 Data analysis",
    "D3": "D3 Coding & automation",
    "D4": "D4 Physical operations",
    "D5": "D5 Planning & scheduling",
    "D6": "D6 Collaboration",
    "D7": "D7 Supervision & QA",
    "D8": "D8 Language & text",
    "D9": "D9 Info mgmt & retrieval",
}


def _parse_sim(sim_text: str) -> List[Tuple[str, float]]:
    if not sim_text:
        return []
    pairs: List[Tuple[str, float]] = []
    for part in sim_text.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        dim, value = part.split(":", 1)
        try:
            pairs.append((dim.strip(), float(value)))
        except ValueError:
            continue
    return pairs


def _read_task_dna(path: Path) -> List[Dict[str, str]]:
    assert path.exists(), f"Missing task DNA file: {path}"
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    assert rows, f"Empty task DNA file: {path}"
    return rows


def _load_topk(path: Path, soc: str, fallback_topn: int) -> List[str]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_soc = payload.get("by_soc", {})
    task_ids = list(by_soc.get(soc, {}).get("topK_task_id", []))
    if task_ids:
        return task_ids
    return task_ids[:fallback_topn]


def _short_task_label(task_id: str, task_text: str, max_len: int = 18) -> str:
    text = task_text.strip().rstrip(".")
    if len(text) > max_len:
        text = text[: max_len - 1].strip() + "…"
    return f"{task_id} {text}".strip()


def _build_edges(
    rows: Sequence[Dict[str, str]],
    top_task_ids: Sequence[str],
    top_n_fallback: int,
) -> Tuple[List[str], List[str], List[Tuple[str, str, float]], Dict[str, str], Sequence[str]]:
    task_rows = []
    for row in rows:
        try:
            weight = float(row["w"])
        except (KeyError, ValueError, TypeError):
            continue
        task_rows.append(
            {
                "task_id": row.get("task_id", "").strip(),
                "task_text": row.get("task_text", "").strip(),
                "w": weight,
                "sim": _parse_sim(row.get("sim", "")),
            }
        )

    task_rows.sort(key=lambda r: r["w"], reverse=True)
    if top_task_ids:
        top_set = set(top_task_ids)
        keep = [r for r in task_rows if r["task_id"] in top_set]
    else:
        keep = task_rows[:top_n_fallback]
    keep_ids = {r["task_id"] for r in keep}
    other = [r for r in task_rows if r["task_id"] not in keep_ids]

    right_nodes = [r["task_id"] for r in keep]
    if other:
        right_nodes.append("Other")

    label_map = {
        r["task_id"]: _short_task_label(r["task_id"], r["task_text"]) for r in keep
    }
    if other:
        label_map["Other"] = "Other tasks"

    edges: List[Tuple[str, str, float]] = []
    for r in keep:
        sims = [(d, v) for d, v in r["sim"] if d in DIM_ORDER]
        total = sum(v for _, v in sims) or 1.0
        for d, v in sims:
            edges.append((d, r["task_id"], r["w"] * v / total))

    if other:
        for r in other:
            sims = [(d, v) for d, v in r["sim"] if d in DIM_ORDER]
            total = sum(v for _, v in sims) or 1.0
            for d, v in sims:
                edges.append((d, "Other", r["w"] * v / total))

    return DIM_ORDER, right_nodes, edges, label_map, list(keep_ids)


def _alloc_arcs(
    nodes: Sequence[str],
    totals: Dict[str, float],
    theta_start: float,
    theta_end: float,
) -> Dict[str, Tuple[float, float]]:
    span = theta_end - theta_start
    total_mass = sum(totals.get(n, 0.0) for n in nodes) or 1.0
    cur = theta_start
    out: Dict[str, Tuple[float, float]] = {}
    for node in nodes:
        frac = totals.get(node, 0.0) / total_mass
        dtheta = span * frac
        out[node] = (cur, cur + dtheta)
        cur += dtheta
    return out


def _mid_theta(theta_pair: Tuple[float, float]) -> float:
    return 0.5 * (theta_pair[0] + theta_pair[1])


def _polar_xy(theta: float, r: float) -> Tuple[float, float]:
    return r * math.cos(theta), r * math.sin(theta)


def _chord_path(theta_a: float, theta_b: float, r: float, r_ctrl: float) -> MplPath:
    ax, ay = _polar_xy(theta_a, r)
    bx, by = _polar_xy(theta_b, r)
    c1x, c1y = _polar_xy(theta_a, r_ctrl)
    c2x, c2y = _polar_xy(theta_b, r_ctrl)
    verts = [(ax, ay), (c1x, c1y), (c2x, c2y), (bx, by)]
    codes = [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4]
    return MplPath(verts, codes)


def _dim_color(dim_id: str) -> str:
    if dim_id in {"D3", "D8"}:
        return PALETTE["warm_brown"]
    if dim_id in {"D7"}:
        return PALETTE["neutral_dark"]
    if dim_id in {"D4", "D5"}:
        return PALETTE["sage"]
    if dim_id in {"D1", "D2"}:
        return PALETTE["blue_gray"]
    return PALETTE["neutral"]


def _draw_arc(ax: plt.Axes, theta1: float, theta2: float, color: str, lw: float) -> None:
    ts = np.linspace(theta1, theta2, 90)
    xs = np.cos(ts)
    ys = np.sin(ts)
    ax.plot(xs, ys, color=color, lw=lw, solid_capstyle="round", zorder=3)


def _draw_labels(
    ax: plt.Axes,
    nodes: Sequence[str],
    arcs: Dict[str, Tuple[float, float]],
    label_map: Dict[str, str],
    side: str,
    top_set: Sequence[str],
) -> None:
    top_set = set(top_set)
    if side == "left":
        y_positions = np.linspace(0.78, -0.78, len(nodes))
        for node, y in zip(nodes, y_positions):
            theta = _mid_theta(arcs[node])
            x_arc, y_arc = _polar_xy(theta, 1.0)
            x_text = -1.63
            label = label_map.get(node, node)
            color = _dim_color(node)
            ax.text(
                x_text,
                y,
                label,
                ha="left",
                va="center",
                fontsize=9,
                color=PALETTE["neutral_dark"],
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=color, lw=1.6),
                zorder=6,
            )
            ax.plot(
                [x_text + 0.26, x_arc],
                [y, y_arc],
                color=color,
                lw=1.05,
                linestyle=(0, (3, 3)),
                alpha=0.9,
                zorder=5,
            )
    else:
        y_positions = np.linspace(0.72, -0.72, len(nodes))
        for node, y in zip(nodes, y_positions):
            theta = _mid_theta(arcs[node])
            x_arc, y_arc = _polar_xy(theta, 1.0)
            x_text = 1.18
            label = label_map.get(node, node)
            if node in top_set:
                fc = "#F4F2ED"
                text_color = PALETTE["neutral_dark"]
            else:
                fc = "#F2F3F5"
                text_color = PALETTE["neutral"]
            ax.text(
                x_text,
                y,
                label,
                ha="left",
                va="center",
                fontsize=8.5,
                color=text_color,
                bbox=dict(boxstyle="round,pad=0.22", fc=fc, ec="none"),
                zorder=6,
            )
            ax.plot(
                [x_text, x_arc],
                [y, y_arc],
                color=PALETTE["neutral_light"],
                lw=1.0,
                linestyle=(0, (2.8, 3.2)),
                alpha=0.85,
                zorder=5,
            )


def plot_chord(
    left_nodes: Sequence[str],
    right_nodes: Sequence[str],
    edges: Sequence[Tuple[str, str, float]],
    label_map: Dict[str, str],
    top_task_ids: Sequence[str],
    title: str,
    output_path: Path,
) -> Dict[str, object]:
    left_total = {d: 0.0 for d in left_nodes}
    right_total = {t: 0.0 for t in right_nodes}
    for d, t, w in edges:
        left_total[d] += w
        right_total[t] += w

    left_arcs = _alloc_arcs(left_nodes, left_total, math.radians(115), math.radians(245))
    right_arcs = _alloc_arcs(right_nodes, right_total, math.radians(-70), math.radians(70))

    fig = plt.figure(figsize=(9.2, 6.8), dpi=300)
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.9, 1.9)
    ax.set_ylim(-1.35, 1.35)

    for d, (a, b) in left_arcs.items():
        _draw_arc(ax, a, b, _dim_color(d), lw=6.0)

    for t, (a, b) in right_arcs.items():
        _draw_arc(ax, a, b, PALETTE["neutral_light"], lw=5.0)

    max_w = max((w for _, _, w in edges), default=1.0)
    for d, t, w in edges:
        ta = _mid_theta(left_arcs[d])
        tb = _mid_theta(right_arcs[t])
        base_color = _dim_color(d)
        alpha = min(0.35, 0.08 + 0.35 * (w / max_w))
        lw = 0.5 + 9.0 * (w / max_w)
        patch = PathPatch(
            _chord_path(ta, tb, r=1.0, r_ctrl=0.18),
            facecolor="none",
            edgecolor=base_color,
            lw=lw,
            alpha=alpha,
            zorder=2,
        )
        ax.add_patch(patch)

    _draw_labels(
        ax,
        left_nodes,
        left_arcs,
        {k: DIM_LABELS.get(k, k) for k in left_nodes},
        side="left",
        top_set=top_task_ids,
    )
    _draw_labels(
        ax,
        right_nodes,
        right_arcs,
        label_map,
        side="right",
        top_set=top_task_ids,
    )

    ax.text(
        0.0,
        1.20,
        title,
        ha="center",
        va="center",
        fontsize=12,
        color=PALETTE["neutral_dark"],
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format="pdf", bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)

    max_dim = max(left_total, key=left_total.get)
    max_task = max(right_total, key=right_total.get)
    return {
        "max_dim": max_dim,
        "max_dim_weight": round(float(left_total[max_dim]), 6),
        "max_task": max_task,
        "max_task_weight": round(float(right_total[max_task]), 6),
        "edges": len(edges),
        "tasks_shown": len(right_nodes),
    }


def write_summary_xml(path: Path, payload: Dict[str, object]) -> None:
    lines = ["<summary>"]
    for key, value in payload.items():
        lines.append(f"  <{key}>{value}</{key}>")
    lines.append("</summary>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _dummy_demo() -> None:
    left_nodes = DIM_ORDER
    right_nodes = ["T1", "T2", "Other"]
    label_map = {"T1": "T1 Demo task A", "T2": "T2 Demo task B", "Other": "Other tasks"}
    edges = [
        ("D1", "T1", 0.6),
        ("D3", "T1", 0.4),
        ("D4", "T2", 0.7),
        ("D7", "T2", 0.3),
        ("D2", "Other", 0.2),
        ("D5", "Other", 0.1),
    ]
    plot_chord(
        left_nodes,
        right_nodes,
        edges,
        label_map,
        top_task_ids=["T1", "T2"],
        title="GenAI Capability → Task DNA Mapping (Demo)",
        output_path=FIG_DIR / "fig_genai_taskdna_chord_demo.pdf",
    )


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--top-n", type=int, default=12)
    parser.add_argument("--topk-json", default=str(DATA_DIR / "task_selection_topk.json"))
    parser.add_argument("--output-dir", default=str(FIG_DIR))
    args = parser.parse_args()

    _dummy_demo()

    output_dir = Path(args.output_dir)
    results = []
    for soc_code, label in OCCUPATIONS:
        csv_path = DATA_DIR / f"task_dna_{soc_code}_authoritative_sc.csv"
        rows = _read_task_dna(csv_path)
        top_task_ids = _load_topk(Path(args.topk_json), soc_code, args.top_n)
        left_nodes, right_nodes, edges, label_map, keep_ids = _build_edges(
            rows, top_task_ids, args.top_n
        )
        title = f"{soc_code} {label}"
        output_path = output_dir / f"fig_genai_taskdna_chord_{soc_code}.pdf"
        summary = plot_chord(
            left_nodes,
            right_nodes,
            edges,
            label_map,
            top_task_ids=keep_ids,
            title=title,
            output_path=output_path,
        )
        summary_payload = {"soc": soc_code, "title": label, **summary}
        summary_path = DATA_DIR / f"genai_taskdna_chord_{soc_code}_summary.xml"
        write_summary_xml(summary_path, summary_payload)
        results.append(summary_payload)

    print(json.dumps(results, ensure_ascii=True))


if __name__ == "__main__":
    main()
