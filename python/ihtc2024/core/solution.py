from .tools import generic_from_dict, generic_to_dict
from ..schemas import solution
from cornflow_client import SolutionCore
from pytups import SuperDict, TupList
from pandas import read_excel

SOLUTION_TABLE_KEYS = {
    "patient_assignment": ["id"],
    "nurse_assignment": ["room", "shift"],
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
        return cls()

    def to_ihtc_json(self, path: str) -> None:
        return
