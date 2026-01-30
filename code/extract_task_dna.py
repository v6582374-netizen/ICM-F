#!/usr/bin/env python3
"""
Extract Task DNA for SOC 15-1252.00 from O*NET 30.1 text database.
Outputs data/processed/task_dna_15-1252.csv
"""
from __future__ import annotations

import csv
import json
import re
import string
import textwrap
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


ZIP_PATH = Path("data/raw/onet/db_30_1_text.zip")
OUTPUT_PATH = Path("data/processed/task_dna_15-1252.csv")
SOC_CODE = "15-1252.00"
TOP_N = 20


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    task_text: str
    im: Optional[float]
    fr: Optional[float]


def _read_tab_rows(zf: zipfile.ZipFile, name: str) -> Iterable[Dict[str, str]]:
    with zf.open(name) as f:
        reader = csv.DictReader(
            (line.decode("utf-8", errors="replace") for line in f), delimiter="\t"
        )
        for row in reader:
            yield row


def load_task_statements(zip_path: Path, soc_code: str) -> List[TaskRecord]:
    with zipfile.ZipFile(zip_path) as zf:
        ts_path = next(n for n in zf.namelist() if n.endswith("Task Statements.txt"))
        rows = [
            row
            for row in _read_tab_rows(zf, ts_path)
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


def load_task_ratings(zip_path: Path, soc_code: str) -> Dict[str, Dict[str, List[Tuple[int, float]]]]:
    ratings: Dict[str, Dict[str, List[Tuple[int, float]]]] = {}
    with zipfile.ZipFile(zip_path) as zf:
        tr_path = next(n for n in zf.namelist() if n.endswith("Task Ratings.txt"))
        for row in _read_tab_rows(zf, tr_path):
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


def keyword_scoring(task_text: str) -> Tuple[float, float, str]:
    text = task_text.lower()
    rules = [
        (r"\b(write|implement|code|coding)\b", 0.8, 0.7, "write/implement/code"),
        (r"\b(test|testing|verify|debug|security)\b", 0.5, 0.8, "test/verify/debug/security"),
        (r"\b(requirements|communicate|communication|stakeholder)\b", 0.3, 0.6, "requirements/communicate/stakeholder"),
    ]
    s_val, c_val = 0.5, 0.5
    matched: List[str] = []
    for pattern, s_rule, c_rule, label in rules:
        if re.search(pattern, text):
            s_val = max(s_val, s_rule)
            c_val = max(c_val, c_rule)
            matched.append(label)
    if matched:
        confidence = "keyword-medium"
        if len(matched) >= 2:
            confidence = "keyword-high"
        return s_val, c_val, f"keywords={';'.join(matched)};confidence={confidence}"
    return s_val, c_val, "keywords=none;confidence=default-low"


def compute_weights(records: List[TaskRecord]) -> List[Tuple[TaskRecord, float]]:
    bases: List[float] = []
    for r in records:
        if r.im is None:
            bases.append(0.0)
            continue
        if r.fr is None:
            bases.append(r.im)
        else:
            bases.append(r.im * r.fr)
    total = sum(bases) if sum(bases) > 0 else 1.0
    return list(zip(records, [b / total for b in bases]))


def write_task_dna_csv(
    records: List[TaskRecord],
    output_path: Path,
    top_n: int = TOP_N,
) -> List[Dict[str, str]]:
    weighted = compute_weights(records)
    weighted.sort(key=lambda x: x[1], reverse=True)
    selected = weighted[:top_n]
    rows: List[Dict[str, str]] = []
    for record, weight in selected:
        s_val, c_val, note = keyword_scoring(record.task_text)
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
    return rows


def plot_weights_if_available(rows: List[Dict[str, str]], output_path: Path) -> Optional[Path]:
    try:
        import matplotlib.pyplot as plt
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
    size_scale = 2400.0
    sizes = [max(50.0, w * size_scale) for w in w_vals]
    edge_widths = [0.6 + 1.0 * s for s in s_vals]

    letters = list(string.ascii_uppercase)
    tag_list = []
    for i in range(len(labels)):
        tag_list.append(letters[i % len(letters)])

    fig = plt.figure(figsize=(10.5, 6.6), dpi=300)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 1.0])
    ax = fig.add_subplot(gs[0, 0])
    ax_text = fig.add_subplot(gs[0, 1])

    scatter = ax.scatter(
        im_vals,
        fr_vals,
        s=sizes,
        c=c_vals,
        cmap="Blues",
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
            fontsize=8,
            color="#1F2937",
            weight="bold",
        )
    ax.set_xlabel("Importance (IM, 1-5)")
    ax.set_ylabel("Frequency rating (FR, expected FT category)")
    ax.grid(axis="both", linestyle="--", alpha=0.25)
    ax.set_xlim(1.0, 5.0)
    ax.set_ylim(1.0, 7.0)
    cbar = fig.colorbar(scatter, ax=ax, pad=0.02)
    cbar.set_label("Complementarity c (rule-based)")

    ax_text.axis("off")
    ax_text.set_title("Task Text Legend (sorted by weight w)", fontsize=9, color="#111827")
    y = 0.98
    line_step = 0.055
    for tag, label, im_v, fr_v, w_v in zip(tag_list, labels, im_vals, fr_vals, w_vals):
        wrapped = textwrap.fill(
            f"{tag}. {label} (IM={im_v:.2f}, FR={fr_v:.2f}, w={w_v:.3f})",
            width=42,
        )
        ax_text.text(0.0, y, wrapped, ha="left", va="top", fontsize=7.6, color="#374151")
        y -= line_step * (wrapped.count("\n") + 1)
        if y < 0.05:
            break

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300)
    key_points = {
        "max_weight": max(w_vals) if w_vals else None,
        "min_weight": min(w_vals) if w_vals else None,
        "count": len(w_vals),
    }
    print(json.dumps(key_points, ensure_ascii=True))
    return output_path


def build_task_dna(zip_path: Path, soc_code: str, output_path: Path) -> List[Dict[str, str]]:
    assert zip_path.exists(), f"Missing zip file: {zip_path}"
    tasks = load_task_statements(zip_path, soc_code)
    ratings = load_task_ratings(zip_path, soc_code)
    merged = merge_tasks_with_ratings(tasks, ratings)
    return write_task_dna_csv(merged, output_path, TOP_N)


def _dummy_data_demo() -> None:
    dummy = [
        TaskRecord("T1", "Write unit tests for code modules.", 4.0, 5.0),
        TaskRecord("T2", "Communicate requirements with stakeholders.", 3.0, 3.0),
    ]
    weighted = compute_weights(dummy)
    for record, weight in weighted:
        s_val, c_val, note = keyword_scoring(record.task_text)
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

    # Real extraction
    rows = build_task_dna(ZIP_PATH, SOC_CODE, OUTPUT_PATH)
    fig_path = plot_weights_if_available(rows, Path("figures/task_dna_15-1252_weights.pdf"))
    if fig_path is None:
        print("matplotlib not available; skipped plotting")
