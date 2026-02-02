#!/usr/bin/env python3
"""
Extract Task DNA from O*NET 30.1 text database for one or more SOC codes.
Outputs:
- data/processed/task_dna_{soc}.csv
- data/processed/task_dna_{soc}_summary.json (key stats)
- data/processed/task_dna_{soc}_summary.xml
- data/processed/task_dna_{soc}_anomaly_report.md
- figures/task_dna_{soc}_weights.pdf
- figures/task_dna_{soc}_weights_legend.pdf
"""
from __future__ import annotations

from argparse import ArgumentParser
import csv
import json
import string
import textwrap
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


TOP_N = 20


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    task_text: str
    im: Optional[float]
    fr: Optional[float]


def _read_tab_rows_from_zip(zf: zipfile.ZipFile, name: str) -> Iterable[Dict[str, str]]:
    with zf.open(name) as f:
        reader = csv.DictReader(
            (line.decode("utf-8", errors="replace") for line in f), delimiter="\t"
        )
        for row in reader:
            yield row


def _read_tab_rows_from_file(path: Path) -> Iterable[Dict[str, str]]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            yield row


def _iter_tab_rows(source: Path, filename: str) -> Iterable[Dict[str, str]]:
    if source.is_file() and source.suffix == ".zip":
        with zipfile.ZipFile(source) as zf:
            target = next(n for n in zf.namelist() if n.endswith(filename))
            yield from _read_tab_rows_from_zip(zf, target)
        return
    if source.is_dir():
        path = source / filename
        yield from _read_tab_rows_from_file(path)
        return
    raise FileNotFoundError(f"Unsupported O*NET source: {source}")


def load_task_statements(source: Path, soc_code: str) -> List[TaskRecord]:
    rows = [
        row
        for row in _iter_tab_rows(source, "Task Statements.txt")
        if row["O*NET-SOC Code"] == soc_code
    ]
    tasks = [
        TaskRecord(
            task_id=row["Task ID"].strip(),
            task_text=row["Task"].strip(),
            im=None,
            fr=None,
        )
        for row in rows
    ]
    return tasks


def load_task_ratings(
    source: Path, soc_code: str
) -> Dict[str, Dict[str, List[Tuple[int, float]]]]:
    ratings: Dict[str, Dict[str, List[Tuple[int, float]]]] = {}
    for row in _iter_tab_rows(source, "Task Ratings.txt"):
        if row["O*NET-SOC Code"] != soc_code:
            continue
        scale_id = row["Scale ID"].strip()
        if scale_id not in {"IM", "FT"}:
            continue
        task_id = row["Task ID"].strip()
        ratings.setdefault(task_id, {}).setdefault(scale_id, [])
        if scale_id == "IM":
            try:
                value = float(row["Data Value"])
            except ValueError:
                continue
            ratings[task_id][scale_id].append((0, value))
        else:
            try:
                category = int(row["Category"])
                value = float(row["Data Value"])
            except ValueError:
                continue
            ratings[task_id][scale_id].append((category, value))
    return ratings


def compute_fr_from_ft(ft_rows: List[Tuple[int, float]]) -> Optional[float]:
    if not ft_rows:
        return None
    total = sum(v for _, v in ft_rows)
    if total <= 0:
        return None
    return sum(cat * v for cat, v in ft_rows) / total


def merge_tasks_with_ratings(
    tasks: List[TaskRecord],
    ratings: Dict[str, Dict[str, List[Tuple[int, float]]]],
) -> List[TaskRecord]:
    merged: List[TaskRecord] = []
    for task in tasks:
        r = ratings.get(task.task_id, {})
        im_val = None
        if r.get("IM"):
            im_vals = [v for _, v in r["IM"]]
            im_val = sum(im_vals) / len(im_vals)
        fr_val = None
        if r.get("FT"):
            fr_val = compute_fr_from_ft(r["FT"])
        merged.append(TaskRecord(task.task_id, task.task_text, im_val, fr_val))
    return merged


def compute_weights(records: List[TaskRecord]) -> List[Tuple[TaskRecord, float]]:
    bases: List[float] = []
    for r in records:
        if r.im is None or r.fr is None:
            bases.append(0.0)
        else:
            bases.append(r.im * r.fr)
    total = sum(bases) if sum(bases) > 0 else 1.0
    return list(zip(records, [b / total for b in bases]))


