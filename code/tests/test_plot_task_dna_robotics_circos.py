from pathlib import Path

import numpy as np

from code.plot_task_dna_robotics_circos import (
    build_dummy_tasks,
    compute_key_points,
    synthesize_ring_data,
)


def test_synthesize_ring_data_shapes() -> None:
    tasks = build_dummy_tasks()
    rings = synthesize_ring_data(len(tasks), seed=1)
    assert set(rings.keys()) == {"Importance", "Frequency", "Complexity", "Impact"}
    for values in rings.values():
        assert isinstance(values, np.ndarray)
        assert len(values) == len(tasks)
        assert np.all((values >= 0.0) & (values <= 1.0))


def test_compute_key_points() -> None:
    tasks = ["t1", "t2", "t3"]
    values = np.array([0.2, 0.8, 0.5])
    key_points = compute_key_points(tasks, values)
    assert key_points["max"]["task"] == "t2"
    assert key_points["min"]["task"] == "t1"
    assert key_points["mean"] == 0.5
