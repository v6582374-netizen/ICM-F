import tempfile
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")

from code.reallocation_metrics_plots import plot_rankflip_and_contribution  # noqa: E402


def _fake_rankflip_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"task_id": "t1", "Delta_p": 0.03, "rank_w": 1, "rank_p_end": 3, "rank_flip": 2},
            {"task_id": "t2", "Delta_p": -0.02, "rank_w": 4, "rank_p_end": 1, "rank_flip": 3},
            {"task_id": "t3", "Delta_p": 0.01, "rank_w": 2, "rank_p_end": 2, "rank_flip": 0},
        ]
    )


def _fake_contrib_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"task_id": "t2", "r": 0.06},
            {"task_id": "t1", "r": 0.04},
            {"task_id": "t3", "r": 0.02},
        ]
    )


def test_plot_rankflip_and_contribution_writes_pdf() -> None:
    labels = {"t1": "Task 1", "t2": "Task 2", "t3": "Task 3"}
    rankflip = _fake_rankflip_df()
    contrib = _fake_contrib_df()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "rankflip_contrib.pdf"
        plot_rankflip_and_contribution(rankflip, contrib, labels, output_path)
        assert output_path.exists()
        assert output_path.stat().st_size > 0
