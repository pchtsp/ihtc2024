from .. import Solution, Instance
from ..core.experiment import Experiment
from ortools.sat.python import cp_model
import random as rn
import os
import sys
from ..core.tools import print_time
import time
from contextlib import contextmanager
from collections import deque
import json
import logging as log

from pytups import SuperDict, TupList

from cornflow_client.constants import (
    STATUS_OPTIMAL,
    STATUS_INFEASIBLE,
    STATUS_UNDEFINED,
    SOLUTION_STATUS_FEASIBLE,
    SOLUTION_STATUS_INFEASIBLE,
)

my_sum = cp_model.LinearExpr.Sum

my_vars_type = dict[str, SuperDict[tuple, cp_model.LinearExpr]]

status_conv = {
    cp_model.OPTIMAL: STATUS_OPTIMAL,
    cp_model.FEASIBLE: STATUS_OPTIMAL,
    cp_model.INFEASIBLE: STATUS_INFEASIBLE,
    cp_model.UNKNOWN: STATUS_UNDEFINED,
    cp_model.MODEL_INVALID: STATUS_UNDEFINED,
}


class CpSAT(Experiment):
    init: float
    rooms_id: dict
    nurses_id: dict

    def __init__(self, instance: Instance, solution: Solution = None):
        Experiment.__init__(self, instance, solution)
        self.rooms_id = self.get_rooms_with_id()
        self.nurses_id = self.get_nurses_with_id()
        self.init = time.time()

    def print_time(self, msg):
        print_time(self.init, msg)
        log.info(msg)

    def warm_start(self, model, my_vars: my_vars_type):
        patient_assignments = self.solution.get_patient_assignment()
        ob_raw = self.get_objective_terms_raw()
        rooms = self.rooms_id
        nurses = self.nurses_id
        admission_bin = my_vars["admission_bin"]
        room_binary = my_vars["room_binary"].vfilter(lambda v: not type(v) == int)
        theater_bin = my_vars["theater_bin"]
        open__ot_d = my_vars["open__ot_d"]
        max_age_diff = my_vars["max_age_diff"]
        worked__s_ot_d = my_vars["worked__s_ot_d"]

        nurse_bin__n_r_s = my_vars.get("nurse_bin__n_r_s")
        nurse_overwork__n_s = my_vars.get("nurse_overwork__n_s")
        nurse_patient__n_p = my_vars.get("nurse_patient__n_p")
        skill_diff__p_s = my_vars.get("skill_diff__p_s")

        model.ClearHints()
        my_values = patient_assignments.values_tl()
        admission_hint = my_values.take(["id", "admission_day"])
        room_hint = my_values.take(["id", "room"]).vapply(
            lambda v: (v[0], rooms[v[1]]["pos"])
        )
        theater_hint = my_values.take(["id", "operating_theater"])

        def add_hint_binary(my_var, my_tup_list: TupList):
            # all available values are 1
            my_tup_list.vapply(lambda v: model.AddHint(my_var[v], 1))
            # all non available values are 0
            my_var.keys_tl().set_diff(my_tup_list).vapply(
                lambda v: model.AddHint(my_var[v], 0)
            )

        def add_hint_value(my_var, my_dict: SuperDict):
            # all available values are 1
            my_dict.kvapply(lambda k, v: model.AddHint(my_var[k], v))
            # all non available values are 0
            my_var.keys_tl().set_diff(my_dict.keys()).vapply(
                lambda v: model.AddHint(my_var[v], 0)
            )

        add_hint_binary(admission_bin, admission_hint)
        add_hint_binary(room_binary, room_hint)
        add_hint_binary(theater_bin, theater_hint)
        add_hint_binary(open__ot_d, ob_raw["open_operating_theater"].keys_tl())
        transfer_hint = (
            ob_raw["surgeon_transfer"].vapply(list).to_tuplist().take([0, 2, 1])
        )
        add_hint_binary(worked__s_ot_d, transfer_hint)

        mixed_age_hint = (
            ob_raw["room_mixed_age"]
            .vapply(lambda v: v[1] - v[0])
            .to_tuplist()
            .vapply(lambda v: (rooms[v[0]]["pos"], v[1], v[2]))
            .to_dict(2, is_list=False)
        )
        add_hint_value(max_age_diff, mixed_age_hint)

        if nurse_bin__n_r_s:
            nurse_hint = (
                self.get_nurse_assignment_shift_ints().to_tuplist().take([2, 0, 1])
            )
            add_hint_binary(nurse_bin__n_r_s, nurse_hint)

        if skill_diff__p_s:
            add_hint_value(skill_diff__p_s, ob_raw["room_nurse_skill"])

        if nurse_patient__n_p:
            continuity_hint = (
                ob_raw["continuity_of_care"]
                .vapply(list)
                .to_tuplist()
                .vapply(lambda v: (nurses[v[1]]["pos"], v[0]))
            )
            add_hint_binary(nurse_patient__n_p, continuity_hint)

        if nurse_overwork__n_s:
            nurse_overwork_hint = (
                ob_raw["nurse_eccessive_workload"]
                .vapply(lambda v: max(v, 0))
                .to_tuplist()
                .vapply(lambda v: (nurses[v[0]]["pos"], v[1], v[2]))
                .to_dict(2, is_list=False)
            )
            add_hint_value(nurse_overwork__n_s, nurse_overwork_hint)

    def get_objective_function(self, model, my_vars):

        patients = self.instance.get_patients()
        weights = self.instance.get_weights()

        admission_bin = my_vars["admission_bin"]
        open__ot_d = my_vars["open__ot_d"]
        worked__s_ot_d = my_vars["worked__s_ot_d"]
        max_age_diff = my_vars["max_age_diff"]

        # optional variables (nurse)
        skill_diff__p_s = my_vars.get("skill_diff__p_s")
        nurse_patient__n_p = my_vars.get("nurse_patient__n_p")
        nurse_overwork__n_s = my_vars.get("nurse_overwork__n_s")
        nurses_part = 0
        if nurse_patient__n_p and nurse_overwork__n_s and skill_diff__p_s:
            nurses_part = (
                # S2
                my_sum(skill_diff__p_s.values()) * weights["room_nurse_skill"]
                +
                # S3
                my_sum(nurse_patient__n_p.values()) * weights["continuity_of_care"]
                # S4
                + my_sum(nurse_overwork__n_s.values())
                * weights["nurse_eccessive_workload"]
            )
        first = patients.get_property("surgery_release_day")
        optional = patients.vfilter(lambda v: not v["mandatory"]).keys()
        model.Minimize(
            # S1
            my_sum(max_age_diff.values()) * weights["room_mixed_age"]
            +
            # S5
            my_sum(open__ot_d.values()) * weights["open_operating_theater"]
            +
            # S6
            my_sum(worked__s_ot_d.values()) * weights["surgeon_transfer"]
            # S7
            + my_sum(
                admission_bin.kvapply(lambda k, v: v * (k[1] - first[k[0]])).values()
            )
            * weights["patient_delay"]
            # S8
            + len(optional) * weights["unscheduled_optional"]
            - my_sum(admission_bin.kfilter(lambda k: k[0] in optional).values())
            * weights["unscheduled_optional"]
            + nurses_part
        )
        return None

    def solve(self, options: dict = None) -> dict:
        options = dict(options)
        options["seed"] = options.get("seed", 42)
        rn.seed(options["seed"])
        VERBOSE = options.get("msg", False)
        options["timeWindow"] = TIME_WINDOW = self.setup_tw(options.get("timeWindow"))
        TIME_LIMIT = options.get("timeLimit", 100)
        WARM_START = options.get("warmStart", False)
        MAX_SAMPLE_OPTIONS = options.get("maxSample", [None])
        if VERBOSE:
            self.print_time("Building of model starts")

        solver = cp_model.CpSolver()
        # for max_sample in MAX_SAMPLE_OPTIONS:
        options["maxSample"] = MAX_SAMPLE_OPTIONS[0]
        if VERBOSE:
            self.print_time(f"Phase1: maxSample: {options["maxSample"]}")

        model = cp_model.CpModel()
        if VERBOSE:
            self.print_time("Non nurse constraints")
        my_vars = self.add_non_nurse_constraints(model, options)
        if VERBOSE:
            self.print_time("Nurse constraints")
        my_vars = self.add_nurse_constraints2(model, my_vars, options)
        if VERBOSE:
            self.print_time("Objective function")
        self.get_objective_function(model, my_vars)
        if self.solution and (TIME_WINDOW or WARM_START):
            self.warm_start(model, my_vars)
        if options.get("dump_vars"):
            model.ExportToFile("model.txt")
        status = self.call_solver(model, solver, options)
        if options.get("dump_vars"):
            self.dump_vars(model, solver, my_vars)

        if options.get("msg", False):
            self.print_time(f"Model finished with status {status_conv.get(status)}")

        if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            if VERBOSE:
                self.print_time("No solution was found")
            return dict(
                status=status_conv.get(status),
                status_sol=SOLUTION_STATUS_INFEASIBLE,
            )

        sol_data = self.my_vars_to_solution(solver, my_vars)
        self.solution = Solution.from_dict(sol_data)
        self.get_objective_function(model, my_vars)

        return dict(status=status_conv.get(status), status_sol=SOLUTION_STATUS_FEASIBLE)

    def call_solver(self, model, solver, options):

        errors = model.Validate()
        if errors:
            if options.get("msg", False):
                self.print_time(errors)

            raise ValueError("Model not formulated correctly")
        if options.get("msg", False):
            solver.parameters.log_search_progress = True
        solver.parameters.max_time_in_seconds = options.get("timeLimit", 10)
        if "threads" in options:
            solver.parameters.num_search_workers = options["threads"]
        if "fixSolution" in options:
            solver.parameters.fix_variables_to_their_hinted_value = True
        if "warmStart" in options or "timeWindow" in options:
            solver.parameters.repair_hint = True
        stop_condition = options.get("stop_condition")
        if stop_condition is None:
            solution_callback = None
        else:
            if stop_condition.get("ma_size") is None:
                stop_condition = dict(ma_size=20, min_imp_per_sec=5, length_bad_imp=20)
            solution_callback = StopOnMovingAverageImprovement(**stop_condition)

        # if options.get("msg", False):
        #     solution_callback = VarArraySolutionPrinter()

        if options.get("msg", False):
            self.print_time("Solver starts")

        path_of_log = options.get("logPath")
        if path_of_log is not None:
            if not os.path.exists(path_of_log):
                open(path_of_log, "w").close()
            with open(path_of_log, "a") as f, stdout_redirected(f):
                return solver.Solve(model, solution_callback)
        else:
            return solver.Solve(model, solution_callback)

    def sample_starts_rooms(self, possible_start, available_rooms__p, MAX_SAMPLE):
        patients = self.instance.get_patients()

        def sample_range(day_range):
            my_sample = rn.sample(day_range, k=min(MAX_SAMPLE, len(day_range)))
            return sorted(my_sample)

        def sample_patient(patient, day_range):
            # occupants get their fixed range
            if patient not in patients:
                return day_range
            # mandatory patients get their full range
            if patients[patient].get("mandatory", True):
                return day_range
            return sample_range(day_range)

        possible_start = possible_start.kvapply(sample_patient)
        available_rooms__p = available_rooms__p.vapply(sample_range)
        # TODO: if a solution is available, we're sure to add all current assignments
        #  as possibilities
        return possible_start, available_rooms__p

    def get_nurse_assignment_shift_ints(self):
        rooms = self.rooms_id
        nurses = self.nurses_id

        return (
            self.get_nurse_assignment_shift()
            .get_property("id")
            .to_tuplist()
            .vapply(lambda v: (rooms[v[0]]["pos"], v[1], nurses[v[2]]["pos"]))
            .to_dict(2, is_list=False)
        )

    def tw_limit_nurse_assignments(self, TIME_WINDOW, p_o_start, domain_n__r_s):
        start = TIME_WINDOW["start"]
        end = start + TIME_WINDOW["size"] - 1
        first_shift = self.instance.get_first_shift_of_day(start)
        horizon_last_shift = self.instance.get_last_shift_horizon()
        # last_shift = min(self.instance.get_last_shift_of_day(end), horizon_last_shift)

        patients_occupants = self.instance.get_patients_occupants()
        l_o_s = patients_occupants.get_property("length_of_stay")
        last_relevant_shift__p = (
            # we get the last possible starts inside the window
            p_o_start.kfilter(lambda k: k[1] < end)
            .to_tuplist()
            .to_dict(1, indices=0)
            .vapply(max)
            # we project it into the future with the length of stay
            .kvapply(lambda k, v: (v + l_o_s[k] - 1) * 3)
            .vapply(lambda v: min(v, horizon_last_shift))
        )
        last_last_possible = max(last_relevant_shift__p.values())
        nurse_assignment = self.get_nurse_assignment_shift_ints()

        def get_nurses(rs, v):
            if first_shift <= rs[1] <= last_last_possible:
                return v
            if rs in nurse_assignment:
                return [nurse_assignment[rs]]
            return []

        new_domain_n__r_s = domain_n__r_s.kvapply(get_nurses)
        # We do not filter domain__p_s because it's calculated from admission_bin already

        return new_domain_n__r_s

    def setup_tw(self, TIME_WINDOW):
        if TIME_WINDOW is None:
            return None
        size = TIME_WINDOW.get("size")
        start = TIME_WINDOW.get("start")
        if start is None:
            max_start = max(0, self.instance.get_horizon_size_days() - size)
            start = rn.randint(0, max_start)
        else:
            size = min(size, self.instance.get_horizon_size_days() - start)
        return dict(start=start, size=size)

    def tw_limit_starts_rooms(
        self, possible_start, available_rooms__p, available_ot__p, TIME_WINDOW
    ):
        start = TIME_WINDOW["start"]
        size = TIME_WINDOW["size"]
        patients = self.instance.get_patients()
        window = range(start, start + size)
        assignments = self.solution.get_patient_assignment().copy_deep()
        patients_in_tw = assignments.vfilter(
            lambda v: v["admission_day"] in window
        ).keys_tl()

        def intersect_range(x, y):
            if not len(x) or not len(y):
                return []
            return range(max(x[0], y[0]), min(x[-1], y[-1]) + 1)
            # return list(set(day_range) & set(window))

        def fix_starts(patient, day_range):
            # patient is occupant
            if patient not in patients:
                return day_range
            # the passenger is inside the tw
            # or the patient is not scheduled
            if patient in patients_in_tw or patient not in assignments:
                return intersect_range(day_range, window)

            # the patient's possibilities are equal to the previous solution
            return [assignments[patient]["admission_day"]]

        def fix_ref(patient, room_range, ref):
            # the passenger is inside the tw
            # or the patient is not scheduled
            # or patient is occupant
            if (
                patient in patients_in_tw
                or patient not in assignments
                or patient not in patients
            ):
                # we do not fix
                return room_range

            # the patient's possibilities are equal to the previous solution
            return [assignments[patient][ref]]

        # we need to be sure that a patient that cannot start in the time window,
        # cannot be assigned a room:
        new_possible_start = possible_start.kvapply(fix_starts).vfilter(lambda v: v)
        new_available_rooms__p = available_rooms__p.kvapply(fix_ref, ref="room").filter(
            new_possible_start
        )
        new_available_ot__p = available_ot__p.kvapply(
            fix_ref, ref="operating_theater"
        ).filter(new_possible_start)

        return new_possible_start, new_available_rooms__p, new_available_ot__p

    def add_non_nurse_constraints(
        self, model: cp_model.CpModel, options=None
    ) -> my_vars_type:
        options = options or {}
        VERBOSE = options.get("msg", False)
        if VERBOSE:
            self.print_time("Getting parameters")

        possible_start = self.instance.get_patient_occupants_available_starts()
        available_rooms__p = self.instance.get_patients_occupants_available_rooms()
        operation_theaters = self.instance.get_operatingtheaters().copy_deep()
        for pos, _theater in enumerate(operation_theaters.values()):
            _theater["pos"] = pos

        available_ot__p = SuperDict(
            {p: operation_theaters.keys_tl() for p in possible_start}
        )

        MAX_SAMPLE = options.get("maxSample")

        # here I will edit my_vars to fix everything
        #  that is not happening inside the time window
        #  I may need to fill the fixed nurse variables

        TIME_WINDOW = options.get("timeWindow")
        WARM_START = options.get("warmStart")

        if TIME_WINDOW is not None and self.solution is not None:
            possible_start, available_rooms__p, available_ot__p = (
                self.tw_limit_starts_rooms(
                    possible_start, available_rooms__p, available_ot__p, TIME_WINDOW
                )
            )

        # we sample the possible starts and available rooms per patient
        if MAX_SAMPLE is not None:
            possible_start, available_rooms__p = self.sample_starts_rooms(
                possible_start, available_rooms__p, MAX_SAMPLE
            )

            if self.solution and (TIME_WINDOW or WARM_START):
                # we make sure that the current patient assignments are part of the domain
                solution = self.solution.get_patient_assignment().values_tl()
                add_starts = (
                    solution.take(["id", "admission_day"]).to_dict(1).vapply(set)
                )
                add_rooms = solution.take(["id", "room"]).to_dict(1).vapply(set)
                possible_start = (
                    possible_start.vapply(set)
                    .kvapply(lambda k, v: v | add_starts.get(k, set()))
                    .vapply(list)
                )
                available_rooms__p = (
                    available_rooms__p.vapply(set)
                    .kvapply(lambda k, v: v | add_rooms.get(k, set()))
                    .vapply(list)
                )

        patients_occupants = self.instance.get_patients_occupants().filter(
            possible_start
        )

        occupants = patients_occupants.vfilter(lambda v: v["is_occupant"])
        patients = patients_occupants.vfilter(lambda v: not v["is_occupant"])

        surgery_duration = patients.get_property("surgery_duration")
        ot_cap = (
            self.instance.get_operatingtheater_capacity()
            .get_property("availability")
            .to_dictdict()
        )
        rooms = self.rooms_id
        horizon_days_size = self.instance.get_horizon_size_days()

        patients__s = (
            patients.get_property("surgeon_id").vapply(lambda v: [v]).list_reverse()
        )

        surgeons_cap = (
            self.instance.get_surgeon_capacity()
            .get_property("max_surgery_time")
            .to_dictdict()
        )

        # admission_binary
        # only patients can be admitted
        if VERBOSE:
            self.print_time("Variables")

        admission_bin = SuperDict(
            {
                (p, d): model.NewBoolVar(name=f"admission_bin_{p}_{d}")
                for p, days in possible_start.items()
                for d in days
                if p in patients
            }
        )
        admission_p = (
            admission_bin.keys_tl()
            .to_dict(1)
            .kvapply(
                lambda k, v: (
                    model.NewIntVarFromDomain(
                        cp_model.Domain.FromValues(values=v), name=f"admission_{k}"
                    )
                )
            )
        )
        # occupants start at 0
        #  we care because we use admission for intervals
        for o in occupants:
            admission_p[o] = 0
        for p, d in admission_bin:
            model.Add(admission_p[p] == d).OnlyEnforceIf(admission_bin[p, d])
            # we cannot add this one because it leads to infeasible solutions
            # when there are optional patients
            # model.Add(admission_p[p] != d).OnlyEnforceIf(
            #     negate_var_bool(admission_bin[p, d])
            # )

        theater_bin = SuperDict(
            {
                (p, ot): model.NewBoolVar(name=f"theater_bin_{p}_{ot}")
                for p, ots in available_ot__p.items()
                for ot in ots
            }
        )

        available_rooms__p = available_rooms__p.vapply(
            lambda v: TupList(rooms[vv]["pos"] for vv in v)
        )

        # variable
        # occupants have a fixed room
        room_binary = (
            available_rooms__p.to_tuplist()
            .to_dict(None)
            .vapply(
                lambda v: (
                    model.NewBoolVar(name=f"room_{v[0]}_{v[1]}")
                    if v[0] in patients
                    else 1
                )
            )
        )

        length_of_stay = patients_occupants.get_property("length_of_stay")

        # this will calculate the usage of the theater by patients
        domain__ot_p_d = TupList(
            (ot, p, d)
            for p, days in possible_start.items()
            for d in days
            if p in patients
            for ot in available_ot__p[p]
            # there needs to be enough available capacity in the operating room
            if surgery_duration[p] <= ot_cap[ot][d]
            # and for the surgeon
            if surgery_duration[p] <= surgeons_cap[patients[p]["surgeon_id"]][d]
        )

        assigned__ot_p_d = SuperDict(
            {
                (ot, p, d): model.NewBoolVar(
                    name=f"ot_assigned_{ot}_{p}_{d}",
                )
                for ot, p, d in domain__ot_p_d
            }
        )

        # binary if surgeon works in ot in day d
        worked__s_ot_d = SuperDict(
            {
                (s, ot, d): model.NewBoolVar(name=f"worked_{s}_{ot}_{d}")
                for s, capacities in surgeons_cap.items()
                for d, cap in capacities.items()
                if cap > 0
                for ot in ot_cap
                if ot_cap[ot][d] > 0
            }
        )

        # ot is open (S5)
        open__ot_d = SuperDict(
            {
                (ot, d): model.NewBoolVar(name=f"open_{ot}_{d}")
                for ot, days in ot_cap.items()
                for d in days
                if ot_cap[ot][d] > 0
            }
        )

        # definition
        # https://groups.google.com/g/or-tools-discuss/c/9trLOMSe_DA
        for ot, p, d in domain__ot_p_d:
            multiple_ands(
                model,
                assigned__ot_p_d[ot, p, d],
                admission_bin[p, d],
                theater_bin[p, ot],
            )
            s = patients[p]["surgeon_id"]
            # if surgeon cannot work on that day:
            # we cannot assign the theater to the patient
            if (s, ot, d) not in worked__s_ot_d:
                model.Add(admission_bin[p, d] + theater_bin[p, ot] <= 1)
            else:
                model.AddBoolOr(
                    worked__s_ot_d[s, ot, d],
                    admission_bin[p, d].Not(),
                    theater_bin[p, ot].Not(),
                )
                # the ot is open in day d if a patient is using it in that day
                model.AddBoolOr(
                    open__ot_d[ot, d],
                    admission_bin[p, d].Not(),
                    theater_bin[p, ot].Not(),
                )

        # if we do not have a domain for ot, p, d:
        # then admission or theater needs to be 0
        domain__ot_p_d_set = set(domain__ot_p_d)
        for (p, d), v in admission_bin.items():
            for ot in available_ot__p[p]:
                if (ot, p, d) not in domain__ot_p_d_set:
                    model.Add(admission_bin[p, d] + theater_bin[p, ot] <= 1)

        # H2
        if VERBOSE:
            self.print_time("H2 constraints")

        # patients that are mandatory will always have a room.
        # occupants are considered mandatory (so default: True)
        gender = patients_occupants.get_property("gender")

        if VERBOSE:
            self.print_time("H1 constraints prep1")

        if VERBOSE:
            self.print_time("H1 constraints prep2")

        if VERBOSE:
            self.print_time("H1 constraints actual")
        # we create an interval per patient-room
        patient_room_interval = SuperDict()
        for p, r in room_binary:
            patient_room_interval[p, r] = model.NewOptionalFixedSizeIntervalVar(
                start=admission_p[p],
                size=length_of_stay[p],
                is_present=room_binary[p, r],
                name=f"interval_{p}_{r}",
            )

        # room capacity
        if VERBOSE:
            self.print_time("Room capacity constraints")

        room_capacity = rooms.values_tl().to_dict(
            "capacity", indices="pos", is_list=False
        )
        p__room = room_binary.keys_tl().to_dict(0).vapply(set)
        p__gender = gender.vapply(lambda v: [v]).list_reverse().vapply(set)
        # here we want to split patients by gender
        # and then create a AddCumulative per room-gender-patientsOfOppositeGender
        # with [all in gender A] + [one in gender B]*capacity <= capacity
        for r, capacity in room_capacity.items():
            for gender, __patients in p__gender.items():
                cap_1 = __patients & p__room[r]
                others = p__room[r] - __patients
                my_intervals = [patient_room_interval[p, r] for p in cap_1]
                # all intervals of gender A consume 1
                # + each interval of gender B consumes "capacity"
                # meaning: I can put at most #capacity gender A intervals
                # but if I put 1 gender B, I cannot put ANY gender A intervals
                for other in others:
                    __my_intervals = my_intervals + [patient_room_interval[other, r]]
                    model.AddCumulative(
                        __my_intervals,
                        [1] * len(my_intervals) + [capacity],
                        capacity,
                    )

        # S1
        if VERBOSE:
            self.print_time("S1 constraints")

        agegroups = self.instance.get_agegroups()
        age_group = patients_occupants.get_property("age_group").vapply(
            lambda v: agegroups[v]["pos"]
        )
        all_age_groups = age_group.values_tl().unique()
        min_ag, max_ag = min(all_age_groups), max(all_age_groups)
        num_ages = len(set(age_group.values_tl()))
        all_rooms = room_binary.keys_tl().take(1).unique()

        max_age_diff = SuperDict()
        min_age = SuperDict()
        max_age = SuperDict()

        for r in all_rooms:
            for d in range(horizon_days_size):
                __dif = model.NewIntVar(0, num_ages - 1, name=f"max_age_diff_{r}_{d}")
                __min = model.NewIntVar(min_ag, max_ag, name=f"min_age_{r}_{d}")
                __max = model.NewIntVar(min_ag, max_ag, name=f"max_age_{r}_{d}")
                max_age_diff[r, d] = __dif
                min_age[r, d] = __min
                max_age[r, d] = __max

        age_group = patients_occupants.get_property("age_group").vapply(
            lambda v: agegroups[v]["pos"]
        )

        # if admission on day d and patient in room r => calculate max/min age in days d2
        p_o_start = SuperDict({(o, 0): 1 for o in occupants})
        p_o_start.update(admission_bin)
        rooms_p = room_binary.keys_tl().to_dict(1)
        for p, d in p_o_start:
            last_date = min(d + length_of_stay[p], horizon_days_size)
            for d2 in range(d, last_date):
                for r in rooms_p[p]:
                    model.Add(max_age[r, d2] >= age_group[p]).OnlyEnforceIf(
                        p_o_start[p, d], room_binary[p, r]
                    )
                    model.Add(min_age[r, d2] <= age_group[p]).OnlyEnforceIf(
                        p_o_start[p, d], room_binary[p, r]
                    )

        for r, d in max_age_diff:
            model.Add(max_age_diff[r, d] == max_age[r, d] - min_age[r, d])

        # H3
        if VERBOSE:
            self.print_time("H3 constraints")

        for surgeon, capacities in surgeons_cap.items():
            _patients = patients__s[surgeon]
            for day, capacity in capacities.items():
                # here I sum all the durations of patients in that day
                _content = [
                    admission_bin.get((p, day), 0) * surgery_duration[p]
                    for p in _patients
                ]
                model.Add(my_sum(_content) <= capacity)
        # H4
        if VERBOSE:
            self.print_time("H4 constraints")

        for ot, capacities in ot_cap.items():
            for d, capacity in capacities.items():
                _content = [
                    assigned__ot_p_d.get((ot, p, d), 0) * surgery_duration[p]
                    for p in patients
                ]
                model.Add(my_sum(_content) <= capacity)
        #  H5
        if VERBOSE:
            self.print_time("H5 constraints")

        for p, patient in patients.items():
            all_admissions = my_sum([admission_bin[p, d] for d in possible_start[p]])
            all_rooms = my_sum([room_binary[p, r] for r in available_rooms__p[p]])
            all_theaters = my_sum([theater_bin[p, ot] for ot in available_ot__p[p]])
            if patient["mandatory"]:
                model.Add(all_admissions == 1)
                model.Add(all_rooms == 1)
                model.Add(all_theaters == 1)
            else:
                model.Add(all_admissions <= 1)
                # if we admit a patient, we assign 1 theater and 1 room
                model.Add(all_rooms == all_admissions)
                model.Add(all_theaters == all_admissions)

        my_vars = dict(
            admission_bin=admission_bin,
            theater_bin=theater_bin,
            room_binary=room_binary,
            open__ot_d=open__ot_d,
            worked__s_ot_d=worked__s_ot_d,
            max_age_diff=max_age_diff,
        )

        return my_vars

    def add_nurse_constraints2(
        self, model: cp_model.CpModel, my_vars: my_vars_type, options: dict
    ) -> my_vars_type:
        patients_occupants = self.instance.get_patients_occupants()
        occupants = patients_occupants.vfilter(lambda v: v["is_occupant"])
        rooms = self.rooms_id
        nurses = self.nurses_id

        nurse_shifts = self.instance.get_nurse_shift()
        needs__p_sPos = self.instance.get_patients_occupants_needs()
        last_shift = self.instance.get_last_shift_horizon()

        skill_level__p_sPos = needs__p_sPos.get_property("skill_level_required")
        workload__p_posShift = needs__p_sPos.get_property("workload_produced")
        positions_p = needs__p_sPos.keys_tl().to_dict(1).vapply(len)

        admission_bin = my_vars["admission_bin"]
        room_binary = my_vars["room_binary"]
        rooms__p = room_binary.keys_tl().to_dict(1)
        Options_wl__p = (
            workload__p_posShift.to_tuplist()
            .to_dict(2, indices=0)
            .vapply(lambda v: v.unique2() + [0])
        )
        MaxWL__p = Options_wl__p.vapply(max)

        nurses__s = (
            nurse_shifts.values_tl()
            .copy_deep()
            .vapply_col("nurse_pos", lambda v: nurses[v["nurse"]]["pos"])
            .to_dict("nurse_pos", indices="shift_pos")
        )
        domain_n__r_s = SuperDict(
            ((r["pos"], shift), _nurses)
            for r in rooms.values()
            for shift, _nurses in nurses__s.items()
        )
        # admission_bin doesn't include occupants.
        # I correct it here to add them:
        p_o_start = SuperDict({(o, 0): 1 for o in occupants})
        p_o_start.update(admission_bin)
        possible_start = p_o_start.keys_tl().to_dict(1)
        possible_stay = self.get_stay_options_from_starts(possible_start)
        __s = self.instance.get_shifts_of_day

        domain__p_s = TupList(
            (p, s) for p, days in possible_stay.items() for d in days for s in __s(d)
        )

        TIME_WINDOW = options.get("timeWindow")
        MAX_SAMPLE = options.get("maxSampleN")
        WARM_START = options.get("warmStart")
        if TIME_WINDOW:
            domain_n__r_s = self.tw_limit_nurse_assignments(
                TIME_WINDOW, p_o_start, domain_n__r_s
            )

        if MAX_SAMPLE:

            def sample_range(nurse_range):
                my_sample = rn.sample(nurse_range, k=min(MAX_SAMPLE, len(nurse_range)))
                return my_sample

            domain_n__r_s = domain_n__r_s.vapply(sample_range)
            if self.solution and (TIME_WINDOW or WARM_START):
                # we guarantee that the current nurse assignment is included in the domain
                nurse_sol = self.get_nurse_assignment_shift_ints().vapply(lambda v: {v})
                domain_n__r_s = (
                    domain_n__r_s.vapply(set)
                    .kvapply(lambda k, v: v | nurse_sol.get(k, set()))
                    .vapply(list)
                )

        domain__n_r_s = domain_n__r_s.to_tuplist().vapply(lambda v: (v[2], v[0], v[1]))
        n__r_s = domain_n__r_s

        nurse_max_load__n_s = (
            nurse_shifts.values_tl()
            .copy_deep()
            .vapply_col("nurse_pos", lambda v: nurses[v["nurse"]]["pos"])
            .to_dict("max_load", indices=["nurse_pos", "shift_pos"], is_list=False)
        )
        domain_n_p_s = TupList((n, p, s) for p, s in domain__p_s for n in nurses__s[s])
        domain_n_p_s__n_s = domain_n_p_s.to_dict(1)
        domain__n_p = domain_n_p_s.take([0, 1]).unique2()

        nurses_skill_level = nurses.values_tl().to_dict(
            "skill_level", indices="pos", is_list=False
        )
        max_skill_level = max(nurses_skill_level.values())

        nurse_bin__n_r_s = SuperDict(
            {
                (n, r, s): model.NewBoolVar(name=f"nurse_bin_{n}_{r}_{s}")
                for n, r, s in domain__n_r_s
            }
        )

        skill_diff__p_s = domain__p_s.to_dict(None).kapply(
            lambda k: model.NewIntVar(
                0, max_skill_level, name=f"skill_diff_{k[0]}_{k[1]}"
            )
        )

        nurse_overwork__n_s = domain_n_p_s__n_s.vapply(
            lambda _patients: sum(MaxWL__p[p] for p in _patients)
        ).kvapply(lambda k, v: model.NewIntVar(0, v, name=f"overwork_{k[0]}_{k[1]}"))
        # TODO: I can constraint a bit better the occupants values, depending on the shift
        patient_nurse_workload__n_p_s = domain_n_p_s.to_dict(None).vapply(
            lambda v: (
                model.NewIntVarFromDomain(
                    cp_model.Domain.FromValues(values=Options_wl__p[v[1]]),
                    name=f"workload_{v[0]}_{v[1]}_{v[2]}",
                )
                if not patients_occupants[v[1]]["is_occupant"]
                else model.NewIntVarFromDomain(
                    cp_model.Domain.FromValues(
                        values=[workload__p_posShift[v[1], v[2]], 0]
                    ),
                    name=f"workload_{v[0]}_{v[1]}_{v[2]}",
                )
            )
        )
        nurse_patient__n_p = SuperDict(
            {
                (n, p): model.NewBoolVar(name=f"nurse_patient_{n}_{p}")
                for n, p in domain__n_p
            }
        )

        # if a patient is in a room, then a nurse needs to be assigned.

        # this is a very big constraint/domain
        self.print_time("Building big domain for p_d_s_ps_r")
        __s = lambda day, posShift: day * 3 + posShift
        shifts__p_d = p_o_start.kapply(
            lambda k: [
                (pS, shift)
                for pS in range(positions_p[k[0]])
                if (shift := __s(k[1], pS)) <= last_shift
            ]
        )
        patient_day_shift_pos_room = [
            (p, d, shift, pS, r)
            for p, d in p_o_start
            for pS, shift in shifts__p_d[p, d]
            for r in rooms__p[p]
        ]
        for p, d, s, _, r in patient_day_shift_pos_room:
            # if there's a patient in a room in a shift, we need exactly one nurse
            model.Add(
                my_sum([nurse_bin__n_r_s[n, r, s] for n in n__r_s.get((r, s), [])]) == 1
            ).OnlyEnforceIf(p_o_start[p, d], room_binary[p, r])
        self.print_time(f"size of semibig domain: {len(patient_day_shift_pos_room)}")

        self.print_time("Building big domain for p_d_s_ps_r_n")
        patient_day_shift_pos_room_nurse = [
            (p, d, s, pS, r, n)
            for p, d, s, pS, r in patient_day_shift_pos_room
            for n in n__r_s.get((r, s), [])
        ]
        self.print_time(f"size of big domain: {len(patient_day_shift_pos_room_nurse)}")
        self.print_time("Most nurse constraints")
        for p, d, s, pS, r, n in patient_day_shift_pos_room_nurse:
            # skill difference definition
            model.Add(
                skill_diff__p_s[p, s]
                >= skill_level__p_sPos[p, pS] - nurses_skill_level[n]
            ).OnlyEnforceIf(
                p_o_start[p, d], nurse_bin__n_r_s[n, r, s], room_binary[p, r]
            )
            model.Add(
                patient_nurse_workload__n_p_s[n, p, s] == workload__p_posShift[p, pS]
            ).OnlyEnforceIf(
                p_o_start[p, d], nurse_bin__n_r_s[n, r, s], room_binary[p, r]
            )
            model.AddBoolOr(
                nurse_patient__n_p[n, p],
                negate_var_bool(p_o_start[p, d]),
                negate_var_bool(nurse_bin__n_r_s[n, r, s]),
                negate_var_bool(room_binary[p, r]),
            )

        self.print_time("nurse overwork constraints")
        for (n, s), _patients in domain_n_p_s__n_s.items():
            _all_workload = [patient_nurse_workload__n_p_s[n, p, s] for p in _patients]
            model.Add(
                nurse_overwork__n_s[n, s]
                >= my_sum(_all_workload) - nurse_max_load__n_s[n, s]
            )
        more_vars = dict(
            skill_diff__p_s=skill_diff__p_s,
            nurse_patient__n_p=nurse_patient__n_p,
            nurse_overwork__n_s=nurse_overwork__n_s,
            nurse_bin__n_r_s=nurse_bin__n_r_s,
        )
        my_vars.update(more_vars)
        return my_vars

    def get_rooms_with_id(self) -> dict:
        rooms = self.instance.get_rooms().copy_deep()
        for pos, r in enumerate(rooms.values()):
            r["pos"] = pos
        return rooms

    def get_nurses_with_id(self) -> dict:
        nurses = self.instance.get_nurses().copy_deep()
        for pos, n in enumerate(nurses.values()):
            n["pos"] = pos
        return nurses

    def dump_vars(self, model, solver: cp_model.CpSolver, my_vars):
        try:
            result = {
                k: v.vapply(solver.Value).vfilter(lambda v: v)
                for k, v in my_vars.items()
            }
        except:
            result = {}

        result = SuperDict(result).to_dictdict()
        with open("my_vars.json", "w") as f:
            json.dump(result, f)

    def my_vars_to_solution(self, solver, my_vars) -> dict:
        admission_bin = my_vars["admission_bin"]
        theater_bin = my_vars["theater_bin"]
        room_binary = my_vars["room_binary"]
        nurse_bin__n_r_s = my_vars.get("nurse_bin__n_r_s")
        # TODO: use binary n_r_s
        rooms_id__pos = self.rooms_id.values_tl().to_dict(
            "id", indices="pos", is_list=False
        )
        nurse_id__pos = self.nurses_id.values_tl().to_dict(
            "id", indices="pos", is_list=False
        )

        admission = transform_to_assignment(
            solver, admission_bin, result_col=1, is_list=False
        )
        theater = transform_to_assignment(
            solver, theater_bin, result_col=1, is_list=False
        )
        r = transform_to_assignment(
            solver, room_binary, result_col=1, is_list=False
        ).vapply(lambda v: rooms_id__pos[v])
        sol_patients = TupList(
            SuperDict(
                admission_day=admission[p],
                id=p,
                operating_theater=theater[p],
                room=r[p],
            )
            for p in admission
        )

        get_shiftday = self.instance.get_shiftype_from_shift
        get_day = self.instance.get_day_from_shift
        sol_nurses = {}
        if nurse_bin__n_r_s:
            nurse__r_s = transform_to_assignment(
                solver, nurse_bin__n_r_s, result_col=0, is_list=False
            )

            sol_nurses = nurse__r_s.kvapply(
                lambda k, v: SuperDict(
                    room=rooms_id__pos[k[0]],
                    day=get_day(k[1]),
                    shift=get_shiftday(k[1]),
                    id=nurse_id__pos[v],
                )
            ).values_tl()
        sol_data = SuperDict(
            nurse_assignment=sol_nurses, patient_assignment=sol_patients
        )
        return sol_data

    def get_stay_options_from_starts(self, possible_start):
        patients_occupants = self.instance.get_patients_occupants()
        horizon_days_size = self.instance.get_horizon_size_days()
        length_of_stay = patients_occupants.get_property("length_of_stay")
        return (
            possible_start.vapply(list)
            .to_tuplist()
            .to_dict(None)
            .vapply(
                lambda v: range(
                    v[1], min(v[1] + length_of_stay[v[0]], horizon_days_size)
                )
            )
            .vapply(list)
            .to_tuplist()
            .to_dict(2, indices=0)
            .vapply(set)
            .vapply(list)
        )


