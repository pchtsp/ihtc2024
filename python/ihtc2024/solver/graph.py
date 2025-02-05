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

from typing import Tuple


class Graph(Experiment):
    my_graph: GraphTool

    @staticmethod
    def get_sum_errors(errors):
        return sum(errors.vapply(len).values())

    def __init__(
        self, instance: Instance, solution: Solution = None, group_nurses: bool = True
    ):
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
            group_nurses=group_nurses,
            patient_forbidden=True,
        )
        self.my_graph = my_graph
        log.info(f"Graph created: {my_graph.g.num_edges()} edges")

    def initialize_best(self):
        if self.solution is not None:
            checks = self.check_solution()
            sum_errors = self.get_sum_errors(checks)
            return sum_errors, self.get_objective(), self.solution.copy()
        return np.Inf, np.Inf, None

    def update_best_solution(
        self,
        sum_errors: int,
        best_errors: int,
        objective: float,
        best_obj: float,
        best_sol: Solution,
    ) -> Tuple[int, float, Solution]:
        if (sum_errors, objective) < (best_errors, best_obj):
            return sum_errors, objective, self.solution.copy()
        return best_errors, best_obj, best_sol

    def restart_to_best(
        self,
        sum_errors: int,
        best_errors: int,
        objective: float,
        best_obj: float,
        best_sol: Solution,
    ):
        if best_sol is None:
            return sum_errors, objective
        if (sum_errors, objective) > (best_errors, best_obj):
            self.solution = best_sol.copy()
            return best_errors, best_obj
        return sum_errors, objective

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
        best_errors, best_obj, best_sol = self.initialize_best()
        if best_errors == 0:
            num_passes = 1
        else:
            num_passes = 2
        sum_errors = best_errors
        time_limit = options.get("timeLimit", 60)
        objective = best_obj
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

                pattern = self.my_graph.nodes_to_pattern(errors, patient_id, self)
                success = self.apply_pattern(pattern, patient_info)
                if not success:
                    log.debug(f"Pattern not applied")
                    if patient_info.get("mandatory", True):
                        log.error("Pattern not applied to mandatory")
                else:
                    log.debug(f"Pattern applied")

                # if the patient was not scheduled and the patient was not added,
                # then there's nothing to recalculate.
                recalculate_stats = True
                if assignment is None and not success:
                    recalculate_stats = False
                # also, if the patient was assigned the exact same assignment
                # we do not recalculate
                if (
                    success
                    and not success.get("nurses")
                    and assignment == success.get("patient")
                ):
                    recalculate_stats = False

                if recalculate_stats:
                    objective = self.get_objective()
                    errors = self.check_solution()
                    sum_errors = self.get_sum_errors(errors)
                    best_errors, best_obj, best_sol = self.update_best_solution(
                        sum_errors, best_errors, objective, best_obj, best_sol
                    )
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
