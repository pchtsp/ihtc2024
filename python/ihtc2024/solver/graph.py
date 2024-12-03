import numpy as np

from ..core.experiment import Experiment
from ihtc2024.graph import get_nodes_ady_par, nodes_per_patient
from ihtc2024.graph.graph import GraphTool
import time

from pytups import SuperDict, TupList
import logging as log

from cornflow_client.constants import (
    SOLUTION_STATUS_FEASIBLE,
    SOLUTION_STATUS_INFEASIBLE,
    STATUS_FEASIBLE,
)


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
        log.info(f"start creating nodes")
        nodes_ady = get_nodes_ady_par(
            self.instance, num_workers=options.get("threads", 4)
        )
        log.info(f"end creating nodes: {len(nodes_ady)} nodes")
        log.info(f"Creating Graph")
        my_nodes__p = nodes_per_patient(nodes_ady, self.instance)
        my_graph = GraphTool(
            instance=self.instance,
            nodes_ady=nodes_ady,
            nodes_ady_p=my_nodes__p,
        )
        log.info(f"Graph created: {my_graph.g.num_edges()} edges")
        best_obj = np.Inf
        best_sol = None
        time_limit = options.get("timeLimit", 60)
        for i in range(2):
            for patient_info in patients_occupants_s:
                if time.time() - time_init > time_limit:
                    log.info(f"TimeLimit ({time_limit}) reached")
                    break
                patient_id = patient_info["id"]
                log.debug(f"Pattern: {patient_id}")
                assignment = self.solution.unassign_patient(patient_id)

                errors = self.get_objective_terms_raw()
                errors = {
                    **errors,
                    **self.calculate_coupling_checks(),
                    # "workload_room": self.get_workload_room(),
                }

                pattern = my_graph.nodes_to_pattern(
                    None, None, errors, None, patient_id, self
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
        # if we have a best solution, we store it.
        # if now, we keep the "current solution".
        if best_sol is not None:
            self.solution = best_sol
        errors = self.check_solution()
        sum_errors = get_sum_errors(errors)
        status_sol = SOLUTION_STATUS_FEASIBLE
        if sum_errors > 0:
            status_sol = SOLUTION_STATUS_INFEASIBLE
        return dict(status_sol=status_sol, status=STATUS_FEASIBLE)
