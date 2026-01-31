#!/usr/bin/env python3
"""
Relabel (s, c) for task_dna_{soc}.csv using authoritative capability evidence,
semantic matching, and tiered rubric. No keyword heuristics are used for scoring.
"""
from __future__ import annotations

from argparse import ArgumentParser
import csv
import hashlib
import json
import os
import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None

try:
    from rapidfuzz.fuzz import token_set_ratio
except Exception:  # pragma: no cover - optional dependency
    token_set_ratio = None


INPUT_CSV = Path("data/processed/task_dna_15-1252.csv")
SOURCES_MD = Path("data/processed/authoritative_sc_sources_domainpack.md")

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
ALLOWED_LEVELS = (0.1, 0.3, 0.5, 0.7, 0.9)
SIM_THRESHOLD = 0.35
TWO_DIM_THRESHOLD = 0.45
TWO_DIM_GAP = 0.08


AUTHORITATIVE_SOURCES = [
    (
        "G1 OpenAI GPT-4 Technical Report (MMLU, ARC, GSM8K, DROP, HellaSwag, preference): "
        "https://cdn.openai.com/papers/gpt-4.pdf",
        ["G1"],
    ),
    (
        "G2 HumanEval benchmark (code generation): https://arxiv.org/abs/2107.03374",
        ["G2"],
    ),
    (
        "G3 SWE-bench benchmark (software issue resolution): https://www.swe-bench.com/",
        ["G3"],
    ),
    (
        "G4 AutoGPT project (autonomous task completion): "
        "https://github.com/Significant-Gravitas/AutoGPT",
        ["G4"],
    ),
    (
        "G5 Whisper ASR (WER performance): https://arxiv.org/abs/2212.04356",
        ["G5"],
    ),
    (
        "G6 DocVQA benchmark: https://www.docvqa.org/",
        ["G6"],
    ),
    (
        "G7 Spider Text-to-SQL benchmark: https://yale-lily.github.io/spider",
        ["G7"],
    ),
    (
        "G8 ImageNet benchmark (vision recognition performance): https://www.image-net.org/",
        ["G8"],
    ),
]

_MODEL_CACHE: Dict[str, object] = {}


@dataclass(frozen=True)
class DimensionProfile:
    dim_id: str
    name: str
    description: str
    exemplar_phrases: Sequence[str]
    default_s: float
    default_c: float
    sources: Sequence[str]


def build_dimension_profiles() -> List[DimensionProfile]:
    return [
        DimensionProfile(
            dim_id="D1",
            name="Engineering Problem Solving",
            description=(
                "Apply engineering knowledge to analyze and resolve technical issues "
                "(debugging, maintenance, technical support)."
            ),
            exemplar_phrases=(
                "diagnose technical issues",
                "troubleshoot system faults",
                "provide technical support",
            ),
            default_s=0.5,
            default_c=0.85,
            sources=("G1",),
        ),
        DimensionProfile(
            dim_id="D2",
            name="Data Analysis and Evaluation",
            description=(
                "Analyze sensor or numerical data and evaluate results against standards "
                "(quality checks, data monitoring)."
            ),
            exemplar_phrases=(
                "analyze sensor data",
                "evaluate quality metrics",
                "monitor data streams",
            ),
            default_s=0.3,
            default_c=0.5,
            sources=("G1",),
        ),
        DimensionProfile(
            dim_id="D3",
            name="Algorithmic Programming and Automation",
            description=(
                "Write and fix code/scripts to implement requirements "
                "(software development, automation workflows)."
            ),
            exemplar_phrases=(
                "write automation scripts",
                "debug software code",
                "implement algorithms",
            ),
            default_s=0.9,
            default_c=0.7,
            sources=("G1", "G2", "G3"),
        ),
        DimensionProfile(
            dim_id="D4",
            name="Field Perception and Physical Operations",
            description=(
                "Perceive physical environments and operate equipment on-site "
                "(inspection, safety checks, device calibration)."
            ),
            exemplar_phrases=(
                "inspect physical equipment",
                "perform on-site checks",
                "calibrate devices",
            ),
            default_s=0.1,
            default_c=0.5,
            sources=("G4", "G8"),
        ),
        DimensionProfile(
            dim_id="D5",
            name="Planning and Process Scheduling",
            description=(
                "Plan tasks and optimize sequences and resource allocation "
                "(scheduling, progress management)."
            ),
            exemplar_phrases=(
                "schedule work activities",
                "allocate resources",
                "optimize task sequences",
            ),
            default_s=0.6,
            default_c=0.5,
            sources=("G4",),
        ),
        DimensionProfile(
            dim_id="D6",
            name="Collaboration, Communication, and Training",
            description=(
                "Communicate and coordinate with people, provide training, "
                "and facilitate cross-team collaboration."
            ),
            exemplar_phrases=(
                "train staff",
                "coordinate teams",
                "communicate procedures",
            ),
            default_s=0.3,
            default_c=0.75,
            sources=("G1",),
        ),
        DimensionProfile(
            dim_id="D7",
            name="Supervision and Quality Control",
            description=(
                "Supervise work performance and ensure outputs meet standards "
                "(performance management, QA)."
            ),
            exemplar_phrases=(
                "review work quality",
                "monitor performance",
                "conduct quality checks",
            ),
            default_s=0.68,
            default_c=0.68,
            sources=("G1",),
        ),
        DimensionProfile(
            dim_id="D8",
            name="Language Understanding and Text Generation",
            description=(
                "Understand spoken or written language and generate accurate written content "
                "(transcription, writing, translation)."
            ),
            exemplar_phrases=(
                "transcribe audio",
                "generate written reports",
                "translate documents",
            ),
            default_s=0.9,
            default_c=0.5,
            sources=("G5", "G1"),
        ),
        DimensionProfile(
            dim_id="D9",
            name="Information Management and Retrieval",
            description=(
                "Organize information and retrieve it accurately on demand "
                "(record management, query answering)."
            ),
            exemplar_phrases=(
                "manage records",
                "retrieve documents",
                "answer database queries",
            ),
            default_s=0.3,
            default_c=0.3,
            sources=("G6", "G7"),
        ),
    ]