class StopOnMovingAverageImprovement(cp_model.CpSolverSolutionCallback):

    def __init__(self, ma_size=20, min_imp_per_sec=1, length_bad_imp=20):
        cp_model.CpSolverSolutionCallback.__init__(self)
        # size of moving average
        self.__queue = Stats(ma_size)
        # threshold to decide if it's low improvement rate
        self.__min_imp = min_imp_per_sec
        # number of consecutive solutions with low improvement per second
        self.__solution_count = 0
        # max number of consecutive solutions with low improvement per second
        self.__solution_max = length_bad_imp

    def on_solution_callback(self):
        average_improvement = self.__queue.push(self.WallTime(), self.ObjectiveValue())
        # print(average_improvement, self.__solution_count)
        if average_improvement < self.__min_imp:
            self.__solution_count += 1
        else:
            self.__solution_count = 0
        if self.__solution_count > self.__solution_max:
            self.StopSearch()


def negate_var_bool(my_var: bool | cp_model.IntVar):
    if isinstance(my_var, int):
        return not my_var
    return my_var.Not()


def fileno(file_or_fd):
    fd = getattr(file_or_fd, "fileno", lambda: file_or_fd)()
    if not isinstance(fd, int):
        raise ValueError("Expected a file (`.fileno()`) or a file descriptor")
    return fd


