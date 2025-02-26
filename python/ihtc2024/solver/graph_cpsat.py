import time
import statistics as stats
import random as rn
import numpy as np
from .graph import Graph, SolStats

from .cp_sat import CpSAT

from .. import Solution, Instance

from cornflow_client.constants import (
    SOLUTION_STATUS_FEASIBLE,
    SOLUTION_STATUS_INFEASIBLE,
    STATUS_FEASIBLE,
)

import logging as log


class GraphCP(CpSAT, Graph):

    def __init__(self, instance: Instance, solution: Solution = None):
        CpSAT.__init__(self, instance, solution)
        Graph.__init__(self, instance, solution)

    def solve(self, options: dict = None) -> dict:
        options["seed"] = options.get("seed", 42)
        rn.seed(options["seed"])
        self.rng = np.random.default_rng(options["seed"])
        options = dict(options)
        TIME_LIMIT = options.get("timeLimit", 60)
        best_sol_stats = self.initialize_best()
        max_restart_sec = min(options.get("maxRestartSec", 120), TIME_LIMIT // 2)
        # we found a good feasible solution with Graph:
        # unless we have a problem finding a feasible solution
        # we take at most X seconds to find a nice solution
        my_time = time.time()
        while time.time() - my_time < max_restart_sec:
            status = Graph.solve(self, options)
            curr_sol_stats = self.get_solStats()
            # if a good solution we keep
            if curr_sol_stats < best_sol_stats:
                best_sol_stats = curr_sol_stats.copy()
                log.info(f"GraphCP: Best solution found: {best_sol_stats}")
            # we restart from scratch
            self.reset_solution()
        # we keep the best of all
        curr_sol_stats = best_sol_stats.copy()
        self.solution = curr_sol_stats.solution

        solver = CpSAT
        maxSampleN = 15
        maxSample = [15]
        timeLimit = TIME_LIMIT - self.elapsed_time()
        my_options = dict(options)
        my_options.update(
            dict(
                maxSample=maxSample,
                maxSampleN=maxSampleN,
                timeLimit=timeLimit,
                stop_condition=None,
                warmStart=True,
                gapRel=0,
            )
        )
        status = solver.solve(self, my_options)
        # if we did not find a feasible solution, we go back
        # because we sometimes store it in CpSAT solver
        curr_sol_stats = self.get_solStats()
        if curr_sol_stats < best_sol_stats:
            best_sol_stats = curr_sol_stats.copy()
        elif best_sol_stats < curr_sol_stats:
            curr_sol_stats = best_sol_stats.copy()
            self.solution = curr_sol_stats.solution
        return self.check_stats_update_solution(curr_sol_stats, best_sol_stats, options)
