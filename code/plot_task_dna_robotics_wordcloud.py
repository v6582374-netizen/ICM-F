#!/usr/bin/env python3
"""
Generate a word cloud for Robotics Engineers Task DNA with top tasks highlighted.
Outputs a PDF under figures/ and a summary XML under data/processed/.
"""
from __future__ import annotations

from argparse import ArgumentParser
import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "figures"
DATA_DIR = ROOT / "data" / "processed"

EXPECTED_COLUMNS = [
    "task_id",
    "task_text",
    "IM",
    "FR",
    "w",
    "s",
    "c",
    "evidence_note",
]


def read_task_dna_csv(path: Path) -> List[Dict[str, str]]:
    assert path.exists(), f"Missing task DNA file: {path}"
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames is not None, "Task DNA CSV missing header."
        for col in EXPECTED_COLUMNS:
            assert col in reader.fieldnames, f"Missing column: {col}"
        for row in reader:
            rows.append(row)
    assert rows, "Task DNA CSV has no rows."
    return rows


def load_top_task_ids(path: Path, soc: str, top_n: int | None = None) -> List[str]:
    assert path.exists(), f"Missing topK selection file: {path}"
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_soc = payload.get("by_soc", {})
    assert soc in by_soc, f"Missing SOC entry in topK file: {soc}"
    task_ids = list(by_soc[soc].get("topK_task_id", []))
    assert task_ids, "TopK task list is empty."
    if top_n is not None:
        return task_ids[:top_n]
    return task_ids


def _safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_frequencies(
    rows: Iterable[Dict[str, str]],
    top_task_ids: Iterable[str],
    boost: float = 1.6,
) -> Tuple[Dict[str, float], Dict[str, str]]:
    top_set = set(top_task_ids)
    freqs: Dict[str, float] = {}
    text_to_id: Dict[str, str] = {}
    for row in rows:
        task_text = row["task_text"].strip()
        task_id = row["task_id"].strip()
        weight = _safe_float(row["w"], 0.0)
        if task_id in top_set:
            weight *= boost
        freqs[task_text] = max(weight, 0.0)
        text_to_id[task_text] = task_id
    assert freqs, "No task frequencies generated."
    return freqs, text_to_id


def make_color_func(top_texts: Iterable[str]) -> "callable":
    top_set = set(top_texts)
    top_colors = [
        "rgb(60, 64, 70)",
        "rgb(94, 94, 94)",
        "rgb(142, 118, 72)",
        "rgb(121, 106, 88)",
        "rgb(120, 138, 112)",
    ]
    other_colors = [
        "rgb(176, 180, 186)",
        "rgb(191, 194, 198)",
        "rgb(198, 186, 164)",
        "rgb(186, 178, 166)",
        "rgb(188, 199, 188)",
    ]

    def _color_func(word: str, *args, **kwargs) -> str:
        if word in top_set:
            return top_colors[hash(word) % len(top_colors)]
        return other_colors[hash(word) % len(other_colors)]

    return _color_func


def plot_wordcloud(
    freqs: Dict[str, float],
    top_texts: Iterable[str],
    output_path: Path,
    title: str,
) -> Dict[str, object]:
    try:
        from wordcloud import WordCloud
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except Exception as exc:
        raise RuntimeError(
            "Missing required dependency. Install via: python3 -m pip install wordcloud"
        ) from exc

    wc = WordCloud(
        width=1600,
        height=1000,
        background_color="white",
        prefer_horizontal=1.0,
        max_words=len(freqs),
        min_font_size=10,
        max_font_size=160,
        collocations=False,
    ).generate_from_frequencies(freqs)

    fig, ax = plt.subplots(figsize=(8.6, 5.4), dpi=300)
    wc.recolor(color_func=make_color_func(top_texts))
    ax.imshow(wc.to_array(), extent=(0, 1, 0, 1))
    ax.set_title(title, fontsize=12, color="#374151", pad=10)
    ax.set_xlabel("Word cloud canvas (normalized units)")
    ax.set_ylabel("Word cloud canvas (normalized units)")
    ax.grid(color="#E6EAF0", linewidth=0.4, alpha=0.55)

    top_patch = mpatches.Patch(color="#8E7648", label="Top tasks")
    other_patch = mpatches.Patch(color="#C9BBA4", label="Other tasks")
    ax.legend(handles=[top_patch, other_patch], loc="lower right", frameon=False)

    for spine in ax.spines.values():
        spine.set_color("#E6EAF0")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, format="pdf")
    plt.close(fig)

    items = sorted(freqs.items(), key=lambda x: x[1], reverse=True)
    max_item = items[0]
    min_item = items[-1]
    return {
        "max_task_text": max_item[0],
        "max_weight": round(float(max_item[1]), 6),
        "min_task_text": min_item[0],
        "min_weight": round(float(min_item[1]), 6),
        "total_tasks": len(items),
    }


def write_summary_xml(path: Path, payload: Dict[str, object]) -> None:
    lines = ["<summary>"]
    for key, value in payload.items():
        lines.append(f"  <{key}>{value}</{key}>")
    lines.append("</summary>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _dummy_data_demo() -> None:
    dummy_rows = [
        {"task_id": "T1", "task_text": "Calibrate sensors", "w": "0.25"},
        {"task_id": "T2", "task_text": "Plan motion trajectories", "w": "0.40"},
        {"task_id": "T3", "task_text": "Integrate control systems", "w": "0.35"},
    ]
    freqs, _ = build_frequencies(dummy_rows, top_task_ids=["T2"])
    plot_wordcloud(
        freqs,
        top_texts=["Plan motion trajectories"],
        output_path=FIG_DIR / "fig_robotics_task_dna_wordcloud_demo.pdf",
        title="Robotics Task DNA Word Cloud (Demo)",
    )


def main() -> None:
    _dummy_data_demo()

    parser = ArgumentParser()
    parser.add_argument(
        "--input",
        default=str(DATA_DIR / "task_dna_17-2199.08.csv"),
        help="Task DNA CSV for robotics engineers.",
    )
    parser.add_argument(
        "--topk-json",
        default=str(DATA_DIR / "task_selection_topk.json"),
        help="TopK selection JSON with task_id lists.",
    )
    parser.add_argument("--soc", default="17-2199.08")
    parser.add_argument("--top-n", type=int, default=None)
    parser.add_argument(
        "--output",
        default=str(FIG_DIR / "fig_robotics_task_dna_wordcloud.pdf"),
    )
    parser.add_argument(
        "--summary-xml",
        default=str(DATA_DIR / "task_dna_17-2199.08_wordcloud_summary.xml"),
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    rows = read_task_dna_csv(input_path)
    top_task_ids = load_top_task_ids(Path(args.topk_json), args.soc, args.top_n)

    freqs, text_to_id = build_frequencies(rows, top_task_ids)
    top_texts = [text for text, task_id in text_to_id.items() if task_id in top_task_ids]
    title = "Robotics Engineers Task DNA Word Cloud"
    key_points = plot_wordcloud(freqs, top_texts, Path(args.output), title)

    summary_payload = {
        "soc": args.soc,
        "top_n": len(top_task_ids),
        "total_tasks": key_points["total_tasks"],
        "max_task_text": key_points["max_task_text"],
        "max_weight": key_points["max_weight"],
        "min_task_text": key_points["min_task_text"],
        "min_weight": key_points["min_weight"],
    }
    write_summary_xml(Path(args.summary_xml), summary_payload)
    print(json.dumps(summary_payload, ensure_ascii=True))


if __name__ == "__main__":
    main()
