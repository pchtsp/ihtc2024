import numpy as np

from ..core.experiment import Experiment, Instance, Solution, SolStats
from ihtc2024.graph import get_nodes_ady_par, nodes_per_patient
from ihtc2024.graph.graph import GraphTool
import time
import random as rn

from pytups import SuperDict, TupList
from typing import Tuple, Iterable
import logging as log

from ..core.constants import (
    SOLUTION_STATUS_FEASIBLE,
    SOLUTION_STATUS_INFEASIBLE,
    STATUS_ITERATION_LIMIT,
    STATUS_USER_INTERRUPT,
)


class Graph(Experiment):
    my_graph: GraphTool
    init: float
    rng: np.random.Generator

    def __init__(
        self, instance: Instance, solution: Solution = None, group_nurses: bool = True
    ):
        self.rng = np.random.default_rng()
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

    def initialize_best(self) -> SolStats:
        if self.solution is not None:
            return self.get_solStats().copy()
        return SolStats(None, np.Inf, None)

    def elapsed_time(self):
        return round(time.time() - self.init)

    @staticmethod
    def need_recalculate(assignment, change):
        # if the patient was not scheduled and the patient was not added,
        # then there's nothing to recalculate.
        if assignment is None and not change:
            return False
        # also, if the patient was assigned the exact same assignment
        # we do not recalculate
        if change and not change.get("nurses") and assignment == change.get("patient"):
            return False

        return True

    def try_to_add_patient(self, patient_info):
        patient_id = patient_info["id"]
        log.debug(f"Pattern: {patient_id}")
        assignment = self.remove_patient(patient_id)

        errors = self.get_objective_terms_raw()
        errors = {
            **errors,
            **self.calculate_coupling_checks(),
        }

        pattern = self.my_graph.nodes_to_pattern(errors, patient_id, self)
        change = self.apply_pattern(pattern, patient_info)
        return assignment, change

    def solve_patients(
        self,
        options: dict,
        patients_occupants_s: Iterable[dict],
        num_passes: int | None = None,
    ) -> Tuple[SolStats, SolStats]:
        log.info("Solving starts")
        VERBOSE = options.get("msg", False)
        my_callback = options.get("stop_condition", None)
        best_stats = self.initialize_best()
        if num_passes is None:
            if best_stats.get_sum_errors() == 0:
                num_passes = 1
            else:
                num_passes = 2
        curr_stats = best_stats.copy()
        for i in range(num_passes):
            skipped_mandatory = 0
            if i == 1:
                # if we haven't reached feasibility, we leave
                if curr_stats.get_sum_errors() != 0:
                    break
                # the second iteration we shuffle the order of the patients
                rn.shuffle(patients_occupants_s)
            for patient_info in patients_occupants_s:
                time_init = self.init
                time_limit = options.get("timeLimit", 60)
                if time.time() - time_init > time_limit:
                    log.info(f"TimeLimit ({time_limit}) reached")
                    break
                if my_callback is not None:
                    try:
                        my_callback.on_solution_callback()
                    except StopIteration:
                        log.info(f"Stop on user input")
                        return curr_stats, best_stats
                assignment, change = self.try_to_add_patient(patient_info)
                if not change:
                    log.debug(f"Pattern not applied")
                    if patient_info.get("mandatory", True):
                        skipped_mandatory += 1
                        log.error("Pattern not applied to mandatory")
                else:
                    log.debug(f"Pattern applied")
                if self.need_recalculate(assignment, change):
                    curr_stats = self.get_solStats()
                    # we update the best solution if we have a better one
                    if curr_stats < best_stats:
                        best_stats = curr_stats.copy()
                        log.info(f"Best solution found: {best_stats}")
                    # if we have some mandatory patients remaining, we need to quickly fix that first
                    if (
                        curr_stats.get_sum_errors() > 0
                        and curr_stats.get_sum_errors() == skipped_mandatory
                    ):
                        break
                if VERBOSE:
                    log.debug(
                        f"current={curr_stats.get_objective()}; errors={curr_stats.get_sum_errors()}; best={best_stats.get_objective()}"
                    )
        log.info(f"Solving ends")
        return curr_stats, best_stats

    def check_stats_update_solution(
        self,
        curr_stats: SolStats,
        best_stats: SolStats,
        options: dict,
        status=None,
        status_sol=None,
    ) -> dict:
        # if we have some solution in best_sol, we store it.
        # if now, we keep the "current solution".
        my_sol = curr_stats
        if best_stats.solution is not None:
            my_sol = best_stats
        self.solution = my_sol.get_solution()
        sum_errors = my_sol.get_sum_errors()
        if status_sol is None:
            if sum_errors > 0:
                status_sol = SOLUTION_STATUS_INFEASIBLE
            else:
                status_sol = SOLUTION_STATUS_FEASIBLE
        if status is None:
            status = STATUS_ITERATION_LIMIT
            my_callback = options.get("stop_condition", None)
            if isinstance(my_callback, StopOnUserInput):
                # if I stopped it via callback, then I return the status
                if my_callback.__stop:
                    status = STATUS_USER_INTERRUPT
        return dict(status_sol=status_sol, status=status)

    def solve(self, options: dict = None) -> dict:
        self.set_log_config(options)
        patients_occupants = self.instance.get_patients_occupants()
        margin = self.instance.get_patient_occupants_available_starts().vapply(len)
        noise = patients_occupants.vapply(lambda v: rn.random())
        mandatory_margins = (
            patients_occupants.vfilter(lambda v: v.get("mandatory", True))
            .kapply(lambda k: margin[k])
            .values()
        )
        noise = self.rng.normal(0, max(mandatory_margins) / 8, len(margin))
        noise = dict(zip(margin.keys(), noise))

        patients_occupants_s = patients_occupants.values_tl().sorted(
            key=lambda v: (
                not v.get("mandatory", True),
                v["is_occupant"],
                margin[v["id"]] + noise[v["id"]],
            )
        )

        curr_stats, best_stats = self.solve_patients(options, patients_occupants_s)

        return self.check_stats_update_solution(curr_stats, best_stats, options)

    @staticmethod
    def getStopOnUser_callback():
        return StopOnUserInput()


class StopOnUserInput(object):
    __stop: bool

    def __init__(self):
        self.__stop = False

    def on_solution_callback(self):
        if self.__stop:
            raise StopIteration

    def stop(self):
        self.__stop = True

    def reset(self):
        self.__stop = False
