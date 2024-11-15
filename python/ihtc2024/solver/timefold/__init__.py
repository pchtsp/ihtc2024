from pytups import TupList, SuperDict
import os
import logging
import logging.config

from timefold.solver import SolverFactory, SolutionManager
from timefold.solver.config import (
    SolverConfig,
    ScoreDirectorFactoryConfig,
    TerminationConfig,
    Duration,
)
from timefold.solver.score import HardSoftScore

from ...core import Experiment, Solution
from .domain import (
    Nurse,
    Theater,
    Room,
    ShiftAssignment,
    Surgeon,
    Patient,
    SurgerySchedule,
    Occupant,
    Configuration,
    ConstraintWeightOverrides,
)
from .constraints import define_constraints, CONSTRAINTS
from cornflow_client.constants import SOLUTION_STATUS_FEASIBLE


class TimefoldPy(Experiment):

    def prepare_data(self, options: dict) -> SurgerySchedule:
        ihtc_format = self.instance.to_ihtc_dict()
        age_groups = self.instance.get_agegroups().get_property("pos")
        configuration = Configuration(
            age_groups=age_groups.values_tl().sorted(),
            num_days=self.instance.get_horizon_size_days(),
            num_shifts=self.instance.get_horizon_size_shifts(),
            num_skill_levels=self.instance.get_num_skill_levels(),
        )
        get_shift = self.instance.get_shift_from_day_shiftype
        all_shifts = self.instance.get_horizon_shifts()
        all_days = self.instance.get_horizon_days()
        nurses = SuperDict()
        shifts__nurse = SuperDict()
        for nurse in ihtc_format["nurses"]:
            max_load = [
                (get_shift(v["day"], v["shift"]), v["max_load"])
                for v in nurse["working_shifts"]
            ]
            my_nurse = Nurse(
                id=nurse["id"],
                skill_level=nurse["skill_level"],
                max_load=dict(max_load),
            )
            nurses[nurse["id"]] = my_nurse
            shifts__nurse[nurse["id"]] = TupList(max_load).take(0)

        theaters = {
            theater["id"]: Theater(**theater)
            for theater in ihtc_format["operating_theaters"]
        }
        theaters = SuperDict(theaters)
        surgeons = {
            surgeon["id"]: Surgeon(**surgeon) for surgeon in ihtc_format["surgeons"]
        }
        surgeons = SuperDict(surgeons)

        nurses__shift = shifts__nurse.list_reverse()
        rooms = SuperDict()
        min_max_age = min(age_groups.values_tl())
        max_min_age = max(age_groups.values_tl())
        for r in ihtc_format["rooms"]:
            # min_max_age
            # max_min_age
            my_room = Room(
                id=r["id"],
                capacity=[r["capacity"] for d in all_days],
                min_max_age=[min_max_age for d in all_days],
                max_min_age=[max_min_age for d in all_days],
            )
            rooms[r["id"]] = my_room

        assignments = SuperDict()
        for r in rooms:
            for shift in all_shifts:
                my_id = f"{r}_{shift}"
                my_nurses = nurses__shift[shift].vapply(lambda x: nurses[x])
                shift_assignment = ShiftAssignment(
                    id=my_id,
                    room=rooms[r],
                    shift=shift,
                    nurse_options=set(my_nurses),
                )
                assignments[r, shift] = shift_assignment

        rooms_p = self.instance.get_patients_occupants_available_rooms()
        starts_p = self.instance.get_patient_occupants_available_starts()
        patients = SuperDict()
        for patient in ihtc_format["patients"]:
            surgeon = surgeons[patient["surgeon_id"]]
            # available_days
            room_list = rooms_p[patient["id"]].vapply(lambda x: rooms[x])
            my_dict = dict(
                **patient,
                surgeon=surgeon,
                room_options=set(room_list),
                admission_options=set(starts_p[patient["id"]]),
                config=configuration,
            )
            my_dict["age_group"] = age_groups[patient["age_group"]]
            my_patient = Patient(**my_dict)
            patients[patient["id"]] = my_patient

        occupants = SuperDict()
        for occupant in ihtc_format["occupants"]:
            my_dict = dict(
                **occupant,
                room=rooms[occupant["room_id"]],
                stay=range(occupant["length_of_stay"]),
                stay_shifts=enumerate(range(occupant["length_of_stay"] * 3)),
            )
            my_dict["age_group"] = age_groups[occupant["age_group"]]
            my_occupant = Occupant(**my_dict)
            occupants[occupant["id"]] = my_occupant
            # we pre-process room information:
            room_min_max_age = rooms[occupant["room_id"]].min_max_age
            room_max_min_age = rooms[occupant["room_id"]].max_min_age
            for d in range(occupant["length_of_stay"]):
                room_min_max_age[d] = max(room_min_max_age[d], my_occupant.age_group)
                room_max_min_age[d] = min(room_max_min_age[d], my_occupant.age_group)
                rooms[occupant["room_id"]].capacity[d] -= 1

        equiv = {
            CONSTRAINTS.NURSE_SKILL: "room_nurse_skill",
            CONSTRAINTS.NURSE_CONTINUITY: "continuity_of_care",
            CONSTRAINTS.NURSE_WORKLOAD: "nurse_eccessive_workload",
            CONSTRAINTS.THEATER_OPEN: "open_operating_theater",
            CONSTRAINTS.SURGEON_TRANSFER: "surgeon_transfer",
            CONSTRAINTS.PATIENTS_DELAY: "patient_delay",
            CONSTRAINTS.PATIENTS_UNSCHEDULED: "unscheduled_optional",
            CONSTRAINTS.ROOM_AGE_GROUPS: "room_mixed_age",
        }
        weights = self.instance.get_weights()
        my_weights = SuperDict(equiv).vapply(
            lambda v: HardSoftScore.of_soft(weights[v])
        )
        if options.get("warmStart") and self.solution is not None:
            nurse_assignment = self.solution.get_nurse_assignment()
            patient_assignment = self.solution.get_patient_assignment()
            for elem in nurse_assignment.values():
                my_shift = get_shift(elem["day"], elem["shift"])
                my_assignment = assignments[elem["room"], my_shift]
                my_assignment.nurse = nurses[elem["id"]]
                if options.get("fixSolution"):
                    my_assignment.nurse_options = {nurses[elem["id"]]}

            # if options.get("fixSolution"):
            #     patients = patients.filter(patient_assignment.keys())
            for my_id, my_patient in patients.items():
                if my_id not in patient_assignment:
                    if options.get("fixSolution"):
                        my_patient.room_options = set()
                    continue
                elem = patient_assignment[my_id]
                my_patient.theater = theaters[elem["operating_theater"]]
                my_patient.room = rooms[elem["room"]]
                admission = elem["admission_day"]
                my_patient.admission = admission
                end = min(admission + my_patient.length_of_stay, len(all_days))
                my_patient.stay = list(range(admission, end))
                my_patient.stay_shifts = list(enumerate(range(admission * 3, end * 3)))
                if options.get("fixSolution"):
                    my_patient.admission_options = {admission}
                    my_patient.room_options = {rooms[elem["room"]]}

        return SurgerySchedule(
            patients=patients.values_l(),
            shiftAssignments=assignments.values_l(),
            theaters=theaters.values_l(),
            rooms=rooms.values_l(),
            nurses=nurses.values_l(),
            surgeons=surgeons.values_l(),
            occupants=occupants.values_l(),
            weight_overrides=ConstraintWeightOverrides(my_weights),
        )

    def solve(self, options: dict = None) -> dict:
        if options is None:
            options = {}
        my_dir = os.path.dirname(__file__)
        logging.config.fileConfig(os.path.join(my_dir, "logging.conf"))
        problem = self.prepare_data(options)
        solver_factory = SolverFactory.create(
            SolverConfig(
                solution_class=SurgerySchedule,
                entity_class_list=[Patient, ShiftAssignment],
                score_director_factory_config=ScoreDirectorFactoryConfig(
                    constraint_provider_function=define_constraints
                ),
                termination_config=TerminationConfig(
                    # The solver runs only for 5 seconds on this small dataset.
                    # It's recommended to run for at least 5 minutes ("5m") otherwise.
                    spent_limit=Duration(seconds=options.get("timeLimit", 30))
                ),
            )
        )
        solver = solver_factory.build_solver()
        solution = solver.solve(problem)
        solution_manager = SolutionManager.create(solver_factory)
        analysis = solution_manager.analyze(solution)
        print(analysis.summary)
        sol_patients = TupList(
            SuperDict(
                admission_day=p.admission,
                id=p.id,
                operating_theater=p.theater.id,
                room=p.room.id,
            )
            for p in solution.patients
            if p.room is not None and p.admission is not None and p.theater is not None
        )
        get_shiftday = self.instance.get_shiftype_from_shift
        get_day = self.instance.get_day_from_shift
        sol_nurses = TupList(
            SuperDict(
                room=sA.room.id,
                day=get_day(sA.shift),
                shift=get_shiftday(sA.shift),
                id=sA.nurse.id,
            )
            for sA in solution.shiftAssignments
        )

        sol_data = SuperDict(
            nurse_assignment=sol_nurses, patient_assignment=sol_patients
        )
        self.solution = Solution.from_dict(sol_data)
        # get solution, status
        return dict(status=1, status_sol=SOLUTION_STATUS_FEASIBLE)
