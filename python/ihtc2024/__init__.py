from typing import List, Dict
import os
from cornflow_client import ApplicationCore, get_empty_schema

from ihtc2024.core import Instance, Solution, Experiment

from ihtc2024.solver import solvers


class WindEnergyBattery(ApplicationCore):
    name = "wind_energy_battery"
    instance = Instance
    solution = Solution
    solvers = solvers
    schema = get_empty_schema(
        properties=dict(timeLimit=dict(type="number")), solvers=list(solvers.keys())
    )
    # schema["properties"]["solver"]["enum"].extend(
    #     ["milp_solver.PULP_CBC_CMD", "milp_solver.GUROBI_CMD"],
    # )
    # schema = add_reports_to_schema(schema, ["report"])

    @property
    def test_cases(self) -> List[Dict]:
        path_to_data = os.path.join(os.path.dirname(__file__), "tests/data")
        return [
            {
                "name": "sample_unit_test_case",
                "instance": Instance.from_ihtc_json(
                    os.path.join(path_to_data, "toy.xlsx")
                ).to_dict(),
                "solution": Solution.from_ihtc_json(
                    os.path.join(path_to_data, "toy_solution.xlsx")
                ).to_dict(),
            }
        ]
