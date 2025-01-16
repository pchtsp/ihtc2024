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

    def test_solve_toy_cpsat(self):
        my_experim = solvers["cpsat"](self.instance)
        my_experim.solve(dict(threads=8, timeLimit=100, msg=True))
        checks = my_experim.check_solution()

        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)
        my_experim.run_validator(PATH_TO_VALIDATOR)

    def test_time_window(self):
        name = "test05.json"
        experiment = self.get_solved_experiment(name)
        my_experim = solvers["cpsat"](experiment.instance, experiment.solution)
        # my_experim = solvers["cpsat"](self.instance, self.solution)
        options = dict(timeWindow=dict(size=10), msg=True, threads=8, timeLimit=60)
        my_experim.solve(options)
        print(my_experim.get_objective())
        # my_experim.run_validator(PATH_TO_VALIDATOR)

    def test_solve_test_instance_1_cpsat(self):
        my_experim_solved = self.get_solved_experiment("test01.json")
        print(my_experim_solved.get_objective())
        my_experim_solved.run_validator(PATH_TO_VALIDATOR)
        my_experim = solvers["cpsat"](my_experim_solved.instance)
        my_experim.solve(dict(threads=8, timeLimit=60, msg=True))
        checks = my_experim.check_solution()
        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)
        my_experim.get_objective_terms().vapply(lambda v: sum(v.values()))
        terms = my_experim.get_objective_terms()
        my_experim.run_validator(PATH_TO_VALIDATOR)

    def test_solve_competition_instance_cpsat(self):

        my_experim = solvers["cpsat"](self.get_test_experiment("i15.json").instance)
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
        my_experim.run_validator(PATH_TO_VALIDATOR)
        experiment.run_validator(PATH_TO_VALIDATOR)
