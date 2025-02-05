import time
import statistics as stats
import random as rn
from .graph import Graph

from .cp_sat import CpSAT

from .cp_sat_2step import CpSAT2Step as CpSAT2
from .. import Solution, Instance

from cornflow_client.constants import (
    SOLUTION_STATUS_FEASIBLE,
    SOLUTION_STATUS_INFEASIBLE,
    STATUS_FEASIBLE,
)

import logging as log


class GraphTW(CpSAT2, Graph):

    def __init__(self, instance: Instance, solution: Solution = None):
        CpSAT.__init__(self, instance, solution)
        Graph.__init__(self, instance, solution)

    def elapsed_time(self):
        return round(time.time() - self.init)

    def solve(self, options: dict = None) -> dict:
        options = dict(options)
        TIME_LIMIT = options.get("timeLimit", 60)
        VERBOSE = options.get("msg", False)
        options["seed"] = options.get("seed", 42)
        rn.seed(options["seed"])
        best_errors, best_obj, best_sol = self.initialize_best()
        run = 0
        while True:
            # we found a good feasible solution with Graph:
            # unless we have a problem finding a feasible solution
            if run == 0 or best_errors == 0:
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
            timeLimit = min(400, TIME_LIMIT - self.elapsed_time())
            if run % 2 == 0:
                solver = CpSAT2
                size = rn.randint(10, 15)
                maxSampleN = 15
                maxSample = [15]
            else:
                solver = CpSAT
                size = rn.randint(5, 10)
                maxSampleN = 7
                maxSample = [7]
            if errors["h5"]:
                # we favor feasibility here, so we use CpSAT2 and a large time window
                solver = CpSAT2
                if run == 0:
                    size = rn.randint(10, 20)
                    pos_starts = (
                        self.instance.get_patient_occupants_available_starts()
                        .filter(errors["h5"])
                        .vapply(list)
                        .to_tuplist()
                        .take(1)
                        .sorted()
                    )
                    start = stats.median(pos_starts)
                    tw = dict(size=size, start=round(start - size / 2))
                else:
                    tw = dict(size=self.instance.get_horizon_size_days(), start=0)
                    maxSample = [None]
                    timeLimit = min(600, TIME_LIMIT - self.elapsed_time())
            else:
                tw = dict(size=size)
            my_options = dict(options)
            stop_condition = dict(ma_size=10, min_imp_per_sec=5, length_bad_imp=10)
            my_options.update(
                dict(
                    maxSample=maxSample,
                    maxSampleN=maxSampleN,
                    timeWindow=tw,
                    timeLimit=timeLimit,
                    stop_condition=stop_condition,
                    warmStart=True,
                )
            )
            curr_solution = self.solution.copy()
            status = solver.solve(self, my_options)
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
            run += 1
        if best_sol is not None:
            self.solution = best_sol
        errors = self.check_solution()
        sum_errors = self.get_sum_errors(errors)
        status_sol = SOLUTION_STATUS_FEASIBLE
        if sum_errors > 0:
            status_sol = SOLUTION_STATUS_INFEASIBLE
        return dict(status_sol=status_sol, status=STATUS_FEASIBLE)
