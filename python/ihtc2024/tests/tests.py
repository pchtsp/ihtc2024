import unittest
import os, sys

from pytups import SuperDict, TupList
import matplotlib.pyplot as plt
import json

from ihtc2024 import Instance, Solution

# conventionally we run the tests from the ROOT so we add the current directory
root_module_path = os.getcwd()

if root_module_path not in sys.path:
    # print('adding root_module_path {} to the sys.path {}'.format(root_module_path, sys.path))
    sys.path.append(root_module_path)


class TestInstance(unittest.TestCase):

    def setUp(self):
        path_to_data = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        self.instance = Instance.from_ihtc_json(os.path.join(path_to_data, "toy.json"))
        self.solution = Solution.from_ihtc_json(
            os.path.join(path_to_data, "toy_solution.json")
        )

    def test_export(self):
        self.instance.to_dict()

    def test_instance_generate_schema(self):
        self.instance.generate_schema()

    def test_solution_generate_schema(self):
        self.solution.generate_schema()


if __name__ == "__main__":
    unittest.main()
