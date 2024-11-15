from timefold.solver.score import (
    constraint_provider,
    HardSoftScore,
    Joiners,
    ConstraintFactory,
    Constraint,
    ConstraintCollectors,
)

from .domain import Patient, Room, Occupant, ShiftAssignment, OccupantPatient


class CONSTRAINTS:
    PATIENTS_MANDATORY = "Assign mandatory"
    PATIENTS_GENDER_MIX = "Patient-patient gender mix"
    OCCUPANTS_GENDER_MIX = "Patient-occupant gender mix"
    SURGEON_OVERTIME = "Surgeon overtime"
    SURGEON_TRANSFER = "Surgeon transfer"
    THEATER_OPEN = "Open theaters"
    ROOM_CAPACITY = "room capacity"
    THEATER_OVERTIME = "theater overtime"
    PATIENTS_UNSCHEDULED = "unscheduled patients"
    PATIENTS_DELAY = "admission delay"
    NURSE_SKILL = "nurse skill"
    NURSE_CONTINUITY = "continuity of care"
    NURSE_WORKLOAD = "nurse workload"
    ROOM_AGE_GROUPS = "Age groups"


@constraint_provider
def define_constraints(factory: ConstraintFactory):
    return [
        plan_all_mandatory(factory),
        gender_dont_mix(factory),
        surgeon_overtime(factory),
        room_capacity(factory),
        theater_overtime(factory),
        gender_dont_mix_occupants(factory),
        surgeon_transfer(factory),
        unscheduled_patients(factory),
        admission_delay(factory),
        open_theaters(factory),
        age_groups(factory),
        continuity_of_care(factory),
        nurse_workload(factory),
        nurse_skill_level(factory),
    ]


def plan_all_mandatory(factory: ConstraintFactory) -> Constraint:
    return (
        factory.for_each_including_unassigned(Patient)
        .filter(lambda p: p.mandatory)
        .filter(lambda p: p.room is None)
        .penalize(HardSoftScore.ONE_HARD)
        .as_constraint(CONSTRAINTS.PATIENTS_MANDATORY)
    )


def gender_dont_mix(factory: ConstraintFactory) -> Constraint:
    return (
        factory.for_each_unique_pair(
            Patient,
            Joiners.overlapping(
                lambda p: p.admission, lambda p: p.admission + p.length_of_stay
            ),
            Joiners.equal(lambda p: p.room),
            Joiners.filtering(lambda p1, p2: p1.gender != p2.gender),
        )
        .penalize(HardSoftScore.ONE_HARD)
        .as_constraint(CONSTRAINTS.PATIENTS_GENDER_MIX)
    )


def gender_dont_mix_occupants(factory: ConstraintFactory) -> Constraint:
    return (
        factory.for_each(Patient)
        .join(
            Occupant,
            Joiners.equal(lambda p: p.room, lambda o: o.room),
            Joiners.filtering(lambda p1, p2: p1.gender != p2.gender),
            Joiners.filtering(lambda p1, p2: p1.admission < p2.length_of_stay),
        )
        .penalize(HardSoftScore.ONE_HARD)
        .as_constraint(CONSTRAINTS.OCCUPANTS_GENDER_MIX)
    )


def surgeon_overtime(factory) -> Constraint:
    return (
        factory.for_each(Patient)
        .group_by(
            lambda p: (p.surgeon, p.admission),
            ConstraintCollectors.sum(lambda p: p.surgery_duration),
        )
        .map(lambda tup, duration: duration - tup[0].max_surgery_time[tup[1]])
        .filter(lambda v: v > 0)
        .penalize(HardSoftScore.ONE_HARD, lambda v: v)
        .as_constraint(CONSTRAINTS.SURGEON_OVERTIME)
    )


def room_capacity(factory):
    return (
        factory.for_each(Patient)
        .map(lambda p: p.room, lambda p: p.stay)
        .flatten_last(lambda p: p)
        .group_by(lambda r, d: (r, d), ConstraintCollectors.count_bi())
        .map(lambda tup, count: count - tup[0].capacity[tup[1]])
        .filter(lambda v: v > 0)
        .penalize(HardSoftScore.ONE_HARD, lambda v: v)
        .as_constraint(CONSTRAINTS.ROOM_CAPACITY)
    )


def theater_overtime(factory):
    return (
        factory.for_each(Patient)
        .group_by(
            lambda p: (p.theater, p.admission),
            ConstraintCollectors.sum(lambda p: p.surgery_duration),
        )
        .map(lambda tup, total: total - tup[0].availability[tup[1]])
        .filter(lambda v: v > 0)
        .penalize(HardSoftScore.ONE_HARD, lambda v: v)
        .as_constraint(CONSTRAINTS.THEATER_OVERTIME)
    )


