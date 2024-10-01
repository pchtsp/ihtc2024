import json

from ..schemas import instance
from cornflow_client import InstanceCore, get_empty_schema
from pytups import SuperDict, TupList
from typing import List, Tuple, Dict
from pandas import read_excel
from .tools import generic_from_dict, generic_to_dict, flat_list


# we define primary keys for each sheet:
# format: table => column
TABLE_KEYS = {
    "patients": ["id"],
    "patient_shifts": ["patient", "pos_shift"],
    "patient_rooms": ["patient", "room"],
    "occupants": ["id"],
    "occupant_shifts": ["occupant", "pos_shift"],
    "surgeons": ["id"],
    "surgeon_days": ["surgeon", "day"],
    "operating_theaters": ["id"],
    "operating_theater_days": ["operating_theater", "day"],
    "rooms": ["id"],
    # capacity
    "nurses": ["id"],
    # skill_level
    "nurse_shifts": ["nurse", "day"],
    # shift, max_load
    "weights": None,
    "shift_types": ["id"],
    "age_groups": ["id"],
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
        # TODO: parametrize this
        with open(path, "r") as f:
            content = json.load(f)

        data = SuperDict()

        def filter_keys(my_dict, my_keys):
            return SuperDict(my_dict).filter(my_keys, check=True)

        data["occupants"] = TupList(content["occupants"]).vapply(
            filter_keys, ["id", "gender", "age_group", "length_of_stay", "room_id"]
        )
        data["patients"] = TupList(content["patients"]).vapply(
            filter_keys,
            ["id", "gender", "age_group", "length_of_stay"],
        )
        data["patient_shifts"] = flat_list(
            content["patients"],
            ["workload_produced", "skill_level_required"],
            "pos_shift",
            id_name_out="patient",
        )
        data["occupant_shifts"] = flat_list(
            content["occupants"],
            ["workload_produced", "skill_level_required"],
            "pos_shift",
            id_name_out="occupant",
        )
        data["surgeons"] = TupList(content["surgeons"]).vapply(filter_keys, ["id"])
        data["surgeon_days"] = flat_list(
            content["surgeons"], ["max_surgery_time"], "day", id_name_out="surgeon"
        )
        data["operating_theaters"] = TupList(content["operating_theaters"]).vapply(
            filter_keys, ["id"]
        )
        data["operating_theater_days"] = flat_list(
            content["operating_theaters"],
            ["availability"],
            "day",
            id_name_out="operating_theater",
        )
        data["rooms"] = content["rooms"]
        data["nurses"] = TupList(content["nurses"]).vapply(
            filter_keys, ["id", "skill_level"]
        )
        my_data = TupList()
        for nurse in content["nurses"]:
            for day in nurse["working_shifts"]:
                elem = SuperDict(nurse=nurse["id"], **day)
                my_data.append(elem)
        data["nurse_shifts"] = my_data
        data["weights"] = content["weights"]

        for table in ["shift_types", "age_groups"]:
            data[table] = [{"id": st for st in content[table]}]
        parameters = ["days"]
        data["parameters"] = SuperDict({p: content[p] for p in parameters})
        return cls.from_dict(data)

    def to_ihtc_json(self, path: str) -> None:
        # TODO: this
        content = generic_to_dict(self.data, TABLE_KEYS)
        with open(path, "w") as f:
            json.dump(content, f)
        return None

    def copy(self):
        return self.from_dict(self.to_dict())
