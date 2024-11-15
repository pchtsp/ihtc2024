# from timefold.solver import SolverStatus
from timefold.solver.domain import (
    ValueRangeProvider,
    PlanningVariable,
    PlanningId,
    planning_entity,
    planning_solution,
    # ValueRangeFactory,
    # CountableValueRange,
    PlanningEntityCollectionProperty,
    ProblemFactCollectionProperty,
    PlanningScore,
    ShadowVariable,
    PiggybackShadowVariable,
    VariableListener,
    DeepPlanningClone,
    ConstraintWeightOverrides,
)
from timefold.solver.score import (
    HardSoftScore,
    ScoreDirector,
)
from typing import Annotated
from pydantic import Field

from .json_serialization import JsonDomainBase, ScoreSerializer, ScoreValidator
from dataclasses import dataclass, field


class Nurse(JsonDomainBase):
    id: str
    skill_level: int
    max_load: Annotated[dict[int, int], Field(default_factory=list)]

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id

    def __str__(self):
        return f"Nurse {self.id}"

    def __repr__(self):
        return self.__str__()


class Theater(JsonDomainBase):
    id: str
    availability: list[int]

    def __str__(self):
        return f"Theater {self.id}"

    def __repr__(self):
        return self.__str__()


class Room(JsonDomainBase):
    id: str
    capacity: list[int]
    min_max_age: list[int]
    max_min_age: list[int]

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id

    def __str__(self):
        return f"Room {self.id}"

    def __repr__(self):
        return self.__str__()


class OccupantPatient(JsonDomainBase):
    age_group: int
    gender: str
    length_of_stay: int
    skill_level_required: list[int]
    workload_produced: list[int]


class Occupant(OccupantPatient):
    id: str
    room: Room
    stay_shifts: list[list[int, int]]
    stay: list[int]

    def __str__(self):
        return f"Occupant {self.id}"

    def __repr__(self):
        return self.__str__()


class PatientUpdatingVariableListener(VariableListener):
    def after_entity_added(self, score_director: ScoreDirector, patient):
        self.update_stay(score_director, patient)

    def after_variable_changed(self, score_director: ScoreDirector, patient):
        self.update_stay(score_director, patient)

    @staticmethod
    def update_stay(score_director: ScoreDirector, patient) -> None:
        score_director.before_variable_changed(patient, "stay")
        score_director.before_variable_changed(patient, "stay_shifts")
        # for some reason we cannot replace the contents of the attribute, only modify it
        if patient.room is None:
            patient.stay.clear()
            patient.stay_shifts.clear()
        else:
            admission = patient.admission
            patient.stay.clear()
            patient.stay_shifts.clear()
            end = min(patient.config.num_days, admission + patient.length_of_stay)
            patient.stay.extend(range(admission, end))
            patient.stay_shifts.extend(enumerate(range(admission * 3, end * 3)))
        score_director.after_variable_changed(patient, "stay")
        score_director.after_variable_changed(patient, "stay_shifts")


@planning_entity
class ShiftAssignment(JsonDomainBase):
    id: Annotated[str, PlanningId]
    room: Annotated[Room, Field(default=None)]
    shift: Annotated[int, Field(default=0)]
    nurse_options: Annotated[
        set[Nurse], Field(default_factory=set), ValueRangeProvider(id="nurse_options")
    ]
    nurse: Annotated[
        Nurse,
        PlanningVariable(value_range_provider_refs=["nurse_options"]),
        Field(default=None),
    ]

    def __str__(self):
        return f"Assignment {self.id}"

    def __repr__(self):
        return self.__str__()


class Surgeon(JsonDomainBase):
    id: str
    max_surgery_time: list[int]

    def __str__(self):
        return f"Surgeon {self.id}"

    def __repr__(self):
        return self.__str__()


class Configuration(JsonDomainBase):
    num_days: int
    age_groups: list[int]
    num_shifts: int
    num_skill_levels: int


@planning_entity
class Patient(OccupantPatient):
    id: Annotated[str, PlanningId]
    mandatory: bool
    surgeon: Surgeon
    surgery_duration: int
    surgery_release_day: int
    room_options: Annotated[set[Room], ValueRangeProvider(id="room_options")]
    theater: Annotated[Theater | None, PlanningVariable, Field(default=None)]
    # only admission is allows_unassigned=True
    admission: Annotated[
        int | None,
        PlanningVariable(value_range_provider_refs=["admission_options"]),
        Field(default=None),
    ]
    room: Annotated[
        Room | None,
        PlanningVariable(
            value_range_provider_refs=["room_options"], allows_unassigned=True
        ),
        Field(default=None),
    ]
    # TODO: we could use CountableValueRange
    admission_options: Annotated[set[int], ValueRangeProvider(id="admission_options")]
    config: Configuration
    # shadow variable with the patient complete stay days:
    stay: Annotated[
        list[int],
        DeepPlanningClone,
        ShadowVariable(
            variable_listener_class=PatientUpdatingVariableListener,
            source_variable_name="admission",
        ),
        Field(default_factory=list),
    ]
    # shadow variable with the patient complete stay shifts:
    stay_shifts: Annotated[
        list[list[int]],
        DeepPlanningClone,
        PiggybackShadowVariable(shadow_variable_name="stay"),
        Field(default_factory=list),
    ]

    def __str__(self):
        return f"Patient {self.id}"

    def __repr__(self):
        return self.__str__()


# TODO: if I use pedantic (JsonDomainBase), it complains about ConstraintWeightOverrides
@dataclass
@planning_solution
class SurgerySchedule:
    patients: Annotated[
        list[Patient], PlanningEntityCollectionProperty, ValueRangeProvider
    ]
    shiftAssignments: Annotated[
        list[ShiftAssignment], PlanningEntityCollectionProperty, ValueRangeProvider
    ]
    nurses: Annotated[list[Nurse], ProblemFactCollectionProperty, ValueRangeProvider]
    rooms: Annotated[list[Room], ProblemFactCollectionProperty, ValueRangeProvider]
    theaters: Annotated[
        list[Theater], ProblemFactCollectionProperty, ValueRangeProvider
    ]
    surgeons: Annotated[
        list[Surgeon], ProblemFactCollectionProperty, ValueRangeProvider
    ]
    occupants: Annotated[
        list[Occupant], ProblemFactCollectionProperty, ValueRangeProvider
    ]
    weight_overrides: ConstraintWeightOverrides
    score: Annotated[
        HardSoftScore | None,
        PlanningScore,
        ScoreSerializer,
        ScoreValidator,
    ] = field(default=None)
