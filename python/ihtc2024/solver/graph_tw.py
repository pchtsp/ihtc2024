import time
import numpy as np
import statistics as stats
from .graph import Graph

# from .cp_sat import CpSAT

from .cp_sat_2step import CpSAT2Step as CpSAT
from .. import Solution, Instance

from cornflow_client.constants import (
    SOLUTION_STATUS_FEASIBLE,
    SOLUTION_STATUS_INFEASIBLE,
    STATUS_FEASIBLE,
)

import logging as log


class GraphTW(CpSAT, Graph):

    def __init__(self, instance: Instance, solution: Solution = None):
        CpSAT.__init__(self, instance, solution)
        Graph.__init__(self, instance, solution)

    def elapsed_time(self):
        return round(time.time() - self.init)

    def solve(self, options: dict = None) -> dict:
        TIME_LIMIT = options.get("timeLimit", 60)
        VERBOSE = options.get("msg", False)
        best_errors, best_obj, best_sol = self.initialize_best()
        while True:
            # we found a good feasible solution with Graph:
            status = Graph.solve(self, options)
            # we find good candidates for time windows:
            errors = self.check_solution()
            sum_errors = self.get_sum_errors(errors)
            objective = self.get_objective()
            best_errors, best_obj, best_sol = self.update_best_solution(
                sum_errors, best_errors, objective, best_obj, best_sol
            )
            if self.elapsed_time() >= TIME_LIMIT:
                break
            if errors["h5"]:
                pos_starts = (
                    self.instance.get_patient_occupants_available_starts()
                    .filter(errors["h5"])
                    .vapply(list)
                    .to_tuplist()
                    .take(1)
                    .sorted()
                )
                start = stats.median(pos_starts)
                size = 10
                tw = dict(size=size, start=round(start - size / 2))
            else:
                tw = dict(size=10)
            my_options = dict(options)
            stop_condition = dict(ma_size=10, min_imp_per_sec=10, length_bad_imp=10)
            my_options.update(
                dict(
                    maxSample=[None],
                    timeWindow=tw,
                    timeLimit=min(300, TIME_LIMIT - self.elapsed_time()),
                    stop_condition=stop_condition,
                    warmStart=True,
                )
            )
            curr_solution = self.solution.copy()
            status = CpSAT.solve(self, my_options)
            # if we did not find a feasible solution, we go back
            # because we sometimes store it in CpSAT solver
            if status["status_sol"] != SOLUTION_STATUS_FEASIBLE:
                self.solution = curr_solution
            objective = self.get_objective()
            errors = self.check_solution()
            sum_errors = self.get_sum_errors(errors)
            best_errors, best_obj, best_sol = self.update_best_solution(
                sum_errors, best_errors, objective, best_obj, best_sol
            )
            sum_errors, objective = self.restart_to_best(
                sum_errors, best_errors, objective, best_obj, best_sol
            )
            log.debug(f"current={objective}; errors={sum_errors}; best={best_obj}")

            if self.elapsed_time() >= TIME_LIMIT:
                break
        if best_sol is not None:
            self.solution = best_sol
        errors = self.check_solution()
        sum_errors = self.get_sum_errors(errors)
        status_sol = SOLUTION_STATUS_FEASIBLE
        if sum_errors > 0:
            status_sol = SOLUTION_STATUS_INFEASIBLE
        return dict(status_sol=status_sol, status=STATUS_FEASIBLE)
