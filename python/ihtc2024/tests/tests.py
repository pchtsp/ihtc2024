import unittest
import json

from ihtc2024 import Instance, Solution, Experiment, solvers
import os, sys
from html.parser import HTMLParser
from typing import Dict, List, Tuple, Optional
from pytups import SuperDict


tests_dir = os.path.dirname(__file__)
root_dir = os.path.join(tests_dir, "../")
my_paths = [root_dir]
for __my_path in my_paths:
    sys.path.insert(1, __my_path)
PATH_TO_VALIDATOR = os.path.join(root_dir, "../../validator/IHTP_Validator")


class BaseTestInstance(unittest.TestCase):

    def setUp(self):
        path_to_data = os.path.join(tests_dir, "data")
        self.instance = Instance.from_ihtc_json(os.path.join(path_to_data, "toy.json"))
        self.solution = Solution.from_ihtc_json(
            os.path.join(path_to_data, "toy_solution.json")
        )

    @staticmethod
    def get_solved_experiment(test_instance_name):
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

    @staticmethod
    def get_test_experiment(test_instance_name) -> Experiment:
        path_to_data = os.path.join(
            tests_dir, "../../../data/ihtc2024_competition_instances/"
        )
        instance = Instance.from_ihtc_json(
            os.path.join(path_to_data, test_instance_name)
        )
        return Experiment(instance)


class TestInstance(BaseTestInstance):

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

    def test_experiment_excel(self):
        my_experim = Experiment(self.instance, self.solution)
        excel_path = os.path.join(tests_dir, "experiment.xlsx")
        my_experim.to_excel(excel_path)
        my_experim = Experiment.from_excel(excel_path)
        my_experim.get_objective()
        my_experim.check_solution()
        try:
            os.remove(excel_path)
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

    def test_validator(self):
        my_experim_solved = self.get_solved_experiment("test01.json")
        print(my_experim_solved.get_objective())
        my_experim_solved.run_validator(PATH_TO_VALIDATOR)

    def test_validator2(self):
        my_experim_solved = self.get_solved_experiment("test02.json")
        print(my_experim_solved.get_objective())
        my_experim_solved.run_validator(PATH_TO_VALIDATOR)

    def test_validator3(self):
        my_experim_solved = self.get_solved_experiment("test03.json")
        print(my_experim_solved.get_objective())
        my_experim_solved.run_validator(PATH_TO_VALIDATOR)

    def test_report(self):
        my_experim_solved = self.get_solved_experiment("test03.json")

        things_to_look = dict(
            section=[
                ("id", "solution"),
                ("id", "instance"),
                ("id", "patient-calendar"),
            ]
        )
        self.generate_check_report(my_experim_solved, things_to_look)

    def generate_check_report(
        self, my_experim, things_to_look, verbose=False, delete_file=True
    ):

        report_path = my_experim.generate_report()
        # check the file is created.
        self.assertTrue(os.path.exists(report_path))

        parser = HTMLCheckTags(things_to_look, verbose)
        with open(report_path, "r") as f:
            content = f.read()

        if delete_file:
            try:
                os.remove(report_path)
            except FileNotFoundError:
                pass
        self.assertRaises(StopIteration, parser.feed, content)


class HTMLCheckTags(HTMLParser):
    things_to_check: Optional[Dict[str, List[Tuple[str, str]]]]

    def __init__(self, things_to_check: Dict[str, List[Tuple[str, str]]], verbose):
        HTMLParser.__init__(self)
        self.verbose = verbose
        if things_to_check is None:
            self.things_to_check = None
        else:
            self.things_to_check = SuperDict(things_to_check).copy_deep()

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]):
        # when things_to_check is None, we traverse everything
        # when verbose=True, we print what we traverse
        if self.verbose:
            print("Start tag:", tag)
        if self.things_to_check is not None and tag not in self.things_to_check:
            return
        for attr in attrs:
            if self.verbose:
                print("     attr:", attr)
            # is we're not looking for keys, we just continue
            if self.things_to_check is None:
                continue
            try:
                # we find the element in the list and remove it
                index = self.things_to_check[tag].index(attr)
                self.things_to_check[tag].pop(index)
            except ValueError:
                continue
            # if the list is empty, we take out the key
            if not len(self.things_to_check[tag]):
                self.things_to_check.pop(tag)
                # if we have nothing else to check,
                # we stop searching
                if not (self.things_to_check):
                    raise StopIteration


if __name__ == "__main__":
    unittest.main()
