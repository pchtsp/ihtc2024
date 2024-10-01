import unittest
import json

from ihtc2024 import Instance, Solution

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

    def test_instance_generate_schema(self):
        schema = self.instance.generate_schema()
        instance_schema_path = os.path.join(tests_dir, "instance_schema.json")
        with open(instance_schema_path, "w") as f:
            json.dump(schema, f, indent=4, sort_keys=True)

    def test_solution_generate_schema(self):
        schema = self.solution.generate_schema()
        schema_path = os.path.join(tests_dir, "solution_schema.json")
        with open(schema_path, "w") as f:
            json.dump(schema, f, indent=4, sort_keys=True)


if __name__ == "__main__":
    unittest.main()