def write_sources_md(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Authoritative Sources Domain Pack",
        "",
        "## Core LLM Benchmarks",
        " - " + AUTHORITATIVE_SOURCES[0][0],
        " - " + AUTHORITATIVE_SOURCES[1][0],
        " - " + AUTHORITATIVE_SOURCES[2][0],
        "",
        "## Agent Autonomy / Task Completion",
        " - " + AUTHORITATIVE_SOURCES[3][0],
        "",
        "## Speech and Vision Perception",
        " - " + AUTHORITATIVE_SOURCES[4][0],
        " - " + AUTHORITATIVE_SOURCES[7][0],
        "",
        "## Information Retrieval and Structured Query",
        " - " + AUTHORITATIVE_SOURCES[5][0],
        " - " + AUTHORITATIVE_SOURCES[6][0],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _hash_embedding(texts: Sequence[str], dim: int = 128):
    if np is None:
        vectors = [[0.0 for _ in range(dim)] for _ in range(len(texts))]
        for i, text in enumerate(texts):
            tokens = re.findall(r"[a-z0-9]+", text.lower())
            for token in tokens:
                digest = hashlib.md5(token.encode("utf-8")).hexdigest()
                idx = int(digest, 16) % dim
                vectors[i][idx] += 1.0
        return _normalize_vectors(vectors)
    vectors = np.zeros((len(texts), dim), dtype=np.float32)
    for i, text in enumerate(texts):
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            idx = int(digest, 16) % dim
            vectors[i, idx] += 1.0
    return _normalize_vectors(vectors)


def _normalize_vectors(vectors):
    if np is None:
        normed = []
        for row in vectors:
            norm = sum(val * val for val in row) ** 0.5
            if norm == 0:
                norm = 1.0
            normed.append([val / norm for val in row])
        return normed
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def _get_sentence_model(model_name: str):
    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    _MODEL_CACHE[model_name] = model
    return model


def embed_texts(
    texts: Sequence[str],
    backend: str,
    model_name: str,
) -> Tuple[np.ndarray, str]:
    if backend == "hash":
        return _hash_embedding(texts), "hash"
    if backend == "sentence_transformers":
        if np is None:
            raise RuntimeError("numpy not available; install numpy or set SC_EMBEDDING_BACKEND=hash")
        try:
            model = _get_sentence_model(model_name)
        except Exception as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError(
                "sentence-transformers not available; install it or set SC_EMBEDDING_BACKEND=hash"
            ) from exc
        embeddings = model.encode(list(texts), normalize_embeddings=True)
        return np.asarray(embeddings, dtype=np.float32), "sentence_transformers"
    if backend == "tfidf":
        if np is None:
            raise RuntimeError("numpy not available; install numpy or set SC_EMBEDDING_BACKEND=hash")
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
        except Exception as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError(
                "scikit-learn not available; install it or use SC_EMBEDDING_BACKEND=hash"
            ) from exc
        vectorizer = TfidfVectorizer()
        mat = vectorizer.fit_transform(texts).toarray().astype(np.float32)
        return _normalize_vectors(mat), "tfidf"
    raise ValueError(f"Unknown embedding backend: {backend}")


def get_backend_from_env() -> str:
    return os.getenv("SC_EMBEDDING_BACKEND", "sentence_transformers")


def get_model_name_from_env() -> str:
    return os.getenv("SC_EMBEDDING_MODEL", DEFAULT_MODEL_NAME)


def build_dimension_texts(dimensions: Sequence[DimensionProfile]) -> List[str]:
    texts = []
    for dim in dimensions:
        exemplars = "; ".join(dim.exemplar_phrases)
        texts.append(f"{dim.name}. {dim.description} Examples: {exemplars}.")
    return texts


def cosine_similarity_matrix(a, b):
    if np is None:
        return [[sum(x * y for x, y in zip(row, col)) for col in b] for row in a]
    return np.matmul(a, b.T)


def get_fuzzy_similarity(task_text: str, dim_text: str) -> Optional[float]:
    if token_set_ratio is None:
        return None
    score = token_set_ratio(task_text, dim_text)
    return float(score) / 100.0


def compute_similarity_scores(
    task_text: str,
    dim_texts: Sequence[str],
    emb_scores: Sequence[float],
) -> Tuple[List[float], bool]:
    fuzzy_available = True
    combined_scores: List[float] = []
    for dim_text, emb_score in zip(dim_texts, emb_scores):
        fuzz_score = get_fuzzy_similarity(task_text, dim_text)
        if fuzz_score is None:
            fuzzy_available = False
            fuzz_score = 0.0
        combined = 0.85 * float(emb_score) + 0.15 * float(fuzz_score)
        combined_scores.append(combined)
    return combined_scores, fuzzy_available


def select_dimensions(
    dim_ids: Sequence[str],
    scores: Sequence[float],
) -> Tuple[List[int], List[float], bool]:
    indexed = list(enumerate(scores))
    indexed.sort(key=lambda x: x[1], reverse=True)
    top1_idx, top1_score = indexed[0]
    top2_idx, top2_score = indexed[1]
    use_two = top2_score >= TWO_DIM_THRESHOLD and (top1_score - top2_score) <= TWO_DIM_GAP
    if use_two:
        weights = [top1_score, top2_score]
        total = sum(weights) if sum(weights) > 0 else 1.0
        weights = [w / total for w in weights]
        return [top1_idx, top2_idx], weights, True
    return [top1_idx], [1.0], False


def snap_to_levels(value: float) -> float:
    return min(ALLOWED_LEVELS, key=lambda x: abs(x - value))


def _apply_strength(value: float, strength: float) -> float:
    scale = 0.6 + 0.8 * max(0.0, min(1.0, strength))
    adjusted = 0.5 + (value - 0.5) * scale
    return max(0.0, min(1.0, adjusted))


def assign_sc(
    dims: Sequence[DimensionProfile],
    weights: Sequence[float],
    scores: Sequence[float],
) -> Tuple[float, float, float, float, float]:
    raw_s = sum(d.default_s * w for d, w in zip(dims, weights))
    raw_c = sum(d.default_c * w for d, w in zip(dims, weights))
    strength = sum(score * w for score, w in zip(scores, weights)) if scores else 0.0
    adj_s = _apply_strength(raw_s, strength)
    adj_c = _apply_strength(raw_c, strength)
    return snap_to_levels(adj_s), snap_to_levels(adj_c), raw_s, raw_c, strength


def compute_mu_task(c_val: float, s_val: float) -> str:
    mu_task = Decimal(str(c_val)) - Decimal(str(s_val))
    return f"{mu_task.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def build_evidence_note(
    dims: Sequence[DimensionProfile],
    similarity_triplet: Sequence[Tuple[str, float]],
    weights: Optional[Sequence[float]],
    final_s: float,
    final_c: float,
    strength: float,
) -> str:
    dim_ids = ",".join(d.dim_id for d in dims)
    sim_parts = ",".join(f"{dim_id}:{score:.2f}" for dim_id, score in similarity_triplet)
    if weights and len(weights) > 1:
        weight_parts = ",".join(f"{d.dim_id}:{w:.2f}" for d, w in zip(dims, weights))
        weight_text = f"weights=[{weight_parts}];"
    else:
        weight_text = ""
    source_ids = sorted({src for d in dims for src in d.sources})
    source_text = "|".join(source_ids)
    return (
        f"dims={dim_ids};"
        f"sim=[{sim_parts}];"
        f"{weight_text}"
        f"s={final_s:.2f};"
        f"c={final_c:.2f};"
        f"strength={strength:.2f};"
        f"sources={source_text}"
    )


