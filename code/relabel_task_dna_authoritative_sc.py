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

import numpy as np

try:
    from rapidfuzz.fuzz import token_set_ratio
except Exception:  # pragma: no cover - optional dependency
    token_set_ratio = None


INPUT_CSV = Path("data/processed/task_dna_15-1252.csv")
SOURCES_MD = Path("data/processed/authoritative_sc_sources_domainpack.md")

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
ALLOWED_LEVELS = (0.25, 0.5, 0.75)
SIM_THRESHOLD = 0.35
TWO_DIM_THRESHOLD = 0.45
TWO_DIM_GAP = 0.08


AUTHORITATIVE_SOURCES = [
    (
        "O1 O*NET Summary - Robotics Engineers (17-2199.08): "
        "https://www.onetonline.org/link/summary/17-2199.08",
        ["O1"],
    ),
    (
        "O2 O*NET Summary - First-Line Supervisors of Mechanics, Installers, and Repairers (49-1011.00): "
        "https://www.onetonline.org/link/summary/49-1011.00",
        ["O2"],
    ),
    (
        "O3 O*NET Summary - Court Reporters and Simultaneous Captioners (27-3092.00): "
        "https://www.onetonline.org/link/summary/27-3092.00",
        ["O3"],
    ),
    (
        "R1 ISO 10218-1: Robotics — Safety requirements Part 1: Industrial robots: "
        "https://www.iso.org/standard/73933.html",
        ["R1"],
    ),
    (
        "R2 ISO 10218-2: Robotics — Safety requirements Part 2: Industrial robot applications and robot cells: "
        "https://www.iso.org/standard/73934.html",
        ["R2"],
    ),
    (
        "R3 NIST IR 8093 - Tools for Robotics in SME Workcells (Calibration & Registration): "
        "https://www.nist.gov/publications/tools-robotics-sme-workcells-challenges-and-approaches-calibration-and-registration",
        ["R3"],
    ),
    (
        "S1 OSHA 29 CFR 1910.212 - General requirements for all machines (machine guarding): "
        "https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.212",
        ["S1"],
    ),
    (
        "C1 NCRA - What is Court Reporting?: https://www.ncra.org/home/the-profession/Court-Reporting",
        ["C1"],
    ),
    (
        "C2 NCRA - Code of Professional Ethics (COPE) Guidelines: "
        "https://www.ncra.org/home/the-profession/NCRA-Code-of-Professional-Ethics/cope---guidelines-for-professional-practice",
        ["C2"],
    ),
    (
        "C3 NCRA - Certified Realtime Captioner (CRC): "
        "https://www.ncra.org/certification/NCRA-Certifications/certified-realtime-captioner",
        ["C3"],
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
            name="Systems Integration / Controls Engineering",
            description="System integration, controls design, robotics programming, and integration testing.",
            exemplar_phrases=(
                "integrate robotic systems",
                "configure control systems",
                "robot cell integration",
            ),
            default_s=0.5,
            default_c=0.75,
            sources=("O1", "R2", "R3"),
        ),
        DimensionProfile(
            dim_id="D2",
            name="Field Commissioning / Troubleshooting",
            description="On-site testing, calibration, diagnostics, maintenance, and fault isolation.",
            exemplar_phrases=(
                "commission equipment",
                "diagnose failures",
                "calibrate sensors",
            ),
            default_s=0.25,
            default_c=0.5,
            sources=("O1", "R3"),
        ),
        DimensionProfile(
            dim_id="D3",
            name="Automation Software / PLC Programming",
            description="Programming automation scripts, PLC logic, HMI interfaces, and control code.",
            exemplar_phrases=(
                "program PLC logic",
                "develop automation scripts",
                "configure HMI",
            ),
            default_s=0.75,
            default_c=0.75,
            sources=("O1", "R3"),
        ),
        DimensionProfile(
            dim_id="D4",
            name="Safety / Regulatory Compliance",
            description="Safety procedures, risk assessments, and regulatory compliance for operations.",
            exemplar_phrases=(
                "enforce safety procedures",
                "risk assessments",
                "regulatory compliance",
            ),
            default_s=0.25,
            default_c=0.5,
            sources=("S1", "R1", "R2"),
        ),
        DimensionProfile(
            dim_id="D5",
            name="Scheduling / Resource Coordination",
            description="Shift planning, workload scheduling, and resource allocation.",
            exemplar_phrases=(
                "schedule staff",
                "allocate resources",
                "plan shifts",
            ),
            default_s=0.5,
            default_c=0.5,
            sources=("O2",),
        ),
        DimensionProfile(
            dim_id="D6",
            name="Supervision / Communication / Training",
            description="Supervise teams, coordinate work, train staff, and communicate updates.",
            exemplar_phrases=(
                "supervise workers",
                "train staff",
                "coordinate work",
            ),
            default_s=0.25,
            default_c=0.75,
            sources=("O2",),
        ),
        DimensionProfile(
            dim_id="D7",
            name="Documentation / QA / Reporting",
            description="Maintain records, produce reports, quality checks, and documentation.",
            exemplar_phrases=(
                "maintain records",
                "prepare reports",
                "quality assurance",
            ),
            default_s=0.5,
            default_c=0.75,
            sources=("O2", "O3"),
        ),
        DimensionProfile(
            dim_id="D8",
            name="Realtime Transcription / ASR Editing",
            description="Realtime transcription, captioning, and correction of ASR output.",
            exemplar_phrases=(
                "real-time transcription",
                "captioning services",
                "edit ASR output",
            ),
            default_s=0.75,
            default_c=0.5,
            sources=("O3", "C1", "C3"),
        ),
        DimensionProfile(
            dim_id="D9",
            name="Legal Procedure / Court Protocol",
            description="Legal terminology, courtroom procedures, confidentiality, and official record-keeping.",
            exemplar_phrases=(
                "courtroom procedures",
                "legal terminology",
                "official record",
            ),
            default_s=0.25,
            default_c=0.5,
            sources=("O3", "C2"),
        ),
        DimensionProfile(
            dim_id="D10",
            name="Client / Stakeholder Service",
            description="Interact with judges, attorneys, clients, and stakeholders; service coordination.",
            exemplar_phrases=(
                "liaise with clients",
                "coordinate with stakeholders",
                "service coordination",
            ),
            default_s=0.5,
            default_c=0.5,
            sources=("O2", "O3"),
        ),
    ]


