#!/usr/bin/env python3
"""
O-variants sensitivity analysis for curriculum pruning.
This script recomputes employability contributions under different O variants
while keeping humanistic and AI-overlap axes fixed.
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
FIGURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "figures"))

ONET_DIR = os.path.join(RAW_DIR, "onet", "db_30_1_text")
TASK_STATEMENTS = os.path.join(ONET_DIR, "Task Statements.txt")
TASK_RATINGS = os.path.join(ONET_DIR, "Task Ratings.txt")
RELATED_OCCUPATIONS = os.path.join(ONET_DIR, "Related Occupations.txt")

TOP_N_TASKS = 20


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    task_text: str
    im: float | None
    fr: float | None


def read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def read_tsv_rows(path: str) -> Iterable[Dict[str, str]]:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            yield row


def assert_columns(rows: Iterable[Dict[str, str]], required: List[str], label: str) -> None:
    for row in rows:
        missing = [col for col in required if col not in row]
        assert not missing, f"{label} missing columns: {missing}"
        break


def normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = "".join(ch if ch.isalnum() or ch in {" ", "-"} else " " for ch in text)
    return " ".join(text.split())


def tokenize(text: str) -> List[str]:
    return [tok for tok in normalize_text(text).split(" ") if tok]


def build_tfidf_vectors(texts: List[str]) -> Tuple[List[Dict[str, float]], Dict[str, float]]:
    docs_tokens = [tokenize(t) for t in texts]
    df = {}
    for tokens in docs_tokens:
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1
    n_docs = len(texts)
    idf = {term: math.log((n_docs + 1) / (freq + 1)) + 1.0 for term, freq in df.items()}
    vectors = []
    for tokens in docs_tokens:
        tf = {}
        for term in tokens:
            tf[term] = tf.get(term, 0.0) + 1.0
        if not tokens:
            vectors.append({})
            continue
        max_tf = max(tf.values())
        vec = {}
        for term, freq in tf.items():
            vec[term] = (freq / max_tf) * idf.get(term, 0.0)
        vectors.append(vec)
    return vectors, idf


def cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    dot = 0.0
    for term, val in vec_a.items():
        dot += val * vec_b.get(term, 0.0)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_similarity_matrix(course_texts: List[str], task_texts: List[str]) -> List[List[float]]:
    vectors, _ = build_tfidf_vectors(course_texts + task_texts)
    course_vecs = vectors[:len(course_texts)]
    task_vecs = vectors[len(course_texts):]
    matrix = []
    for c_vec in course_vecs:
        row = [cosine_similarity(c_vec, t_vec) for t_vec in task_vecs]
        max_val = max(row) if row else 0.0
        if max_val > 0.0:
            row = [val / max_val for val in row]
        matrix.append(row)
    return matrix


def course_text(course: dict) -> str:
    parts = [
        course.get("title") or "",
        course.get("description") or "",
        course.get("course_code") or "",
    ]
    return " ".join(p for p in parts if p).strip()


def load_programs() -> dict:
    programs_path = os.path.join(RAW_DIR, "curricula", "programs.json")
    payload = read_json(programs_path)
    assert "programs" in payload, "Missing programs in programs.json"
    return payload


def load_courses(program_id: str) -> List[dict]:
    file_map = {
        "mrsd_cmu": "mrsd_courses.json",
        "uti_diesel": "uti_diesel_courses.json",
        "generations_court_reporting": "generations_court_reporting_courses.json",
    }
    path = os.path.join(RAW_DIR, "curricula", file_map[program_id])
    payload = read_json(path)
    assert payload["program_id"] == program_id
    courses = payload["courses"]
    for course in courses:
        assert "course_code" in course and "title" in course and "description" in course
    return courses


def load_course_metrics_v2(program_id: str) -> dict:
    path = os.path.join(PROCESSED_DIR, f"course_metrics_{program_id}_v2.json")
    payload = read_json(path)
    assert payload["program_id"] == program_id
    return payload


def parse_related_occupations() -> Dict[str, List[dict]]:
    rows = list(read_tsv_rows(RELATED_OCCUPATIONS))
    assert_columns(rows, ["O*NET-SOC Code", "Related O*NET-SOC Code", "Relatedness Tier", "Index"], "Related Occupations")
    related_map: Dict[str, List[dict]] = {}
    for row in rows:
        soc = row["O*NET-SOC Code"].strip()
        related = row["Related O*NET-SOC Code"].strip()
        tier = row["Relatedness Tier"].strip()
        idx = int(row["Index"]) if row["Index"].strip() else 0
        related_map.setdefault(soc, []).append({
            "soc": related,
            "tier": tier,
            "index": idx,
        })
    for soc in related_map:
        related_map[soc].sort(key=lambda x: x["index"])
    return related_map


def build_o_variants(base_soc: str, related_map: Dict[str, List[dict]]) -> dict:
    candidates = related_map.get(base_soc, [])
    primary_short = [c["soc"] for c in candidates if c["tier"].startswith("Primary-Short")]
    primary_long = [c["soc"] for c in candidates if c["tier"].startswith("Primary-Long")]
    secondary_short = [c["soc"] for c in candidates if c["tier"].startswith("Secondary-Short")]
    secondary_long = [c["soc"] for c in candidates if c["tier"].startswith("Secondary-Long")]

    medium = [base_soc] + primary_short[:2]
    wide = medium + primary_long[:4]
    if len(wide) < 1 + 2 + 4:
        fillers = secondary_short + secondary_long
        for soc in fillers:
            if soc not in wide:
                wide.append(soc)
            if len(wide) >= 1 + 2 + 4:
                break
    return {
        "O_narrow": [base_soc],
        "O_medium": list(dict.fromkeys(medium)),
        "O_wide": list(dict.fromkeys(wide)),
    }


def load_task_data_for_socs(socs: List[str]) -> Tuple[Dict[str, List[TaskRecord]], Dict[str, Dict[str, Dict[str, List[Tuple[int, float]]]]]]:
    target = set(socs)
    tasks_by_soc: Dict[str, List[TaskRecord]] = {soc: [] for soc in target}
    ratings_by_soc: Dict[str, Dict[str, Dict[str, List[Tuple[int, float]]]]] = {soc: {} for soc in target}

    statement_rows = read_tsv_rows(TASK_STATEMENTS)
    assert_columns(statement_rows, ["O*NET-SOC Code", "Task ID", "Task"], "Task Statements")
    for row in read_tsv_rows(TASK_STATEMENTS):
        soc = row["O*NET-SOC Code"].strip()
        if soc not in target:
            continue
        tasks_by_soc[soc].append(TaskRecord(
            task_id=row["Task ID"].strip(),
            task_text=row["Task"].strip(),
            im=None,
            fr=None,
        ))

    rating_rows = read_tsv_rows(TASK_RATINGS)
    assert_columns(rating_rows, ["O*NET-SOC Code", "Task ID", "Scale ID", "Data Value"], "Task Ratings")
    for row in read_tsv_rows(TASK_RATINGS):
        soc = row["O*NET-SOC Code"].strip()
        if soc not in target:
            continue
        scale_id = row["Scale ID"].strip()
        if scale_id not in {"IM", "FT"}:
            continue
        task_id = row["Task ID"].strip()
        ratings_by_soc[soc].setdefault(task_id, {}).setdefault(scale_id, [])
        if scale_id == "IM":
            try:
                value = float(row["Data Value"])
            except ValueError:
                continue
            ratings_by_soc[soc][task_id][scale_id].append((0, value))
        else:
            try:
                category = int(row["Category"])
                value = float(row["Data Value"])
            except ValueError:
                continue
            ratings_by_soc[soc][task_id][scale_id].append((category, value))
    return tasks_by_soc, ratings_by_soc


def compute_fr_from_ft(ft_rows: List[Tuple[int, float]]) -> float | None:
    if not ft_rows:
        return None
    total = sum(v for _, v in ft_rows)
    if total <= 0:
        return None
    return sum(cat * v for cat, v in ft_rows) / total


def merge_tasks_with_ratings(tasks: List[TaskRecord], ratings: Dict[str, Dict[str, List[Tuple[int, float]]]]) -> List[TaskRecord]:
    merged = []
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


def compute_task_weights(records: List[TaskRecord]) -> List[Tuple[TaskRecord, float]]:
    bases = []
    for r in records:
        if r.im is None and r.fr is None:
            bases.append(0.0)
        elif r.fr is None:
            bases.append(r.im or 0.0)
        elif r.im is None:
            bases.append(0.0)
        else:
            bases.append(r.im * r.fr)
    total = sum(bases) if sum(bases) > 0 else 1.0
    weighted = list(zip(records, [b / total for b in bases]))
    weighted.sort(key=lambda x: x[1], reverse=True)
    return weighted[: min(TOP_N_TASKS, len(weighted))]


def select_tasks(records: List[TaskRecord], ratings: Dict[str, Dict[str, List[Tuple[int, float]]]]) -> List[dict]:
    merged = merge_tasks_with_ratings(records, ratings)
    weighted = compute_task_weights(merged)
    selected_weight_sum = sum(w for _, w in weighted)
    if selected_weight_sum > 0:
        normalized = [(rec, w / selected_weight_sum) for rec, w in weighted]
    else:
        normalized = [(rec, 1.0 / max(len(weighted), 1)) for rec, _ in weighted]
    return [
        {"task_id": rec.task_id, "task_text": rec.task_text, "weight": w}
        for rec, w in normalized
    ]


def compute_coverages(sim_matrix: List[List[float]]) -> Tuple[List[float], List[Tuple[float, float, int]]]:
    if not sim_matrix:
        return [], []
    task_count = len(sim_matrix[0])
    top_stats = []
    for j in range(task_count):
        top1_val, top1_idx, top2_val = 0.0, -1, 0.0
        for i, row in enumerate(sim_matrix):
            val = row[j]
            if val > top1_val:
                top2_val = top1_val
                top1_val = val
                top1_idx = i
            elif val > top2_val:
                top2_val = val
        top_stats.append((top1_val, top2_val, top1_idx))
    c_all = [t[0] for t in top_stats]
    return c_all, top_stats


def compute_employability_contribs(
    courses: List[dict],
    soc_tasks: Dict[str, List[dict]],
) -> Dict[str, float]:
    course_texts = [course_text(c) for c in courses]
    course_count = len(courses)
    per_course_employability = [0.0 for _ in range(course_count)]
    employability_all = 0.0

    if not soc_tasks:
        return {c["course_code"]: 0.0 for c in courses}

    soc_weight = 1.0 / len(soc_tasks)
    for tasks in soc_tasks.values():
        task_texts = [t["task_text"] for t in tasks]
        weights = [t["weight"] for t in tasks]
        sim_matrix = build_similarity_matrix(course_texts, task_texts)
        c_all, top_stats = compute_coverages(sim_matrix)
        employability_all += soc_weight * sum(w * c for w, c in zip(weights, c_all))
        for i in range(course_count):
            without = 0.0
            for (top1, top2, top_idx), w in zip(top_stats, weights):
                val = top2 if top_idx == i else top1
                without += w * val
            per_course_employability[i] += soc_weight * without

    contribs = {}
    for i, course in enumerate(courses):
        contribs[course["course_code"]] = employability_all - per_course_employability[i]
    return contribs


def weighted_quantile(values: List[float], weights: List[float], q: float) -> float:
    assert 0.0 <= q <= 1.0, "Quantile must be in [0, 1]"
    if not values:
        return 0.0
    pairs = sorted(zip(values, weights), key=lambda x: x[0])
    total = sum(weights) if sum(weights) > 0 else 1.0
    target = q * total
    cum = 0.0
    for value, w in pairs:
        cum += w
        if cum >= target:
            return value
    return pairs[-1][0]


def compute_thresholds(
    delta_e: List[float],
    h_vals: List[float],
    a_vals: List[float],
    a_strict_vals: List[float],
    credits: List[float],
) -> dict:
    all_numeric = all(isinstance(c, (int, float)) for c in credits)
    if all_numeric:
        weights = credits
        weighting_rule = "credit_weighted_empirical_quantile"
    else:
        weights = [1.0 for _ in credits]
        weighting_rule = "uniform_empirical_quantile"
    return {
        "e_low": weighted_quantile(delta_e, weights, 0.25),
        "h_low": weighted_quantile(h_vals, weights, 0.25),
        "a_high": weighted_quantile(a_vals, weights, 0.75),
        "a_strict_high": weighted_quantile(a_strict_vals, weights, 0.90),
        "weighting_rule": weighting_rule,
    }


def assign_label(delta_e: float, h_val: float, a_val: float, a_strict_val: float, thresholds: dict) -> str:
    if (
        delta_e < thresholds["e_low"]
        and h_val < thresholds["h_low"]
        and a_strict_val > thresholds["a_strict_high"]
    ):
        return "PRUNE"
    if a_val > thresholds["a_high"] and a_strict_val <= thresholds["a_strict_high"]:
        return "TRANSFORM"
    return "KEEP"


def compare_position(value: float, threshold: float) -> str:
    if value > threshold:
        return "above"
    if value < threshold:
        return "below"
    return "equal"


def compute_label_stability(per_variant_labels: List[Dict[str, str]]) -> Dict[str, dict]:
    codes = per_variant_labels[0].keys() if per_variant_labels else []
    out = {}
    for code in codes:
        labels = [labels_map.get(code, "KEEP") for labels_map in per_variant_labels]
        mode_label = max(set(labels), key=labels.count) if labels else "KEEP"
        stab = sum(1 for label in labels if label == mode_label) / max(len(labels), 1)
        out[code] = {
            "stability": stab,
            "mode_label": mode_label,
        }
    return out


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(len(a | b), 1)


def compute_transform_jaccard(per_variant_labels: Dict[str, Dict[str, str]]) -> dict:
    variants = list(per_variant_labels.keys())
    jaccard_mat = {}
    for i, v1 in enumerate(variants):
        for v2 in variants[i:]:
            t1 = {k for k, v in per_variant_labels[v1].items() if v == "TRANSFORM"}
            t2 = {k for k, v in per_variant_labels[v2].items() if v == "TRANSFORM"}
            jaccard_mat[f"{v1}__{v2}"] = jaccard(t1, t2)
    return jaccard_mat


def kendall_tau(x: List[float], y: List[float]) -> float:
    assert len(x) == len(y)
    n = len(x)
    if n < 2:
        return 1.0
    concordant = 0
    discordant = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            dx = x[i] - x[j]
            dy = y[i] - y[j]
            if dx == 0 or dy == 0:
                continue
            if dx * dy > 0:
                concordant += 1
            else:
                discordant += 1
    denom = concordant + discordant
    return (concordant - discordant) / denom if denom > 0 else 0.0


def compute_rank_stability(per_variant_delta_e: Dict[str, Dict[str, float]]) -> dict:
    variants = list(per_variant_delta_e.keys())
    tau_mat = {}
    for i, v1 in enumerate(variants):
        for v2 in variants[i:]:
            keys = list(per_variant_delta_e[v1].keys())
            x = [per_variant_delta_e[v1][k] for k in keys]
            y = [per_variant_delta_e[v2][k] for k in keys]
            tau_mat[f"{v1}__{v2}"] = kendall_tau(x, y)
    return tau_mat


def ensure_dirs() -> None:
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(FIGURES_DIR, exist_ok=True)


def load_o_variants_config() -> dict:
    config_path = os.path.join(PROCESSED_DIR, "o_variants_related_occupations.json")
    return read_json(config_path)


def run_analysis() -> dict:
    ensure_dirs()
    programs_payload = load_programs()
    variants_map = load_o_variants_config()
    programs = programs_payload["programs"]

    all_socs = set()
    for program in programs:
        program_id = program["program_id"]
        variants = variants_map[program_id]["variants"]
        for socs in variants.values():
            all_socs.update(socs)

    tasks_by_soc, ratings_by_soc = load_task_data_for_socs(sorted(all_socs))

    per_program_summary = []
    for program in programs:
        program_id = program["program_id"]
        courses = load_courses(program_id)
        metrics_payload = load_course_metrics_v2(program_id)
        course_metrics = {c["course_code"]: c for c in metrics_payload["courses"]}
        h_vals = []
        a_vals = []
        a_strict_vals = []
        credits = []
        for course in courses:
            m = course_metrics.get(course["course_code"], {})
            h_val = float(m.get("civic", 0.0)) + float(m.get("agency", 0.0)) + float(m.get("wellbeing", 0.0)) + float(m.get("lifelong", 0.0))
            h_vals.append(h_val)
            a_vals.append(float(m.get("ai_overlap_v2", 0.0)))
            a_strict_vals.append(float(m.get("ai_overlap_v2_strict", 0.0)))
            credits.append(m.get("credits", course.get("credits", 1.0)))

        variant_labels = {}
        variant_delta_e = {}
        variant_thresholds = {}
        for variant_name, soc_list in variants_map[program_id]["variants"].items():
            soc_tasks = {}
            for soc in soc_list:
                records = tasks_by_soc.get(soc, [])
                ratings = ratings_by_soc.get(soc, {})
                if not records:
                    continue
                soc_tasks[soc] = select_tasks(records, ratings)
            contribs = compute_employability_contribs(courses, soc_tasks)
            delta_e = [contribs[c["course_code"]] for c in courses]
            thresholds = compute_thresholds(delta_e, h_vals, a_vals, a_strict_vals, credits)
            variant_thresholds[variant_name] = thresholds

            per_course = []
            labels_map = {}
            for idx, course in enumerate(courses):
                code = course["course_code"]
                label = assign_label(delta_e[idx], h_vals[idx], a_vals[idx], a_strict_vals[idx], thresholds)
                labels_map[code] = label
                per_course.append({
                    "course_code": code,
                    "title": course.get("title"),
                    "delta_e": delta_e[idx],
                    "h_m": h_vals[idx],
                    "a_m": a_vals[idx],
                    "a_strict_m": a_strict_vals[idx],
                    "label_keep_transform_prune": label,
                })

            out_payload = {
                "program_id": program_id,
                "variant": variant_name,
                "o_variant": soc_list,
                "thresholds": thresholds,
                "courses": per_course,
                "prune_add": labels_map,
            }
            out_path = os.path.join(PROCESSED_DIR, f"prune_add_{program_id}_v2_O{variant_name.replace('O_', '')}.json")
            write_json(out_path, out_payload)

            variant_labels[variant_name] = labels_map
            variant_delta_e[variant_name] = {c["course_code"]: contribs[c["course_code"]] for c in courses}

        stability = compute_label_stability(list(variant_labels.values()))
        jaccard_mat = compute_transform_jaccard(variant_labels)
        tau_mat = compute_rank_stability(variant_delta_e)
        boundary_courses = []
        for course in courses:
            code = course["course_code"]
            labels = {v: variant_labels[v].get(code, "KEEP") for v in variant_labels}
            if len(set(labels.values())) <= 1:
                continue
            detail = {"course_code": code, "labels": labels, "variants": {}}
            for vname, thresholds in variant_thresholds.items():
                idx = next(i for i, c in enumerate(courses) if c["course_code"] == code)
                delta_e = variant_delta_e[vname][code]
                h_val = h_vals[idx]
                a_val = a_vals[idx]
                a_strict_val = a_strict_vals[idx]
                detail["variants"][vname] = {
                    "delta_e": delta_e,
                    "h_m": h_val,
                    "a_m": a_val,
                    "a_strict_m": a_strict_val,
                    "thresholds": thresholds,
                    "positions": {
                        "delta_e_vs_e_low": compare_position(delta_e, thresholds["e_low"]),
                        "h_vs_h_low": compare_position(h_val, thresholds["h_low"]),
                        "a_vs_a_high": compare_position(a_val, thresholds["a_high"]),
                        "a_strict_vs_a_strict_high": compare_position(a_strict_val, thresholds["a_strict_high"]),
                    },
                }
            boundary_courses.append(detail)

        robustness = {
            "program_id": program_id,
            "o_variants": variants_map[program_id]["variants"],
            "labels_variant": variant_labels,
            "per_course_stability": stability,
            "transform_jaccard": jaccard_mat,
            "employability_rank_stability": tau_mat,
            "boundary_courses": boundary_courses,
        }
        robustness_path = os.path.join(PROCESSED_DIR, f"robustness_summary_{program_id}_O_variants_final.json")
        write_json(robustness_path, robustness)

        per_program_summary.append({
            "program_id": program_id,
            "o_variants_path": robustness_path,
            "variant_outputs": list(variant_labels.keys()),
        })

    summary = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "programs": per_program_summary,
        "o_variants_config": os.path.join(PROCESSED_DIR, "o_variants_related_occupations.json"),
    }
    return summary


def build_summary_xml(summary: dict) -> str:
    lines = ["<o_variants_sensitivity_summary>"]
    lines.append(f"  <timestamp_utc>{summary['timestamp_utc']}</timestamp_utc>")
    lines.append(f"  <o_variants_config>{summary['o_variants_config']}</o_variants_config>")
    lines.append("  <programs>")
    for item in summary["programs"]:
        lines.append(f"    <program id=\"{item['program_id']}\">")
        lines.append(f"      <robustness>{item['o_variants_path']}</robustness>")
        lines.append("    </program>")
    lines.append("  </programs>")
    lines.append("</o_variants_sensitivity_summary>")
    return "\n".join(lines)


def run_demo() -> dict:
    courses = [
        {"course_code": "C1", "title": "Intro Robotics", "description": "robot motion planning"},
        {"course_code": "C2", "title": "Ethics", "description": "public safety ethics"},
    ]
    soc_tasks = {
        "00-0000.00": [
            {"task_id": "T1", "task_text": "robot motion planning", "weight": 0.7},
            {"task_id": "T2", "task_text": "mechanical design", "weight": 0.3},
        ]
    }
    contribs = compute_employability_contribs(courses, soc_tasks)
    demo = {"contribs": contribs}
    print(json.dumps(demo, ensure_ascii=False, indent=2))
    return demo


def main() -> None:
    if "--demo" in sys.argv:
        run_demo()
        return
    summary = run_analysis()
    xml_path = os.path.join(PROCESSED_DIR, "o_variants_sensitivity_summary.xml")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(build_summary_xml(summary))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
