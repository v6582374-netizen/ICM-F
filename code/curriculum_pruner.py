import csv
import json
import math
import os
import re
import sys
import time
from typing import Dict, List, Tuple


DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
RAW_DIR = os.path.join(DATA_DIR, "raw", "curricula")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
FIGURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "figures"))

DIMENSION_PARAMS = {
    "D1": {"Mk": 0.90, "sk": 0.50, "ck": 0.85, "rho": 0.35},
    "D2": {"Mk": 0.80, "sk": 0.30, "ck": 0.50, "rho": 0.20},
    "D3": {"Mk": 0.67, "sk": 0.90, "ck": 0.70, "rho": -0.20},
    "D4": {"Mk": 0.25, "sk": 0.10, "ck": 0.50, "rho": 0.40},
    "D5": {"Mk": 0.65, "sk": 0.60, "ck": 0.50, "rho": -0.10},
    "D6": {"Mk": 0.70, "sk": 0.30, "ck": 0.75, "rho": 0.45},
    "D7": {"Mk": 0.80, "sk": 0.68, "ck": 0.68, "rho": 0.00},
    "D8": {"Mk": 0.95, "sk": 0.90, "ck": 0.50, "rho": -0.40},
    "D9": {"Mk": 0.90, "sk": 0.30, "ck": 0.30, "rho": 0.00}
}
DIMENSION_IDS = tuple(DIMENSION_PARAMS.keys())