def write_sources_md(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Authoritative Sources Domain Pack",
        "",
        "## Occupational Base Sources (O*NET)",
        " - " + AUTHORITATIVE_SOURCES[0][0],
        " - " + AUTHORITATIVE_SOURCES[1][0],
        " - " + AUTHORITATIVE_SOURCES[2][0],
        "",
        "## Robotics / Systems Integration / Safety",
        " - " + AUTHORITATIVE_SOURCES[3][0],
        " - " + AUTHORITATIVE_SOURCES[4][0],
        " - " + AUTHORITATIVE_SOURCES[5][0],
        " - " + AUTHORITATIVE_SOURCES[6][0],
        "",
        "## Court Reporting / Realtime Captioning / Ethics",
        " - " + AUTHORITATIVE_SOURCES[7][0],
        " - " + AUTHORITATIVE_SOURCES[8][0],
        " - " + AUTHORITATIVE_SOURCES[9][0],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _hash_embedding(texts: Sequence[str], dim: int = 128) -> np.ndarray:
    vectors = np.zeros((len(texts), dim), dtype=np.float32)
    for i, text in enumerate(texts):
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            idx = int(digest, 16) % dim
            vectors[i, idx] += 1.0
    return _normalize_vectors(vectors)


def _normalize_vectors(vectors: np.ndarray) -> np.ndarray:
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
        try:
            model = _get_sentence_model(model_name)
        except Exception as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError(
                "sentence-transformers not available; install it or set SC_EMBEDDING_BACKEND=hash"
            ) from exc
        embeddings = model.encode(list(texts), normalize_embeddings=True)
        return np.asarray(embeddings, dtype=np.float32), "sentence_transformers"
    if backend == "tfidf":
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


def cosine_similarity_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
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


def assign_sc(
    dims: Sequence[DimensionProfile],
    weights: Sequence[float],
) -> Tuple[float, float, float, float]:
    raw_s = sum(d.default_s * w for d, w in zip(dims, weights))
    raw_c = sum(d.default_c * w for d, w in zip(dims, weights))
    return snap_to_levels(raw_s), snap_to_levels(raw_c), raw_s, raw_c


def compute_mu_task(c_val: float, s_val: float) -> str:
    mu_task = Decimal(str(c_val)) - Decimal(str(s_val))
    return f"{mu_task.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def build_evidence_note(
    dims: Sequence[DimensionProfile],
    similarity_triplet: Sequence[Tuple[str, float]],
    weights: Optional[Sequence[float]],
    final_s: float,
    final_c: float,
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
        emb_scores = sim_matrix[idx].tolist()
        score_values, fuzzy_ok = compute_similarity_scores(task_text, dim_texts, emb_scores)
        if not fuzzy_ok:
            fuzzy_available = False
        selected_idx, weights, used_two = select_dimensions(dim_ids, score_values)
        selected_dims = [dimensions[i] for i in selected_idx]
        final_s, final_c, raw_s, raw_c = assign_sc(selected_dims, weights)

        top3 = sorted(
            [(dim_ids[i], score_values[i]) for i in range(len(dim_ids))],
            key=lambda x: x[1],
            reverse=True,
        )[:3]
        evidence_note = build_evidence_note(
            selected_dims, top3, weights if used_two else None, final_s, final_c
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

    fig, ax = plt.subplots(figsize=(8.2, 5.2), dpi=300)
    width = 0.35
    x = np.arange(len(levels))
    ax.bar(x - width / 2, s_counts, width, label="s counts", color="#A7BFD9")
    ax.bar(x + width / 2, c_counts, width, label="c counts", color="#C9B59A")
    ax.plot(x, s_counts, color="#6B7280", marker="o", linestyle="--", label="s trend")
    ax.plot(x, c_counts, color="#8B7A63", marker="o", linestyle="--", label="c trend")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{lvl:.2f}" for lvl in levels])
    ax.set_xlabel("s / c levels")
    ax.set_ylabel("Task count")
    ax.set_title("Authoritative s,c distribution")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.legend()

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
