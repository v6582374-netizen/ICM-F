#!/usr/bin/env python3
"""
Aggregate diagnostics for authoritative s,c relabel output.
Inputs: data/processed/task_dna_{soc}_authoritative_sc.csv
Outputs: data/processed/task_dna_{soc}_authoritative_agg.json
"""
from __future__ import annotations

from argparse import ArgumentParser
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd


INPUT_CSV = Path("data/processed/task_dna_15-1252_authoritative_sc.csv")
SIM_THRESHOLD = 0.35


@dataclass(frozen=True)
class EvidenceInfo:
    dims: List[str]
    weights: Optional[Dict[str, float]]
    sim_top: Optional[float]


def parse_evidence_note(note: str) -> EvidenceInfo:
    dims_match = re.search(r"dims=([^;]+);", note)
    dims = dims_match.group(1).split(",") if dims_match else []

    weights_match = re.search(r"weights=\[([^\]]+)\];", note)
    weights: Optional[Dict[str, float]] = None
    if weights_match:
        weights = {}
        for pair in weights_match.group(1).split(","):
            dim, val = pair.split(":")
            weights[dim] = float(val)

    sim_match = re.search(r"sim=\[([^\]]+)\];", note)
    sim_top = None
    if sim_match:
        pairs = sim_match.group(1).split(",")
        if pairs:
            _, val = pairs[0].split(":")
            sim_top = float(val)

    return EvidenceInfo(dims=dims, weights=weights, sim_top=sim_top)


def weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    total = sum(weights)
    return sum(v * w for v, w in zip(values, weights)) / total if total else 0.0


def weighted_var(values: Sequence[float], weights: Sequence[float], mean: float) -> float:
    total = sum(weights)
    if total == 0:
        return 0.0
    return sum(w * (v - mean) ** 2 for v, w in zip(values, weights)) / total


def to_hist(
    values: Sequence[float],
    weights: Sequence[float],
    levels: Sequence[float],
) -> Dict[str, float]:
    hist = {f"{level:.2f}": 0.0 for level in levels}
    for v, w in zip(values, weights):
        key = f"{v:.2f}"
        if key in hist:
            hist[key] += w
    return {k: round(v, 6) for k, v in hist.items()}