def assert_task_dna_schema(rows: Sequence[Dict[str, str]]) -> None:
    required = {"task_id", "task_text", "IM", "FR", "w", "s", "c", "evidence_note"}
    assert rows, "Input CSV has no rows."
    missing = required.difference(rows[0].keys())
    assert not missing, f"Missing columns: {sorted(missing)}"
    for row in rows:
        float(row["w"])


def load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert_task_dna_schema(rows)
    return rows


def write_csv(path: Path, rows: Sequence[Dict[str, str]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def relabel_task_rows(
    rows: Sequence[Dict[str, str]],
    dimensions: Sequence[DimensionProfile],
    backend: str,
    model_name: str,
) -> Tuple[List[Dict[str, str]], Dict[str, int], List[Dict[str, str]], Dict[str, float], bool]:
    dim_texts = build_dimension_texts(dimensions)
    dim_embeddings, used_backend = embed_texts(dim_texts, backend, model_name)
    task_texts = [row["task_text"].strip() for row in rows]
    task_embeddings, _ = embed_texts(task_texts, used_backend, model_name)
    sim_matrix = cosine_similarity_matrix(task_embeddings, dim_embeddings)
    dim_ids = [d.dim_id for d in dimensions]
    updated: List[Dict[str, str]] = []
    dim_counts: Dict[str, int] = {d.dim_id: 0 for d in dimensions}
    anomalies: List[Dict[str, str]] = []
    fuzzy_available = True

    for idx, row in enumerate(rows):
        task_text = task_texts[idx]
        emb_scores = sim_matrix[idx]
        if hasattr(emb_scores, "tolist"):
            emb_scores = emb_scores.tolist()
        score_values, fuzzy_ok = compute_similarity_scores(task_text, dim_texts, emb_scores)
        if not fuzzy_ok:
            fuzzy_available = False
        selected_idx, weights, used_two = select_dimensions(dim_ids, score_values)
        selected_dims = [dimensions[i] for i in selected_idx]
        selected_scores = [score_values[i] for i in selected_idx]
        final_s, final_c, raw_s, raw_c, strength = assign_sc(
            selected_dims, weights, selected_scores
        )

        top3 = sorted(
            [(dim_ids[i], score_values[i]) for i in range(len(dim_ids))],
            key=lambda x: x[1],
            reverse=True,
        )[:3]
        evidence_note = build_evidence_note(
            selected_dims,
            top3,
            weights if used_two else None,
            final_s,
            final_c,
            strength,
        )
        dims_text = ",".join(d.dim_id for d in selected_dims)
        sim_text = ",".join(f"{dim_id}:{score:.2f}" for dim_id, score in top3)
        sources_text = "|".join(sorted({src for d in selected_dims for src in d.sources}))

        if top3[0][1] < SIM_THRESHOLD:
            anomalies.append(
                {
                    "task_id": row["task_id"],
                    "task_text": task_text,
                    "w": row["w"],
                    "top_dim": top3[0][0],
                    "top_score": f"{top3[0][1]:.2f}",
                    "second_dim": top3[1][0],
                    "second_score": f"{top3[1][1]:.2f}",
                }
            )

        for dim in selected_dims:
            dim_counts[dim.dim_id] += 1

        updated_row = {
            "task_id": row["task_id"],
            "task_text": row["task_text"],
            "IM": row["IM"],
            "FR": row["FR"],
            "w": row["w"],
            "s": f"{final_s:.2f}",
            "c": f"{final_c:.2f}",
            "mu_task": compute_mu_task(final_c, final_s),
            "evidence_note": evidence_note,
            "dims": dims_text,
            "sim": sim_text,
            "sources": sources_text,
        }
        updated.append(updated_row)

    weights = [float(r["w"]) for r in rows]
    w_stats = {
        "w_sum": float(sum(weights)),
        "w_min": float(min(weights)) if weights else 0.0,
        "w_max": float(max(weights)) if weights else 0.0,
    }
    return updated, dim_counts, anomalies, w_stats, fuzzy_available


def write_anomaly_report(path: Path, anomalies: Sequence[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Task DNA Authoritative SC Anomaly Report",
        "",
        f"- Low-confidence threshold: {SIM_THRESHOLD:.2f}",
        f"- Total flagged tasks: {len(anomalies)}",
        "",
    ]
    if not anomalies:
        lines.append("No low-confidence matches were detected.")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    lines.append("| task_id | w | task_text | top_dim | top_score | second_dim | second_score |")
    lines.append("|---|---:|---|---:|---:|---:|---:|")
    for item in anomalies:
        lines.append(
            f"| {item['task_id']} | {item['w']} | {item['task_text']} | {item['top_dim']} | "
            f"{item['top_score']} | {item['second_dim']} | {item['second_score']} |"
        )
    lines.append("")
    lines.append("Manual override suggestions: review tasks with low scores and confirm dim mapping.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary_json(
    path: Path,
    rows: Sequence[Dict[str, str]],
    dim_counts: Dict[str, int],
    anomalies: Sequence[Dict[str, str]],
    w_stats: Dict[str, float],
    backend: str,
    model_name: str,
    fuzzy_available: bool,
    output_csv: Path,
    input_csv: Path,
) -> None:
    summary = {
        "input_csv": str(input_csv),
        "output_csv": str(output_csv),
        "rows": len(rows),
        "dim_counts": dim_counts,
        "low_confidence_count": len(anomalies),
        "thresholds": {
            "sim_threshold": SIM_THRESHOLD,
            "two_dim_threshold": TWO_DIM_THRESHOLD,
            "two_dim_gap": TWO_DIM_GAP,
        },
        "embedding_backend": backend,
        "embedding_model": model_name,
        "fuzzy_available": fuzzy_available,
        "weight_stats": w_stats,
        "allowed_levels": list(ALLOWED_LEVELS),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def write_summary_xml(path: Path, summary: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["<summary>"]
    lines.append(f"  <rows>{summary['rows']}</rows>")
    lines.append("  <dim_counts>")
    for dim_id, count in summary["dim_counts"].items():
        lines.append(f"    <dim id=\"{dim_id}\">{count}</dim>")
    lines.append("  </dim_counts>")
    lines.append(f"  <low_confidence_count>{summary['low_confidence_count']}</low_confidence_count>")
    lines.append("  <weight_stats>")
    lines.append(f"    <w_sum>{summary['weight_stats']['w_sum']:.6f}</w_sum>")
    lines.append(f"    <w_min>{summary['weight_stats']['w_min']:.6f}</w_min>")
    lines.append(f"    <w_max>{summary['weight_stats']['w_max']:.6f}</w_max>")
    lines.append("  </weight_stats>")
    lines.append("</summary>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_distribution(rows: Sequence[Dict[str, str]], output_path: Path) -> Optional[Path]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return None
    s_vals = [float(r["s"]) for r in rows]
    c_vals = [float(r["c"]) for r in rows]
    levels = sorted(set(ALLOWED_LEVELS))
    s_counts = [s_vals.count(level) for level in levels]
    c_counts = [c_vals.count(level) for level in levels]

    fig, ax = plt.subplots(figsize=(6.6, 4.4), dpi=300)
    width = 0.34
    x = np.arange(len(levels))
    ax.bar(x - width / 2, s_counts, width, label="s counts", color="#C9D6E6")
    ax.bar(x + width / 2, c_counts, width, label="c counts", color="#D8CBBE")
    ax.plot(x, s_counts, color="#6B7280", marker="o", linestyle="--", label="s trend")
    ax.plot(x, c_counts, color="#8A7A6A", marker="o", linestyle="--", label="c trend")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{lvl:.2f}" for lvl in levels])
    ax.set_facecolor("#FBFBFB")
    ax.set_xlabel("s / c levels", fontsize=11)
    ax.set_ylabel("Task count", fontsize=11)
    ax.set_title("Authoritative s,c distribution", fontsize=11)
    ax.grid(axis="y", linestyle="--", alpha=0.22)
    ax.legend(frameon=False, fontsize=8)
    ax.tick_params(axis="both", labelsize=10)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#D1D5DB")

    max_count = max(s_counts + c_counts) if s_counts or c_counts else 0
    if max_count > 0:
        max_idx = (s_counts + c_counts).index(max_count) % len(levels)
        ax.annotate(
            f"max={max_count}",
            (x[max_idx], max_count),
            textcoords="offset points",
            xytext=(0, 6),
            ha="center",
        )

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300)
    key_points = {"max_count": max_count, "levels": [f"{lvl:.2f}" for lvl in levels]}
    print(json.dumps(key_points, ensure_ascii=True))
    return output_path


def _derive_soc_code(input_csv: Path) -> str:
    match = re.search(r"task_dna_([^_]+)\.csv", input_csv.name)
    return match.group(1) if match else "unknown"


def _paths_for_soc(soc_code: str) -> Dict[str, Path]:
    return {
        "output_csv": Path(f"data/processed/task_dna_{soc_code}_authoritative_sc.csv"),
        "anomaly_md": Path(f"data/processed/task_dna_{soc_code}_authoritative_anomaly_report.md"),
        "summary_json": Path(f"data/processed/task_dna_{soc_code}_authoritative_summary.json"),
        "summary_xml": Path(f"data/processed/task_dna_{soc_code}_authoritative_summary.xml"),
        "fig_path": Path(f"figures/task_dna_{soc_code}_authoritative_sc_distribution.pdf"),
    }


def run_pipeline(input_csv: Path) -> None:
    assert input_csv.exists(), f"Missing input file: {input_csv}"
    soc_code = _derive_soc_code(input_csv)
    outputs = _paths_for_soc(soc_code)
    rows = load_csv(input_csv)
    dimensions = build_dimension_profiles()
    backend = get_backend_from_env()
    model_name = get_model_name_from_env()

    updated, dim_counts, anomalies, w_stats, fuzzy_available = relabel_task_rows(
        rows, dimensions, backend, model_name
    )
    write_sources_md(SOURCES_MD)
    write_csv(outputs["output_csv"], updated)
    write_anomaly_report(outputs["anomaly_md"], anomalies)
    write_summary_json(
        outputs["summary_json"],
        updated,
        dim_counts,
        anomalies,
        w_stats,
        backend,
        model_name,
        fuzzy_available,
        outputs["output_csv"],
        input_csv,
    )
    summary = json.loads(outputs["summary_json"].read_text(encoding="utf-8"))
    write_summary_xml(outputs["summary_xml"], summary)
    plot_distribution(updated, outputs["fig_path"])


def _dummy_data_demo() -> None:
    dummy_rows = [
        {
            "task_id": "T1",
            "task_text": "Develop and implement new software features.",
            "IM": "4.0",
            "FR": "5.0",
            "w": "0.6",
            "s": "0.50",
            "c": "0.50",
            "evidence_note": "",
        },
        {
            "task_id": "T2",
            "task_text": "Prepare reports and coordinate user training.",
            "IM": "3.0",
            "FR": "3.0",
            "w": "0.4",
            "s": "0.50",
            "c": "0.50",
            "evidence_note": "",
        },
    ]
    dimensions = build_dimension_profiles()
    backend = "hash"
    model_name = DEFAULT_MODEL_NAME
    updated, dim_counts, anomalies, w_stats, fuzzy_available = relabel_task_rows(
        dummy_rows, dimensions, backend, model_name
    )
    demo_summary = {
        "rows": len(updated),
        "dim_counts": dim_counts,
        "low_confidence_count": len(anomalies),
        "weight_stats": w_stats,
        "fuzzy_available": fuzzy_available,
    }
    print(json.dumps(demo_summary, ensure_ascii=True))
    for row in updated:
        print(
            {
                "task_id": row["task_id"],
                "s": row["s"],
                "c": row["c"],
                "evidence_note": row["evidence_note"],
            }
        )


if __name__ == "__main__":
    _dummy_data_demo()
    parser = ArgumentParser()
    parser.add_argument("--input", default=str(INPUT_CSV))
    args = parser.parse_args()
    input_csv = Path(args.input)
    if input_csv.exists():
        run_pipeline(input_csv)
    else:
        print(f"Input CSV not found: {input_csv}")
