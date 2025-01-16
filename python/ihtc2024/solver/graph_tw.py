import time
import numpy as np
from .graph import Graph
from .cp_sat import CpSAT
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
        return time.time() - self.init

    def solve(self, options: dict = None) -> dict:
        TIME_LIMIT = options.get("timeLimit", 60)
        VERBOSE = options.get("msg", False)
        best_obj = np.Inf
        best_sol = None
        while True:
            # we found a good feasible solution with Graph:
            status = Graph.solve(self, options)
            # we find good candidates for time windows:
            if status["status_sol"] == SOLUTION_STATUS_INFEASIBLE:
                errors = self.check_solution()
                tw = dict(size=15)
            else:
                tw = dict(size=20)
            options = dict(options, timeWindow=tw, timeLimit=60, msg=False)
            status = CpSAT.solve(self, options)
            objective = self.get_objective()
            errors = self.check_solution()
            sum_errors = self.get_sum_errors(errors)
            if sum_errors == 0 and objective < best_obj:
                best_obj = objective
                best_sol = self.solution.copy()
            log.debug(f"current={objective}; errors={sum_errors}; best={best_obj}")

            if self.elapsed_time() >= TIME_LIMIT:
                break
        if best_sol is not None:
            self.solution = best_sol
        return status
