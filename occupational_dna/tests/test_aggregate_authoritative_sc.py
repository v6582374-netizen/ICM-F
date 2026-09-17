import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from occupational_dna.aggregate_authoritative_sc import aggregate_task_dna


class TestAuthoritativeScAggregate(unittest.TestCase):
    def test_mu_occ_consistency_two_ways(self) -> None:
        df = pd.DataFrame(
            {
                "task_id": ["T1", "T2"],
                "task_text": ["Build features", "Prepare reports"],
                "IM": [4.0, 3.0],
                "FR": [5.0, 3.0],
                "w": [0.6, 0.4],
                "s": [0.25, 0.50],
                "c": [0.75, 0.50],
                "mu_task": [0.50, 0.00],
                "evidence_note": ["dims=D1;sim=[D1:0.60];sources=S1", "dims=D6;sim=[D6:0.50];sources=S2"],
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            input_csv = Path(tmpdir) / "authoritative_sc.csv"
            output_json = Path(tmpdir) / "authoritative_agg.json"
            df.to_csv(input_csv, index=False)
            payload = aggregate_task_dna(input_csv, output_json)
            disk_payload = json.loads(output_json.read_text(encoding="utf-8"))

        self.assertEqual(payload, disk_payload)
        self.assertIn("mu_occ", payload)
        self.assertNotIn("mu", payload)
        self.assertIn("consistency_check", payload)
        self.assertAlmostEqual(
            payload["consistency_check"]["mu_occ_vs_beta_minus_alpha"], 0.0, places=9
        )
        self.assertAlmostEqual(
            payload["consistency_check"]["mu_occ_vs_sum_w_mu_task"], 0.0, places=9
        )
        self.assertAlmostEqual(
            payload["consistency_check"]["mu_task_vs_c_minus_s_max_abs"], 0.0, places=9
        )
        self.assertIn("weighted_hist_mu_task", payload)


if __name__ == "__main__":
    unittest.main()
