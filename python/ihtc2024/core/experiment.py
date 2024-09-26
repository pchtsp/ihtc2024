from pytups import SuperDict, TupList
import pandas as pd
import copy
from typing import List, Dict
import os
from .instance import Instance
from .solution import Solution
from cornflow_client.core.tools import load_json

from cornflow_client import ExperimentCore
import json, tempfile
import quarto


class Experiment(ExperimentCore):
    schema_checks = load_json(
        os.path.join(os.path.dirname(__file__), "../schemas/solution_checks.json")
    )

    def __init__(self, instance: Instance, solution: Solution = None):
        super().__init__(instance, solution)
        if solution is None:
            solution = Solution(SuperDict())
        self.solution = solution
        return

    @property
    def instance(self) -> Instance:
        return super().instance

    @property
    def solution(self) -> Solution:
        return super().solution

    @solution.setter
    def solution(self, value):
        self._solution = value

    def to_dict(self) -> dict:
        return dict(instance=self.instance.to_dict(), solution=self.solution.to_dict())

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            Instance.from_dict(data["instance"]), Solution.from_dict(data["solution"])
        )

    @classmethod
    def from_json(cls, path: str) -> "Experiment":
        with open(path, "r") as f:
            data_json = json.load(f)
        return cls.from_dict(data_json)

    def to_json(self, path: str) -> None:
        data = self.to_dict()
        with open(path, "w") as f:
            json.dump(data, f, indent=4, sort_keys=True)

    @classmethod
    def from_excel(cls, path: str):
        instance = Instance.from_excel(path)
        # solution will be created even if the solution sheet is empty,
        # the data SuperDict component will be present, but empty
        solution = Solution.from_excel(path)
        return cls(instance, solution)

    def to_excel(self, path: str):
        data = {**self.instance.to_dict(), **self.solution.to_dict()}
        with pd.ExcelWriter(path) as writer:
            for table in data.keys():
                content = data[table]
                # TODO: check the schema for array / object
                if isinstance(content, list):
                    pd.DataFrame.from_records(content).to_excel(
                        writer, table, index=False
                    )
                elif isinstance(content, dict):
                    pd.DataFrame.from_dict(content, orient="index").to_excel(
                        writer, table, header=False
                    )
        return True

    def solve(self, options: dict = None):
        raise NotImplementedError("Must be implemented in the inherited class")

    def check_solution(self, **params) -> SuperDict:
        return SuperDict()

    def get_objective(self) -> float:
        """
        A default method form, a wrapper to sum all objective components
        """
        return 0

    def generate_report(self, report_name="report") -> str:

        if not os.path.isabs(report_name):
            report_name = os.path.join(
                os.path.dirname(__file__), "../report/", report_name
            )

        return self.generate_report_quarto(quarto, report_name=report_name)