def admission_delay(factory):
    return (
        factory.for_each(Patient)
        .penalize(HardSoftScore.ONE_SOFT, lambda p: p.admission - p.surgery_release_day)
        .as_constraint(CONSTRAINTS.PATIENTS_DELAY)
    )


def unscheduled_patients(factory):
    return (
        factory.for_each_including_unassigned(Patient)
        .filter(lambda p: p.room is None)
        .penalize(HardSoftScore.ONE_SOFT)
        .as_constraint(CONSTRAINTS.PATIENTS_UNSCHEDULED)
    )


def surgeon_transfer(factory):
    return (
        factory.for_each(Patient)
        .group_by(
            lambda p: (p.surgeon, p.admission),
            ConstraintCollectors.count_distinct(lambda p: p.theater),
        )
        .filter(lambda tup, count: count > 1)
        .penalize(HardSoftScore.ONE_SOFT, lambda tup, count: count - 1)
        .as_constraint(CONSTRAINTS.SURGEON_TRANSFER)
    )


def open_theaters(factory):
    return (
        factory.for_each(Patient)
        .map(lambda p: p.theater, lambda p: p.admission)
        .distinct()
        .penalize(HardSoftScore.ONE_SOFT)
        .as_constraint(CONSTRAINTS.THEATER_OPEN)
    )


def print_my_func(my_func):
    def wrapper(*args, **kwargs):
        result = my_func(*args, **kwargs)
        print(result)
        return result

    return wrapper


def print_and_return(value):
    print(value)
    return value


def age_groups(factory):
    # def get_age_dif_room_day(tup: tuple[Room, int], max_age, min_age):
    #     room, day = tup
    #     return max(room.min_max_age[day], max_age) - min(room.max_min_age[day], min_age)

    return (
        factory.for_each(OccupantPatient)
        # factory.for_each(Patient)
        .filter(lambda p: p.room is not None)
        .map(lambda p: p.room, lambda p: p.age_group, lambda p: p.stay)
        .flatten_last(lambda p: p)
        .group_by(
            lambda r, ag, d: (r, d),
            ConstraintCollectors.max(lambda r, ag, d: ag),
            ConstraintCollectors.min(lambda r, ag, d: ag),
        )
        # .penalize(HardSoftScore.ONE_SOFT, get_age_dif_room_day)
        .penalize(
            HardSoftScore.ONE_SOFT, lambda tup, max_age, min_age: max_age - min_age
        )
        .as_constraint(CONSTRAINTS.ROOM_AGE_GROUPS)
    )


def get_shifts_of_day(day):
    return [day * 3 + i for i in range(3)]


def mega_join_patient_shift(factory):
    return (
        factory.for_each(OccupantPatient)
        .filter(lambda p: p.room is not None)
        .map(lambda p: p, lambda p: p.stay_shifts)
        # .map(lambda p, d: print_and_return(p), lambda p, d: print_and_return(d))
        .flatten_last(lambda p: p)
        # p, (pos, s)
        .join(
            ShiftAssignment,
            Joiners.equal(lambda p, s: p.room, lambda sa: sa.room),
            Joiners.equal(lambda p, s: s[1], lambda sa: sa.shift),
        )
        # p, (pos, s), sa
    )


def continuity_of_care(factory):
    return (
        mega_join_patient_shift(factory)
        # p, (pos, s), sa
        .map(lambda p, s, sa: (p.id, sa.nurse))
        # p, n
        .distinct()
        .penalize(HardSoftScore.ONE_SOFT)
        .as_constraint(CONSTRAINTS.NURSE_CONTINUITY)
    )


def nurse_workload(factory):
    return (
        mega_join_patient_shift(factory)
        # p, (pos, s), sa
        .group_by(
            lambda p, s, sa: (sa.nurse, s[1]),
            ConstraintCollectors.sum(lambda p, s, sa: p.workload_produced[s[0]]),
        )
        # (n, s), sum
        .map(lambda tup, _sum: _sum - tup[0].max_load[tup[1]])
        # number
        .filter(lambda v: v > 0)
        .penalize(HardSoftScore.ONE_SOFT, lambda v: v)
        .as_constraint(CONSTRAINTS.NURSE_WORKLOAD)
    )


def nurse_skill_level(factory):
    return (
        mega_join_patient_shift(factory)
        # p, (pos, s), sa
        .map(
            lambda p, s, sa: p.skill_level_required[s[0]] - sa.nurse.skill_level,
            lambda p, s, sa: (p, s[1], sa),
        )
        # number
        .filter(lambda v, tup: v > 0)
        .penalize(HardSoftScore.ONE_SOFT, lambda v, tup: v)
        .as_constraint(CONSTRAINTS.NURSE_SKILL)
    )
