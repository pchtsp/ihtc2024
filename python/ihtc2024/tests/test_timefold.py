import unittest
from timefold.solver.test import ConstraintVerifier
from datetime import datetime, date, time, timedelta
from ihtc2024 import solvers
import os, sys
from .tests import BaseTestInstance

tests_dir = os.path.dirname(__file__)
root_dir = os.path.join(tests_dir, "../")
my_paths = [root_dir]
for __my_path in my_paths:
    sys.path.insert(1, __my_path)

from ihtc2024.solver.timefold.constraints import (
    room_capacity,
    define_constraints,
    gender_dont_mix,
    surgeon_transfer,
    open_theaters,
    age_groups,
    continuity_of_care,
    nurse_workload,
    nurse_skill_level,
)
from ihtc2024.solver.timefold.domain import (
    SurgerySchedule,
    Room,
    Patient,
    Surgeon,
    Configuration,
    Theater,
    Nurse,
    ShiftAssignment,
)


constraint_verifier = ConstraintVerifier.build(
    define_constraints, SurgerySchedule, Patient, ShiftAssignment
)
PATH_TO_VALIDATOR = os.path.join(root_dir, "../../validator/IHTP_Validator")

class TestInstance(BaseTestInstance):
    
    def test_solve_toy_timefold(self):
        my_experim = solvers["timefold_py"](self.instance)
        my_experim.solve(dict(timeLimit=5, msg=True))
        checks = my_experim.check_solution()

        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)
        my_experim.run_validator(PATH_TO_VALIDATOR)

    def test_solve_test_instance_1_timefold(self):
        my_experim_solved = self.get_solved_experiment("test01.json")
        print(my_experim_solved.get_objective())
        my_experim_solved.run_validator(PATH_TO_VALIDATOR)
        my_experim = solvers["timefold_py"](
            my_experim_solved.instance, my_experim_solved.solution
        )
        my_experim.solve(
            dict(warmStart=True, timeLimit=60, msg=True, fixSolution=False)
        )
        checks = my_experim.check_solution()
        print(checks)
        # self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)
        my_experim.run_validator(PATH_TO_VALIDATOR)

