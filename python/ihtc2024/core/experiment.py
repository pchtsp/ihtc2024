from pytups import SuperDict, TupList
import pandas as pd
import logging as log
import os
from .instance import Instance
from .solution import Solution
from cornflow_client.core.tools import load_json

from cornflow_client import ExperimentCore
import json, tempfile
import quarto
import subprocess


class Experiment(ExperimentCore):
    schema_checks = load_json(
        os.path.join(os.path.dirname(__file__), "../schemas/solution_checks.json")
    )

    def __init__(self, instance: Instance, solution: Solution = None):
        super().__init__(instance, solution)
        if solution is None:
            empty_solution = SuperDict(
                patient_assignment=TupList(), nurse_assignment=TupList()
            )
            solution = Solution.from_dict(empty_solution)
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
    def from_dir(
        cls,
        path: str,
        instance_file: str = "input.json",
        solution_file: str = "output.json",
    ) -> "Experiment":
        instance_path = os.path.join(path, instance_file)
        solution_path = os.path.join(path, solution_file)
        instance = Instance.from_json(instance_path)
        solution = None
        if os.path.exists(solution_path):
            solution = Solution.from_json(os.path.join(path, solution_file))
        return cls(instance, solution)

    def to_dir(
        self,
        path: str,
        instance_file: str = "input.json",
        solution_file: str = "output.json",
    ) -> None:
        instance_path = os.path.join(path, instance_file)
        solution_path = os.path.join(path, solution_file)
        if not os.path.exists(path):
            os.makedirs(path)
        self.instance.to_json(instance_path)
        self.solution.to_json(solution_path)

    @classmethod
    def from_json(cls, path: str) -> "Experiment":
        with open(path, "r") as f:
            data_json = json.load(f)
        return cls.from_dict(data_json)

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

    def calculate_coupling_checks(self):
        patients = self.instance.get_patients_occupants()
        room_usage = self.get_room_usage()
        p_gender = patients.get_property("gender")
        p_assignment = self.get_all_assignments()
        gender_err = (
            room_usage.vapply_col("gender", lambda v: p_gender[v["patient"]])
            .to_dict("gender", indices=["room", "day"])
            .vapply(set)
        )
        surgeons_cap = self.instance.get_surgeon_capacity().get_property(
            "max_surgery_time"
        )
        surgeon_use = (
            p_assignment.values_tl()
            # only new patients, not occupants
            .vfilter(lambda v: not patients[v["id"]]["is_occupant"])
            .copy_deep()
            .vapply_col("surgeon", lambda v: patients[v["id"]]["surgeon_id"])
            .vapply_col("duration", lambda v: patients[v["id"]]["surgery_duration"])
            .to_dict("duration", indices=["surgeon", "admission_day"])
            .vapply(sum)
        )
        surgeon_overtime = surgeons_cap.kvapply(lambda k, v: surgeon_use.get(k, 0) - v)
        ot_capacity = self.instance.get_operatingtheater_capacity().get_property(
            "availability"
        )
        ot_use = (
            p_assignment.values_tl()
            # only new patients, not occupants
            .vfilter(lambda v: not patients[v["id"]]["is_occupant"])
            .copy_deep()
            .vapply_col("duration", lambda v: patients[v["id"]]["surgery_duration"])
            .to_dict("duration", indices=["operating_theater", "admission_day"])
            .vapply(sum)
        )
        ot_overtime = ot_capacity.kvapply(lambda k, v: ot_use.get(k, 0) - v)

        rooms_capacity = self.instance.get_rooms().get_property("capacity")
        capacity_overuse = (
            room_usage.to_dict(indices=["room", "day"], result_col=None)
            .vapply(len)
            .kvapply(lambda k, v: v - rooms_capacity[k[0]])
        )
        return dict(
            gender=gender_err,
            surgeon_overtime=surgeon_overtime,
            ot_overtime=ot_overtime,
            capacity_overuse=capacity_overuse,
        )

    def check_solution(self, **params) -> SuperDict:

        checks = self.calculate_coupling_checks()
        patients = self.instance.get_patients_occupants()
        room_usage = self.get_room_usage()
        gender_err = checks["gender"].vapply(len).vfilter(lambda v: v > 1)
        surgeon_overtime = checks["surgeon_overtime"].vfilter(lambda v: v > 0)
        ot_overtime = checks["ot_overtime"].vfilter(lambda v: v > 0)
        capacity_overuse = checks["capacity_overuse"].vfilter(lambda v: v > 0)

        p_assignment = self.get_all_assignments()

        wrong_rooms = (
            self.instance.get_patient_room_ban()
            .keys_tl()
            .intersect(room_usage.take(["patient", "room"]))
        )

        # mandatory patients:
        mandatory_err = (
            patients.vfilter(lambda v: not patients[v["id"]]["is_occupant"])
            .vfilter(lambda v: v["mandatory"])
            .keys_tl()
            .set_diff(p_assignment.keys())
        )
        # admission day
        p_days = self.instance.get_patient_occupants_available_starts()
        admission_err = p_assignment.vfilter(
            lambda v: not patients[v["id"]]["is_occupant"]
        ).vfilter(lambda v: v["admission_day"] not in p_days[v["id"]])

        return SuperDict(
            h1=gender_err,
            h2=wrong_rooms,
            h3=surgeon_overtime,
            h4=ot_overtime,
            h5=mandatory_err,
            h6=admission_err,
            h7=capacity_overuse,
        )

    def get_workload_room(self):
        return (
            self.get_patient_shift_details()
            .values_tl()
            .to_dict("workload_produced", indices=["room", "shift", "nurse"])
            .vapply(sum)
        )

    def get_objective_terms_raw(self):
        # we leave the coupling constraints as raw as possible
        patients = self.instance.get_patients_occupants()
        room_usage = self.get_room_usage()
        age_groups = self.instance.get_agegroups().get_property("pos")
        p_agegroup = patients.get_property("age_group").vapply(lambda v: age_groups[v])
        # age groups:
        age_group_err = (
            room_usage.vapply_col("agegroup", lambda v: p_agegroup[v["patient"]])
            .to_dict("agegroup", indices=["room", "day"])
            .vapply(lambda v: (min(v), max(v)))
        )
        # minimum skill level
        nurses = self.instance.get_nurses()
        patient_solution_details = self.get_patient_shift_details()
        patient_solution_details.values_tl().vapply_col(
            "nurse_skill", lambda v: nurses[v["nurse"]]["skill_level"]
        )
        # S2
        skill_level_err = patient_solution_details.vapply(
            lambda v: max(v["skill_level_required"] - v["nurse_skill"], 0)
        ).vfilter(lambda v: v > 0)
        # S3
        continuity_err = (
            patient_solution_details.values_tl()
            .to_dict("nurse", indices="id")
            .vapply(set)
            .vapply(len)
        )

        # S4
        nurse_shift = self.instance.get_nurse_shift()
        overwork_nurse = (
            patient_solution_details.values_tl()
            .to_dict("workload_produced", indices=["nurse", "shift"])
            .vapply(sum)
        )
        overwork_nurse = nurse_shift.kvapply(
            lambda k, v: overwork_nurse.get(k, 0) - v["max_load"]
        )

        # open OTs [S5]:
        patient_assignment = self.get_all_assignments()
        ot_days = (
            patient_assignment.values_tl()
            .vfilter(lambda v: v["operating_theater"] is not None)
            .take(["operating_theater", "admission_day"])
            .unique2()
            .to_dict(None)
            .vapply(lambda v: 1)
        )

        # surgeon transfer [S6]:
        ots__s_d = (
            patient_assignment.values_tl()
            .vfilter(lambda v: v["operating_theater"] is not None)
            .copy_deep()
            .vapply_col("surgeon", lambda v: patients[v["id"]]["surgeon_id"])
            .to_dict("operating_theater", indices=["surgeon", "admission_day"])
            .vapply(set)
        )

        # admission delay [S7]
        admission_delay = (
            patient_assignment.vfilter(lambda v: v["operating_theater"]).get_property(
                "admission_day"
            )
            - patients.get_property("surgery_release_day")
        ).vfilter(lambda v: v > 0)

        # unscheduled patients [S8]:
        unscheduled_patients = (
            patients.keys_tl()
            .set_diff(patient_assignment.keys())
            .to_dict(None)
            .vapply(lambda v: 1)
        )
        return SuperDict(
            room_mixed_age=age_group_err,
            room_nurse_skill=skill_level_err,
            continuity_of_care=continuity_err,
            nurse_eccessive_workload=overwork_nurse,
            open_operating_theater=ot_days,
            surgeon_transfer=ots__s_d,
            patient_delay=admission_delay,
            unscheduled_optional=unscheduled_patients,
        )

    def get_objective_terms(self):
        terms = self.get_objective_terms_raw()

        return SuperDict(
            room_mixed_age=(
                terms["room_mixed_age"]
                .vapply(lambda v: v[1] - v[0])
                .vfilter(lambda v: v > 0)
            ),
            room_nurse_skill=terms["room_nurse_skill"],
            continuity_of_care=terms["continuity_of_care"],
            nurse_eccessive_workload=(
                terms["nurse_eccessive_workload"]
                .vapply(lambda v: max(v, 0))
                .vfilter(lambda v: v > 0)
            ),
            open_operating_theater=terms["open_operating_theater"],
            surgeon_transfer=(
                terms["surgeon_transfer"]
                .vapply(lambda v: len(v) - 1)
                .vfilter(lambda v: v > 0)
            ),
            patient_delay=terms["patient_delay"],
            unscheduled_optional=terms["unscheduled_optional"],
        )

    def get_objective(self) -> float:
        """
        A default method form, a wrapper to sum all objective components
        """
        weights = self.instance.get_weights()
        terms = self.get_objective_terms().vapply(lambda v: sum(v.values()))
        return sum((weights * terms).values())

    def generate_report(self, report_name="report") -> str:

        if not os.path.isabs(report_name):
            report_name = os.path.join(
                os.path.dirname(__file__), "../report/", report_name
            )

        return self.generate_report_quarto(quarto, report_name=report_name)

    def get_room_usage(self):
        # includes patients and occupants
        result = TupList()
        p_length = self.instance.get_patients_occupants().get_property("length_of_stay")
        p_assignment = self.get_all_assignments()
        for patient, assignment in p_assignment.items():
            for pos_d in range(p_length[patient]):
                elem = SuperDict(
                    patient=patient,
                    room=assignment["room"],
                    day=assignment["admission_day"] + pos_d,
                )
                result.append(elem)

        return result

    def get_patient_occupant_stay_days(self):
        assignment = self.get_all_assignments()
        patients = self.instance.get_patients_occupants()
        first = assignment.get_property("admission_day")
        last = first + patients.get_property("length_of_stay")
        return first.sapply(range, last)

    def get_patient_occupant_stay_shifts(self):
        get_first = self.instance.get_first_shift_of_day

        def get_last(day):
            return min(
                self.instance.get_last_shift_of_day(day) + 1,
                self.instance.get_horizon_size_shifts(),
            )

        return self.get_patient_occupant_stay_days().vapply(
            lambda v: range(get_first(v[0]), get_last(v[-1]))
        )

    def get_nurse_assignment_shift(self):
        nurse_assign = self.solution.get_nurse_assignment()

        result = SuperDict()
        for (room, day, st), content in nurse_assign.items():
            shift = self.instance.get_shift_from_day_shiftype(day, st)
            result[room, shift] = SuperDict(**content, shift_pos=shift)
        return result

    def get_patient_shift_details(self):
        patient_assignment = self.get_all_assignments()
        needs__p_s = self.instance.get_patients_occupants_needs()
        patient_occupants_shifts = self.get_patient_occupant_stay_shifts()
        nurse_shift_assignment = self.get_nurse_assignment_shift()
        result = SuperDict()
        for p, shifts in patient_occupants_shifts.items():
            room = patient_assignment[p]["room"]
            for pos, shift in enumerate(shifts):
                if (room, shift) not in nurse_shift_assignment:
                    # if we do not have a nurse, we do not have an assignment
                    continue
                nurse = nurse_shift_assignment[room, shift]["id"]
                needs__p_s[p, pos].update(
                    SuperDict(shift=shift, nurse=nurse, room=room)
                )
                result[p, shift] = needs__p_s[p, pos]
        return result

    def get_all_assignments(self):
        patients = self.solution.get_patient_assignment()
        patients = patients.copy_deep()
        occupants = self.instance.get_occupants()
        for occupant, content in occupants.items():
            patients[occupant] = SuperDict(
                id=content["id"],
                room=content["room_id"],
                admission_day=0,
                operating_theater=None,
            )
        return patients

    def run_validator(self, path_of_validator):
        with tempfile.TemporaryDirectory() as tmp:
            path_to_inst = os.path.join(tmp, "input.json")
            path_to_sol = os.path.join(tmp, "output.json")
            self.instance.to_ihtc_json(path_to_inst)
            self.solution.to_ihtc_json(path_to_sol)
            args = [os.path.abspath(path_of_validator), path_to_inst, path_to_sol]
            # pipe = None
            pipe = open(os.devnull, "w")
            # pipe = open(self.optionsDict["logPath"], "w")
            validator = subprocess.Popen(args)
            validator.wait()
            try:
                pipe.close()
            except:
                pass

    def apply_pattern(self, pattern, patient_info):
        # pattern is a list of nodes
        # I need to make the assignments for the patient: room, theater, admission
        # I need to make the assignments for nurses: per shift and room
        # I can start in node 4
        if len(pattern) == 0:
            raise ValueError("Pattern is empty")
        assignments = self.solution.get_patient_assignment()
        if len(pattern) == 2:
            # we decided to not take the patient.
            return 0
        my_node = 4
        # occupants are already assigned
        if not patient_info["is_occupant"]:
            # theater_node is position 2 I think
            theater_node = 2
            theater = pattern[theater_node].theater
            start_node = pattern[my_node]
            admission_day = start_node.shift // 3
            room = start_node.room
            patient = patient_info["id"]
            assignments[patient] = SuperDict(
                id=patient,
                admission_day=admission_day,
                room=room,
                operating_theater=theater,
            )

        new_nurse_assignments = pattern[my_node:-1]
        nurse_assignments = self.solution.get_nurse_assignment()
        get_shift_type = self.instance.get_shiftype_from_shift
        get_day = self.instance.get_day_from_shift
        for node in new_nurse_assignments:
            my_data = node.get_data()
            room = my_data["room"]
            shift = my_data["shift"]
            nurse = my_data["nurse"]
            shift_type = get_shift_type(shift)
            day = get_day(shift)
            nurse_assignments[room, day, shift_type] = SuperDict(
                id=nurse, room=room, shift=shift_type, day=day
            )
        return 1

    @staticmethod
    def set_log_config(options):
        """
        Sets logging according to options
        :param options: options dictionary
        :return: None
        """
        level = log.INFO
        if options.get("msg", False):
            level = log.DEBUG
        logFile = options.get("logPath")
        open(logFile, "w").close()
        logFormat = "%(asctime)s %(levelname)s:%(message)s"
        formatter = log.Formatter(logFormat)

        # to file:
        file_log_handler = log.FileHandler(logFile, "a")
        file_log_handler.setFormatter(formatter)

        # to command line
        stderr_log_handler = log.StreamHandler()
        stderr_log_handler.setFormatter(formatter)

        outputs = {"file": file_log_handler, "console": stderr_log_handler}
        output_choices = options.get("logOutput", ["file"])

        _log = log.getLogger()
        _log.handlers = [v for k, v in outputs.items() if k in output_choices]

        # option to add a custom handler:
        custom_handler = options.get("log_handler")
        if custom_handler:
            custom_handler.setFormatter(formatter)
            _log.handlers.append(custom_handler)

        _log.setLevel(level)
