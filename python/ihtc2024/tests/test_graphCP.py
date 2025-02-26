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
        my_experim = solvers["graphCP"](self.instance)
        my_experim.solve(dict(threads=8, timeLimit=20, msg=True))
        checks = my_experim.check_solution()

        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)
        my_experim.run_validator(PATH_TO_VALIDATOR)

    def test_solve_test04(self):
        my_experim = self.get_solved_experiment("test04.json")
        my_experim = solvers["graphCP"](my_experim.instance)
        my_experim.solve(dict(threads=8, timeLimit=300, msg=True, maxRestartSec=10))

    def test_solved_fixed_4(self):
        name = f"test04.json"
        experiment = self.get_solved_experiment(name)
        print(experiment.check_solution())
        my_experim = solvers["graphCP"](experiment.instance)
        old_objective = my_experim.get_objective()
        status = my_experim.solve(
            dict(
                threads=8,
                timeLimit=60,
                msg=True,
                warmStart=True,
                fixSolution=True,
                dump_vars=True,
                maxRestartSec=10,
            )
        )
        # it needs to find a solution:
        self.assertEqual(status["status"], 1)
        new_objective = my_experim.get_objective()
        self.assertTrue(old_objective, new_objective)

    def test_solve_test29(self):
        my_experim = self.get_test_experiment("i29.json")
        my_experim = solvers["grahpGRASP"](my_experim.instance)
        my_experim.solve(dict(threads=8, timeLimit=300, msg=True))
