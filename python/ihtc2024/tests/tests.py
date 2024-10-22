import unittest
import json
import random
import numpy as np
import multiprocessing as multi
from ihtc2024 import Instance, Solution, Experiment, solvers
from ihtc2024.graph import patient_to_graph
from pytups import SuperDict
import time
import os, sys
import logging as log

from ihtc2024.graph.node import get_source_node
from ihtc2024.graph.graph import GraphTool

tests_dir = os.path.dirname(__file__)
root_dir = os.path.join(tests_dir, "../")
my_paths = [root_dir]
for __my_path in my_paths:
    sys.path.insert(1, __my_path)
PATH_TO_VALIDATOR = os.path.join(root_dir, "../../validator/IHTP_Validator")


class TestInstance(unittest.TestCase):

    def setUp(self):
        path_to_data = os.path.join(tests_dir, "data")
        self.instance = Instance.from_ihtc_json(os.path.join(path_to_data, "toy.json"))
        self.solution = Solution.from_ihtc_json(
            os.path.join(path_to_data, "toy_solution.json")
        )

    def test_export(self):
        dict_data = self.instance.to_dict()

    def test_export_solution(self):
        dict_data = self.solution.to_dict()

    def test_instance_generate_schema(self):
        schema = self.instance.generate_schema()
        schema_path = os.path.join(tests_dir, "instance.json")
        with open(schema_path, "w") as f:
            json.dump(schema, f, indent=4, sort_keys=True)
        try:
            os.remove(schema_path)
        except OSError:
            pass

    def test_solution_generate_schema(self):
        schema = self.solution.generate_schema()
        schema_path = os.path.join(tests_dir, "solution_schema.json")
        with open(schema_path, "w") as f:
            json.dump(schema, f, indent=4, sort_keys=True)
        try:
            os.remove(schema_path)
        except OSError:
            pass

    def test_objective(self):
        my_experim = Experiment(self.instance, self.solution)
        objective = my_experim.get_objective()
        self.assertEqual(292, objective)

    def test_check_solution(self):
        my_experim = Experiment(self.instance, self.solution)
        checks = my_experim.check_solution()
        self.assertEqual(len(checks["h1"]), 3)
        for elem in ["h2", "h3", "h4", "h5", "h6"]:
            self.assertEqual(len(checks[elem]), 0)

    def test_solution_to_ithc(self):
        path = os.path.join(tests_dir, "solution_ithc.json")
        self.solution.to_ihtc_json(path)
        another_solution = self.solution.from_ihtc_json(path)
        self.assertEqual(self.solution.data, another_solution.data)
        try:
            os.remove(path)
        except OSError:
            pass

    def test_instance_to_ithc(self):
        path = os.path.join(tests_dir, "instance_ithc.json")
        self.instance.to_ihtc_json(path)
        another_instance = self.instance.from_ihtc_json(path)
        self.assertEqual(self.instance.data, another_instance.data)
        try:
            os.remove(path)
        except OSError:
            pass

    def test_solve_toy_cpsat(self):
        my_experim = solvers["cpsat"](self.instance)
        my_experim.solve(dict(threads=8, timeLimit=100, msg=True))
        checks = my_experim.check_solution()

        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)
        my_experim.run_validator(PATH_TO_VALIDATOR)

    def get_solved_experiment(self, test_instance_name):
        path_to_data = os.path.join(tests_dir, "../../../data/")
        # test_instance_name = "test01.json"
        instance_path = os.path.join(
            path_to_data, "ihtc2024_test_dataset/" + test_instance_name
        )
        instance = Instance.from_ihtc_json(instance_path)
        solution_path = os.path.join(
            path_to_data, "ihtc2024_test_solutions/" + "sol_" + test_instance_name
        )
        solution = Solution.from_ihtc_json(solution_path)
        my_experim_solved = solvers["cpsat"](instance, solution)
        return my_experim_solved

    def test_solve_test_instance_1_cpsat(self):
        my_experim_solved = self.get_solved_experiment("test01.json")
        print(my_experim_solved.get_objective())
        my_experim_solved.run_validator(PATH_TO_VALIDATOR)
        my_experim = solvers["cpsat"](my_experim_solved.instance)
        my_experim.solve(dict(threads=8, timeLimit=30, msg=True))
        checks = my_experim.check_solution()
        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)
        my_experim.get_objective_terms().vapply(lambda v: sum(v.values()))
        terms = my_experim.get_objective_terms()
        my_experim.run_validator(PATH_TO_VALIDATOR)

    def test_validator(self):
        my_experim_solved = self.get_solved_experiment("test01.json")
        print(my_experim_solved.get_objective())
        my_experim_solved.run_validator(PATH_TO_VALIDATOR)

    def test_validator2(self):
        my_experim_solved = self.get_solved_experiment("test02.json")
        print(my_experim_solved.get_objective())
        my_experim_solved.run_validator(PATH_TO_VALIDATOR)

    def test_validator3(self):
        my_experim_solved = self.get_solved_experiment("test03.json")
        print(my_experim_solved.get_objective())
        my_experim_solved.run_validator(PATH_TO_VALIDATOR)

    def test_solve_competition_instance_cpsat(self):
        path_to_data = os.path.join(
            tests_dir, "../../../data/ihtc2024_competition_instances/"
        )
        instance = Instance.from_ihtc_json(os.path.join(path_to_data, "i15.json"))
        my_experim = solvers["cpsat"](instance)
        my_experim.solve(dict(threads=8, timeLimit=60, msg=True))
        checks = my_experim.check_solution()
        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)

    def test_solved_fixed(self):
        for name in [f"test0{i}.json" for i in range(1, 6)]:
            print(name)
            experiment = self.get_solved_experiment(name)
            my_experim = solvers["cpsat"](experiment.instance, experiment.solution)
            old_objective = my_experim.get_objective()
            status = my_experim.solve(
                dict(
                    threads=8, timeLimit=60, msg=True, warmStart=True, fixSolution=True
                )
            )
            # it needs to find a solution:
            self.assertEqual(status["status"], 1)
            new_objective = my_experim.get_objective()
            self.assertTrue(old_objective, new_objective)

    def test_hint_solution(self):
        # for name in [f"test0{i}.json" for i in range(1, 6)]:
        name = "test05.json"
        experiment = self.get_solved_experiment(name)
        my_experim = solvers["cpsat"](experiment.instance, experiment.solution)
        old_objective = my_experim.get_objective()
        status = my_experim.solve(
            dict(threads=8, timeLimit=60, msg=True, warmStart=True)
        )
        # it needs to find a solution:
        self.assertEqual(status["status"], 1)
        new_objective = my_experim.get_objective()

        print(old_objective)
        print(new_objective)
        my_experim.run_validator(PATH_TO_VALIDATOR)
        experiment.run_validator(PATH_TO_VALIDATOR)

    def test_create_patient_graph(self):
        time_init = time.time()
        my_experim = solvers["cpsat"](self.instance, self.solution)
        my_experim = self.get_solved_experiment("test04.json")
        my_instance = my_experim.instance
        patients_occupants = my_instance.get_patients_occupants()
        print(my_experim.get_objective())
        some_patient = patients_occupants.values_tl(0)["id"]
        graphs = {}
        # patients_occupants = random.sample(patients_occupants.keys_tl(), )
        # my_graph = patient_to_graph(my_instance, 5)
        nodes_ady = SuperDict()
        source = get_source_node(my_instance)
        nodes_ady = source.walk_over_nodes(nodes_ady, max_neighbors=5, max_nurses=7)
        print(time.time() - time_init)
        graph = GraphTool(instance=my_instance, nodes_ady=nodes_ady)
        print(time.time() - time_init)
        # my_graph = patient_to_graph(my_instance, max_neighbors=10, max_nurses=7)

        # my_graph.draw()
        # source = my_graph.get_source_node()
        # sink = my_graph.get_sink_node()
        # all_paths_iter = gt.all_paths(
        #     my_graph.g, source=source, target=sink, edges=False
        # )
        # first_path = next(all_paths_iter)
        # second_path = next(all_paths_iter)
        # for a, b in zip(first_path, second_path):
        #     print(a == b)
        # first_path[-1]
        # second_path[-1]
        # trio of start, room, length of stay?
        # while sampling the possible starts of optionals
        # all_nodes = my_graph.refs.keys_tl()
        # all_nodes.vfilter(lambda v: v.shift == 3)
        # all_paths = [[my_graph.refs_inv[n] for n in p] for p in all_paths_iter]
        # pp = my_experim.instance.get_patients_occupants()
        # pp.vfilter(lambda v: v["length_of_stay"] > 6)
        # my_experim.instance.get_patients_occupants().get_property("length_of_stay")
        # my_experim.instance.get_patient_occupants_available_starts()
        # my_experim.instance.get_horizon_size_days()
        #
        # all_paths[0]
        # all_paths[10]
        # len(all_paths)
        # day_nodes = [
        #     my_graph.refs_inv[n] for n in my_graph.g.get_out_neighbours(source)
        # ]
        # theater_nodes = [
        #     my_graph.refs_inv[n]
        #     for n in my_graph.g.get_out_neighbours(my_graph.refs[day_nodes[0]])
        # ]
        # room_nodes = [
        #     my_graph.refs_inv[n]
        #     for n in my_graph.g.get_out_neighbours(my_graph.refs[theater_nodes[0]])
        # ]
        # nurse_nodes = [
        #     my_graph.refs_inv[n]
        #     for n in my_graph.g.get_out_neighbours(my_graph.refs[room_nodes[0]])
        # ]
        # nurse_nodes2 = [
        #     my_graph.refs_inv[n]
        #     for n in my_graph.g.get_out_neighbours(my_graph.refs[nurse_nodes[0]])
        # ]
        # for some_patient in patients_occupants:
        #     print(f"Graph: {some_patient}")
        #     graphs[some_patient] = patient_to_graph(my_instance, some_patient, 5)
        # num_workers = 8
        # results = SuperDict()
        # print(
        #     "time={}, current={}, errors={}".format(round(time_now), objective, errors)
        # )
        # with multi.Pool(processes=num_workers) as pool:
        #     for some_patient in patients_occupants:
        #         _instance = my_instance.copy()
        #         results[some_patient] = pool.apply_async(
        #             patient_to_graph, [_instance, some_patient, 3]
        #         )
        #     for p, result in results.items():
        #         graphs[p] = result.get(timeout=10000)
        # objective = my_experim.get_objective()
        # errors = my_experim.check_solution()
        # time_now = time.time() - time_init
        # print(
        #     "time={}, current={}, errors={}".format(round(time_now), objective, errors)
        # )
        # for some_patient in patients_occupants:
        #     print(f"Pattern: {some_patient}")
        #     assignment = my_experim.solution.unassign_patient(some_patient)
        #     errors = my_experim.get_objective_terms_raw()
        #     errors = {
        #         **errors,
        #         **my_experim.calculate_coupling_checks(),
        #         "workload_room": my_experim.get_workload_room(),
        #     }
        #
        #     pattern = my_graph.nodes_to_pattern(None, None, errors, some_patient, {})
        #     success = my_experim.apply_pattern(pattern)
        #     if not success:
        #         print("Pattern not applied")
        #         my_experim.solution.assign_patient(assignment)
        #     print("Pattern applied")
        #     objective = my_experim.get_objective()
        #     errors = my_experim.check_solution()
        #     time_now = time.time() - time_init
        #     print(
        #         "time={}, current={}, errors={}".format(
        #             round(time_now), objective, errors
        #         )
        #     )
        # print(time_now)
        # print(my_experim.get_objective())
        # some_graph.draw()
        # len(my_graph.g.get_vertices())
        # len(my_graph.g.get_edges())
        # my_graph.g.get_out_degrees(my_graph.g.get_vertices())
        # max(my_graph.g.get_out_degrees(my_graph.g.get_vertices()))
        # # import numpy as np
        #
        # np.histogram(my_graph.g.get_out_degrees(my_graph.g.get_vertices()), bins=8)


if __name__ == "__main__":
    unittest.main()