def aggregate_task_dna(input_csv: Path, output_json: Path) -> Dict[str, object]:
    df = pd.read_csv(input_csv)
    weights = df["w"].astype(float).tolist()
    s_vals = df["s"].astype(float).tolist()
    c_vals = df["c"].astype(float).tolist()
    if "mu_task" not in df.columns:
        raise ValueError("Missing required column: mu_task")
    mu_task_vals = df["mu_task"].astype(float).tolist()

    alpha = weighted_mean(s_vals, weights)
    beta = weighted_mean(c_vals, weights)
    mu_occ = beta - alpha
    mu_occ_from_task = sum(w * m for w, m in zip(weights, mu_task_vals))
    mu_task_from_sc = [c - s for c, s in zip(c_vals, s_vals)]

    var_s = weighted_var(s_vals, weights, alpha)
    var_c = weighted_var(c_vals, weights, beta)

    hist_levels = [0.25, 0.50, 0.75]
    hist_s = to_hist(s_vals, weights, hist_levels)
    hist_c = to_hist(c_vals, weights, hist_levels)
    hist_mu_task = to_hist(mu_task_vals, weights, [-0.50, -0.25, 0.00, 0.25, 0.50])

    dim_mass = {f"D{i}": 0.0 for i in range(1, 11)}
    low_conf = []
    for _, row in df.iterrows():
        evidence = parse_evidence_note(str(row["evidence_note"]))
        w = float(row["w"])
        if evidence.weights:
            for dim, share in evidence.weights.items():
                dim_mass[dim] = dim_mass.get(dim, 0.0) + w * share
        else:
            for dim in evidence.dims:
                dim_mass[dim] = dim_mass.get(dim, 0.0) + w

        if evidence.sim_top is not None and evidence.sim_top < SIM_THRESHOLD:
            low_conf.append(
                {
                    "task_id": str(row["task_id"]),
                    "w": round(w, 6),
                    "dims": ",".join(evidence.dims),
                    "reason": f"low_sim:{evidence.sim_top:.2f}<{SIM_THRESHOLD:.2f}",
                }
            )

    dim_mass = {k: round(v, 6) for k, v in dim_mass.items()}

    df["alpha_contrib"] = df["w"].astype(float) * df["s"].astype(float)
    df["beta_contrib"] = df["w"].astype(float) * df["c"].astype(float)
    top_alpha = (
        df.sort_values("alpha_contrib", ascending=False)
        .head(5)
        .apply(
            lambda r: {
                "task_id": str(r["task_id"]),
                "w": round(float(r["w"]), 6),
                "s": round(float(r["s"]), 2),
                "w*s": round(float(r["alpha_contrib"]), 6),
                "dims": parse_evidence_note(str(r["evidence_note"])).dims,
            },
            axis=1,
        )
        .tolist()
    )
    top_beta = (
        df.sort_values("beta_contrib", ascending=False)
        .head(5)
        .apply(
            lambda r: {
                "task_id": str(r["task_id"]),
                "w": round(float(r["w"]), 6),
                "c": round(float(r["c"]), 2),
                "w*c": round(float(r["beta_contrib"]), 6),
                "dims": parse_evidence_note(str(r["evidence_note"])).dims,
            },
            axis=1,
        )
        .tolist()
    )

    consistency_check = {
        "mu_occ_vs_beta_minus_alpha": round(mu_occ - (beta - alpha), 12),
        "mu_occ_vs_sum_w_mu_task": round(mu_occ - mu_occ_from_task, 12),
        "mu_task_vs_c_minus_s_max_abs": round(
            max(abs(a - b) for a, b in zip(mu_task_vals, mu_task_from_sc))
            if mu_task_vals
            else 0.0,
            12,
        ),
    }

    payload = {
        "schema_version": "taskfirst_mu_v1",
        "alpha": round(alpha, 6),
        "beta": round(beta, 6),
        "mu_occ": round(mu_occ, 6),
        "mu_definition_occ": "mu_occ = beta - alpha",
        "mu_definition_task": "mu_task = c - s",
        "consistency_check": consistency_check,
        "weighted_var_s": round(var_s, 6),
        "weighted_var_c": round(var_c, 6),
        "weighted_hist_s": hist_s,
        "weighted_hist_c": hist_c,
        "weighted_hist_mu_task": hist_mu_task,
        "weight_mass_by_dim": dim_mass,
        "top5_alpha_contrib": top_alpha,
        "top5_beta_contrib": top_beta,
        "low_confidence_tasks": low_conf,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _dummy_data_demo() -> None:
    demo = {
        "task_id": ["T1", "T2"],
        "task_text": ["Build features", "Prepare reports"],
        "IM": [4.0, 3.0],
        "FR": [5.0, 3.0],
        "w": [0.6, 0.4],
        "s": [0.75, 0.5],
        "c": [0.75, 0.75],
        "evidence_note": [
            "dims=D1;sim=[D1:0.60,D2:0.20,D5:0.10];s=0.75;c=0.75;sources=S1|S2",
            "dims=D6;sim=[D6:0.50,D5:0.30,D1:0.20];s=0.50;c=0.75;sources=S3",
        ],
    }
    df = pd.DataFrame(demo)
    temp_path = Path("data/processed/_temp_authoritative_demo.csv")
    df.to_csv(temp_path, index=False)
    aggregate_task_dna(temp_path, Path("data/processed/_temp_authoritative_demo.json"))
    temp_path.unlink(missing_ok=True)
    Path("data/processed/_temp_authoritative_demo.json").unlink(missing_ok=True)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--input", default=str(INPUT_CSV))
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    input_csv = Path(args.input)
    if not args.output:
        match = re.search(r"task_dna_([^_]+)_authoritative_sc\.csv", input_csv.name)
        soc_code = match.group(1) if match else "unknown"
        output_json = Path(f"data/processed/task_dna_{soc_code}_authoritative_agg.json")
    else:
        output_json = Path(args.output)

    if input_csv.exists():
        aggregate_task_dna(input_csv, output_json)
    else:
        print(f"Missing input: {input_csv}")
