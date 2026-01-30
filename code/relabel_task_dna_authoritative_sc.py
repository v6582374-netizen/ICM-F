#!/usr/bin/env python3
"""
Relabel (s, c) for task_dna_15-1252.csv using authoritative capability evidence,
semantic matching, and tiered rubric. No keyword heuristics are used for scoring.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    from rapidfuzz.fuzz import token_set_ratio
except Exception:  # pragma: no cover - optional dependency
    token_set_ratio = None


INPUT_CSV = Path("data/processed/task_dna_15-1252.csv")
OUTPUT_CSV = Path("data/processed/task_dna_15-1252_authoritative_sc.csv")
SOURCES_MD = Path("data/processed/authoritative_sc_sources.md")
ANOMALY_MD = Path("data/processed/task_dna_15-1252_authoritative_anomaly_report.md")
SUMMARY_JSON = Path("data/processed/task_dna_15-1252_authoritative_summary.json")
SUMMARY_XML = Path("data/processed/task_dna_15-1252_authoritative_summary.xml")
FIG_PATH = Path("figures/task_dna_15-1252_authoritative_sc_distribution.pdf")

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
ALLOWED_LEVELS = (0.25, 0.5, 0.75)
SIM_THRESHOLD = 0.35
TWO_DIM_THRESHOLD = 0.45
TWO_DIM_GAP = 0.08


AUTHORITATIVE_SOURCES = [
    (
        "S1 OpenAI GPT-4 Technical Report (HumanEval etc.): https://arxiv.org/pdf/2303.08774.pdf",
        ["S1"],
    ),
    (
        "S2 Anthropic Claude 2 announcement (HumanEval 71.2%): https://www.anthropic.com/news/claude-2",
        ["S2"],
    ),
    (
        "S3 Anthropic Claude 2 Model Card (PDF): https://www-cdn.anthropic.com/bd2a28d2535bfb0494cc8e2a3bf135d2e7523226/Model-Card-Claude-2.pdf",
        ["S3"],
    ),
    (
        "S4 Microsoft Research Debug-gym blog: https://www.microsoft.com/en-us/research/blog/debug-gym-an-environment-for-ai-coding-tools-to-learn-how-to-debug-code-like-programmers/",
        ["S4"],
    ),
    (
        "S5 IBM Research ASTER blog: https://research.ibm.com/blog/aster-llm-unit-testing",
        ["S5"],
    ),
    (
        "S6 IBM Research ASTER publication page: https://research.ibm.com/publications/aster-natural-and-multi-language-unit-test-generation-with-llms",
        ["S6"],
    ),
    (
        "(Optional) OpenAI GPT-4 research page: https://openai.com/index/gpt-4-research/",
        ["S7"],
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
            name="Code Generation / Implementation",
            description="Writing new code, implementing features, producing code artifacts.",
            exemplar_phrases=(
                "implement new features",
                "write source code",
                "create software components",
            ),
            default_s=0.75,
            default_c=0.75,
            sources=("S1", "S2"),
        ),
        DimensionProfile(
            dim_id="D2",
            name="Code Modification / Refactoring",
            description="Modify existing software, adapt to hardware, upgrade interfaces, performance improvements.",
            exemplar_phrases=(
                "modify existing software",
                "refactor modules",
                "optimize performance",
            ),
            default_s=0.5,
            default_c=0.75,
            sources=("S1", "S2"),
        ),
        DimensionProfile(
            dim_id="D3",
            name="Testing / Validation / Documentation-as-code",
            description="Unit tests, validation procedures, generating test scaffolds, test-driven verification.",
            exemplar_phrases=(
                "unit test generation",
                "validation procedures",
                "test harness creation",
            ),
            default_s=0.5,
            default_c=0.75,
            sources=("S5", "S6"),
        ),
        DimensionProfile(
            dim_id="D4",
            name="Debugging / Issue Resolving / Tool-using repair",
            description="Finding root cause, fixing bugs, using debuggers, resolving repo issues.",
            exemplar_phrases=(
                "debug software defects",
                "resolve errors",
                "trace root cause",
            ),
            default_s=0.25,
            default_c=0.5,
            sources=("S4",),
        ),
        DimensionProfile(
            dim_id="D5",
            name="Requirements & Feasibility Analysis",
            description="Analyze user needs, feasibility within cost/time, define standards.",
            exemplar_phrases=(
                "analyze requirements",
                "feasibility assessment",
                "define standards",
            ),
            default_s=0.25,
            default_c=0.5,
            sources=("S1", "S3"),
        ),
        DimensionProfile(
            dim_id="D6",
            name="Communication / Reporting / Coordination / Training",
            description="Prepare reports, confer with stakeholders, coordinate installation, train users, supervision.",
            exemplar_phrases=(
                "prepare reports",
                "coordinate installation",
                "train users",
            ),
            default_s=0.5,
            default_c=0.75,
            sources=("S3",),
        ),
        DimensionProfile(
            dim_id="D7",
            name="Monitoring / Operations",
            description="Monitor equipment/system functioning, ensure conformance with specs.",
            exemplar_phrases=(
                "monitor system performance",
                "ensure conformance",
                "operations monitoring",
            ),
            default_s=0.25,
            default_c=0.5,
            sources=("S4",),
        ),
    ]


def write_sources_md(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [line for line, _ in AUTHORITATIVE_SOURCES]
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")


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

        if top3[0][1] < SIM_THRESHOLD:
            anomalies.append(
                {
                    "task_id": row["task_id"],
                    "task_text": task_text,
                    "top_dim": top3[0][0],
                    "top_score": f"{top3[0][1]:.2f}",
                    "second_dim": top3[1][0],
                    "second_score": f"{top3[1][1]:.2f}",
                }
            )

        for dim in selected_dims:
            dim_counts[dim.dim_id] += 1

        updated_row = dict(row)
        updated_row["s"] = f"{final_s:.2f}"
        updated_row["c"] = f"{final_c:.2f}"
        updated_row["evidence_note"] = evidence_note
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
    lines.append("| task_id | task_text | top_dim | top_score | second_dim | second_score |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for item in anomalies:
        lines.append(
            f"| {item['task_id']} | {item['task_text']} | {item['top_dim']} | "
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
) -> None:
    summary = {
        "input_csv": str(INPUT_CSV),
        "output_csv": str(OUTPUT_CSV),
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
    ax.bar(x - width / 2, s_counts, width, label="s counts", color="#60A5FA")
    ax.bar(x + width / 2, c_counts, width, label="c counts", color="#F59E0B")
    ax.plot(x, s_counts, color="#1D4ED8", marker="o", linestyle="--", label="s trend")
    ax.plot(x, c_counts, color="#B45309", marker="o", linestyle="--", label="c trend")
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


def run_pipeline(input_csv: Path) -> None:
    assert input_csv.exists(), f"Missing input file: {input_csv}"
    rows = load_csv(input_csv)
    dimensions = build_dimension_profiles()
    backend = get_backend_from_env()
    model_name = get_model_name_from_env()

    updated, dim_counts, anomalies, w_stats, fuzzy_available = relabel_task_rows(
        rows, dimensions, backend, model_name
    )
    write_sources_md(SOURCES_MD)
    write_csv(OUTPUT_CSV, updated)
    write_anomaly_report(ANOMALY_MD, anomalies)
    write_summary_json(
        SUMMARY_JSON, updated, dim_counts, anomalies, w_stats, backend, model_name, fuzzy_available
    )
    summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    write_summary_xml(SUMMARY_XML, summary)
    plot_distribution(updated, FIG_PATH)


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
    if INPUT_CSV.exists():
        run_pipeline(INPUT_CSV)
    else:
        print(f"Input CSV not found: {INPUT_CSV}")
