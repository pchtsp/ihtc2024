from .. import Solution
from ..core.experiment import Experiment
from ortools.sat.python import cp_model

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
        model = cp_model.CpModel()
        patients = self.instance.get_patients()
        possible_start = self.instance.get_patient_occupants_available_starts()
        nurse_shifts = self.instance.get_nurse_shift()
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
        rooms = self.instance.get_rooms().copy_deep()
        for pos, room in enumerate(rooms.values()):
            room["pos"] = pos

        rooms_id__pos = rooms.values_tl().to_dict("id", indices="pos", is_list=False)
        nurses = self.instance.get_nurses().copy_deep()
        for pos, nurse in enumerate(nurses.values()):
            nurse["pos"] = pos
        nurse_id__pos = nurses.values_tl().to_dict("id", indices="pos", is_list=False)
        horizon_days = self.instance.get_horizon_days()
        horizon_days_size = self.instance.get_horizon_size_days()
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
            if surgery_duration[p] <= ot_cap[ot][d]
        )

        hours__ot_p_d = {
            (ot, p, d): model.NewIntVarFromDomain(
                domain=cp_model.Domain.FromValues(values=[0, surgery_duration[p]]),
                name=f"hours_{ot}_{p}_{d}",
            )
            for ot, p, d in domain__ot_p_d
        }
        # definition
        for ot, p, d in domain__ot_p_d:
            model.Add(hours__ot_p_d[ot, p, d] == surgery_duration[p]).OnlyEnforceIf(
                admission_bin[p, d]
            ).OnlyEnforceIf(theater_bin[p, ot])
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

        # kvapply(
        #     lambda k, v: model.NewIntVarFromDomain(
        #         cp_model.Domain.FromValues(values=v), "room_{}".format(k)
        #     )
        # )

        nurse = SuperDict()
        nurses__s = (
            nurse_shifts.values_tl()
            .copy_deep()
            .vapply_col("nurse_pos", lambda v: nurses[v["nurse"]]["pos"])
            .to_dict("nurse_pos", indices="shift_pos")
        )
        for room in rooms:
            for shift, nurses in nurses__s.items():
                nurse[room, shift] = model.NewIntVarFromDomain(
                    domain=cp_model.Domain.FromValues(values=nurses),
                    name="nurse_{}_{}".format(room, shift),
                )

        # constraints:
        # H1
        # TODO: this should be a 2D no-overlap I suspect?
        gender = patients_occupants.get_property("gender")
        patients_list = patients_occupants.keys_tl()
        for pos, p1 in enumerate(patients_list):
            for p2 in patients_list[pos + 1 :]:
                if gender[p1] == gender[p2]:
                    continue
                for d in possible_stay[p1]:
                    if d not in possible_stay[p2]:
                        # if p2 cannot stay in that day, it doesn't matter
                        continue
                    for room_pos in available_rooms__p[p1]:
                        # if the room is not available for p2, it doesn't matter
                        if room_pos not in available_rooms__p[p2]:
                            continue
                        # cannot have the same room, unless they do not share dates.
                        model.Add(
                            room_binary[p1, room_pos] + room_binary[p2, room_pos] <= 1
                        ).OnlyEnforceIf(stay_bin[p1, d]).OnlyEnforceIf(stay_bin[p2, d])

        # H3
        patients__s = (
            patients.get_property("surgeon_id").vapply(lambda v: [v]).list_reverse()
        )

        surgeons_cap = (
            self.instance.get_surgeon_capacity()
            .get_property("max_surgery_time")
            .to_dictdict()
        )
        for surgeon, capacities in surgeons_cap.items():
            _patients = patients__s[surgeon]
            for day, capacity in capacities.items():
                # here I sum all the durations of patients in that day
                model.Add(
                    sum(
                        admission_bin.get((p, day), 0) * surgery_duration[p]
                        for p in _patients
                    )
                    <= capacity
                )
        # H4
        for ot, capacities in ot_cap.items():
            for d, capacity in capacities.items():
                model.Add(
                    sum(hours__ot_p_d.get((ot, p, d), 0) for p in patients) <= capacity
                )
        #  H5
        for p, patient in patients.items():
            all_admissions = sum(admission_bin[p, d] for d in possible_start[p])
            all_rooms = sum(room_binary[p, r] for r in available_rooms__p[p])
            all_theaters = sum(theater_bin[p, ot] for ot in operation_theaters)
            if patient["mandatory"]:
                model.Add(all_admissions == 1)
                model.Add(all_rooms == 1)
                model.Add(all_theaters == 1)
            else:
                model.Add(all_admissions <= 1)
                model.Add(all_rooms <= 1)
                model.Add(all_theaters <= 1)

        errors = model.Validate()
        if errors:
            if options.get("msg", True):
                print(errors)
            raise ValueError("Model not formulated correctly")

        # model.Minimize()
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = options.get("timeLimit", 10)
        if "threads" in options:
            solver.parameters.num_search_workers = options["threads"]
        solution_callback = None

        if options.get("msg", False):
            solution_callback = VarArraySolutionPrinter()

        status = solver.Solve(model, solution_callback=solution_callback)
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
            if options.get("msg", True):
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
        room = transform_to_assignment(room_binary, result_col=1, is_list=False).vapply(
            lambda v: rooms_id__pos[v]
        )
        sol_patients = TupList(
            SuperDict(
                admission_day=admission[p],
                id=p,
                operating_theater=theater[p],
                room=room[p],
            )
            for p in admission
        )
        get_shiftday = self.instance.get_shiftype_from_shift
        get_day = self.instance.get_day_from_shift
        sol_nurses = (
            nurse.vapply(solver.Value)
            .to_tuplist()
            .vapply(
                lambda v: SuperDict(
                    room=v[0],
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
        # Solution.
        # TODO: load solution
        return dict(status=status_conv.get(status), status_sol=SOLUTION_STATUS_FEASIBLE)


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
