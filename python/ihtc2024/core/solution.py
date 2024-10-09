import json
from .tools import generic_from_dict, generic_to_dict, flat_list
from ..schemas import solution
from cornflow_client import SolutionCore
from pytups import SuperDict, TupList
from pandas import read_excel

SOLUTION_TABLE_KEYS = {
    "patient_assignment": ["id"],
    "nurse_assignment": ["room", "day", "shift"],
}


class Solution(SolutionCore):
    schema = solution

    def __init__(self, data):
        super().__init__(data)
        return

    @property
    def data(self) -> SuperDict:
        return self._data

    @data.setter
    def data(self, value: SuperDict):
        self._data = value

    @classmethod
    def from_excel(cls, path: str) -> "Solution":
        my_sheets = list(SOLUTION_TABLE_KEYS.keys())
        # we read all relevant sheets from Excel:
        data_raw = read_excel(path, sheet_name=my_sheets)

        # SuperDict is just a dictionary with additional methods:
        data = SuperDict(data_raw).vapply(lambda v: v.to_dict(orient="records"))

        return cls.from_dict(data)

    def to_dict(self) -> SuperDict:
        return generic_to_dict(self.data, SOLUTION_TABLE_KEYS)

    @classmethod
    def from_dict(cls, data: dict) -> "Solution":
        data = generic_from_dict(data, SOLUTION_TABLE_KEYS)
        return cls(data)

    @classmethod
    def from_ihtc_json(cls, path: str) -> "Solution":
        with open(path, "r") as f:
            content = json.load(f)
        data = SuperDict()
        data["patient_assignment"] = [
            elem
            for elem in content["patients"]
            if elem["admission_day"] not in [None, "none"]
        ]
        data["nurse_assignment"] = [
            SuperDict(id=nurse["id"], day=a["day"], shift=a["shift"], room=r)
            for nurse in content["nurses"]
            for a in nurse["assignments"]
            for r in a["rooms"]
        ]
        data = generic_from_dict(data, SOLUTION_TABLE_KEYS)
        return cls(data)

    def to_ihtc_json(self, path: str) -> None:
        content = generic_to_dict(self.data, SOLUTION_TABLE_KEYS)
        nurses = []
        _temp = content["nurse_assignment"].to_dict(None, indices="id")
        for nurse, rows in _temp.items():
            elem = {"id": nurse}
            row_indexed = rows.to_dict("room", indices=["day", "shift"])
            elem["assignments"] = [
                dict(day=day, shift=shift, rooms=v)
                for (day, shift), v in row_indexed.items()
            ]
            nurses.append(elem)
        result = dict(patients=content["patient_assignment"], nurses=nurses)
        with open(path, "w") as f:
            json.dump(result, f)
        return None

    def get_patient_assignment(self):
        return self.data["patient_assignment"]

    def get_nurse_assignment(self):
        return self.data["nurse_assignment"]
