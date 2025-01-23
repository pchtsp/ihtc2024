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

    def warm_start(self, model, my_vars: my_vars_type):
        patient_assignments = self.solution.get_patient_assignment()
        rooms = self.rooms_id
        nurses = self.nurses_id
        admission_bin = my_vars["admission_bin"]
        room_binary = my_vars["room_binary"]
        theater_bin = my_vars["theater_bin"]
        nurse_r_s = my_vars.get("nurse_r_s")
        nurse_patient__n_p_s = my_vars.get("nurse_patient__n_p_s")
        model.ClearHints()
        for v in patient_assignments.values():
            p = v["id"]
            d = v["admission_day"]
            r = rooms[v["room"]]["pos"]
            t = v["operating_theater"]
            model.AddHint(admission_bin[p, d], 1)
            model.AddHint(room_binary[p, r], 1)
            model.AddHint(theater_bin[p, t], 1)

        if nurse_r_s:
            nurse_assignments = self.get_nurse_assignment_shift()
            for v in nurse_assignments.values():
                r = rooms[v["room"]]["pos"]
                n = nurses[v["id"]]["pos"]
                s = v["shift_pos"]
                model.AddHint(nurse_r_s[r, s], n)
        if nurse_patient__n_p_s:
            patient_details = self.get_patient_shift_details()
            for v in patient_details.values():
                n = nurses[v["nurse"]]["pos"]
                p = v["id"]
                s = v["shift"]
                model.AddHint(nurse_patient__n_p_s[n, p, s], 1)

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
            + my_sum(admission_bin.kvapply(lambda k, v: v * k[1]).values())
            * weights["patient_delay"]
            # S8
            - my_sum(
                admission_bin.kfilter(
                    lambda k: not patients[k[0]]["mandatory"]
                ).values()
            )
            * weights["unscheduled_optional"]
            + nurses_part
        )
        return None

    def solve(self, options: dict = None) -> dict:
        options["seed"] = options.get("seed", 42)
        rn.seed(options["seed"])
        VERBOSE = options.get("msg", False)
        TIME_WINDOW = options.get("timeWindow")
        TIME_LIMIT = options.get("timeLimit", 100)
        WARM_START = options.get("warmStart", False)
        MAX_SAMPLE_OPTIONS = options.get("maxSample", [7, 10, None])
        if TIME_WINDOW:
            MAX_SAMPLE_OPTIONS = [None]
        if VERBOSE:
            self.print_time("Building of model starts")

        solver = cp_model.CpSolver()
        status = cp_model.UNKNOWN
        for max_sample in MAX_SAMPLE_OPTIONS:
            if VERBOSE:
                self.print_time(f"Phase1: maxSample: {max_sample}")
            my_options_1 = dict(options)
            my_options_1["maxSample"] = max_sample
            my_options_1["timeLimit"] = min(TIME_LIMIT, 500)
            if "logPath" in my_options_1:
                name, ext = os.path.splitext(my_options_1["logPath"])
                my_options_1["logPath"] = name + "_pre" + ext

            model = cp_model.CpModel()
            my_vars = self.add_non_nurse_constraints(model, my_options_1)
            my_vars = self.add_nurse_constraints(model, my_vars)

            if VERBOSE:
                self.print_time("Objective function")
            self.get_objective_function(model, my_vars)
            if self.solution and (TIME_WINDOW or WARM_START):
                self.warm_start(model, my_vars)
            status = self.call_solver(model, solver, my_options_1)
            if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                # as soon as we find a feasible solution, we exit
                break

        if options.get("msg", False):
            print(f"Model finished with status {status_conv.get(status)}")

            if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                if VERBOSE:
                    print("No solution was found")
                return dict(
                    status=status_conv.get(status),
                    status_sol=SOLUTION_STATUS_INFEASIBLE,
                )

        sol_data = self.my_vars_to_solution(solver, my_vars)
        self.solution = Solution.from_dict(sol_data)

        return dict(status=status_conv.get(status), status_sol=SOLUTION_STATUS_FEASIBLE)

    def call_solver(self, model, solver, options):

        errors = model.Validate()
        if errors:
            if options.get("msg", False):
                print(errors)

            raise ValueError("Model not formulated correctly")
        if options.get("msg", False):
            solver.parameters.log_search_progress = True
        solver.parameters.max_time_in_seconds = options.get("timeLimit", 10)
        if "threads" in options:
            solver.parameters.num_search_workers = options["threads"]
        if "fixSolution" in options:
            solver.parameters.fix_variables_to_their_hinted_value = True
        solution_callback = None
        stop_condition = options.get("stop_condition")
        if stop_condition is None:
            stop_condition = dict(ma_size=20, min_imp_per_sec=5, length_bad_imp=20)
        solution_callback = StopOnMovingAverageImprovement(**stop_condition)

        # if options.get("msg", False):
        #     solution_callback = VarArraySolutionPrinter()

        if options.get("msg", False):
            print("Solver starts")

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
        return possible_start, available_rooms__p

    def tw_limit_starts_rooms(self, possible_start, available_rooms__p, TIME_WINDOW):
        patients = self.instance.get_patients()
        size = TIME_WINDOW.get("size")
        start = TIME_WINDOW.get("start")
        if start is None:
            max_start = max(0, self.instance.get_horizon_size_days() - size)
            start = rn.randint(0, max_start)
        else:
            size = min(size, self.instance.get_horizon_size_days() - start)
        window = range(start, start + size)
        assignments = self.solution.get_patient_assignment().copy_deep()
        patients_in_tw = assignments.vfilter(
            lambda v: v["admission_day"] in window
        ).keys_tl()

        def fix_variable(patient, day_range, ref):
            # the passenger is inside the tw
            # or the patient is not scheduled
            # or patient is occupant
            if (
                patient in patients_in_tw
                or patient not in assignments
                or patient not in patients
            ):
                # we do not fix
                return day_range

            # the patient's possibilities are equal to the previous solution
            return [assignments[patient][ref]]

        possible_start = possible_start.kvapply(fix_variable, ref="admission_day")
        available_rooms__p = available_rooms__p.kvapply(fix_variable, ref="room")
        return possible_start, available_rooms__p

    def add_non_nurse_constraints(
        self, model: cp_model.CpModel, options=None
    ) -> my_vars_type:
        options = options or {}
        VERBOSE = options.get("msg", False)
        if VERBOSE:
            self.print_time("Getting parameters")
        patients = self.instance.get_patients()
        possible_start = self.instance.get_patient_occupants_available_starts()
        available_rooms__p = self.instance.get_patients_occupants_available_rooms()
        MAX_SAMPLE = options.get("maxSample")

        # here I will edit my_vars to fix everything
        #  that is not happening inside the time window
        #  I may need to fill the fixed nurse variables

        TIME_WINDOW = options.get("timeWindow")
        if TIME_WINDOW is not None and self.solution is not None:
            if MAX_SAMPLE and VERBOSE:
                self.print_time("We deactivate sampling because of time window")
            MAX_SAMPLE = None
            possible_start, available_rooms__p = self.tw_limit_starts_rooms(
                possible_start, available_rooms__p, TIME_WINDOW
            )

        # we sample the possible starts and available rooms per patient
        if MAX_SAMPLE is not None:
            possible_start, available_rooms__p = self.sample_starts_rooms(
                possible_start, available_rooms__p, MAX_SAMPLE
            )

        operation_theaters = self.instance.get_operatingtheaters().copy_deep()
        patients_occupants = self.instance.get_patients_occupants()
        occupants = self.instance.get_occupants()

        for pos, _theater in enumerate(operation_theaters.values()):
            _theater["pos"] = pos
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
        DUMMY_ROOM_POS = len(rooms)

        # admission_binary
        # only patients can be admitted
        if VERBOSE:
            self.print_time("Variables")

        admission_bin = SuperDict(
            {
                (p, d): model.NewBoolVar(f"admission_bin_{p}_{d}")
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
                        cp_model.Domain.FromValues(values=v), f"admission_{k}"
                    )
                )
            )
        )
        # occupants start at 0
        #  we care because we use admission for intervals/stay
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
                (p, ot): model.NewBoolVar(f"theater_bin_{p}_{ot}")
                for p in patients
                for ot in operation_theaters
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
                    model.NewBoolVar(f"room_{v[0]}_{v[1]}") if v[0] in patients else 1
                )
            )
        )

        # stay_binary, if a patient is in a room
        length_of_stay = patients_occupants.get_property("length_of_stay")
        possible_stay = possible_start.kvapply(
            lambda k, v: range(v[0], min(v[-1] + length_of_stay[k], horizon_days_size))
        )

        # possible_stay
        # occupants have a 1 during their whole stay
        stay_bin = SuperDict(
            {
                (p, d): model.NewBoolVar(f"stay_bin_{p}_{d}") if p in patients else 1
                for p, days in possible_stay.items()
                for d in days
            }
        )

        # tie stay with admission.
        # if admission on day d => stay on days d .. d + length
        # if admission not on d -> do nothing
        for p, days in possible_start.items():
            # we only tie with patients, not occupants
            if p in occupants:
                continue
            for d in days:
                last_date = min(d + length_of_stay[p], horizon_days_size)
                for d2 in range(d, last_date):
                    model.AddImplication(admission_bin[p, d], stay_bin[p, d2])

        # this will calculate the usage of the theater by patients
        domain__ot_p_d = TupList(
            (ot, p, d)
            for p, days in possible_start.items()
            for ot in operation_theaters
            for d in days
            if p in patients
            if (p, ot) in theater_bin
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
        # definition
        # https://groups.google.com/g/or-tools-discuss/c/9trLOMSe_DA
        for ot, p, d in domain__ot_p_d:
            multiple_ands(
                model,
                assigned__ot_p_d[ot, p, d],
                admission_bin[p, d],
                theater_bin[p, ot],
            )

        # binary if surgeon works in ot in day d
        worked__s_ot_d = SuperDict(
            {
                (s, ot, d): model.NewBoolVar(f"worked_{s}_{ot}_{d}")
                for s, capacities in surgeons_cap.items()
                for d, cap in capacities.items()
                if cap > 0
                for ot in ot_cap
                if ot_cap[ot][d] > 0
            }
        )
        # definition
        # if at least one patient of surgen is operated by ot in that day
        # we count it
        for ot, p, d in domain__ot_p_d:
            model.Add(
                worked__s_ot_d.get((patients[p]["surgeon_id"], ot, d), 0)
                >= assigned__ot_p_d[ot, p, d]
            )

        # ot is open (S5)
        open__ot_d = SuperDict(
            {
                (ot, d): model.NewBoolVar(f"open_{ot}_{d}")
                for ot, days in ot_cap.items()
                for d in days
                if ot_cap[ot][d] > 0
            }
        )
        # definition:
        # if at least one patient is assigned, we open the ot
        for ot, p, d in domain__ot_p_d:
            model.Add(open__ot_d[ot, d] >= assigned__ot_p_d[ot, p, d])

        # if we do not have a domain for ot, p, d:
        # then admission or theater needs to be 0
        domain__ot_p_d_set = set(domain__ot_p_d)
        for (p, d), v in admission_bin.items():
            for ot in operation_theaters:
                if (ot, p, d) not in domain__ot_p_d_set:
                    model.Add(admission_bin[p, d] + theater_bin[p, ot] <= 1)

        # H2
        if VERBOSE:
            self.print_time("H2 constraints")

        # domain__p_r_d = TupList(
        #     [
        #         (p, r, d)
        #         for p, rr in available_rooms__p.items()
        #         for r in rr
        #         for d in possible_stay[p]
        #     ]
        # )
        # room__p_r_d = domain__p_r_d.to_dict(None).vapply(
        #     lambda v: model.NewBoolVar(f"room_{v[0]}_{v[1]}_{v[2]}")
        # )
        # # we tie room_p_r_d to room and stay:
        # for p, r, d in domain__p_r_d:
        #     multiple_ands(
        #         model, room__p_r_d[p, r, d], room_binary[p, r], stay_bin[p, d]
        #     )

        # patients that are mandatory will always have a room.
        # occupants are considered mandatory (so default: True)
        available_rooms__p_with_dummy = available_rooms__p.kvapply(
            lambda k, v: (
                v
                if patients_occupants[k].get("mandatory", True)
                else v + [DUMMY_ROOM_POS]
            )
        )
        room_p = available_rooms__p_with_dummy.kvapply(
            lambda k, v: (
                model.NewIntVarFromDomain(
                    cp_model.Domain.FromValues(values=v), "room_{}".format(k)
                )
                if k in patients
                else v[0]
            )
        )

        # we tie binary and element variables
        for p, _rooms in available_rooms__p.items():
            for r in _rooms:
                model.Add(room_p[p] == r).OnlyEnforceIf(room_binary[p, r])
                model.Add(room_p[p] != r).OnlyEnforceIf(
                    negate_var_bool(room_binary[p, r])
                )

        gender = patients_occupants.get_property("gender")
        # patients_list = patients_occupants.keys_tl()
        # patients_num = len(patients_list)
        # possible_stay_s = possible_stay.vapply(set)

        # possible_stays = {
        #     (p1, patients_list[pos2]): possible_stay_s[p1]
        #     & possible_stay_s[patients_list[pos2]]
        #     for pos1, p1 in enumerate(patients_list)
        #     for pos2 in range(pos1 + 1, patients_num)
        # }
        # available_rooms__p_s = available_rooms__p.vapply(set)
        # possible_rooms = {
        #     (p1, patients_list[pos2]): available_rooms__p_s[p1]
        #     & available_rooms__p_s[patients_list[pos2]]
        #     for pos1, p1 in enumerate(patients_list)
        #     for pos2 in range(pos1 + 1, patients_num)
        # }
        if VERBOSE:
            self.print_time("H1 constraints prep1")

        # shared_room_domain__p1_p2_r_d = TupList(
        #     (p1, p2, room_pos, d)
        #     for (p1, p2), days in possible_stays.items()
        #     for room_pos in possible_rooms[p1, p2]
        #     for d in days
        # )
        if VERBOSE:
            self.print_time("H1 constraints prep2")

        # two patients share a room on day d?
        # share_room = SuperDict(
        #     {
        #         (p1, p2, r, d): model.NewBoolVar(f"share_{p1}_{p2}_{r}_{d}")
        #         for p1, p2, r, d in shared_room_domain__p1_p2_r_d
        #         if gender[p1] == gender[p2]
        #     }
        # )
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

        # H1
        # for p1, p2, room_pos, d in shared_room_domain__p1_p2_r_d:
        #     # if they share the same gender, we need to register if they share a room
        #     if gender[p1] == gender[p2]:
        #         multiple_ands(
        #             model,
        #             share_room[p1, p2, room_pos, d],
        #             room__p_r_d[p1, room_pos, d],
        #             room__p_r_d[p2, room_pos, d],
        #         )
        #         # model.Add(share_room[p1, p2, room_pos, d] == 1).OnlyEnforceIf(
        #         #     room__p_r_d[p1, room_pos, d], room__p_r_d[p2, room_pos, d]
        #         # )
        #     else:
        #         # if they do not share gender they cannot share a room
        #         model.AddImplication(
        #             room__p_r_d[p1, room_pos, d],
        #             negate_var_bool(room__p_r_d[p2, room_pos, d]),
        #         )
        #         model.AddImplication(
        #             room__p_r_d[p2, room_pos, d],
        #             negate_var_bool(room__p_r_d[p1, room_pos, d]),
        #         )

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

        # patients__r_d = domain__p_r_d.to_dict(0)
        # for (room_pos, day), _patients in patients__r_d.items():
        #     _patients_in_room = [room__p_r_d[p, room_pos, day] for p in _patients]
        #     model.Add(my_sum(_patients_in_room) <= room_capacity[room_pos])

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
        max_age_diff = SuperDict(
            {
                (r, d): model.NewIntVar(0, num_ages - 1, name=f"max_age_diff_{r}_{d}")
                for r in all_rooms
                for d in range(horizon_days_size)
            }
        )
        max_age = SuperDict(
            {
                (r, d): model.NewIntVar(min_ag, max_ag, name=f"max_age_{r}_{d}")
                for r, d in max_age_diff
            }
        )
        min_age = SuperDict(
            {
                (r, d): model.NewIntVar(min_ag, max_ag, name=f"min_age_{r}_{d}")
                for r, d in max_age_diff
            }
        )
        age_group = patients_occupants.get_property("age_group").vapply(
            lambda v: agegroups[v]["pos"]
        )
        for p, r in room_binary:
            for d in possible_stay[p]:
                model.Add(max_age[r, d] >= age_group[p]).OnlyEnforceIf(
                    stay_bin[p, d], room_binary[p, r]
                )
                model.Add(min_age[r, d] <= age_group[p]).OnlyEnforceIf(
                    stay_bin[p, d], room_binary[p, r]
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
            all_theaters = my_sum([theater_bin[p, ot] for ot in operation_theaters])
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
            stay_bin=stay_bin,
            room_p=room_p,
            open__ot_d=open__ot_d,
            worked__s_ot_d=worked__s_ot_d,
            max_age_diff=max_age_diff,
        )

        return my_vars

    def add_nurse_constraints(
        self,
        model: cp_model.CpModel,
        my_vars: my_vars_type,
    ) -> my_vars_type:

        patients = self.instance.get_patients()
        patients_occupants = self.instance.get_patients_occupants()
        rooms = self.rooms_id
        nurses = self.nurses_id

        DUMMY_NURSE_POS = len(nurses)
        nurse_shifts = self.instance.get_nurse_shift()
        needs__p_sPos = self.instance.get_patients_occupants_needs()
        last_shift = self.instance.get_last_shift_horizon()

        # nurses part
        # TODO: if tw mode, maybe constraint this?
        nurse_r_s = SuperDict()
        nurses__s = (
            nurse_shifts.values_tl()
            .copy_deep()
            .vapply_col("nurse_pos", lambda v: nurses[v["nurse"]]["pos"])
            .to_dict("nurse_pos", indices="shift_pos")
        )
        domain__n_r_s = TupList(
            (n, r["pos"], shift)
            for r in rooms.values()
            for shift, _nurses in nurses__s.items()
            for n in _nurses
        )
        nurse_bin__n_r_s = SuperDict(
            {
                (n, r, s): model.NewBoolVar(f"nurse_bin_{n}_{r}_{s}")
                for n, r, s in domain__n_r_s
            }
        )
        domain_n_r_s__r_s = domain__n_r_s.to_dict(0)
        for (r, s), _nurses in domain_n_r_s__r_s.items():
            nurse_r_s[r, s] = model.NewIntVarFromDomain(
                domain=cp_model.Domain.FromValues(values=_nurses),
                name=f"nurse_{r}_{s}",
            )
            for n in _nurses:
                model.Add(nurse_r_s[r, s] == n).OnlyEnforceIf(nurse_bin__n_r_s[n, r, s])
                model.Add(nurse_r_s[r, s] != n).OnlyEnforceIf(
                    nurse_bin__n_r_s[n, r, s].Not()
                )
        # for each patient-shift, we store the nurse assigned
        stay_bin = my_vars["stay_bin"]
        domain_n_p_s = TupList(
            (n, p, s)
            for p, d in stay_bin.keys()
            for s in self.instance.get_shifts_of_day(d)
            for n in nurses__s[s]
        )
        # nurse covers patient
        nurse_patient__n_p_s = SuperDict(
            {
                (n, p, s): model.NewBoolVar(name=f"nurse_patient_{n}_{p}_{s}")
                for n, p, s in domain_n_p_s
            }
        )
        # when a passenger is not staying in a giving day, it's assigned a dummy nurse:
        # so all shifts (in theory) can have a dummy nurse
        # except occupants, where I know when they're staying
        domain_n_p_s__p_s = domain_n_p_s.to_dict(0)
        domain_n_p_s__p_s_with_dummy = domain_n_p_s__p_s.kvapply(
            lambda k, v: v + [DUMMY_NURSE_POS] if k[0] in patients else v
        )
        nurse__p_s = domain_n_p_s__p_s_with_dummy.kvapply(
            lambda k, v: model.NewIntVarFromDomain(
                cp_model.Domain.FromValues(values=v), name=f"nurse__p_s{k[0]}_{k[1]}"
            )
        )

        domain__n_p = domain_n_p_s.take([0, 1]).unique2()
        nurse_patient__n_p = SuperDict(
            {
                (n, p): model.NewBoolVar(name=f"nurse_patient_{n}_{p}")
                for n, p in domain__n_p
            }
        )

        # for each, p, s:
        nurse_r_s__s_r = (
            nurse_r_s.to_tuplist()
            .to_dict(2, indices=[1, 0], is_list=False)
            .to_dictdict()
        )
        room_p = my_vars["room_p"]
        room_positions = rooms.vapply(lambda v: v["pos"]).values_tl().sorted()
        for p, d in stay_bin.keys():
            for s in self.instance.get_shifts_of_day(d):
                nurses_per_room = [nurse_r_s__s_r[s][r] for r in room_positions]
                # we add the dummy nurse in the dummy room position
                nurses_per_room.append(DUMMY_NURSE_POS)
                model.AddElement(room_p[p], nurses_per_room, nurse__p_s[p, s])

        for n, p, s in domain_n_p_s:
            _day = self.instance.get_day_from_shift(s)
            # tie the binary to the element variable
            model.Add(nurse__p_s[p, s] == n).OnlyEnforceIf(
                nurse_patient__n_p_s[n, p, s], stay_bin[p, _day]
            )
            model.Add(nurse__p_s[p, s] != n).OnlyEnforceIf(
                nurse_patient__n_p_s[n, p, s].Not(), stay_bin[p, _day]
            )
            # if the patient is not staying that shift, no nurse is assigned
            model.AddImplication(nurse_patient__n_p_s[n, p, s], stay_bin[p, _day])
            # model.Add(nurse_patient__n_p_s[n, p, s] <= stay_bin[p, _day])

            # S3
            # if a nurse treats once, we count
            model.AddImplication(
                nurse_patient__n_p_s[n, p, s], nurse_patient__n_p[n, p]
            )
            # model.Add(nurse_patient__n_p[n, p] >= nurse_patient__n_p_s[n, p, s])

        # S4 maximum workload
        domain_n_p_s__n_s = domain_n_p_s.to_dict(1)
        nurse_max_load__n_s = (
            nurse_shifts.values_tl()
            .copy_deep()
            .vapply_col("nurse_pos", lambda v: nurses[v["nurse"]]["pos"])
            .to_dict("max_load", indices=["nurse_pos", "shift_pos"], is_list=False)
        )

        MaxWL__p = (
            needs__p_sPos.values_tl()
            .to_dict("workload_produced", indices="id")
            .vapply(max)
        )
        # the upper bound is the sum of the largest possible workloads of patients available for that nurse in that shift
        nurse_overwork__n_s = domain_n_p_s__n_s.vapply(
            lambda _patients: sum(MaxWL__p[p] for p in _patients)
        ).kvapply(lambda k, v: model.NewIntVar(0, v, name=f"overwork_{k[0]}_{k[1]}"))

        workload__p_posShift = needs__p_sPos.get_property("workload_produced")
        skill_level__p_sPos = needs__p_sPos.get_property("skill_level_required")

        # occupants, the workload comes directly from the position of the shift
        # all the others are variables:
        patient_workload__p_s = (
            domain_n_p_s.take([1, 2])
            .unique2()
            .to_dict(None)
            .vapply(
                lambda v: (
                    model.NewIntVar(0, MaxWL__p[v[0]], name=f"workload_{v[0]}_{v[1]}")
                    if not patients_occupants[v[0]]["is_occupant"]
                    else workload__p_posShift[v[0], v[1]]
                )
            )
        )
        positions_p = needs__p_sPos.keys_tl().to_dict(1).vapply(len)
        # TODO: I can filter some values based on the position of the shift relative to the start/end of potential stay
        patient_posShift__p_s = nurse__p_s.kapply(
            lambda k: (
                model.NewIntVar(0, positions_p[k[0]], name=f"position_{k[0]}_{k[1]}")
                if not patients_occupants[k[0]]["is_occupant"]
                else k[1]
            )
        )

        patient_nurse_workload__n_p_s = domain_n_p_s.to_dict(None).vapply(
            lambda v: (
                model.NewIntVar(
                    0, MaxWL__p[v[1]], name=f"workload_{v[0]}_{v[1]}_{v[2]}"
                )
                if not patients_occupants[v[1]]["is_occupant"]
                else workload__p_posShift[v[1], v[2]]
            )
        )
        # we define the position shift for each active shift
        admission_bin = my_vars["admission_bin"]
        for (p, day), admission in admission_bin.items():
            for posShift in range(positions_p[p]):
                my_shift = day * 3 + posShift
                if my_shift > last_shift:
                    continue
                model.Add(patient_posShift__p_s[p, my_shift] == posShift).OnlyEnforceIf(
                    admission
                )

        # we assign this workload to a nurse
        # when there is an assignment
        for n, p, s in domain_n_p_s:
            model.Add(
                patient_nurse_workload__n_p_s[n, p, s] == patient_workload__p_s[p, s]
            ).OnlyEnforceIf(nurse_patient__n_p_s[n, p, s])

        for (n, s), _patients in domain_n_p_s__n_s.items():
            _all_workload = [patient_nurse_workload__n_p_s[n, p, s] for p in _patients]
            model.Add(
                nurse_overwork__n_s[n, s]
                >= my_sum(_all_workload) - nurse_max_load__n_s[n, s]
            )

        # S2
        # calculate the skill levels ordered by position of nurse (for element constraint)
        nurses_skill_level = (
            nurses.values_tl().sorted(key=lambda v: v["pos"]).take("skill_level")
        )
        # we add dummy_nurse has all skills:
        max_skill_level = max(nurses_skill_level)
        nurses_skill_level += [max_skill_level]
        # skill level given to patient p in shift s
        skill_level__p_s = nurse__p_s.kapply(
            lambda k: model.NewIntVar(
                0, max_skill_level, name=f"skill_level_{k[0]}_{k[1]}"
            )
        )
        # skill difference between required and actual
        skill_diff__p_s = nurse__p_s.kapply(
            lambda k: model.NewIntVar(
                0, max_skill_level, name=f"skill_diff_{k[0]}_{k[1]}"
            )
        )
        max_skill_level__p = (
            skill_level__p_sPos.to_tuplist().to_dict(2, indices=0).vapply(max)
        )
        skill_needed__p_s = nurse__p_s.kapply(
            lambda k: (
                model.NewIntVar(
                    0, max_skill_level__p[k[0]], name=f"skill_need_{k[0]}_{k[1]}"
                )
                if not patients_occupants[k[0]]["is_occupant"]
                else skill_level__p_sPos[k[0], k[1]]
            )
        )

        for p, s in patient_posShift__p_s.keys():
            workload_per_pos = [
                workload__p_posShift[p, pos] for pos in range(positions_p[p])
            ]
            skill_level_per_pos = [
                skill_level__p_sPos[p, pos] for pos in range(positions_p[p])
            ]
            if not patients_occupants[p]["is_occupant"]:
                # we get the workload from the position
                # occupants have it already pre-assigned
                model.AddElement(
                    patient_posShift__p_s[p, s],
                    workload_per_pos,
                    patient_workload__p_s[p, s],
                )
                # we get the required skill level from the position
                # occupants have it already pre-assigned
                model.AddElement(
                    patient_posShift__p_s[p, s],
                    skill_level_per_pos,
                    skill_needed__p_s[p, s],
                )
            # we use nurse[p, s] to get the skill-level given to patient p in shift s
            model.AddElement(
                nurse__p_s[p, s], nurses_skill_level, skill_level__p_s[p, s]
            )
            my_day = self.instance.get_day_from_shift(s)
            # we calculate the difference between the level and the required level
            # but only if the stay is active
            model.Add(
                skill_diff__p_s[p, s]
                >= skill_needed__p_s[p, s] - skill_level__p_s[p, s]
            ).OnlyEnforceIf(stay_bin[p, my_day])

        more_vars = dict(
            skill_diff__p_s=skill_diff__p_s,
            nurse_patient__n_p=nurse_patient__n_p,
            nurse_overwork__n_s=nurse_overwork__n_s,
            nurse_r_s=nurse_r_s,
            nurse_patient__n_p_s=nurse_patient__n_p_s,
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

    def my_vars_to_solution(self, solver, my_vars) -> dict:
        admission_bin = my_vars["admission_bin"]
        theater_bin = my_vars["theater_bin"]
        room_binary = my_vars["room_binary"]
        nurse_r_s = my_vars.get("nurse_r_s")
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
        if nurse_r_s:
            sol_nurses = (
                nurse_r_s.vapply(solver.Value)
                .to_tuplist()
                .vapply(
                    lambda v: SuperDict(
                        room=rooms_id__pos[v[0]],
                        day=get_day(v[1]),
                        shift=get_shiftday(v[1]),
                        id=nurse_id__pos[v[2]],
                    )
                )
            )
        sol_data = SuperDict(
            nurse_assignment=sol_nurses, patient_assignment=sol_patients
        )
        return sol_data


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
        print(average_improvement, self.__solution_count)
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
