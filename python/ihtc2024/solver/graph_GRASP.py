import logging as log
from .graph import Graph, SolStats
import random as rn


from .. import Solution, Instance


class GraphGRASP(Graph):

    def __init__(self, instance: Instance, solution: Solution = None):
        Graph.__init__(self, instance, solution)

    def solve(self, options: dict = None) -> dict:
        VERBOSE = options.get("msg", False)
        options = dict(options)
        options["msg"] = False
        self.set_log_config(options)
        # we get an initial solution, using the basic class
        status = Graph.solve(self, options)
        all_patients = self.instance.get_patients_occupants()
        all_patients_keys = all_patients.keys()
        best_stats = self.initialize_best()
        curr_stats = best_stats.copy()
        TIME_LIMIT = options.get("timeLimit", 60)
        margin = (
            self.instance.get_patient_occupants_available_starts()
            .vapply(len)
            .filter(all_patients_keys)
        )
        mandatory_margins = margin.kfilter(
            lambda k: all_patients[k].get("mandatory", True)
        ).values()
        is_mandatory = all_patients.get_property("mandatory")

        def get_priority(mandatory, margin, noise):
            if mandatory:
                margin = margin * 0.2

            return margin + noise

        # now, we want to:
        # 1. take out some patients from the solution.
        while True:
            if curr_stats < best_stats:
                best_stats = curr_stats.copy()
            elif best_stats < curr_stats:
                curr_stats = best_stats
            if self.elapsed_time() >= TIME_LIMIT:
                break
            patients = self.solution.get_patient_assignment()
            population = patients.keys()
            percentage_keep = 0.3
            num_to_take_out = round((1 - percentage_keep) * len(population))
            out = rn.sample(sorted(population), num_to_take_out)
            for p in out:
                self.remove_patient(p)
            # now, let's try to add some patients

            remaining = (
                all_patients_keys - self.solution.get_patient_assignment().keys()
            )
            noise = self.rng.normal(0, max(mandatory_margins) / 4, len(remaining))
            noise = dict(zip(remaining, noise))
            my_priority = lambda v: get_priority(
                is_mandatory.get(v["id"], True), margin[v["id"]], noise[v["id"]]
            )
            my_list_to_add = (
                all_patients.filter(remaining).values_tl().sorted(key=my_priority)
            )
            _, curr_stats = Graph.solve_patients(
                self, options, my_list_to_add, num_passes=1
            )
            if VERBOSE:
                log.info(
                    f"current={curr_stats.get_objective()}; errors={curr_stats.get_sum_errors()}; best={best_stats.get_objective()}"
                )
        return self.check_stats_update_solution(curr_stats, best_stats, options)
