#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
import numpy as np

from occupational_dna.adoption_task_share_forecast import compute_q_p


class TestAdoptionTaskShareForecast(unittest.TestCase):
    def test_sum_to_one(self):
        weights = np.array([0.4, 0.3, 0.3])
        mu_task = np.array([0.2, -0.1, 0.0])
        a_values = np.array([0.0, 0.5, 1.0])
        p = compute_q_p(weights, mu_task, a_values, eta=1.0)
        row_sums = p.sum(axis=1)
        self.assertTrue(np.allclose(row_sums, 1.0, atol=1e-8))

    def test_a_zero_equals_weights(self):
        weights = np.array([0.5, 0.3, 0.2])
        mu_task = np.array([0.4, -0.2, 0.1])
        a_values = np.zeros(3)
        p = compute_q_p(weights, mu_task, a_values, eta=1.0)
        for row in p:
            self.assertTrue(np.allclose(row, weights, atol=1e-8))

    def test_a_one_proportional(self):
        weights = np.array([0.5, 0.3, 0.2])
        mu_task = np.array([0.4, -0.2, 0.1])
        a_values = np.ones(2)
        eta = 1.2
        p = compute_q_p(weights, mu_task, a_values, eta=eta)
        expected = weights * np.exp(eta * mu_task)
        expected = expected / expected.sum()
        for row in p:
            self.assertTrue(np.allclose(row, expected, atol=1e-8))

    def test_monotonic_sanity(self):
        weights = np.array([0.5, 0.5])
        mu_task = np.array([0.5, -0.5])
        a_values = np.array([0.0, 0.5, 1.0])
        p = compute_q_p(weights, mu_task, a_values, eta=1.0)
        self.assertTrue(p[2, 0] >= p[1, 0] >= p[0, 0])


if __name__ == "__main__":
    unittest.main()
