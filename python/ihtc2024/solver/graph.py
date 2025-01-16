import numpy as np

from ..core.experiment import Experiment, Instance, Solution
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


class Graph(Experiment):
    my_graph: GraphTool

    @staticmethod
    def get_sum_errors(errors):
        return sum(errors.vapply(len).values())

    def __init__(self, instance: Instance, solution: Solution = None):
        super().__init__(instance, solution)
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

        # TODO: try to guarantee feasible solution?
        # possibilities:
        # gender, surgeon capacity, room capacity, theater capacity
        # available days:
        # av_days = self.instance.get_patient_occupants_available_starts()[
        #     patient_info["id"]
        # ]
        # s_available = errors['surgeon_overtime'].to_dictdict()[patient_info["surgeon_id"]].vfilter(lambda v: v <= -patient_info['surgery_duration'])
        # ots_available = errors['ot_overtime'].vfilter(lambda v: v < -patient_info['surgery_duration']).keys_tl().to_dict(0)
        # set(av_days) & set(s_available) & set(ots_available)
        # patient_info["gender"]
        # errors['gender'].
        # errors.keys()

        # if we have a best solution, we store it.
        # if now, we keep the "current solution".
        if best_sol is not None:
            self.solution = best_sol
        errors = self.check_solution()
        sum_errors = self.get_sum_errors(errors)
        status_sol = SOLUTION_STATUS_FEASIBLE
        if sum_errors > 0:
            status_sol = SOLUTION_STATUS_INFEASIBLE
        return dict(status_sol=status_sol, status=STATUS_FEASIBLE)
