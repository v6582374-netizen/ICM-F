#!/usr/bin/env python3
"""
Recompute AI-overlap v2 using GenAI 9-dimension scores and backfill JSON outputs.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Dict, List, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from occupational_dna.curriculum_pruner import (
    DATA_DIR,
    PROCESSED_DIR,
    read_json,
    write_json,
    load_programs,
    load_courses,
    load_tasks_and_weights,
    build_similarity_matrix,
    compute_course_metrics
)


DELIVERABLES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "deliverables_adoption_package", "curriculum_pruner_jsons")
)


def preview_tasks(tasks: List[dict], sample_size: int = 3) -> List[dict]:
    return tasks[:sample_size]


def compute_program_metrics(program: dict, base_year: float, scenario: str, eta: float) -> Tuple[List[dict], float]:
    courses = load_courses(program["program_id"])
    horizon_year = base_year + program["duration_years"]
    tasks, d_j = load_tasks_and_weights(program["soc"], scenario, eta, horizon_year)
    _ = preview_tasks(tasks)
    similarity_matrix = build_similarity_matrix(courses, tasks)
    metrics, _ = compute_course_metrics(courses, tasks, d_j, similarity_matrix)
    return metrics, horizon_year


def coerce_float(value) -> Tuple[bool, float]:
    if isinstance(value, (int, float)):
        return True, float(value)
    return False, 0.0


def compute_program_means(courses: List[dict]) -> Tuple[float, float, str]:
    ai_values = []
    ai_strict_values = []
    credit_values = []
    all_credits_numeric = True
    for course in courses:
        ai_values.append(float(course.get("ai_overlap_v2", 0.0)))
        ai_strict_values.append(float(course.get("ai_overlap_v2_strict", 0.0)))
        ok, credit = coerce_float(course.get("credits"))
        if ok:
            credit_values.append(credit)
        else:
            all_credits_numeric = False
    if not ai_values:
        return 0.0, 0.0, "none"
    if all_credits_numeric and credit_values:
        weight_sum = sum(credit_values)
        if weight_sum == 0.0:
            return sum(ai_values) / len(ai_values), sum(ai_strict_values) / len(ai_strict_values), "uniform"
        mean_v2 = sum(v * w for v, w in zip(ai_values, credit_values)) / weight_sum
        mean_strict = sum(v * w for v, w in zip(ai_strict_values, credit_values)) / weight_sum
        return mean_v2, mean_strict, "credit"
    return sum(ai_values) / len(ai_values), sum(ai_strict_values) / len(ai_strict_values), "uniform"


def weighted_quantile(values: List[float], weights: List[float], quantile: float) -> float:
    if not values:
        return 0.0
    if len(values) != len(weights):
        raise ValueError("Values and weights length mismatch.")
    pairs = sorted(zip(values, weights), key=lambda x: x[0])
    total_weight = sum(w for _, w in pairs)
    if total_weight == 0.0:
        return pairs[-1][0]
    target = quantile * total_weight
    cumulative = 0.0
    for value, weight in pairs:
        cumulative += weight
        if cumulative >= target:
            return value
    return pairs[-1][0]


def compute_thresholds_per_program(courses: List[dict], quantiles: dict) -> dict:
    e_vals = [float(c.get("employability_contrib", 0.0)) for c in courses]
    h_vals = [compute_humanistic_score(c) for c in courses]
    a_vals = [float(c.get("ai_overlap_v2", 0.0)) for c in courses]
    a_strict_vals = [float(c.get("ai_overlap_v2_strict", 0.0)) for c in courses]

    credit_ok = []
    for c in courses:
        ok, credit = coerce_float(c.get("credits"))
        if ok:
            credit_ok.append(credit)
        else:
            credit_ok.append(0.0)
    all_credits_numeric = all(coerce_float(c.get("credits"))[0] for c in courses)
    if all_credits_numeric:
        weights = credit_ok
        weighting = "credit_weighted_empirical_quantile"
    else:
        weights = [1.0 for _ in courses]
        weighting = "uniform_empirical_quantile"

    return {
        "e_low": weighted_quantile(e_vals, weights, quantiles["e_low"]),
        "h_low": weighted_quantile(h_vals, weights, quantiles["h_low"]),
        "a_high": weighted_quantile(a_vals, weights, quantiles["a_high"]),
        "a_strict_high": weighted_quantile(a_strict_vals, weights, quantiles["a_strict_high"]),
        "weighting_rule": weighting
    }


def update_course_payload(payload: dict, metrics: List[dict]) -> dict:
    metric_map = {m["course_code"]: m for m in metrics}
    for course in payload.get("courses", []):
        code = course.get("course_code")
        if code in metric_map:
            course["ai_overlap_v2"] = metric_map[code]["ai_overlap_v2"]
            course["ai_overlap_v2_strict"] = metric_map[code]["ai_overlap_v2_strict"]
            course["w_mk"] = metric_map[code]["w_mk"]
    return payload


def compute_humanistic_score(course: dict) -> float:
    return float(course.get("civic", 0.0)) + float(course.get("agency", 0.0)) + float(course.get("wellbeing", 0.0)) + float(course.get("lifelong", 0.0))


def label_course(course: dict, thresholds: dict) -> str:
    employability = float(course.get("employability_contrib", 0.0))
    humanistic = compute_humanistic_score(course)
    ai_overlap = float(course.get("ai_overlap_v2", 0.0))
    ai_overlap_strict = float(course.get("ai_overlap_v2_strict", 0.0))
    if (
        employability < thresholds["e_low"]
        and humanistic < thresholds["h_low"]
        and ai_overlap_strict > thresholds["a_strict_high"]
    ):
        return "PRUNE"
    if ai_overlap > thresholds["a_high"] and ai_overlap_strict <= thresholds["a_strict_high"]:
        return "TRANSFORM"
    return "KEEP"


def build_prune_add_v2(payload: dict, thresholds: dict) -> dict:
    labels = {}
    prune_list = []
    transform_list = []
    keep_list = []
    for course in payload.get("courses", []):
        code = course.get("course_code")
        label = label_course(course, thresholds)
        course["label_keep_transform_prune"] = label
        labels[code] = label
        if label == "PRUNE":
            prune_list.append(code)
        elif label == "TRANSFORM":
            transform_list.append(code)
        else:
            keep_list.append(code)
    return {
        "program_id": payload["program_id"],
        "horizon_year": payload["horizon_year"],
        "scenario": payload["scenario"],
        "eta": payload["eta"],
        "thresholds_v2": thresholds,
        "labels": labels,
        "prune_list": prune_list,
        "transform_list": transform_list,
        "keep_list": keep_list
    }


def write_summary(
    program_id: str,
    horizon_year: float,
    scenario: str,
    eta: float,
    courses: List[dict],
    output_dir: str
) -> Tuple[str, dict]:
    mean_v2, mean_strict, weighting = compute_program_means(courses)
    payload = {
        "program_id": program_id,
        "horizon_year": horizon_year,
        "scenario": scenario,
        "eta": eta,
        "course_count": len(courses),
        "ai_overlap_v2_mean": round(mean_v2, 6),
        "ai_overlap_v2_strict_mean": round(mean_strict, 6),
        "weighting": weighting
    }
    path = os.path.join(output_dir, f"ai_overlap_v2_summary_{program_id}.json")
    write_json(path, payload)
    return path, payload


def build_summary_xml(summaries: List[dict]) -> str:
    lines = ["<ai_overlap_v2_summary>"]
    lines.append(f"  <timestamp_utc>{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}</timestamp_utc>")
    lines.append("  <programs>")
    for item in summaries:
        lines.append(f"    <program id=\"{item['program_id']}\">")
        lines.append(f"      <course_count>{item['course_count']}</course_count>")
        lines.append(f"      <ai_overlap_v2_mean>{item['ai_overlap_v2_mean']}</ai_overlap_v2_mean>")
        lines.append(f"      <ai_overlap_v2_strict_mean>{item['ai_overlap_v2_strict_mean']}</ai_overlap_v2_strict_mean>")
        lines.append(f"      <weighting>{item['weighting']}</weighting>")
        lines.append("    </program>")
    lines.append("  </programs>")
    lines.append("</ai_overlap_v2_summary>")
    return "\n".join(lines)


def run_recompute(quantiles: dict) -> Dict[str, object]:
    scenario = "Baseline"
    eta = 1.0
    programs_payload = load_programs()

    outputs = []
    summaries = []
    for program in programs_payload["programs"]:
        metrics, horizon_year = compute_program_metrics(program, programs_payload["base_year"], scenario, eta)
        program_id = program["program_id"]
        per_course_path = os.path.join(PROCESSED_DIR, f"course_metrics_{program_id}.json")
        payload = read_json(per_course_path)
        payload = update_course_payload(payload, metrics)
        write_json(per_course_path, payload)

        summary_path, summary_payload = write_summary(
            program_id, horizon_year, scenario, eta, payload["courses"], PROCESSED_DIR
        )
        summaries.append(summary_payload)

        per_course_v2_path = os.path.join(PROCESSED_DIR, f"course_metrics_{program_id}_v2.json")
        thresholds = compute_thresholds_per_program(payload["courses"], quantiles)
        prune_add_v2 = build_prune_add_v2(payload, thresholds)
        write_json(per_course_v2_path, payload)
        prune_add_v2_path = os.path.join(PROCESSED_DIR, f"prune_add_{program_id}_v2.json")
        write_json(prune_add_v2_path, prune_add_v2)

        if os.path.isdir(DELIVERABLES_DIR):
            deliverable_path = os.path.join(DELIVERABLES_DIR, f"course_metrics_{program_id}.json")
            if os.path.exists(deliverable_path):
                write_json(deliverable_path, payload)
            write_summary(program_id, horizon_year, scenario, eta, payload["courses"], DELIVERABLES_DIR)
            deliverable_v2 = os.path.join(DELIVERABLES_DIR, f"course_metrics_{program_id}_v2.json")
            deliverable_prune_v2 = os.path.join(DELIVERABLES_DIR, f"prune_add_{program_id}_v2.json")
            write_json(deliverable_prune_v2, prune_add_v2)
            write_json(deliverable_v2, payload)

        outputs.append({
            "program_id": program_id,
            "course_metrics": per_course_path,
            "summary": summary_path,
            "course_metrics_v2": per_course_v2_path,
            "prune_add_v2": prune_add_v2_path
        })
    xml_text = build_summary_xml(summaries)
    xml_path = os.path.join(PROCESSED_DIR, "ai_overlap_v2_summary.xml")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml_text)
    if os.path.isdir(DELIVERABLES_DIR):
        deliverable_xml = os.path.join(DELIVERABLES_DIR, "ai_overlap_v2_summary.xml")
        with open(deliverable_xml, "w", encoding="utf-8") as f:
            f.write(xml_text)
    return {"outputs": outputs, "summary_xml": xml_path}


def run_demo() -> None:
    demo_courses = [
        {"course_code": "DEMO-1", "title": "Robotics", "description": "robotics control", "credits": 3},
        {"course_code": "DEMO-2", "title": "Diagnostics", "description": "diagnostic testing", "credits": 3}
    ]
    demo_tasks = [
        {"task_id": "T1", "task_text": "robotic control", "s": "0.3", "c": "0.7", "dims": "D3"},
        {"task_id": "T2", "task_text": "diagnose systems", "s": "0.6", "c": "0.4", "dims": "D1"}
    ]
    demo_weights = {"T1": 0.6, "T2": 0.4}
    sim = build_similarity_matrix(demo_courses, demo_tasks)
    metrics, _ = compute_course_metrics(demo_courses, demo_tasks, demo_weights, sim)
    print(json.dumps({"demo_metrics": metrics}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if "--demo" in os.sys.argv:
        run_demo()
    else:
        args = os.sys.argv
        if "--e-low-q" not in args or "--h-low-q" not in args or "--a-high-q" not in args or "--a-strict-high-q" not in args:
            raise SystemExit(
                "Missing quantiles. Provide --e-low-q, --h-low-q, --a-high-q, --a-strict-high-q."
            )
        quantiles = {
            "e_low": float(args[args.index("--e-low-q") + 1]),
            "h_low": float(args[args.index("--h-low-q") + 1]),
            "a_high": float(args[args.index("--a-high-q") + 1]),
            "a_strict_high": float(args[args.index("--a-strict-high-q") + 1])
        }
        result = run_recompute(quantiles)
        print(json.dumps(result, ensure_ascii=False, indent=2))
