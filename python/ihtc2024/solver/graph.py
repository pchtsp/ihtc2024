import numpy as np

from ..core.experiment import Experiment, Instance, Solution
from ihtc2024.graph import get_nodes_ady_par, nodes_per_patient
from ihtc2024.graph.graph import GraphTool
import time
import random as rn

from pytups import SuperDict, TupList
import logging as log

from cornflow_client.constants import (
    SOLUTION_STATUS_FEASIBLE,
    SOLUTION_STATUS_INFEASIBLE,
    STATUS_FEASIBLE,
)


class Graph(Experiment):
    my_graph: GraphTool

    @staticmethod
    def get_sum_errors(errors):
        return sum(errors.vapply(len).values())

    def __init__(self, instance: Instance, solution: Solution = None):
        Experiment.__init__(self, instance, solution)
        self.init = time.time()
        log.info(f"start creating nodes")
        nodes_ady = get_nodes_ady_par(self.instance, num_workers=4)
        log.info(f"end creating nodes: {len(nodes_ady)} nodes")
        log.info(f"Creating Graph")
        my_nodes__p = nodes_per_patient(nodes_ady, self.instance)
        my_graph = GraphTool(
            instance=self.instance,
            nodes_ady=nodes_ady,
            nodes_ady_p=my_nodes__p,
        )
        self.my_graph = my_graph
        log.info(f"Graph created: {my_graph.g.num_edges()} edges")

    def solve(self, options: dict = None) -> dict:
        self.set_log_config(options)
        time_init = self.init
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
        if self.solution is not None:
            # if we already have a solution
            # we only pass once
            best_sol = self.solution.copy()
            best_obj = self.get_objective()
            num_passes = 1
        else:
            # if we're building a new solution,
            # we do two tours
            best_sol = None
            best_obj = np.Inf
            num_passes = 2

        time_limit = options.get("timeLimit", 60)
        sum_errors = 0
        for i in range(num_passes):
            if i == 1:
                # if we haven't reached feasibility, we leave
                if sum_errors != 0:
                    break
                # the second iteration we shuffle the order of the patients
                rn.shuffle(patients_occupants_s)
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
                }

                pattern = self.my_graph.nodes_to_pattern(
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
                sum_errors = self.get_sum_errors(errors)
                if sum_errors == 0 and objective < best_obj:
                    best_obj = objective
                    best_sol = self.solution.copy()
                log.debug(f"current={objective}; errors={sum_errors}; best={best_obj}")

        # if we have some solution in best_sol, we store it.
        # if now, we keep the "current solution".
        if best_sol is not None:
            self.solution = best_sol
        errors = self.check_solution()
        sum_errors = self.get_sum_errors(errors)
        status_sol = SOLUTION_STATUS_FEASIBLE
        if sum_errors > 0:
            status_sol = SOLUTION_STATUS_INFEASIBLE
        return dict(status_sol=status_sol, status=STATUS_FEASIBLE)
