import unittest
import json

from ihtc2024 import Instance, Solution, Experiment, solvers

import os, sys

tests_dir = os.path.dirname(__file__)
root_dir = os.path.join(tests_dir, "../")
my_paths = [root_dir]
for __my_path in my_paths:
    sys.path.insert(1, __my_path)
PATH_TO_VALIDATOR = os.path.join(root_dir, "../../validator/IHTP_Validator")


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
        my_experim.solve(dict(threads=8, timeLimit=100, msg=True))
        checks = my_experim.check_solution()

        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)
        my_experim.run_validator(PATH_TO_VALIDATOR)

    def get_solved_experiment(self, test_instance_name):
        path_to_data = os.path.join(tests_dir, "../../../data/")
        # test_instance_name = "test01.json"
        instance_path = os.path.join(
            path_to_data, "ihtc2024_test_dataset/" + test_instance_name
        )
        instance = Instance.from_ihtc_json(instance_path)
        solution_path = os.path.join(
            path_to_data, "ihtc2024_test_solutions/" + "sol_" + test_instance_name
        )
        solution = Solution.from_ihtc_json(solution_path)
        my_experim_solved = solvers["cpsat"](instance, solution)
        return my_experim_solved

    def test_solve_test_instance_1_cpsat(self):
        my_experim_solved = self.get_solved_experiment("test01.json")
        print(my_experim_solved.get_objective())
        my_experim = solvers["cpsat"](my_experim_solved.instance)
        my_experim.solve(dict(threads=8, timeLimit=30, msg=True))
        checks = my_experim.check_solution()
        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)

    def test_solve_competition_instance_cpsat(self):
        path_to_data = os.path.join(
            tests_dir, "../../../data/ihtc2024_competition_instances/"
        )
        instance = Instance.from_ihtc_json(os.path.join(path_to_data, "i15.json"))
        my_experim = solvers["cpsat"](instance)
        my_experim.solve(dict(threads=8, timeLimit=60, msg=True))
        checks = my_experim.check_solution()
        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)

    def test_solved_fixed(self):
        for name in [f"test0{i}.json" for i in range(1, 6)]:
            print(name)
            experiment = self.get_solved_experiment(name)
            my_experim = solvers["cpsat"](experiment.instance, experiment.solution)
            old_objective = my_experim.get_objective()
            status = my_experim.solve(
                dict(
                    threads=8, timeLimit=60, msg=True, warmStart=True, fixSolution=True
                )
            )
            # it needs to find a solution:
            self.assertEqual(status["status"], 1)
            new_objective = my_experim.get_objective()
            self.assertTrue(old_objective, new_objective)

    def test_hint_solution(self):
        # for name in [f"test0{i}.json" for i in range(1, 6)]:
        name = "test05.json"
        # print(name)
        experiment = self.get_solved_experiment(name)
        my_experim = solvers["cpsat"](experiment.instance, experiment.solution)
        old_objective = my_experim.get_objective()
        status = my_experim.solve(
            dict(threads=8, timeLimit=60, msg=True, warmStart=True)
        )
        # it needs to find a solution:
        self.assertEqual(status["status"], 1)
        new_objective = my_experim.get_objective()

        print(old_objective)
        print(new_objective)


if __name__ == "__main__":
    unittest.main()
