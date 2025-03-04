import json

from ..schemas import instance
from cornflow_client import InstanceCore, get_empty_schema
from pytups import SuperDict, TupList
from typing import List, Tuple, Dict
from pandas import read_excel
from .tools import generic_from_dict, generic_to_dict, flat_list
from ortools.sat.python import cp_model
import pulp as pl

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
    __get_patients_occupants_needs_cache: Dict | None
    __get_nurse_shift_cache: Dict | None
    __get_patients_occupants_cache: SuperDict | None

    def __init__(self, data: dict):
        data = SuperDict(data).copy_deep().kfilter(lambda k: k in TABLE_KEYS)
        super().__init__(data)
        # some cache values
        self.__get_patients_occupants_needs_cache = None
        self.__get_nurse_shift_cache = None
        self.__get_patients_occupants_cache = None

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

    def to_json_str(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json_str(cls, data: str) -> "Instance":
        return cls.from_dict(json.loads(data))

    @classmethod
    def from_dict(cls, data: Dict[str, List[dict]]) -> "Instance":
        data = generic_from_dict(data, TABLE_KEYS)
        return cls(data)

    @classmethod
    def from_ihtc_json(cls, path: str, content: dict = None) -> "Instance":
        if content is None:
            with open(path, "r") as f:
                content = json.load(f)

        data = SuperDict()

        def filter_keys(my_dict, my_keys):
            return SuperDict(my_dict).filter(my_keys, check=True)

        data["occupants"] = TupList(content["occupants"]).vapply(
            filter_keys, ["id", "gender", "age_group", "length_of_stay", "room_id"]
        )
        # default value of due_day -> -1 for non-mandatory
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
        parameters = ["days", "skill_levels"]
        data["parameters"] = SuperDict({p: content[p] for p in parameters})
        return cls.from_dict(data)

    def to_ihtc_dict(self) -> dict:

        patients = self.data["patients"].copy_deep()
        _rows = (
            self.data["patient_shifts"]
            .values_tl()
            .to_dict(
                ["pos_shift", "workload_produced", "skill_level_required"],
                indices="patient",
            )
            .vapply(sorted)
            .vapply(TupList)
        )
        for p, elem in _rows.items():
            patients[p]["workload_produced"] = elem.take(1)
            patients[p]["skill_level_required"] = elem.take(2)

        incompatible = (
            self.data["patient_room_ban"].values_tl().to_dict("room", indices="patient")
        )
        for k, v in incompatible.items():
            patients[k]["incompatible_room_ids"] = v

        occupants = self.data["occupants"].copy_deep()
        _rows = (
            self.data["occupant_shifts"]
            .values_tl()
            .to_dict(
                ["shift", "workload_produced", "skill_level_required"],
                indices="occupant",
            )
            .vapply(sorted)
            .vapply(TupList)
        )
        for p, elem in _rows.items():
            occupants[p]["workload_produced"] = elem.take(1)
            occupants[p]["skill_level_required"] = elem.take(2)

        surgeons = self.data["surgeons"].copy_deep()
        _rows = (
            self.data["surgeon_days"]
            .values_tl()
            .to_dict(["day", "max_surgery_time"], indices="surgeon")
            .vapply(sorted)
            .vapply(TupList)
        )
        for k, v in _rows.items():
            surgeons[k]["max_surgery_time"] = v.take(1)

        theaters = self.data["operating_theaters"].copy_deep()
        _rows = (
            self.data["operating_theater_days"]
            .values_tl()
            .to_dict(["day", "availability"], indices="operating_theater")
            .vapply(sorted)
            .vapply(TupList)
        )
        for k, v in _rows.items():
            theaters[k]["availability"] = v.take(1)

        nurses = self.data["nurses"].copy_deep()
        _rows = (
            self.data["nurse_shifts"]
            .copy_deep()
            .values_tl()
            .to_dict(None, indices="nurse")
        )
        for k, v in _rows.items():
            v.vapply(lambda v: v.pop("nurse"))
            nurses[k]["working_shifts"] = v
        content = SuperDict()
        for v, k in [
            (self.data["rooms"].copy_deep(), "rooms"),
            (patients, "patients"),
            (occupants, "occupants"),
            (surgeons, "surgeons"),
            (theaters, "operating_theaters"),
            (nurses, "nurses"),
        ]:
            content[k] = v

        content = generic_to_dict(content, TABLE_KEYS)

        content["weights"] = self.data["weights"]
        content["days"] = self.data["parameters"]["days"]
        content["skill_levels"] = self.data["parameters"]["skill_levels"]
        content["shift_types"] = (
            self.data["shift_types"].values_tl().take(["pos", "id"]).sorted().take(1)
        )
        content["age_groups"] = (
            self.data["age_groups"].values_tl().take(["pos", "id"]).sorted().take(1)
        )
        return content

    def to_ihtc_json(self, path: str) -> None:
        content = self.to_ihtc_dict()
        with open(path, "w") as f:
            json.dump(content, f)
        return None

    def copy(self):
        return self.from_dict(self.to_dict())

    def get_length_day(self) -> int:
        return len(self.get_shifttypes())

    def get_horizon_size_days(self) -> int:
        return self.data["parameters"]["days"]

    def get_num_skill_levels(self) -> int:
        return self.data["parameters"]["skill_levels"]

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
        if self.__get_patients_occupants_cache is not None:
            return self.__get_patients_occupants_cache
        patients = self.get_patients().copy_deep()
        for k, v in patients.items():
            patients[k]["is_occupant"] = False
        occupants = self.get_occupants()
        my_keys = ["age_group", "gender", "length_of_stay", "id"]
        for _id, occupant in occupants.items():
            patients[_id] = SuperDict(is_occupant=True)
            for key in my_keys:
                patients[_id][key] = occupant[key]
        self.__get_patients_occupants_cache = patients
        return patients

    def get_patient_shifts(self) -> SuperDict:
        return self.data["patient_shifts"]

    def get_nurses(self) -> SuperDict:
        return self.data["nurses"]

    def get_nurse_days(self):
        return self.data["nurse_shifts"]

    def get_nurse_shift(self):
        if self.__get_nurse_shift_cache is not None:
            return self.__get_nurse_shift_cache
        nurse_info = self.get_nurse_days().values_tl().copy_deep()
        get_shift = self.get_shift_from_day_shiftype
        nurse_info.vapply_col("shift_pos", lambda v: get_shift(v["day"], v["shift"]))
        result = nurse_info.to_dict(None, indices=["nurse", "shift_pos"], is_list=False)
        self.__get_nurse_shift_cache = result
        return result

    def get_agegroups(self):
        return self.data["age_groups"]

    def get_patient_room_ban(self):
        return self.data["patient_room_ban"]

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

    def get_operatingtheaters(self):
        return self.data["operating_theaters"]

    def get_operatingtheater_capacity(self):
        return self.data["operating_theater_days"]

    def get_rooms(self):
        return self.data["rooms"]

    def get_patient_occupants_available_starts(self):

        patients = self.get_patients()
        first = patients.get_property("surgery_release_day")
        last = patients.vapply(
            lambda v: (
                v["surgery_due_day"] + 1
                if v["mandatory"]
                else self.get_horizon_size_days()
            )
        )
        patient_starts = first.sapply(range, last)
        occupants_starts = self.get_occupants().vapply(lambda v: range(0, 1))

        return SuperDict(**patient_starts, **occupants_starts)

    def get_shifts_of_day(self, day: int):
        first = self.get_first_shift_of_day(day)
        last = self.get_last_shift_of_day(day)
        return range(first, last + 1)

    def get_first_shift_of_day(self, day: int):
        length_day = 3
        return day * length_day

    def get_last_shift_of_day(self, day: int):
        length_day = 3
        return (day + 1) * length_day - 1

    def get_shift_from_day_shiftype(self, day: int, shift_type: str):
        shift_types = self.get_shifttypes()
        return self.get_first_shift_of_day(day) + shift_types[shift_type]["pos"]

    def get_day_from_shift(self, shift):
        shift_types = self.get_shifttypes()
        return shift // len(shift_types)

    def get_shiftype_from_shift(self, shift):
        shift_types = (
            self.get_shifttypes()
            .values_tl()
            .to_dict("id", indices="pos", is_list=False)
        )
        return shift_types[shift % len(shift_types)]

    def get_patients_occupants_needs(self):
        if self.__get_patients_occupants_needs_cache is not None:
            return self.__get_patients_occupants_needs_cache
        needs__p_s = self.get_patient_shifts().copy_deep()
        for elem in needs__p_s.values():
            elem["id"] = elem["patient"]
            elem.pop("patient")
            elem.pop("pos_shift")
        needs__o_s = self.get_occupant_shifts().copy_deep()
        for elem in needs__o_s.values():
            elem["id"] = elem["occupant"]
            elem.pop("occupant")
            elem.pop("shift")
        needs__p_s.update(needs__o_s)
        self.__get_patients_occupants_needs_cache = needs__p_s
        return needs__p_s

    def get_patients_occupants_available_rooms(self):
        banned_rooms = (
            self.get_patient_room_ban().values_tl().to_dict("room", indices="patient")
        )
        rooms = self.get_rooms()
        patients = self.get_patients()
        available_rooms__p = patients.kvapply(
            lambda k, v: [
                r["id"]
                for r in rooms.values()
                if r["id"] not in banned_rooms.get(k, [])
            ]
        )
        # occupants have a fixed room:
        occupants = self.get_occupants()
        occupants_rooms = occupants.get_property("room_id").vapply(lambda v: [v])
        available_rooms__p = SuperDict(**available_rooms__p, **occupants_rooms)
        return available_rooms__p.vapply(TupList)

    @staticmethod
    def solve_color_cpsat(share_shift, consecutive_shift, weight, weight2):
        model = cp_model.CpModel()
        all_nurses = (
            share_shift.keys_tl().take(0).unique()
            + share_shift.keys_tl().take(1).unique()
        ).unique()
        max_colors = round(len(all_nurses) * 0.1)
        color = {
            nurse: model.NewIntVar(0, max_colors, "color_{}".format(nurse))
            for nurse in all_nurses
        }
        color = SuperDict(color)
        violate_link = {
            (n1, n2): model.NewBoolVar(f"violate_{n1}_{n2}") for n1, n2 in share_shift
        }
        violate_link = SuperDict(violate_link)
        for n1, n2 in share_shift:
            model.Add(color[n1] != color[n2]).OnlyEnforceIf(violate_link[n1, n2].Not())
        same_color = {
            (n1, n2): model.NewBoolVar(f"same_{n1}_{n2}")
            for n1, n2 in consecutive_shift
        }
        same_color = SuperDict(same_color)
        for n1, n2 in same_color:
            model.Add(color[n1] == color[n2]).OnlyEnforceIf(same_color[n1, n2])
        # obj_var = model.NewIntVar(0, max_colors, "total_colors")
        # model.AddMaxEquality(obj_var, color.values())
        model.Minimize(
            # obj_var
            cp_model.LinearExpr.Sum((violate_link * share_shift).values()) * weight
            - cp_model.LinearExpr.Sum((same_color * consecutive_shift).values())
            * weight2
        )
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30
        solver.parameters.log_search_progress = True
        termination_condition = solver.Solve(model)
        color_sol = color.vapply(solver.Value)
        return color_sol

    @staticmethod
    def solve_color_cbc(share_shift, consecutive_shift, weight, weight2):
        model = pl.LpProblem("NurseGroups", pl.LpMinimize)
        all_nurses = (
            share_shift.keys_tl().take(0).unique()
            + share_shift.keys_tl().take(1).unique()
        ).unique()
        all_nurses.sort()
        max_colors = round(len(all_nurses) * 0.1) + 1
        nurse_color = [(n, c) for n in all_nurses for c in range(max_colors)]
        nurse_nurse = [
            (n1, n2)
            for pos, n1 in enumerate(all_nurses)
            for n2 in all_nurses[pos + 1 :]
        ]
        assign = pl.LpVariable.dicts("color", nurse_color, cat=pl.LpBinary)
        assign = SuperDict(assign)
        share_color = pl.LpVariable.dicts("assign", nurse_nurse, cat=pl.LpBinary)
        share_color = SuperDict(share_color)
        model += (
            sum((share_shift * share_color).values()) * weight
            - sum((consecutive_shift * share_color).values()) * weight2
        )
        for n in all_nurses:
            model += pl.lpSum([assign[n, c] for c in range(max_colors)]) == 1
        for n1, n2 in share_color:

            for c in range(max_colors):
                # if both nurses have the same color: activate share_color
                model += assign[n1, c] + assign[n2, c] <= 1 + share_color[n1, n2]
                # if share_color is true, then the variables should be the same
                model += (
                    assign[n1, c] - assign[n2, c]
                    <= (1 - share_color[n1, n2]) * max_colors
                )
                model += (
                    assign[n2, c] - assign[n1, c]
                    <= (1 - share_color[n1, n2]) * max_colors
                )
        solver = pl.PULP_CBC_CMD(msg=True, timeLimit=60)
        model.solve(solver)
        color_sol = (
            assign.vfilter(lambda v: v.varValue == 1)
            .keys_tl()
            .to_dict(1, is_list=False)
        )
        return color_sol

    def get_nurse_groups(self, nurse_shifts, weight, weight2):
        nurse__shift = (
            nurse_shifts.keys_tl()
            .to_dict(result_col=0)
            .vapply(sorted, key=lambda x: int(x[1:]))
        )

        share_shift = SuperDict()
        for s, nurses in nurse__shift.items():
            for pos, n1 in enumerate(nurses):
                for n2 in nurses[pos + 1 :]:
                    my_tup = n1, n2
                    if n1 > n2:
                        my_tup = n2, n1
                    if my_tup not in share_shift:
                        share_shift[my_tup] = 0
                    share_shift[my_tup] += 1

        consecutive_shift = SuperDict()
        for s, nurses in nurse__shift.items():
            for pos, n1 in enumerate(nurses):
                # we only check the following shifts as the reverse
                # should be seen from the other nurse
                # my_nurses = nurse__shift.get((s+1), []) + nurse__shift.get((s+2), [])
                my_nurses = nurse__shift.get((s + 1), [])
                for n2 in my_nurses:
                    my_tup = n1, n2
                    if n1 > n2:
                        my_tup = n2, n1
                    if my_tup not in consecutive_shift:
                        consecutive_shift[my_tup] = 0
                    consecutive_shift[my_tup] += 1
        return self.solve_color_cpsat(share_shift, consecutive_shift, weight, weight2)
        # return self.solve_color_cbc(share_shift, consecutive_shift, weight, weight2)
