import time
import statistics as stats
import random as rn
import numpy as np
from .graph import Graph, SolStats

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
        options["seed"] = options.get("seed", 42)
        rn.seed(options["seed"])
        self.rng = np.random.default_rng(options["seed"])
        options = dict(options)
        TIME_LIMIT = options.get("timeLimit", 60)
        VERBOSE = options.get("msg", False)
        # best_errors, best_obj, best_sol = self.initialize_best()
        best_sol_stats = self.initialize_best()
        run = 0
        max_restart_sec = 5
        while True:
            # we found a good feasible solution with Graph:
            # unless we have a problem finding a feasible solution
            if run == 0:
                # we take at most 2 mins to find a nice solution
                my_time = time.time()
                while time.time() - my_time < max_restart_sec:
                    status = Graph.solve(self, options)
                    curr_sol_stats = self.get_solStats()
                    # if a good solution we keep
                    if curr_sol_stats < best_sol_stats:
                        best_sol_stats = curr_sol_stats.copy()
                    # we restart from scratch
                    # or we just take out half the patients?
                    self.reset_solution()
                    # print(f"Best: {best_sol_stats.get_objective()}")
                # we keep the best of all
                curr_sol_stats = best_sol_stats.copy()
                self.solution = curr_sol_stats.solution
            elif best_sol_stats.get_sum_errors() == 0:
                # we just apply the graph to improve
                status = Graph.solve(self, options)
            # we find good candidates for time windows:
            curr_sol_stats = self.get_solStats()
            if curr_sol_stats < best_sol_stats:
                best_sol_stats = curr_sol_stats.copy()
            if self.elapsed_time() >= TIME_LIMIT:
                break
            timeLimit = min(400, TIME_LIMIT - self.elapsed_time())
            # if True:
            solver = CpSAT2
            size = rn.randint(10, 15)
            maxSampleN = 15
            maxSample = [rn.randint(7, 15)]
            # else:
            #     solver = CpSAT
            #     size = rn.randint(5, 10)
            #     maxSampleN = 7
            #     maxSample = [7]
            if curr_sol_stats.errors["h5"]:
                # we favor feasibility here, so we use CpSAT2 and a large time window
                solver = CpSAT2
                if run == 0:
                    size = rn.randint(10, 20)
                    pos_starts = (
                        self.instance.get_patient_occupants_available_starts()
                        .filter(curr_sol_stats.errors["h5"])
                        .vapply(list)
                        .to_tuplist()
                        .take(1)
                        .sorted()
                    )
                    start = stats.median(pos_starts)
                    tw = dict(size=size, start=round(start - size / 2))
                else:
                    tw = dict(size=self.instance.get_horizon_size_days(), start=0)
                    # maxSample = [None]
                    timeLimit = min(600, TIME_LIMIT - self.elapsed_time())
            else:
                tw = dict(size=size)
            my_options = dict(options)
            stop_condition = dict(ma_size=10, min_imp_per_sec=5, length_bad_imp=5)
            my_options.update(
                dict(
                    maxSample=maxSample,
                    maxSampleN=maxSampleN,
                    timeWindow=tw,
                    timeLimit=timeLimit,
                    stop_condition=stop_condition,
                    warmStart=True,
                    gapRel=0.05,
                )
            )
            curr_solution = self.solution.copy()
            status = solver.solve(self, my_options)
            # if we did not find a feasible solution, we go back
            # because we sometimes store it in CpSAT solver
            if status["status_sol"] != SOLUTION_STATUS_FEASIBLE:
                self.solution = curr_solution
            curr_sol_stats = self.get_solStats()
            if curr_sol_stats < best_sol_stats:
                best_sol_stats = curr_sol_stats.copy()
            elif best_sol_stats < curr_sol_stats:
                curr_sol_stats = best_sol_stats.copy()
                self.solution = curr_sol_stats.solution
            log.debug(
                f"current={curr_sol_stats.get_objective()}; errors={curr_sol_stats.get_sum_errors()}; best={best_sol_stats.get_objective()}"
            )

            if self.elapsed_time() >= TIME_LIMIT:
                break
            run += 1
        my_sol = curr_sol_stats
        if best_sol_stats.solution is not None:
            my_sol = best_sol_stats
        self.solution = my_sol.get_solution()
        sum_errors = my_sol.get_sum_errors()
        if sum_errors > 0:
            status_sol = SOLUTION_STATUS_INFEASIBLE
        else:
            status_sol = SOLUTION_STATUS_FEASIBLE
        return dict(status_sol=status_sol, status=STATUS_FEASIBLE)
