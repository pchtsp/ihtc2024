from ..schemas import instance
from cornflow_client import InstanceCore, get_empty_schema
from pytups import SuperDict, TupList
from typing import List, Tuple, Dict
from pandas import read_excel
from .tools import generic_from_dict, generic_to_dict


# we define primary keys for each sheet:
# format: table => column
TABLE_KEYS = {
    "patients": "id",
    "patient_shifts": ["patient", "pos_shift"],
    # workload_produced, skill_level_required
    "patient_rooms": ["patient", "room"],
    "occupants": "id",
    "occupant_shifts": ["occupant", "pos_shift"],
    "surgeons": "id",
    "surgeon_days": ["surgeon", "day"],
    "operating_theaters": "id",
    "operating_theater_days": ["operating_theater", "day"],
    "rooms": "id",
    # capacity
    "nurses": "id",
    # skill_level
    "nurse_shifts": ["nurse", "day"],
    # shift, max_load
    "weights": None,
    "shift_types": "shift_type",
    "age_groups": "age_group",
}


class Instance(InstanceCore):
    schema = instance
    schema_checks = get_empty_schema()

    def __init__(self, data: dict):
        data = SuperDict(data).copy_deep().kfilter(lambda k: k in TABLE_KEYS)
        super().__init__(data)

    @property
    def data(self) -> SuperDict:
        return self._data

    @data.setter
    def data(self, value: SuperDict):
        self._data = value

    @classmethod
    def from_excel(cls, path: str) -> "Instance":
        my_sheets = list(TABLE_KEYS.keys())
        # we read all relevant sheets from Excel:
        data_raw = read_excel(path, sheet_name=my_sheets)

        # SuperDict is just a dictionary with additional methods:
        data = SuperDict(data_raw).vapply(lambda v: v.to_dict(orient="records"))

        return cls.from_dict(data)

    def to_dict(self) -> SuperDict:
        return generic_to_dict(self.data, TABLE_KEYS)

    @classmethod
    def from_dict(cls, data: Dict[str, List[dict]]) -> "Instance":
        data = generic_from_dict(data, TABLE_KEYS)
        return cls(data)

    @classmethod
    def from_ihtc_json(cls, path: str) -> "Instance":
        return cls()

    def to_ihtc_json(self, path: str) -> None:
        return

    def copy(self):
        return self.from_dict(self.to_dict())
