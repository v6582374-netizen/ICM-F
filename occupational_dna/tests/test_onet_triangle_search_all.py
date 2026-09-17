import unittest
import pandas as pd

from occupational_dna.onet_triangle_search_all import compute_triangle_search, map_domain, soc_major_group


class TestOnetTriangleSearchAll(unittest.TestCase):
    def test_domain_mapping(self):
        self.assertEqual(map_domain("15"), "S")
        self.assertEqual(map_domain("47"), "T")
        self.assertEqual(map_domain("27"), "A")
        self.assertEqual(map_domain("99"), "Unknown")

    def test_triangle_search_area(self):
        s_df = pd.DataFrame(
            [
                {
                    "O*NET-SOC Code": "11-0000.00",
                    "Title": "S Job",
                    "domain": "S",
                    "digit": 0.0,
                    "physical": 0.0,
                    "iprisk": 0.0,
                }
            ]
        )
        t_df = pd.DataFrame(
            [
                {
                    "O*NET-SOC Code": "15-0000.00",
                    "Title": "T Job",
                    "domain": "T",
                    "digit": 1.0,
                    "physical": 0.0,
                    "iprisk": 0.0,
                }
            ]
        )
        a_df = pd.DataFrame(
            [
                {
                    "O*NET-SOC Code": "47-0000.00",
                    "Title": "A Job",
                    "domain": "A",
                    "digit": 0.0,
                    "physical": 1.0,
                    "iprisk": 0.0,
                }
            ]
        )
        result = compute_triangle_search(s_df, t_df, a_df)
        self.assertAlmostEqual(result.area, 0.5)
        self.assertEqual(len(result.points), 3)

    def test_soc_major_group(self):
        self.assertEqual(soc_major_group("15-1252.00"), "15")
        self.assertEqual(soc_major_group("47-2111.00"), "47")
        self.assertEqual(soc_major_group(""), "")


if __name__ == "__main__":
    unittest.main()
