import numpy as np

from .. import Solution
from ..core.experiment import Experiment
from ihtc2024.graph.node import get_source_node
from ihtc2024.graph.graph import GraphTool
import time

from pytups import SuperDict, TupList
import logging as log

from cornflow_client.constants import (
    SOLUTION_STATUS_FEASIBLE,
    SOLUTION_STATUS_INFEASIBLE,
    STATUS_FEASIBLE,
)


def print_time(time_init, msg: str):
    print(f"t={round(time.time() - time_init)}", msg)
    return


def get_sum_errors(errors):
    return sum(errors.vapply(len).values())


class Graph(Experiment):

    def solve(self, options: dict = None) -> dict:
        self.set_log_config(options)

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
        log.info(f"start creating nodes")
        nodes_ady = source.walk_over_nodes(nodes_ady, max_neighbors=None, max_nurses=7)
        log.info(f"end creating nodes: {len(nodes_ady)} nodes")
        my_graph = GraphTool(instance=self.instance, nodes_ady=nodes_ady)
        all_graphs = {}
        for patient_info in patients_occupants_s:
            my_id = patient_info["id"]
            all_graphs[my_id] = GraphTool(
                my_graph.instance,
                nodes_ady=None,
                gt=my_graph,
                patient_info=patient_info,
            )

        log.info(f"Graph created: {my_graph.g.num_edges()} edges")
        best_obj = np.Inf
        best_sol = None
        for i in range(2):
            for patient_info in patients_occupants_s:
                if time.time() - time_init > options.get("timeLimit", 60):
                    break
                patient_id = patient_info["id"]
                log.debug(f"Pattern: {patient_id}")
                assignment = self.solution.unassign_patient(patient_id)

                errors = self.get_objective_terms_raw()
                errors = {
                    **errors,
                    **self.calculate_coupling_checks(),
                    "workload_room": self.get_workload_room(),
                    "shift_details": self.get_patient_shift_details(),
                }

                pattern = all_graphs[patient_id].nodes_to_pattern(
                    None, None, errors, None, patient_id
                )
                success = self.apply_pattern(pattern, patient_info)
                if not success:
                    log.debug(f"Pattern not applied")
                    if patient_info.get("mandatory", True):
                        log.error("Pattern not applied to mandatory")
                else:
                    log.debug(f"Pattern applied")

                objective = self.get_objective()
                errors = self.check_solution()
                sum_errors = get_sum_errors(errors)
                if get_sum_errors(errors) == 0 and objective < best_obj:
                    best_obj = objective
                    best_sol = self.solution.copy()
                log.debug(f"current={objective}; errors={sum_errors}; best={best_obj}")
        if best_sol is None:
            empty_solution = SuperDict(
                patient_assignment=TupList(), nurse_assignment=TupList()
            )
            self.solution = Solution.from_dict(empty_solution)
        else:
            self.solution = best_sol
        errors = self.check_solution()
        sum_errors = get_sum_errors(errors)
        status_sol = SOLUTION_STATUS_FEASIBLE
        if sum_errors > 0:
            status_sol = SOLUTION_STATUS_INFEASIBLE
        return dict(status_sol=status_sol, status=STATUS_FEASIBLE)