def write_task_dna_csv(
    records: List[TaskRecord], output_path: Path, top_n: int = TOP_N
) -> Tuple[List[Dict[str, str]], int]:
    weighted = compute_weights(records)
    weighted.sort(key=lambda x: x[1], reverse=True)
    selected = weighted[: min(top_n, len(weighted))]
    selected_weight_sum = sum(w for _, w in selected)
    if selected:
        if selected_weight_sum <= 0:
            normalized = [1.0 / len(selected)] * len(selected)
        else:
            normalized = [w / selected_weight_sum for _, w in selected]
    else:
        normalized = []
    rows: List[Dict[str, str]] = []
    for (record, _), weight in zip(selected, normalized):
        s_val, c_val = 0.5, 0.5
        note = "placeholder=authoritative_sc_required"
        evidence_parts = [
            note,
            "FR=E[FT category] from Scale ID FT (Frequency of Task)"
            if record.fr is not None
            else "FR missing; weight uses IM only",
        ]
        rows.append(
            {
                "task_id": record.task_id,
                "task_text": record.task_text,
                "IM": "" if record.im is None else f"{record.im:.4f}",
                "FR": "" if record.fr is None else f"{record.fr:.4f}",
                "w": f"{weight:.6f}",
                "s": f"{s_val:.2f}",
                "c": f"{c_val:.2f}",
                "evidence_note": " | ".join(evidence_parts),
            }
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["task_id", "task_text", "IM", "FR", "w", "s", "c", "evidence_note"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return rows, len(selected)


def plot_weights_if_available(rows: List[Dict[str, str]], output_path: Path) -> Optional[Path]:
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        return None
    data = []
    for row in rows:
        try:
            im_val = float(row["IM"]) if row["IM"] else None
            fr_val = float(row["FR"]) if row["FR"] else None
            w_val = float(row["w"])
            c_val = float(row["c"])
        except ValueError:
            continue
        if im_val is None or fr_val is None:
            continue
        label = row["task_text"].strip()
        data.append((im_val, fr_val, w_val, c_val, float(row["s"]), label))
    if not data:
        return None

    data.sort(key=lambda x: x[2], reverse=True)
    im_vals, fr_vals, w_vals, c_vals, s_vals, labels = zip(*data)
    max_w = max(w_vals)
    min_w = min(w_vals)
    if max_w > min_w:
        norm_w = [(w - min_w) / (max_w - min_w) for w in w_vals]
    else:
        norm_w = [0.5 for _ in w_vals]
    size_exp = 1.7
    min_size = 140.0
    max_size = 2600.0
    sizes = [min_size + (n ** size_exp) * (max_size - min_size) for n in norm_w]
    edge_widths = [0.9 + 1.3 * s for s in s_vals]

    letters = list(string.ascii_uppercase)
    tag_list = [letters[i % len(letters)] for i in range(len(labels))]

    fig = plt.figure(figsize=(7.8, 5.2), dpi=300)
    ax = fig.add_subplot(1, 1, 1)

    scatter = ax.scatter(
        im_vals,
        fr_vals,
        s=sizes,
        c=c_vals,
        cmap="GnBu",
        alpha=0.78,
        edgecolors="#6B7280",
        linewidths=edge_widths,
    )
    offsets = [(6, 4), (-8, 4), (6, -6), (-8, -6)]
    for idx, (x, y, tag) in enumerate(zip(im_vals, fr_vals, tag_list)):
        dx, dy = offsets[idx % len(offsets)]
        ax.annotate(
            tag,
            (x, y),
            textcoords="offset points",
            xytext=(dx, dy),
            fontsize=9.5,
            color="#1F2937",
            weight="bold",
        )
    ax.set_facecolor("#FBFBFB")
    ax.set_xlabel("Importance (IM, 1-5)", fontsize=11)
    ax.set_ylabel("Frequency rating (FR, expected FT category)", fontsize=11)
    ax.grid(axis="both", linestyle="--", alpha=0.22)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#D1D5DB")
    if len(im_vals) >= 2 and len(fr_vals) >= 2:
        x_min, x_max = min(im_vals), max(im_vals)
        y_min, y_max = min(fr_vals), max(fr_vals)
        x_pad = max(0.18, 0.10 * (x_max - x_min))
        y_pad = max(0.18, 0.10 * (y_max - y_min))
        ax.set_xlim(x_min - x_pad, x_max + x_pad)
        ax.set_ylim(y_min - y_pad, y_max + y_pad)
    if len(im_vals) >= 2:
        coeffs = np.polyfit(im_vals, fr_vals, 1)
        x_line = np.linspace(min(im_vals), max(im_vals), 100)
        y_line = coeffs[0] * x_line + coeffs[1]
        ax.plot(x_line, y_line, color="#64748B", linestyle="--", linewidth=1.0, label="trend")
    cbar = fig.colorbar(scatter, ax=ax, pad=0.02, fraction=0.05)
    cbar.set_label("Complementarity c (rule-based)", fontsize=9.5)
    cbar.ax.tick_params(labelsize=8.5)
    ax.legend(loc="lower right", frameon=False, fontsize=8.5)
    ax.tick_params(axis="both", labelsize=10)

    entries = []
    for tag, label, im_v, fr_v, w_v in zip(tag_list, labels, im_vals, fr_vals, w_vals):
        entries.append(
            f"{tag}. {label} (IM={im_v:.2f}, FR={fr_v:.2f}, w={w_v:.3f})"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300)

    legend_path = output_path.with_name(f"{output_path.stem}_legend{output_path.suffix}")
    legend_fig = plt.figure(figsize=(8.2, 6.0), dpi=300)
    legend_ax = legend_fig.add_subplot(1, 1, 1)
    legend_ax.set_facecolor("#FBFBFB")
    legend_ax.axis("off")
    legend_ax.set_title(
        "Task Text Legend (sorted by weight w)",
        fontsize=10.2,
        color="#111827",
        loc="left",
        pad=6,
    )

    mid = (len(entries) + 1) // 2
    left_entries = entries[:mid]
    right_entries = entries[mid:]
    wrap_width = 48

    def _column_line_count(items: List[str]) -> int:
        return sum(max(1, len(textwrap.wrap(item, width=wrap_width))) for item in items)

    def _draw_column(items: List[str], x_pos: float) -> None:
        total_lines = _column_line_count(items)
        line_step = min(0.072, 0.92 / max(total_lines, 1))
        y = 0.98
        for item in items:
            wrapped = textwrap.fill(item, width=wrap_width)
            legend_ax.text(
                x_pos,
                y,
                wrapped,
                ha="left",
                va="top",
                fontsize=9.2,
                color="#374151",
            )
            y -= line_step * (wrapped.count("\n") + 1)

    _draw_column(left_entries, 0.02)
    _draw_column(right_entries, 0.52)

    legend_fig.savefig(legend_path, dpi=300)
    max_idx = int(w_vals.index(max(w_vals))) if w_vals else None
    min_idx = int(w_vals.index(min(w_vals))) if w_vals else None
    key_points = {
        "max_weight": max(w_vals) if w_vals else None,
        "min_weight": min(w_vals) if w_vals else None,
        "max_task_id": rows[max_idx]["task_id"] if max_idx is not None else None,
        "min_task_id": rows[min_idx]["task_id"] if min_idx is not None else None,
        "count": len(w_vals),
    }
    print(json.dumps(key_points, ensure_ascii=True))
    return output_path


def build_task_dna(source: Path, soc_code: str, output_path: Path) -> Tuple[List[Dict[str, str]], int]:
    assert source.exists(), f"Missing O*NET source: {source}"
    tasks = load_task_statements(source, soc_code)
    ratings = load_task_ratings(source, soc_code)
    merged = merge_tasks_with_ratings(tasks, ratings)
    return write_task_dna_csv(merged, output_path, TOP_N)


def _count_missing(rows: List[Dict[str, str]]) -> Tuple[int, int]:
    missing_im = sum(1 for r in rows if not r["IM"])
    missing_fr = sum(1 for r in rows if not r["FR"])
    return missing_im, missing_fr


def _weight_stats(rows: List[Dict[str, str]]) -> Dict[str, float]:
    weights = [float(r["w"]) for r in rows] if rows else []
    return {
        "w_sum": float(sum(weights)),
        "w_min": float(min(weights)) if weights else 0.0,
        "w_max": float(max(weights)) if weights else 0.0,
    }


def write_summary_json(path: Path, rows: List[Dict[str, str]]) -> Dict[str, float]:
    missing_im, missing_fr = _count_missing(rows)
    stats = _weight_stats(rows)
    payload = {
        "rows": len(rows),
        "missing_im": missing_im,
        "missing_fr": missing_fr,
        "w_sum": stats["w_sum"],
        "w_min": stats["w_min"],
        "w_max": stats["w_max"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def write_summary_xml(
    path: Path,
    stats: Dict[str, float],
    selected_n: int,
    total_tasks: int,
    top_n: int,
    reason: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["<summary>"]
    lines.append(f"  <rows>{int(stats['rows'])}</rows>")
    lines.append(f"  <missing_im>{int(stats['missing_im'])}</missing_im>")
    lines.append(f"  <missing_fr>{int(stats['missing_fr'])}</missing_fr>")
    lines.append("  <weight_stats>")
    lines.append(f"    <w_sum>{stats['w_sum']:.6f}</w_sum>")
    lines.append(f"    <w_min>{stats['w_min']:.6f}</w_min>")
    lines.append(f"    <w_max>{stats['w_max']:.6f}</w_max>")
    lines.append("  </weight_stats>")
    lines.append("  <selection>")
    lines.append(f"    <top_n>{top_n}</top_n>")
    lines.append(f"    <selected_n>{selected_n}</selected_n>")
    lines.append(f"    <total_tasks>{total_tasks}</total_tasks>")
    lines.append(f"    <reason>{reason}</reason>")
    lines.append("  </selection>")
    lines.append("</summary>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_anomaly_report(
    path: Path,
    rows: List[Dict[str, str]],
    missing_im: int,
    missing_fr: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Task DNA Anomaly Report",
        "",
        f"- Total rows: {len(rows)}",
        f"- Missing IM: {missing_im}",
        f"- Missing FR: {missing_fr}",
        "",
        "| task_id | missing_im | missing_fr | task_text |",
        "|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['task_id']} | {1 if not row['IM'] else 0} | {1 if not row['FR'] else 0} | "
            f"{row['task_text']} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_outputs_for_soc(source: Path, soc_code: str, top_n: int = TOP_N) -> None:
    output_csv = Path(f"data/processed/task_dna_{soc_code}.csv")
    summary_json = Path(f"data/processed/task_dna_{soc_code}_summary.json")
    summary_xml = Path(f"data/processed/task_dna_{soc_code}_summary.xml")
    anomaly_md = Path(f"data/processed/task_dna_{soc_code}_anomaly_report.md")
    fig_path = Path(f"figures/task_dna_{soc_code}_weights.pdf")

    tasks = load_task_statements(source, soc_code)
    rows, selected_n = write_task_dna_csv(
        merge_tasks_with_ratings(tasks, load_task_ratings(source, soc_code)),
        output_csv,
        top_n,
    )

    missing_im, missing_fr = _count_missing(rows)
    stats = write_summary_json(summary_json, rows)
    reason = "ok"
    if selected_n < top_n:
        reason = "available_tasks_lt_top_n_or_rating_filter"
    write_summary_xml(
        summary_xml,
        stats,
        selected_n=selected_n,
        total_tasks=len(tasks),
        top_n=top_n,
        reason=reason,
    )
    write_anomaly_report(anomaly_md, rows, missing_im, missing_fr)
    plot_weights_if_available(rows, fig_path)


def _dummy_data_demo() -> None:
    dummy = [
        TaskRecord("T1", "Write unit tests for code modules.", 4.0, 5.0),
        TaskRecord("T2", "Communicate requirements with stakeholders.", 3.0, 3.0),
    ]
    weighted = compute_weights(dummy)
    for record, weight in weighted:
        s_val, c_val = 0.5, 0.5
        note = "placeholder=authoritative_sc_required"
        print(
            {
                "task_id": record.task_id,
                "task_text": record.task_text,
                "IM": record.im,
                "FR": record.fr,
                "w": weight,
                "s": s_val,
                "c": c_val,
                "evidence_note": note,
            }
        )


if __name__ == "__main__":
    # Dummy data demo (does not replace real extraction)
    _dummy_data_demo()

    parser = ArgumentParser()
    parser.add_argument("--soc", action="append", dest="soc_codes", default=[])
    parser.add_argument("--source", default="data/raw/onet/db_30_1_text")
    parser.add_argument("--top-n", type=int, default=TOP_N)
    args = parser.parse_args()

    soc_codes = args.soc_codes or ["15-1252.00"]
    source_path = Path(args.source)

    for soc in soc_codes:
        build_outputs_for_soc(source_path, soc, top_n=args.top_n)
