from ihtc2024 import Instance, Solution, Experiment, solvers
import os, sys

tests_dir = os.path.dirname(__file__)
root_dir = os.path.join(tests_dir, "../")
my_paths = [root_dir]
for __my_path in my_paths:
    sys.path.insert(1, __my_path)
PATH_TO_VALIDATOR = os.path.join(root_dir, "../../validator/IHTP_Validator")
from .tests import BaseTestInstance


class TestInstance(BaseTestInstance):

    def test_solve_toy(self):
        my_experim = solvers["graph_tw"](self.instance)
        my_experim.solve(dict(threads=8, timeLimit=20, msg=True))
        checks = my_experim.check_solution()

        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)
        my_experim.run_validator(PATH_TO_VALIDATOR)

    def test_solve_test_instance_1(self):
        my_experim_solved = self.get_solved_experiment("test01.json")
        print(my_experim_solved.get_objective())
        my_experim_solved.run_validator(PATH_TO_VALIDATOR)
        my_experim = solvers["graph_tw"](my_experim_solved.instance)
        my_experim.solve(dict(threads=8, timeLimit=300, msg=True))
        checks = my_experim.check_solution()
        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)
        my_experim.get_objective_terms().vapply(lambda v: sum(v.values()))
        terms = my_experim.get_objective_terms()
        my_experim.run_validator(PATH_TO_VALIDATOR)

    def test_solve_competition_instance(self):

        my_experim = solvers["graph_tw"](self.get_test_experiment("i15.json").instance)
        my_experim.solve(dict(threads=8, timeLimit=200, msg=True))
        checks = my_experim.check_solution()
        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)
