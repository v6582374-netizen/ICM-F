import unittest

from code.curriculum_pruner import (
    tokenize,
    cosine_similarity,
    build_similarity_matrix,
    compute_course_metrics
)


class CurriculumPrunerTests(unittest.TestCase):
    def test_tokenize(self):
        tokens = tokenize("Robotics, Systems & Control!")
        self.assertIn("robotics", tokens)
        self.assertIn("systems", tokens)
        self.assertIn("control", tokens)

    def test_cosine_similarity(self):
        vec_a = {"a": 1.0, "b": 0.0}
        vec_b = {"a": 1.0, "b": 1.0}
        self.assertGreater(cosine_similarity(vec_a, vec_b), 0.0)

    def test_metrics_shape(self):
        courses = [
            {"course_code": "C1", "title": "Robotics", "description": "robotics control", "credits": 3},
            {"course_code": "C2", "title": "Diagnostics", "description": "diagnostic testing", "credits": 3}
        ]
        tasks = [
            {"task_id": "T1", "task_text": "robotic control", "s": "0.3", "c": "0.7"},
            {"task_id": "T2", "task_text": "diagnose systems", "s": "0.6", "c": "0.4"}
        ]
        d_j = {"T1": 0.6, "T2": 0.4}
        sim = build_similarity_matrix(courses, tasks)
        metrics, coverage = compute_course_metrics(courses, tasks, d_j, sim)
        self.assertEqual(len(metrics), 2)
        self.assertEqual(len(coverage), 2)


if __name__ == "__main__":
    unittest.main()
