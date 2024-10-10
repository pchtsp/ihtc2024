from .. import Solution
from ..core.experiment import Experiment
from ortools.sat.python import cp_model

import os
import sys
from contextlib import contextmanager

from pytups import SuperDict, TupList

from cornflow_client.constants import (
    STATUS_OPTIMAL,
    STATUS_INFEASIBLE,
    STATUS_UNDEFINED,
    SOLUTION_STATUS_FEASIBLE,
    SOLUTION_STATUS_INFEASIBLE,
)


class CpSAT(Experiment):

    def solve(self, options: dict = None) -> dict:
        VERBOSE = options.get("msg", False)
        if VERBOSE:

            print("Building of model starts")

        weights = self.instance.get_weights()
        model = cp_model.CpModel()
        patients = self.instance.get_patients()
        possible_start = self.instance.get_patient_occupants_available_starts()
        nurse_shifts = self.instance.get_nurse_shift()
        patient_shifts = self.instance.get_patient_shifts()
        operation_theaters = self.instance.get_operatingtheaters().copy_deep()
        patients_occupants = self.instance.get_patients_occupants()
        occupants = self.instance.get_occupants()
        needs__p_sPos = self.instance.get_patients_occupants_needs()
        last_shift = self.instance.get_last_shift_horizon()
        my_sum = cp_model.LinearExpr.Sum

        for pos, _theater in enumerate(operation_theaters.values()):
            _theater["pos"] = pos
        surgery_duration = patients.get_property("surgery_duration")
        ot_cap = (
            self.instance.get_operatingtheater_capacity()
            .get_property("availability")
            .to_dictdict()
        )
        rooms = self.instance.get_rooms().copy_deep()
        for pos, r in enumerate(rooms.values()):
            r["pos"] = pos

        rooms_id__pos = rooms.values_tl().to_dict("id", indices="pos", is_list=False)
        nurses = self.instance.get_nurses().copy_deep()
        for pos, _nurse in enumerate(nurses.values()):
            _nurse["pos"] = pos
        nurse_id__pos = nurses.values_tl().to_dict("id", indices="pos", is_list=False)
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
        DUMMY_NURSE_POS = len(nurses)

        # I reserve the next to last day of the horizon for non-admissions.

        # H6
        # admission = possible_start.kvapply(
        #     lambda k, v: model.NewIntVar(v[0], v[-1], "admission_{}".format(k))
        # )
        # admission_binary
        # only patients can be admitted
        admission_bin = SuperDict(
            {
                (p, d): model.NewBoolVar(f"admission_bin_{p}_{d}")
                for p, days in possible_start.items()
                for d in days
                if p in patients
            }
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
                    model.Add(stay_bin[p, d2] == 1).OnlyEnforceIf(admission_bin[p, d])

        # # tie the binary with the decision variable:
        # for p, days in possible_start.items():
        #     for d in days:
        #         model.Add(admission[p] == d).OnlyEnforceIf(admission_bin[p, d])
        #         model.Add(admission[p] != d).OnlyEnforceIf(admission_bin[p, d].Not())

        # theater = patients.kvapply(
        #     lambda k, v: model.NewIntVar(
        #         0, len(operation_theaters) - 1, "theater_{}".format(k)
        #     )
        # )
        theater_bin = SuperDict(
            {
                (p, ot): model.NewBoolVar(f"theater_bin_{p}_{ot}")
                for p in patients
                for ot in operation_theaters
            }
        )

        # this will calculate the usage of the theater by patients
        domain__ot_p_d = TupList(
            (ot, p, d)
            for p, days in possible_start.items()
            for ot in operation_theaters
            for d in days
            if p in patients
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
        for ot, p, d in domain__ot_p_d:
            model.Add(assigned__ot_p_d[ot, p, d] == 1).OnlyEnforceIf(
                admission_bin[p, d]
            ).OnlyEnforceIf(theater_bin[p, ot])

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

        # # tie the binary with the decision variable:
        # for p in patients:
        #     for ot in operation_theaters:
        #         model.Add(theater[p] == d).OnlyEnforceIf(admission_bin[p, d])
        #         model.Add(admission[p] != d).OnlyEnforceIf(admission_bin[p, d].Not())

        # H2
        banned_rooms = (
            self.instance.get_patient_room_ban()
            .values_tl()
            .to_dict("room", indices="patient")
        )

        available_rooms__p = patients.kvapply(
            lambda k, v: [
                r["pos"]
                for r in rooms.values()
                if r["id"] not in banned_rooms.get(k, [])
            ]
        )
        # occupants have a fixed room:
        occupants_rooms = occupants.get_property("room_id").vapply(
            lambda v: [rooms[v]["pos"]]
        )
        available_rooms__p = SuperDict(**available_rooms__p, **occupants_rooms)

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
        domain_n_p_s = TupList(
            (n, p, s)
            for p, days in possible_stay.items()
            for d in days
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

        # but I need to add a dummy room, dummy nurse for that room.
        # for each, p, s:
        nurse_r_s__s_r = (
            nurse_r_s.to_tuplist()
            .to_dict(2, indices=[1, 0], is_list=False)
            .to_dictdict()
        )
        room_positions = rooms.vapply(lambda v: v["pos"]).values_tl().sorted()
        for p, days in possible_stay.items():
            for d in days:
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
            model.Add(nurse_patient__n_p_s[n, p, s] <= stay_bin[p, _day])

            # S3
            # if a nurse treats once, we count
            model.Add(nurse_patient__n_p[n, p] >= nurse_patient__n_p_s[n, p, s])

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
        workload__p__posShift = workload__p_posShift.to_dictdict()

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
        patient_nurse_workload__n_p_s = domain_n_p_s.to_dict(None).vapply(
            lambda v: (
                model.NewIntVar(
                    0, MaxWL__p[v[1]], name=f"workload_{v[0]}_{v[1]}_{v[2]}"
                )
                if not patients_occupants[v[1]]["is_occupant"]
                else workload__p_posShift[v[1], v[2]]
            )
        )

        for p, days in possible_start.items():
            if patients_occupants[p]["is_occupant"]:
                # we already have the workload as a parameter
                continue
            for day in days:
                workload = workload__p__posShift[p]
                for posShift, workload in workload.items():
                    my_shift = day * 3 + posShift
                    if my_shift > last_shift:
                        continue
                    model.Add(
                        patient_workload__p_s[p, my_shift] == workload
                    ).OnlyEnforceIf(admission_bin[p, day])

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

        gender = patients_occupants.get_property("gender")
        patients_list = patients_occupants.keys_tl()

        shared_room_domain__p1_p2_r_d = TupList(
            (p1, p2, room_pos, d)
            for pos, p1 in enumerate(patients_list)
            for p2 in patients_list[pos + 1 :]
            for d in possible_stay[p1]
            if d in possible_stay[p2]
            for room_pos in available_rooms__p[p1]
            if room_pos in available_rooms__p[p2]
        )

        # two patients share a room on day d?
        share_room = SuperDict(
            {
                (p1, p2, r, d): model.NewBoolVar(f"share_{p1}_{p2}_{r}_{d}")
                for p1, p2, r, d in shared_room_domain__p1_p2_r_d
                if gender[p1] == gender[p2]
            }
        )
        # constraints:
        # H1
        # TODO: this could be a 2D no-overlap I suspect?
        for p1, p2, room_pos, d in shared_room_domain__p1_p2_r_d:
            # if they share the same gender, we need to register if they share a room
            if gender[p1] == gender[p2]:
                model.Add(share_room[p1, p2, room_pos, d] == 1).OnlyEnforceIf(
                    stay_bin[p1, d],
                    stay_bin[p2, d],
                    room_binary[p1, room_pos],
                    room_binary[p2, room_pos],
                )
            else:
                # they cannot share a room
                model.Add(
                    room_binary[p1, room_pos] + room_binary[p2, room_pos] <= 1
                ).OnlyEnforceIf(stay_bin[p1, d], stay_bin[p2, d])

        # S1
        agegroups = self.instance.get_agegroups()
        age_group = patients_occupants.get_property("age_group").vapply(
            lambda v: agegroups[v]["pos"]
        )
        num_ages = len(set(age_group.values_tl()))
        shared_room__r_d = shared_room_domain__p1_p2_r_d.to_dict(None, indices=[2, 3])
        max_age_diff = SuperDict(
            {
                (r, d): model.NewIntVar(0, num_ages - 1, name=f"max_age_diff_{r}_{d}")
                for r, d in shared_room__r_d
            }
        )
        age_group = patients_occupants.get_property("age_group").vapply(
            lambda v: agegroups[v]["pos"]
        )
        for p1, p2, room_pos, d in shared_room_domain__p1_p2_r_d:
            if gender[p1] != gender[p2]:
                continue
            model.Add(
                max_age_diff[room_pos, d] >= age_group[p1] - age_group[p2]
            ).OnlyEnforceIf(share_room[p1, p2, room_pos, d])
            model.Add(
                max_age_diff[room_pos, d] >= age_group[p2] - age_group[p1]
            ).OnlyEnforceIf(share_room[p1, p2, room_pos, d])

        # S2
        # calculate the skill levels ordered by position of nurse (for element constraint)
        nurses_skill_level = (
            nurses.values_tl().sorted(key=lambda v: v["pos"]).take("skill_level")
        )
        # we add dummy_nurse has all skills:
        max_skill_level = max(nurses_skill_level)
        nurses_skill_level += [max_skill_level]
        skill_level__p_s = nurse__p_s.kapply(
            lambda k: model.NewIntVar(
                0, max_skill_level, name=f"skill_level_{k[0]}_{k[1]}"
            )
        )
        skill_diff__p_s = nurse__p_s.kapply(
            lambda k: model.NewIntVar(
                0, max_skill_level, name=f"skill_diff_{k[0]}_{k[1]}"
            )
        )
        skill_level__p_sPos = needs__p_sPos.get_property("skill_level_required")
        skill_level__p__sPos = skill_level__p_sPos.to_dictdict()
        max_skill_level__p = (
            skill_level__p_sPos.to_tuplist().to_dict(2, indices=0).vapply(max)
        )
        skill_needed__p_s = nurse__p_s.kapply(
            lambda k: (
                model.NewIntVar(
                    0, max_skill_level__p[k[0]], name=f"skill_diff_{k[0]}_{k[1]}"
                )
                if not patients_occupants[k[0]]["is_occupant"]
                else skill_level__p_sPos[k[0], k[1]]
            )
        )

        for p, days in possible_start.items():
            if patients_occupants[p]["is_occupant"]:
                # we already have the workload as a parameter for occupants
                continue
            for day in days:
                _skill_level = skill_level__p__sPos[p]
                for posShift, skill_level in _skill_level.items():
                    my_shift = day * 3 + posShift
                    if my_shift > last_shift:
                        continue
                    # if patient p is admitted in "day", then the following shifts
                    # should have the skill_level assigned.
                    model.Add(
                        skill_needed__p_s[p, my_shift] == skill_level
                    ).OnlyEnforceIf(admission_bin[p, day])

        for p, s in domain_n_p_s__p_s_with_dummy:
            # we use nurse[p, s] to get the skill for patient, shift
            model.AddElement(
                nurse__p_s[p, s], nurses_skill_level, skill_level__p_s[p, s]
            )
            # we calculate the difference between the level and the required level
            model.Add(
                skill_diff__p_s[p, s]
                >= skill_needed__p_s[p, s] - skill_level__p_s[p, s]
            )

        # H3
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
        for ot, capacities in ot_cap.items():
            for d, capacity in capacities.items():
                _content = [
                    assigned__ot_p_d.get((ot, p, d), 0) * surgery_duration[p]
                    for p in patients
                ]
                model.Add(my_sum(_content) <= capacity)
        #  H5
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
            +
            # S2
            my_sum(skill_diff__p_s.values()) * weights["room_nurse_skill"]
            +
            # S3
            my_sum(nurse_patient__n_p.values()) * weights["continuity_of_care"]
            # S4
            + my_sum(nurse_overwork__n_s.values()) * weights["nurse_eccessive_workload"]
        )

        # we try to explore the smallest domains of rooms and nurses
        # model.AddDecisionStrategy(
        #     room_p.kfilter(lambda k: k in patients).values_tl() + nurse_r_s.values_tl(),
        #     cp_model.CHOOSE_MIN_DOMAIN_SIZE,
        #     cp_model.SELECT_MIN_VALUE,
        # )
        # # we try to force admissions to true as much as possible
        # model.AddDecisionStrategy(
        #     admission_bin.values_tl(),
        #     cp_model.CHOOSE_FIRST,
        #     cp_model.SELECT_MAX_VALUE,
        # )
        errors = model.Validate()
        if errors:
            if VERBOSE:
                print(errors)

            raise ValueError("Model not formulated correctly")
        solver = cp_model.CpSolver()
        if VERBOSE:
            solver.parameters.log_search_progress = True
        solver.parameters.max_time_in_seconds = options.get("timeLimit", 10)
        if "threads" in options:
            solver.parameters.num_search_workers = options["threads"]
        solution_callback = None

        if options.get("msg", False):
            solution_callback = VarArraySolutionPrinter()

        if VERBOSE:
            print("Solver starts")
        path_of_log = options.get("logPath")

        if path_of_log is not None:
            with open(path_of_log, "w") as f, stdout_redirected(f):
                status = solver.Solve(model)
        else:
            status = solver.Solve(model)

        status_conv = {
            cp_model.OPTIMAL: STATUS_OPTIMAL,
            cp_model.FEASIBLE: STATUS_OPTIMAL,
            cp_model.INFEASIBLE: STATUS_INFEASIBLE,
            cp_model.UNKNOWN: STATUS_UNDEFINED,
            cp_model.MODEL_INVALID: STATUS_UNDEFINED,
        }

        if options.get("msg", False):
            print(f"Model finished with status {status_conv.get(status)}")

        if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            if VERBOSE:
                print("No solution was found")
            return dict(
                status=status_conv.get(status), status_sol=SOLUTION_STATUS_INFEASIBLE
            )

        def transform_to_assignment(ot_bin_var, **to_dict_args):
            return (
                ot_bin_var.vapply(solver.Value)
                .vfilter(lambda v: v == 1)
                .keys_tl()
                .to_dict(**to_dict_args)
            )

        admission = transform_to_assignment(admission_bin, result_col=1, is_list=False)
        theater = transform_to_assignment(theater_bin, result_col=1, is_list=False)
        r = transform_to_assignment(room_binary, result_col=1, is_list=False).vapply(
            lambda v: rooms_id__pos[v]
        )
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
        self.solution = Solution.from_dict(sol_data)

        return dict(status=status_conv.get(status), status_sol=SOLUTION_STATUS_FEASIBLE)

        ####### TEMP DEBUG
        self.solution.get_patient_assignment().get_property("room")
        room_p.vapply(solver.Value).vapply(lambda v: rooms_id__pos.get(v))

        patient_details = self.get_patient_shift_details()
        model_needed_sl = skill_needed__p_s.vapply(solver.Value)
        model_nurse = nurse__p_s.vapply(solver.Value).vapply(
            lambda v: nurse_id__pos.get(v)
        )
        model_skill_level_assigned = skill_level__p_s.vapply(solver.Value)
        model_skill_level_diff = skill_diff__p_s.vapply(solver.Value)
        # we compare the required skill per shift
        patient_details.get_property("skill_level_required").kvfilter(
            lambda k, v: v != model_needed_sl[k]
        )
        model_needed_sl.kvfilter(
            lambda k, v: v
            != patient_details.get_m(k, "skill_level_required", default=0)
        )
        assigned_nurse = patient_details.get_property("nurse")

        # we compare the nurses assignment
        assigned_nurse.kvfilter(lambda k, v: v != model_nurse[k])
        model_nurse.vfilter(lambda v: v is not None).kvfilter(
            lambda k, v: v != assigned_nurse.get_m(k, default=0)
        )

        skill_level_assigned = patient_details.get_property("nurse").vapply(
            lambda v: nurses[v]["skill_level"]
        )
        # we compare the assigned skill level
        skill_level_diff = (
            patient_details.get_property("skill_level_required") - skill_level_assigned
        ).vapply(lambda v: max(v, 0))
        skill_level_assigned.kvfilter(lambda k, v: v != model_skill_level_assigned[k])
        model_skill_level_assigned.kvfilter(
            lambda k, v: v != skill_level_assigned.get_m(k, default=0)
        )
        # we compare skill_level_diff
        (skill_level_diff - model_skill_level_diff).vfilter(lambda v: v > 0)
        model_skill_level_diff.kvfilter(
            lambda k, v: v != skill_level_diff.get_m(k, default=0)
        )
        # Out[31]: {('p16', 33): 1, ('p16', 36): 1, ('p40', 33): 1, ('p47', 10): 1}
        assigned_n_p = patient_details.values_tl().take(["nurse", "id"]).unique2()
        model_nurse_patients = (
            nurse_patient__n_p.vapply(solver.Value)
            .vfilter(lambda v: v > 0)
            .keys_tl()
            .vapply(lambda v: (nurse_id__pos[v[0]], v[1]))
        )
        # we compare the count of nurses to patient
        #  we have one difference.
        assigned_n_p.set_diff(model_nurse_patients)
        model_nurse_patients.set_diff(assigned_n_p)

        # the model assigns more shift-nurses-patients than it should
        model_n_p_s = (
            nurse_patient__n_p_s.vapply(solver.Value)
            .vfilter(lambda v: v > 0)
            .keys_tl()
            .vapply(lambda v: (nurse_id__pos[v[0]], v[1], v[2]))
        )
        assigned_n_p_s = patient_details.values_tl().take(["nurse", "id", "shift"])
        assigned_n_p_s.set_diff(model_n_p_s)
        model_n_p_s.set_diff(assigned_n_p_s)
        # Out[39]: [('n03', 'p56', 34), ('n04', 'p56', 35), ('n09', 'p56', 33)]
        model_p_s = (
            nurse_patient__n_p_s.vapply(solver.Value)
            .vfilter(lambda v: v > 0)
            .keys_tl()
            .vapply(lambda v: (v[1], v[2]))
            .unique2()
        )
        patient_occupants_shifts = self.get_patient_occupant_stay_shifts()
        assigned_p_s = patient_occupants_shifts.vapply(list).to_tuplist()
        assigned_p_s.set_diff(model_p_s)
        model_p_s.set_diff(assigned_p_s)
        # Out[44]: [('p56', 33), ('p56', 34), ('p56', 35)]

        mode_admission_bin = admission_bin.vapply(solver.Value)
        model_stay_bin = stay_bin.vapply(solver.Value)
        # mode_admission_bin.kfilter(lambda k: k[0]=='p56')
        # model_stay_bin.kfilter(lambda k: k[0]=='p56')
        # stay_bin[('p56', 11)]
        # patients['p56']
        patient_occupants_days = self.get_patient_occupant_stay_days()

        # we're counting p4 to have n2, but it's not true.
        # nurse__p_s
        # model.ExportToFile("model.txt")


class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__solution_count = 0

    def on_solution_callback(self):
        self.__solution_count += 1
        print("Objective value: {}".format(self.ObjectiveValue()))
        print("WallTime: {}".format(round(self.WallTime(), 2)))

        print()

    def solution_count(self):
        return self.__solution_count


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
