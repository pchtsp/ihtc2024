from typing import List, Dict
import os
from cornflow_client import ApplicationCore
from cornflow_client.core.tools import load_json
from ihtc2024.core import Instance, Solution, Experiment

from ihtc2024.solver import solvers
from typing import Type, Union


class IntegratedHealtcareTimetable(ApplicationCore):
    name = "healthacare_timetable"
    instance = Instance
    solution = Solution
    solvers: Dict[str, Type[Experiment]] = solvers
    schema = load_json(os.path.join(os.path.dirname(__file__), "./schemas/config.json"))

    @property
    def test_cases(self) -> List[Dict]:
        path_to_data = os.path.join(os.path.dirname(__file__), "tests/data")
        return [
            {
                "name": "sample_unit_test_case",
                "instance": Instance.from_ihtc_json(
                    os.path.join(path_to_data, "toy.json")
                ).to_dict(),
                "solution": Solution.from_ihtc_json(
                    os.path.join(path_to_data, "toy_solution.json")
                ).to_dict(),
            }
        ]

    def get_solver(self, name: str = "default") -> Union[Type[Experiment], None]:
        return ApplicationCore.get_solver(self, name)
