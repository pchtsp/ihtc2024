import logging as log
from .graph import Graph, SolStats
import random as rn


from .. import Solution, Instance


class GraphGRASP(Graph):

    def __init__(self, instance: Instance, solution: Solution = None, **kwargs):
        Graph.__init__(self, instance, solution, **kwargs)

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
            # we want to prioritize mandatory patients
            # then, we want to prioritize patients with less margin
            return (-mandatory, margin + noise)

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
            percentage_keep = self.rng.triangular(0.1, 0.5, 0.9)
            num_to_take_out = round((1 - percentage_keep) * len(population))
            out = rn.sample(sorted(population), num_to_take_out)
            for p in out:
                self.remove_patient(p)
            # now, let's try to add some patients

            remaining = (
                all_patients_keys - self.solution.get_patient_assignment().keys()
            )
            max_margin = max(mandatory_margins)
            noise = self.rng.triangular(
                -max_margin // 2, 0, max_margin // 2, len(remaining)
            )
            noise = dict(zip(remaining, noise))
            my_priority = lambda v: get_priority(
                is_mandatory.get(v["id"], True), margin[v["id"]], noise[v["id"]]
            )
            my_list_to_add = (
                all_patients.filter(remaining).values_tl().sorted(key=my_priority)
            )
            my_list_to_add.vapply(
                lambda v: (margin[v["id"]], is_mandatory.get(v["id"]), v["is_occupant"])
            )
            _, curr_stats = Graph.solve_patients(
                self,
                options,
                my_list_to_add,
                num_passes=1,
                max_skipped_mandatory=best_stats.get_sum_errors() + 1,
            )
            if VERBOSE:
                log.info(f"current={curr_stats}; best={best_stats}")
        return self.check_stats_update_solution(curr_stats, best_stats, options)
