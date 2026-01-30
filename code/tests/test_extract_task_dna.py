import unittest

from code.extract_task_dna import compute_fr_from_ft, compute_weights, keyword_scoring, TaskRecord


class TestExtractTaskDna(unittest.TestCase):
    def test_compute_fr_from_ft(self) -> None:
        ft_rows = [(1, 10.0), (2, 20.0), (3, 70.0)]
        fr = compute_fr_from_ft(ft_rows)
        self.assertIsNotNone(fr)
        self.assertAlmostEqual(fr, (1 * 10 + 2 * 20 + 3 * 70) / 100.0)

    def test_keyword_scoring(self) -> None:
        s_val, c_val, note = keyword_scoring("Write code and debug security issues.")
        self.assertGreaterEqual(s_val, 0.8)
        self.assertGreaterEqual(c_val, 0.8)
        self.assertIn("keywords=", note)

    def test_compute_weights(self) -> None:
        records = [
            TaskRecord("T1", "Write code.", 4.0, 5.0),
            TaskRecord("T2", "Communicate requirements.", 2.0, 2.0),
        ]
        weighted = compute_weights(records)
        weights = [w for _, w in weighted]
        self.assertAlmostEqual(sum(weights), 1.0)


if __name__ == "__main__":
    unittest.main()
