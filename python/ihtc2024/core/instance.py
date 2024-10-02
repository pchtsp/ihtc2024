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
    "parameters": None,
    "patients": ["id"],
    "patient_shifts": ["patient", "pos_shift"],
    "patient_room_ban": ["patient", "room"],
    "occupants": ["id"],
    "occupant_shifts": ["occupant", "shift"],
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
        # default value of due_day -> last day for non-mandatory
        data["patients"] = (
            TupList(content["patients"])
            .vapply_col(
                "surgery_due_day",
                lambda v: v.get("surgery_due_day", -1),
            )
            .vapply(
                filter_keys,
                [
                    "id",
                    "gender",
                    "age_group",
                    "length_of_stay",
                    "mandatory",
                    "surgeon_id",
                    "surgery_release_day",
                    "surgery_duration",
                    "surgery_due_day",
                ],
            )
        )
        data["patient_shifts"] = flat_list(
            content["patients"],
            ["workload_produced", "skill_level_required"],
            "pos_shift",
            id_name_out="patient",
        )
        data["patient_room_ban"] = flat_list(
            content["patients"],
            ["incompatible_room_ids"],
            "__",
            id_name_out="patient",
        ).vapply(
            lambda v: SuperDict(patient=v["patient"], room=v["incompatible_room_ids"])
        )
        data["occupant_shifts"] = flat_list(
            content["occupants"],
            ["workload_produced", "skill_level_required"],
            "shift",
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
            data[table] = [
                SuperDict(id=st, pos=pos) for pos, st in enumerate(content[table])
            ]
            # data[table] = [{"id": st for st in content[table]}]
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

    def get_length_day(self) -> int:
        return len(self.get_shifttypes())

    def get_horizon_size_days(self) -> int:
        return self.data["parameters"]["days"]

    def get_horizon_size_shifts(self) -> int:
        return self.data["parameters"]["days"] * self.get_length_day()

    def get_horizon_days(self) -> range:
        return range(self.get_horizon_size_days())

    def get_last_shift_horizon(self) -> int:
        return self.get_last_shift_of_day(self.get_horizon_days()[-1])

    def get_horizon_shifts(self) -> range:
        return range(self.get_horizon_size_shifts())

    def get_weights(self) -> SuperDict:
        return self.data["weights"]

    def get_patients(self) -> SuperDict:
        return self.data["patients"]

    def get_patients_occupants(self) -> SuperDict:
        patients = self.get_patients().copy_deep()
        for k, v in patients.items():
            patients[k]["is_occupant"] = False
        occupants = self.get_occupants()
        my_keys = ["age_group", "gender", "length_of_stay", "id"]
        for _id, occupant in occupants.items():
            patients[_id] = SuperDict(is_occupant=True)
            for key in my_keys:
                patients[_id][key] = occupant[key]
        return patients

    def get_patient_shifts(self) -> SuperDict:
        return self.data["patient_shifts"]

    def get_nurses(self) -> SuperDict:
        return self.data["nurses"]

    def get_nurse_days(self):
        return self.data["nurse_shifts"]

    def get_nurse_shift(self):
        nurse_info = self.get_nurse_days().values_tl().copy_deep()
        get_shift = self.get_shift_from_day_shiftype
        nurse_info.vapply_col("shift_pos", lambda v: get_shift(v["day"], v["shift"]))
        return nurse_info.to_dict(None, indices=["nurse", "shift_pos"], is_list=False)

    def get_agegroups(self):
        return self.data["age_groups"]

    def get_shifttypes(self):
        return self.data["shift_types"]

    def get_surgeons(self):
        return self.data["surgeons"]

    def get_surgeon_capacity(self):
        return self.data["surgeon_days"]

    def get_occupants(self):
        return self.data["occupants"]

    def get_occupant_shifts(self):
        return self.data["occupant_shifts"]

    def get_operatingtheater_capacity(self):
        return self.data["operating_theater_days"]

    def get_patient_available_days(self):
        first = self.data["patients"].get_property("surgery_release_day")
        last = self.data["patients"].vapply(
            lambda v: (
                v["surgery_due_day"] if v["mandatory"] else self.get_horizon_size_days()
            )
            + 1
        )
        return first.sapply(range, last)

    def get_shifts_of_day(self, day: int):
        first = self.get_first_shift_of_day(day)
        last = self.get_last_shift_of_day(day)
        return range(first, last)

    def get_first_shift_of_day(self, day: int):
        length_day = len(self.get_shifttypes())
        return day * length_day

    def get_last_shift_of_day(self, day: int):
        length_day = len(self.get_shifttypes())
        return (day + 1) * length_day - 1

    def get_shift_from_day_shiftype(self, day: int, shift_type: str):
        shift_types = self.get_shifttypes()
        return self.get_first_shift_of_day(day) + shift_types[shift_type]["pos"]
