import time
import numpy as np
import statistics as stats
import os
import random as rn
from ortools.sat.python import cp_model
from .cp_sat import CpSAT
from .. import Solution, Instance

from cornflow_client.constants import (
    SOLUTION_STATUS_FEASIBLE,
    SOLUTION_STATUS_INFEASIBLE,
    STATUS_TIME_LIMIT,
    STATUS_UNDEFINED,
    STATUS_OPTIMAL,
    STATUS_INFEASIBLE,
)

status_conv = {
    cp_model.OPTIMAL: STATUS_OPTIMAL,
    cp_model.FEASIBLE: STATUS_OPTIMAL,
    cp_model.INFEASIBLE: STATUS_INFEASIBLE,
    cp_model.UNKNOWN: STATUS_UNDEFINED,
    cp_model.MODEL_INVALID: STATUS_UNDEFINED,
}

import logging as log


class CpSAT2Step(CpSAT):

    def __init__(self, instance: Instance, solution: Solution = None):
        CpSAT.__init__(self, instance, solution)

    def solve(self, options: dict = None) -> dict:
        options = dict(options)
        stop_condition = dict(ma_size=20, min_imp_per_sec=5, length_bad_imp=20)
        options["stop_condition"] = options.get("stop_condition", stop_condition)
        options["seed"] = options.get("seed", 42)
        rn.seed(options["seed"])
        VERBOSE = options.get("msg", False)
        TIME_WINDOW = options.get("timeWindow")
        TIME_LIMIT = options.get("timeLimit", 100)
        WARM_START = options.get("warmStart", False)
        MAX_SAMPLE_OPTIONS = options.get("maxSample", [7, 10, None])
        if TIME_WINDOW:
            MAX_SAMPLE_OPTIONS = [None]
        if VERBOSE:
            self.print_time("Building of model starts")

        solver = cp_model.CpSolver()
        status1 = STATUS_UNDEFINED
        for max_sample in MAX_SAMPLE_OPTIONS:
            if VERBOSE:
                self.print_time(f"Phase1: maxSample: {max_sample}")
            my_options_1 = dict(options)
            my_options_1["maxSample"] = max_sample
            my_options_1["timeLimit"] = min(TIME_LIMIT, 500)
            if "logPath" in my_options_1:
                name, ext = os.path.splitext(my_options_1["logPath"])
                my_options_1["logPath"] = name + "_pre" + ext

            model = cp_model.CpModel()
            if VERBOSE:
                self.print_time("Non-nurse constraints")
            my_vars = self.add_non_nurse_constraints(model, my_options_1)

            if VERBOSE:
                self.print_time("Objective function")
            self.get_objective_function(model, my_vars)
            if self.solution and (TIME_WINDOW or WARM_START):
                self.warm_start(model, my_vars)
            status1 = self.call_solver(model, solver, my_options_1)
            if status1 in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                # as soon as we find a feasible solution, we exit
                break

        if status1 not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            if VERBOSE:
                print("No solution was found")
            return dict(
                status=STATUS_TIME_LIMIT,
                status_sol=SOLUTION_STATUS_INFEASIBLE,
            )
        sol_data = self.my_vars_to_solution(solver, my_vars)
        self.solution = Solution.from_dict(sol_data)
        # here we warm start the values of non-nurse variables
        self.warm_start(model, my_vars)
        # here we fix the values of admissions, room assignments, theater and stay
        for var_name in ["admission_bin", "room_binary", "theater_bin"]:
            my_vars[var_name] = my_vars[var_name].vfilter(solver.Value)

        if VERBOSE:
            self.print_time("Nurse constraints")

        # we add the nurse constraints
        my_vars = self.add_nurse_constraints2(model, my_vars)
        if VERBOSE:
            self.print_time("Objective function constraints")

        # we add the complete objective function
        self.get_objective_function(model, my_vars)
        # we subtract the elapsed time from the time limit
        my_options_2 = dict(options)
        my_options_2["timeLimit"] = TIME_LIMIT - min(
            my_options_1["timeLimit"], solver.UserTime()
        )
        my_options_2["timeLimit"] = max(my_options_2["timeLimit"], 10)
        my_options_2["fixSolution"] = True
        status = self.call_solver(model, solver, my_options_2)

        if options.get("msg", False):
            print(f"Model finished with status {status_conv.get(status)}")

        if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            if VERBOSE:
                print("No solution was found")
            return dict(
                status=status_conv.get(status), status_sol=SOLUTION_STATUS_INFEASIBLE
            )

        sol_data = self.my_vars_to_solution(solver, my_vars)
        self.solution = Solution.from_dict(sol_data)

        return dict(status=status_conv.get(status), status_sol=SOLUTION_STATUS_FEASIBLE)