def read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def read_csv(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> List[str]:
    text = normalize_text(text)
    tokens = [t for t in text.split(" ") if t]
    return tokens


def parse_dims(raw: str) -> List[str]:
    if not raw:
        return []
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    return [p for p in parts if p in DIMENSION_PARAMS]


def compute_dimension_weights(
    tasks: List[dict],
    d_vec: List[float],
    coverage_row: List[float]
) -> Dict[str, float]:
    assert len(tasks) == len(d_vec) == len(coverage_row)
    dim_mass = {dim: 0.0 for dim in DIMENSION_IDS}
    uniform_share = 1.0 / len(DIMENSION_IDS)
    for idx, task in enumerate(tasks):
        task_weight = coverage_row[idx] * d_vec[idx]
        if task_weight == 0.0:
            continue
        dims = parse_dims(task.get("dims", ""))
        if dims:
            share = 1.0 / len(dims)
            for dim in dims:
                dim_mass[dim] += task_weight * share
        else:
            for dim in dim_mass:
                dim_mass[dim] += task_weight * uniform_share
    total = sum(dim_mass.values())
    if total > 0.0:
        return {dim: dim_mass[dim] / total for dim in dim_mass}
    return {dim: uniform_share for dim in DIMENSION_IDS}


def compute_ai_overlap_v2(dim_weights: Dict[str, float], strict_gate: bool) -> float:
    total = 0.0
    for dim, params in DIMENSION_PARAMS.items():
        rho = params["rho"]
        gate = rho < 0.0 if strict_gate else rho <= 0.0
        if not gate:
            continue
        a_k = params["Mk"] * params["sk"]
        total += dim_weights.get(dim, 0.0) * a_k
    return total


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


def course_text(course: dict) -> str:
    parts = [
        course.get("title") or "",
        course.get("description") or "",
        course.get("course_code") or ""
    ]
    return " ".join(p for p in parts if p).strip()


def task_text(task: dict) -> str:
    return task.get("task_text", "").strip()


def load_programs() -> dict:
    programs_path = os.path.join(RAW_DIR, "programs.json")
    return read_json(programs_path)


def load_courses(program_id: str) -> List[dict]:
    file_map = {
        "mrsd_cmu": "mrsd_courses.json",
        "uti_diesel": "uti_diesel_courses.json",
        "generations_court_reporting": "generations_court_reporting_courses.json"
    }
    path = os.path.join(RAW_DIR, file_map[program_id])
    payload = read_json(path)
    assert payload["program_id"] == program_id
    courses = payload["courses"]
    for course in courses:
        assert "course_code" in course and "title" in course and "description" in course
        assert "credits" in course
    return courses


def load_tasks_and_weights(soc: str, scenario: str, eta: float, horizon_year: float) -> Tuple[List[dict], Dict[str, float]]:
    # Data Source: O*NET Task DNA processed outputs [onet2025database]
    task_path = os.path.join(PROCESSED_DIR, f"task_dna_{soc}_authoritative_sc.csv")
    tasks = read_csv(task_path)
    for row in tasks:
        assert "task_id" in row and "task_text" in row
    # Data Source: Task share forecasts (Q2 outputs) [onet2025database]
    p_share_path = os.path.join(PROCESSED_DIR, f"p_share_{soc}_{scenario}_eta{eta}.csv")
    p_rows = read_csv(p_share_path)

    times = sorted(set(float(row["t"]) for row in p_rows))
    target_t = min(times, key=lambda t: abs(t - horizon_year))
    d_j = {}
    for row in p_rows:
        if float(row["t"]) == target_t:
            d_j[row["task_id"]] = float(row["p_ij"])
    assert d_j, "No task weights found for horizon year."
    return tasks, d_j


def build_similarity_matrix(courses: List[dict], tasks: List[dict]) -> List[List[float]]:
    course_texts = [course_text(c) for c in courses]
    task_texts = [task_text(t) for t in tasks]
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


def compute_humanistic_scores(course: dict, lexicons: dict) -> dict:
    text = normalize_text(course_text(course))
    tokens = set(tokenize(text))
    scores = {}
    for dim, keywords in lexicons.items():
        hits = sum(1 for kw in keywords if kw in tokens)
        scores[dim] = hits / max(len(keywords), 1)
    return scores


def normalize_scores(score_list: List[dict], keys: List[str]) -> List[dict]:
    for key in keys:
        values = [s[key] for s in score_list]
        max_val = max(values) if values else 0.0
        if max_val > 0.0:
            for s in score_list:
                s[key] = s[key] / max_val
    return score_list


def compute_course_metrics(
    courses: List[dict],
    tasks: List[dict],
    d_j: Dict[str, float],
    similarity_matrix: List[List[float]]
) -> Tuple[List[dict], List[List[float]]]:
    task_index = {t["task_id"]: idx for idx, t in enumerate(tasks)}
    s_map = {t["task_id"]: float(t["s"]) for t in tasks if t.get("s") not in (None, "")}
    c_map = {t["task_id"]: float(t["c"]) for t in tasks if t.get("c") not in (None, "")}

    coverage = similarity_matrix
    task_ids = [t["task_id"] for t in tasks]
    d_vec = [d_j.get(task_id, 0.0) for task_id in task_ids]

    employability_all = 0.0
    for j in range(len(task_ids)):
        total = sum(coverage[m][j] for m in range(len(courses)))
        employability_all += d_vec[j] * min(1.0, total)

    metrics = []
    lexicons = {
        "civic": ["ethics", "public", "civic", "law", "compliance", "responsibility"],
        "agency": ["decision", "leadership", "management", "planning", "strategy", "autonomy"],
        "wellbeing": ["safety", "health", "wellbeing", "risk", "care", "quality"],
        "lifelong": ["learning", "training", "skill", "development", "professional", "continuous"]
    }

    for i, course in enumerate(courses):
        weights = [coverage[i][j] * d_vec[j] for j in range(len(task_ids))]
        weight_sum = sum(weights)
        replaceability = 0.0
        if weight_sum > 0.0:
            replaceability = sum(weights[j] * s_map.get(task_ids[j], 0.0) for j in range(len(task_ids))) / weight_sum
        redundancy = 0.0
        if len(courses) > 1:
            sims = []
            for k in range(len(courses)):
                if k == i:
                    continue
                sims.append(cosine_similarity(
                    {str(j): coverage[i][j] for j in range(len(task_ids))},
                    {str(j): coverage[k][j] for j in range(len(task_ids))}
                ))
            redundancy = sum(sims) / max(len(sims), 1)

        employability_without = 0.0
        for j in range(len(task_ids)):
            total = sum(coverage[m][j] for m in range(len(courses)) if m != i)
            employability_without += d_vec[j] * min(1.0, total)
        employability_contrib = employability_all - employability_without

        dim_weights = compute_dimension_weights(tasks, d_vec, coverage[i])
        ai_overlap_v2 = compute_ai_overlap_v2(dim_weights, strict_gate=False)
        ai_overlap_v2_strict = compute_ai_overlap_v2(dim_weights, strict_gate=True)
        human_scores = compute_humanistic_scores(course, lexicons)
        metrics.append({
            "course_code": course.get("course_code"),
            "title": course.get("title"),
            "credits": course.get("credits"),
            "replaceability": replaceability,
            "redundancy": redundancy,
            "employability_contrib": employability_contrib,
            "ai_overlap_v2": ai_overlap_v2,
            "ai_overlap_v2_strict": ai_overlap_v2_strict,
            "w_mk": dim_weights,
            "civic": human_scores["civic"],
            "agency": human_scores["agency"],
            "wellbeing": human_scores["wellbeing"],
            "lifelong": human_scores["lifelong"]
        })

    metrics = normalize_scores(metrics, ["replaceability", "redundancy", "employability_contrib", "civic", "agency", "wellbeing", "lifelong"])
    return metrics, coverage


def prune_add_decision(metrics: List[dict], coverage: List[List[float]], thresholds: dict) -> dict:
    prune_list = []
    merge_pairs = []
    for m in metrics:
        if m["employability_contrib"] <= thresholds["employability_floor"] and m["redundancy"] >= thresholds["redundancy_floor"]:
            prune_list.append(m["course_code"])

    for i in range(len(metrics)):
        for k in range(i + 1, len(metrics)):
            sim = cosine_similarity(
                {str(j): coverage[i][j] for j in range(len(coverage[i]))},
                {str(j): coverage[k][j] for j in range(len(coverage[k]))}
            )
            if sim >= thresholds["merge_similarity"]:
                merge_pairs.append({
                    "course_a": metrics[i]["course_code"],
                    "course_b": metrics[k]["course_code"],
                    "coverage_similarity": sim
                })

    credits_freed = 0.0
    for m in metrics:
        if m["course_code"] in prune_list and isinstance(m["credits"], (int, float)):
            credits_freed += float(m["credits"])

    return {
        "prune_list": prune_list,
        "merge_suggestions": merge_pairs,
        "add_budget_credits": credits_freed
    }


def stability_grid(metrics: List[dict], coverage: List[List[float]], grid: dict) -> dict:
    thresholds_list = []
    for e_floor in grid["employability_floor"]:
        for r_floor in grid["redundancy_floor"]:
            thresholds_list.append({
                "employability_floor": e_floor,
                "redundancy_floor": r_floor,
                "merge_similarity": grid["merge_similarity"]
            })

    counts = {m["course_code"]: 0 for m in metrics}
    for th in thresholds_list:
        decision = prune_add_decision(metrics, coverage, th)
        for code in decision["prune_list"]:
            counts[code] += 1

    total = len(thresholds_list)
    stability = {}
    for code, cnt in counts.items():
        stability[code] = {
            "prune_frequency": cnt / max(total, 1)
        }

    stable_prune = [code for code, info in stability.items() if info["prune_frequency"] >= grid["stable_threshold"]]
    return {
        "grid_size": total,
        "stable_prune": stable_prune,
        "stability": stability
    }


def build_summary_xml(summary: dict) -> str:
    lines = ["<curriculum_pruner_summary>"]
    lines.append(f"  <timestamp_utc>{summary['timestamp_utc']}</timestamp_utc>")
    lines.append("  <programs>")
    for item in summary["programs"]:
        lines.append(f"    <program id=\"{item['program_id']}\">")
        lines.append(f"      <courses>{item['course_count']}</courses>")
        lines.append(f"      <pruned>{item['pruned_count']}</pruned>")
        lines.append(f"      <add_budget_credits>{item['add_budget_credits']}</add_budget_credits>")
        lines.append(f"      <outputs>{item['outputs']}</outputs>")
        lines.append("    </program>")
    lines.append("  </programs>")
    lines.append("</curriculum_pruner_summary>")
    return "\n".join(lines)


def ensure_dirs() -> None:
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(FIGURES_DIR, exist_ok=True)


def run_program(program: dict, base_year: float, scenario: str, eta: float) -> Tuple[dict, dict]:
    program_id = program["program_id"]
    courses = load_courses(program_id)
    horizon_year = base_year + program["duration_years"]
    tasks, d_j = load_tasks_and_weights(program["soc"], scenario, eta, horizon_year)
    similarity_matrix = build_similarity_matrix(courses, tasks)
    metrics, coverage = compute_course_metrics(courses, tasks, d_j, similarity_matrix)

    thresholds = {
        "employability_floor": 0.08,
        "redundancy_floor": 0.65,
        "merge_similarity": 0.85
    }
    decision = prune_add_decision(metrics, coverage, thresholds)
    stability = stability_grid(metrics, coverage, {
        "employability_floor": [0.05, 0.08, 0.10],
        "redundancy_floor": [0.60, 0.65, 0.70],
        "merge_similarity": 0.85,
        "stable_threshold": 0.7
    })

    per_course_out = {
        "program_id": program_id,
        "credits_unit": program["credits_unit"],
        "horizon_year": horizon_year,
        "scenario": scenario,
        "eta": eta,
        "courses": metrics
    }
    decision_out = {
        "program_id": program_id,
        "horizon_year": horizon_year,
        "scenario": scenario,
        "eta": eta,
        "thresholds": thresholds,
        "prune_add": decision,
        "stability": stability
    }
    return per_course_out, decision_out


def render_scatter(metrics: List[dict], program_id: str) -> str:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    fig_path = os.path.join(FIGURES_DIR, f"fig_curriculum_pruner_{program_id}.png")
    x = [m["redundancy"] for m in metrics]
    y = [m["employability_contrib"] for m in metrics]
    labels = [m["course_code"] for m in metrics]
    plt.figure(figsize=(7, 5), dpi=300)
    plt.scatter(x, y, alpha=0.8, label="Courses")
    for idx, label in enumerate(labels):
        if idx < 6:
            plt.annotate(label, (x[idx], y[idx]), fontsize=6)
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.xlabel("Redundancy (normalized)")
    plt.ylabel("Employability contribution (normalized)")
    plt.title(f"Curriculum Pruner Diagnostics: {program_id}")
    plt.legend(loc="best", fontsize=7)
    plt.tight_layout()
    plt.savefig(fig_path, dpi=300)
    plt.close()
    return fig_path


def main() -> None:
    ensure_dirs()
    scenario = "Baseline"
    eta = 1.0

    demo_mode = "--demo" in sys.argv
    programs_payload = load_programs()

    summary = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "programs": []
    }

    if demo_mode:
        dummy_program = {
            "program_id": "demo_program",
            "credits_unit": "credits",
            "duration_years": 1.0,
            "base_year": programs_payload["base_year"],
            "soc": "17-2199.08"
        }
        dummy_courses = [
            {
                "course_code": "DEMO-1",
                "title": "Robotics Foundations",
                "description": "Robotics systems, sensing, and control fundamentals.",
                "credits": 3,
                "prerequisites": []
            },
            {
                "course_code": "DEMO-2",
                "title": "Data and Diagnostics",
                "description": "Diagnostic reasoning, data logging, and maintenance workflows.",
                "credits": 3,
                "prerequisites": []
            }
        ]
        dummy_tasks = [
            {"task_id": "T1", "task_text": "Design and test robotic systems", "s": 0.3, "c": 0.7},
            {"task_id": "T2", "task_text": "Diagnose equipment failures", "s": 0.6, "c": 0.4}
        ]
        d_j = {"T1": 0.6, "T2": 0.4}
        similarity_matrix = build_similarity_matrix(dummy_courses, dummy_tasks)
        metrics, coverage = compute_course_metrics(dummy_courses, dummy_tasks, d_j, similarity_matrix)
        thresholds = {
            "employability_floor": 0.08,
            "redundancy_floor": 0.65,
            "merge_similarity": 0.85
        }
        decision = prune_add_decision(metrics, coverage, thresholds)
        stability = stability_grid(metrics, coverage, {
            "employability_floor": [0.05, 0.08, 0.10],
            "redundancy_floor": [0.60, 0.65, 0.70],
            "merge_similarity": 0.85,
            "stable_threshold": 0.7
        })
        per_course_out = {
            "program_id": dummy_program["program_id"],
            "credits_unit": dummy_program["credits_unit"],
            "horizon_year": dummy_program["base_year"] + dummy_program["duration_years"],
            "scenario": scenario,
            "eta": eta,
            "courses": metrics
        }
        decision_out = {
            "program_id": dummy_program["program_id"],
            "horizon_year": dummy_program["base_year"] + dummy_program["duration_years"],
            "scenario": scenario,
            "eta": eta,
            "thresholds": thresholds,
            "prune_add": decision,
            "stability": stability
        }
        print(json.dumps({"demo_per_course": per_course_out, "demo_prune_add": decision_out}, ensure_ascii=False, indent=2))
        return

    for program in programs_payload["programs"]:
        per_course_out, decision_out = run_program(program, programs_payload["base_year"], scenario, eta)
        metrics = per_course_out["courses"]

        per_course_path = os.path.join(PROCESSED_DIR, f"course_metrics_{program['program_id']}.json")
        decision_path = os.path.join(PROCESSED_DIR, f"prune_add_{program['program_id']}.json")
        write_json(per_course_path, per_course_out)
        write_json(decision_path, decision_out)

        fig_path = render_scatter(metrics, program["program_id"])

        summary["programs"].append({
            "program_id": program["program_id"],
            "course_count": len(metrics),
            "pruned_count": len(decision_out["prune_add"]["prune_list"]),
            "add_budget_credits": decision_out["prune_add"]["add_budget_credits"],
            "outputs": ", ".join(p for p in [per_course_path, decision_path, fig_path] if p)
        })

    xml_text = build_summary_xml(summary)
    xml_path = os.path.join(PROCESSED_DIR, "curriculum_pruner_summary.xml")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml_text)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