@contextmanager
def stdout_redirected(to=os.devnull, stdout=None):
    if stdout is None:
        stdout = sys.stdout

    stdout_fd = fileno(stdout)
    # copy stdout_fd before it is overwritten
    # NOTE: `copied` is inheritable on Windows when duplicating a standard stream
    with os.fdopen(os.dup(stdout_fd), "wb") as copied:
        stdout.flush()  # flush library buffers that dup2 knows nothing about
        try:
            os.dup2(fileno(to), stdout_fd)  # $ exec >&to
        except ValueError:  # filename
            with open(to, "wb") as to_file:
                os.dup2(to_file.fileno(), stdout_fd)  # $ exec > to
        try:
            yield stdout  # allow code to be run with the redirected stdout
        finally:
            # restore stdout to its previous value
            # NOTE: dup2 makes stdout_fd inheritable unconditionally
            stdout.flush()
            os.dup2(copied.fileno(), stdout_fd)  # $ exec >&copied


def multiple_ands(model: cp_model.CpModel, result, *ands):
    nots = [negate_var_bool(a) for a in ands]
    # if all the ands are false, then the result is false
    model.AddBoolOr(result, *nots)
    for a in ands:
        # if result is true, then all the ands are true
        model.AddImplication(result, a)


def transform_to_assignment(solver, ot_bin_var, **to_dict_args):
    return (
        ot_bin_var.vapply(solver.Value)
        .vfilter(lambda v: v == 1)
        .keys_tl()
        .to_dict(**to_dict_args)
    )


class Stats:
    def __init__(self, window=5):
        self._time = deque(maxlen=window)
        self._best = deque(maxlen=window)

    def push(self, my_time, best):
        self._time.append(my_time)
        self._best.append(best)
        time_dif = round(self._time[-1] - self._time[0], 1)
        if time_dif > 0:
            sol_dif = round((self._best[0] - self._best[-1]))
            return sol_dif / time_dif
        return 10000
        # diff = ma - self._prev_ma if self._prev_ma is not None else None
        # self._prev_ma = ma
        # print(f"value: {value}, MA: {ma}, diff: {diff}")
