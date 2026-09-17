import os
import unittest

from occupational_dna.relabel_task_dna_authoritative_sc import (
    ALLOWED_LEVELS,
    build_dimension_profiles,
    relabel_task_rows,
)


class TestAuthoritativeScRelabel(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["SC_EMBEDDING_BACKEND"] = "hash"

    def tearDown(self) -> None:
        os.environ.pop("SC_EMBEDDING_BACKEND", None)

    def test_relabel_basic_constraints(self) -> None:
        rows = [
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
        updated, _, _, w_stats, _ = relabel_task_rows(
            rows, dimensions, backend="hash", model_name="dummy"
        )
        self.assertAlmostEqual(w_stats["w_sum"], 1.0, places=6)
        for original, row in zip(rows, updated):
            self.assertEqual(original["w"], row["w"])
            self.assertIn(float(row["s"]), ALLOWED_LEVELS)
            self.assertIn(float(row["c"]), ALLOWED_LEVELS)
            self.assertAlmostEqual(
                float(row["mu_task"]),
                float(row["c"]) - float(row["s"]),
                places=6,
            )
            self.assertIn("dims=", row["evidence_note"])
            self.assertIn("sim=[", row["evidence_note"])
            self.assertIn("sources=", row["evidence_note"])
            self.assertTrue(row["dims"])
            self.assertTrue(row["sim"])
            self.assertTrue(row["sources"])


if __name__ == "__main__":
    unittest.main()
