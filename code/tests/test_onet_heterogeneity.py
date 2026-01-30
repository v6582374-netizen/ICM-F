import unittest
import pandas as pd

from code.onet_heterogeneity import aggregate_axes, normalize_to_0_100, score_title_matches


class TestOnetHeterogeneity(unittest.TestCase):
    def test_normalize_to_0_100(self):
        self.assertAlmostEqual(normalize_to_0_100(3.0, (1.0, 5.0)), 50.0)
        self.assertAlmostEqual(normalize_to_0_100(1.0, (1.0, 5.0)), 0.0)
        self.assertAlmostEqual(normalize_to_0_100(5.0, (1.0, 5.0)), 100.0)

    def test_aggregate_axes(self):
        df = pd.DataFrame(
            [
                {
                    "occupation_code": "11-1111.00",
                    "descriptor_key": "a",
                    "axis": "digit",
                    "norm_all": 0.2,
                },
                {
                    "occupation_code": "11-1111.00",
                    "descriptor_key": "b",
                    "axis": "digit",
                    "norm_all": 0.6,
                },
                {
                    "occupation_code": "11-1111.00",
                    "descriptor_key": "c",
                    "axis": "physical",
                    "norm_all": 0.4,
                },
                {
                    "occupation_code": "11-1111.00",
                    "descriptor_key": "d",
                    "axis": "physical",
                    "norm_all": 0.8,
                },
            ]
        )
        weights = {"a": 1.0, "b": 3.0, "c": 1.0, "d": 1.0}
        agg = aggregate_axes(df, weights, "norm_all")
        digit = agg[agg["axis"] == "digit"].iloc[0]
        self.assertAlmostEqual(digit["norm_all_equal"], 0.4)
        self.assertAlmostEqual(digit["norm_all_weighted"], 0.5)

    def test_score_title_matches(self):
        occupation_df = pd.DataFrame(
            [{"O*NET-SOC Code": "15-1252.00", "Title": "Software Developers"}]
        )
        alternate_df = pd.DataFrame(
            [{"O*NET-SOC Code": "15-1252.00", "Alternate Title": "Software Engineer"}]
        )
        reported_df = pd.DataFrame(
            [{"O*NET-SOC Code": "15-1252.00", "Reported Job Title": "Software Developer"}]
        )
        code, evidence = score_title_matches(
            "Software Developer / Software Engineer",
            occupation_df,
            alternate_df,
            reported_df,
        )
        self.assertEqual(code, "15-1252.00")
        self.assertFalse(evidence.empty)


if __name__ == "__main__":
    unittest.main()
