from ..core.experiment import Experiment
from ihtc2024.graph.node import get_source_node
from ihtc2024.graph.graph import GraphTool
import time

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
    STATUS_FEASIBLE,
)


def print_time(time_init, msg: str):
    print(f"t={round(time.time() - time_init)}", msg)
    return


class Graph(Experiment):

    def solve(self, options: dict = None) -> dict:
        VERBOSE = options.get("msg", False)
        time_init = time.time()
        patients_occupants = self.instance.get_patients_occupants()

        def get_start_margin(v):
            return v.get("surgery_due_day", 0) - v.get("surgery_release_day", 0)

        patients_occupants_s = patients_occupants.values_tl().sorted(
            key=lambda v: (
                not v.get("mandatory", True),
                v["is_occupant"],
                get_start_margin(v),
            )
        )
        nodes_ady = SuperDict()
        source = get_source_node(self.instance)
        if VERBOSE:
            print_time(time_init, "start")
        nodes_ady = source.walk_over_nodes(nodes_ady, max_neighbors=None, max_nurses=7)
        if VERBOSE:
            print_time(time_init, "nodes created")
        my_graph = GraphTool(instance=self.instance, nodes_ady=nodes_ady)
        if VERBOSE:
            print_time(time_init, "graph created")

        for i in range(2):
            for patient_info in patients_occupants_s:
                some_patient = patient_info["id"]
                if VERBOSE:
                    print_time(time_init, f"Pattern: {some_patient}")
                assignment = self.solution.unassign_patient(some_patient)

                errors = self.get_objective_terms_raw()
                errors = {
                    **errors,
                    **self.calculate_coupling_checks(),
                    "workload_room": self.get_workload_room(),
                    "shift_details": self.get_patient_shift_details(),
                }

                pattern = my_graph.nodes_to_pattern(
                    None, None, errors, None, some_patient
                )
                success = self.apply_pattern(pattern, patient_info)
                if not success:
                    if VERBOSE:
                        print("Pattern not applied")
                    if patient_info.get("mandatory", True):
                        raise ValueError("Pattern not applied to mandatory")
                else:
                    if VERBOSE:
                        print("Pattern applied")
                objective = self.get_objective()
                errors = self.check_solution()
                time_now = time.time() - time_init
                if VERBOSE:
                    print(
                        "time={}, current={}, errors={}".format(
                            round(time_now), objective, errors
                        )
                    )
        errors = self.check_solution()
        sum_errors = sum(errors.vapply(len).values())
        status_sol = SOLUTION_STATUS_FEASIBLE
        if not sum_errors:
            status_sol = SOLUTION_STATUS_INFEASIBLE
        return dict(status_sol=status_sol, status=STATUS_FEASIBLE)