class TestTimefold(unittest.TestCase):
    def setUp(self):
        self.room0 = Room(
            id="r0",
            capacity=[1, 1, 1],
            min_max_age=[1, 1, 1, 1],
            max_min_age=[3, 3, 3, 3],
        )
        self.room1 = Room(
            id="r1",
            capacity=[1, 1, 1],
            min_max_age=[1, 1, 1, 1],
            max_min_age=[3, 3, 3, 3],
        )
        self.surgeon1 = Surgeon(id="s1", maxSurgeryTime=[100])
        self.theater1 = Theater(id="t1", availability=[100])
        self.theater2 = Theater(id="t2", availability=[100])
        config = Configuration(
            num_days=3, age_groups=[1, 2, 3], num_shifts=3, num_skill_levels=1
        )
        other_params = dict(
            mandatory=True,
            surgery_duration=0,
            skill_level_required=[2, 1, 0] * 3,
            workload_produced=[1, 2, 1] * 3,
            room_options=[self.room0, self.room1],
            admission_options=[0, 1],
            config=config,
        )
        self.patient1 = Patient(
            ageGroup=3,
            id="p1",
            room=self.room0,
            admission=0,
            length_of_stay=2,
            **other_params,
            stay=range(0, 2),
            stay_shifts=enumerate(range(0, 6)),
            gender="M",
            surgeon=self.surgeon1,
            theater=self.theater1,
        )
        self.patient2 = Patient(
            ageGroup=2,
            surgeon=self.surgeon1,
            id="p2",
            room=self.room0,
            admission=1,
            length_of_stay=2,
            **other_params,
            stay=range(1, 3),
            stay_shifts=range(3, 9),
            gender="F",
            theater=self.theater1,
        )
        self.patient3 = Patient(
            ageGroup=1,
            surgeon=self.surgeon1,
            id="p3",
            room=self.room1,
            admission=1,
            length_of_stay=2,
            **other_params,
            stay=range(1, 3),
            stay_shifts=range(3, 9),
            gender="F",
            theater=self.theater2,
        )
        self.patient4 = Patient(
            ageGroup=1,
            surgeon=self.surgeon1,
            id="p4",
            room=self.room0,
            admission=1,
            length_of_stay=3,
            **other_params,
            stay=range(1, 4),
            stay_shifts=range(3, 12),
            gender="F",
            theater=self.theater1,
        )
        self.patients = [self.patient1, self.patient2, self.patient3, self.patient4]
        max_load = dict(zip(range(12), [1] * 12))
        self.nurse1 = Nurse(id="n1", skill_level=0, max_load=max_load)
        self.nurse2 = Nurse(id="n1", skill_level=2, max_load=max_load)
        self.nurse3 = Nurse(id="n1", skill_level=3, max_load=max_load)
        self.nurses = [self.nurse1, self.nurse2, self.nurse3]
        self.assignment1 = ShiftAssignment(
            id="sa1", room=self.room0, shift=3, nurse=self.nurse1
        )
        self.assignment2 = ShiftAssignment(
            id="sa1", room=self.room0, shift=4, nurse=self.nurse2
        )
        self.assignment3 = ShiftAssignment(
            id="sa2", room=self.room0, shift=5, nurse=self.nurse3
        )
        self.assignment4 = ShiftAssignment(
            id="sa3", room=self.room1, shift=3, nurse=self.nurse1
        )
        self.assignment5 = ShiftAssignment(
            id="sa4", room=self.room1, shift=4, nurse=self.nurse2
        )
        self.assignment6 = ShiftAssignment(
            id="sa5", room=self.room1, shift=5, nurse=self.nurse3
        )
        self.assignment7 = ShiftAssignment(
            id="sa6", room=self.room1, shift=6, nurse=self.nurse1
        )
        self.assignments = [
            self.assignment1,
            self.assignment2,
            self.assignment3,
            self.assignment4,
            self.assignment5,
            self.assignment6,
            self.assignment7,
        ]

    def test_room_capacity(self):
        (
            constraint_verifier.verify_that(room_capacity)
            .given(
                self.room0, self.patient1, self.patient2, self.surgeon1, self.theater1
            )
            .penalizes_by(1)
        )

    def test_gender_dont_mix(self):

        (
            constraint_verifier.verify_that(gender_dont_mix)
            .given(
                self.room0, self.patient1, self.patient2, self.surgeon1, self.theater1
            )
            .penalizes_by(1)
        )

    def test_surgeon_transfer(self):
        (
            constraint_verifier.verify_that(surgeon_transfer)
            .given(
                self.room0,
                self.room1,
                *self.patients,
                self.surgeon1,
                self.theater1,
                self.theater2,
            )
            .penalizes_by(1)
        )

    def test_open_theaters(self):
        (
            constraint_verifier.verify_that(open_theaters)
            .given(
                self.room0,
                self.room1,
                *self.patients,
                self.surgeon1,
                self.theater1,
                self.theater2,
            )
            .penalizes_by(3)
        )

    def test_age_groups(self):
        (
            constraint_verifier.verify_that(age_groups)
            .given(
                self.room0,
                self.room1,
                *self.patients,
                self.surgeon1,
                self.theater1,
                self.theater2,
            )
            .penalizes_by(3)
        )

    def test_continuity_of_care(self):
        (
            constraint_verifier.verify_that(continuity_of_care).given(
                self.room0,
                self.room1,
                *self.patients,
                *self.assignments,
                *self.nurses,
                self.surgeon1,
                self.theater1,
                self.theater2,
            )
            # 4 patients, each with one nurse assigned in 3-4 shifts
            .penalizes_by(4)
        )

    def test_nurse_workload(self):
        (
            constraint_verifier.verify_that(nurse_workload)
            .given(
                self.room0,
                self.room1,
                *self.patients,
                *self.assignments,
                *self.nurses,
                self.surgeon1,
                self.theater1,
                self.theater2,
            )
            .penalizes_by(13)
        )

    def test_nurse_skill_level(self):
        (
            constraint_verifier.verify_that(nurse_skill_level)
            .given(
                self.room0,
                self.room1,
                *self.patients,
                *self.assignments,
                *self.nurses,
                self.surgeon1,
                self.theater1,
                self.theater2,
            )
            .penalizes_by(10)
        )
