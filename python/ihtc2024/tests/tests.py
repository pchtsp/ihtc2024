import unittest
import json

from ihtc2024 import Instance, Solution, Experiment, solvers

import os, sys

tests_dir = os.path.dirname(__file__)
root_dir = os.path.join(tests_dir, "../")
my_paths = [root_dir]
for __my_path in my_paths:
    sys.path.insert(1, __my_path)


class TestInstance(unittest.TestCase):

    def setUp(self):
        path_to_data = os.path.join(tests_dir, "data")
        self.instance = Instance.from_ihtc_json(os.path.join(path_to_data, "toy.json"))
        self.solution = Solution.from_ihtc_json(
            os.path.join(path_to_data, "toy_solution.json")
        )

    def test_export(self):
        dict_data = self.instance.to_dict()

    def test_export_solution(self):
        dict_data = self.solution.to_dict()

    def test_instance_generate_schema(self):
        schema = self.instance.generate_schema()
        schema_path = os.path.join(tests_dir, "instance.json")
        with open(schema_path, "w") as f:
            json.dump(schema, f, indent=4, sort_keys=True)
        try:
            os.remove(schema_path)
        except OSError:
            pass

    def test_solution_generate_schema(self):
        schema = self.solution.generate_schema()
        schema_path = os.path.join(tests_dir, "solution_schema.json")
        with open(schema_path, "w") as f:
            json.dump(schema, f, indent=4, sort_keys=True)
        try:
            os.remove(schema_path)
        except OSError:
            pass

    def test_objective(self):
        my_experim = Experiment(self.instance, self.solution)
        objective = my_experim.get_objective()
        self.assertEqual(292, objective)

    def test_check_solution(self):
        my_experim = Experiment(self.instance, self.solution)
        checks = my_experim.check_solution()
        self.assertEqual(len(checks["h1"]), 3)
        for elem in ["h2", "h3", "h4", "h5", "h6"]:
            self.assertEqual(len(checks[elem]), 0)

    def test_solution_to_ithc(self):
        path = os.path.join(tests_dir, "solution_ithc.json")
        self.solution.to_ihtc_json(path)
        another_solution = self.solution.from_ihtc_json(path)
        self.assertEqual(self.solution.data, another_solution.data)
        try:
            os.remove(path)
        except OSError:
            pass

    def test_instance_to_ithc(self):
        path = os.path.join(tests_dir, "instance_ithc.json")
        self.instance.to_ihtc_json(path)
        another_instance = self.instance.from_ihtc_json(path)
        self.assertEqual(self.instance.data, another_instance.data)
        try:
            os.remove(path)
        except OSError:
            pass

    def test_solve_toy_cpsat(self):
        my_experim = solvers["cpsat"](self.instance)
        my_experim.solve(dict())
        checks = my_experim.check_solution()

        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        my_experim.get_objective()

    def test_solve_test_instance_1_cpsat(self):
        path_to_data = os.path.join(tests_dir, "../../../data/ihtc2024_test_dataset/")
        self.instance = Instance.from_ihtc_json(
            os.path.join(path_to_data, "test01.json")
        )
        my_experim = solvers["cpsat"](self.instance)
        my_experim.solve(dict())
        checks = my_experim.check_solution()
        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        my_experim.get_objective()

    def test_solve_competition_instance_cpsat(self):
        path_to_data = os.path.join(
            tests_dir, "../../../data/ihtc2024_competition_instances/"
        )
        self.instance = Instance.from_ihtc_json(os.path.join(path_to_data, "i01.json"))
        my_experim = solvers["cpsat"](self.instance)
        my_experim.solve(dict())
        checks = my_experim.check_solution()
        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        my_experim.get_objective()


if __name__ == "__main__":
    unittest.main()
