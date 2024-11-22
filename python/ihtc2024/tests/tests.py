import unittest
import json
import random
import numpy as np

from ihtc2024 import Instance, Solution, Experiment, solvers
import ihtc2024.graph as gr
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

    def test_solve_toy_timefold(self):
        my_experim = solvers["timefold_py"](self.instance)
        my_experim.solve(dict(timeLimit=5, msg=True))
        checks = my_experim.check_solution()

        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)
        my_experim.run_validator(PATH_TO_VALIDATOR)

    @staticmethod
    def get_solved_experiment(test_instance_name):
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

    @staticmethod
    def get_test_experiment(test_instance_name) -> Experiment:
        path_to_data = os.path.join(
            tests_dir, "../../../data/ihtc2024_competition_instances/"
        )
        instance = Instance.from_ihtc_json(
            os.path.join(path_to_data, test_instance_name)
        )
        return Experiment(instance)

    def test_solve_test_instance_1_cpsat(self):
        my_experim_solved = self.get_solved_experiment("test01.json")
        print(my_experim_solved.get_objective())
        my_experim_solved.run_validator(PATH_TO_VALIDATOR)
        my_experim = solvers["cpsat"](my_experim_solved.instance)
        my_experim.solve(dict(threads=8, timeLimit=60, msg=True))
        checks = my_experim.check_solution()
        self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)
        my_experim.get_objective_terms().vapply(lambda v: sum(v.values()))
        terms = my_experim.get_objective_terms()
        my_experim.run_validator(PATH_TO_VALIDATOR)

    def test_solve_test_instance_1_timefold(self):
        my_experim_solved = self.get_solved_experiment("test01.json")
        print(my_experim_solved.get_objective())
        my_experim_solved.run_validator(PATH_TO_VALIDATOR)
        my_experim = solvers["timefold_py"](
            my_experim_solved.instance, my_experim_solved.solution
        )
        my_experim.solve(
            dict(warmStart=True, timeLimit=60, msg=True, fixSolution=False)
        )
        checks = my_experim.check_solution()
        print(checks)
        # self.assertEqual(sum(checks.values_tl().vapply(len)), 0)
        objective = my_experim.get_objective()
        print(objective)
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

        my_experim = solvers["cpsat"](self.get_test_experiment("i15.json").instance)
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

    def test_group_nurses(self):
        nurse_shifts = self.instance.get_nurse_shift()
        nurse__shift = (
            nurse_shifts.keys_tl()
            .to_dict(result_col=0)
            .vapply(sorted, key=lambda x: int(x[1:]))
        )
        share_shift = SuperDict()
        for s, nurses in nurse__shift.items():
            for pos, n1 in enumerate(nurses):
                for n2 in nurses[pos + 1 :]:
                    share_shift[n1, n2] = share_shift.get((n1, n2), 0) + 1

    def test_build_graph(self):
        my_experim = self.get_solved_experiment("test01.json")
        one = gr.get_nodes_ady(my_experim.instance)
        two = gr.get_nodes_ady_par(my_experim.instance, num_workers=4)
        self.assertDictEqual(one, two)

    def test_build_graph_par(self):
        my_experim = self.get_test_experiment("i15.json")
        nodes_ady = gr.get_nodes_ady_par(my_experim.instance, num_workers=8)
        # my_graph = GraphTool(instance=my_experim.instance, nodes_ady=nodes_ady)
        gr.nodes_per_patient(nodes_ady, my_experim.instance)

    def test_many_graphs(self):
        # my_experim = self.get_test_experiment("i01.json")
        my_experim = Experiment(self.instance)
        nodes_ady = gr.get_nodes_ady_par(my_experim.instance, num_workers=8)
        my_graph = GraphTool(instance=my_experim.instance, nodes_ady=nodes_ady)
        patients = my_experim.instance.get_patients_occupants()
        nodes_per_patient = gr.nodes_per_patient(nodes_ady, my_experim.instance)
        source = get_source_node(my_experim.instance)
        for some_patient in patients:
            print(some_patient)
            my_nodes = nodes_per_patient[some_patient]
            one_graph = my_graph.patient_graphs[some_patient]
            one_graph_nodes = set([my_graph.refs_inv[v] for v in one_graph.vertices()])
            one_graph_nodes -= {my_graph.sink}
            self.assertEqual(set(my_nodes), one_graph_nodes)
            edges = {(n1, n2) for n1, n2_list in my_nodes.items() for n2 in n2_list}
            one_graph_edges = set(
                (my_graph.refs_inv[n1], my_graph.refs_inv[n2])
                for n1, n2 in one_graph.iter_edges()
            )
            self.assertEqual(edges, one_graph_edges)

    def test_time_nodes_per_patient(self):
        my_experim = self.get_test_experiment("i19.json")
        nodes_ady = gr.get_nodes_ady_par(my_experim.instance, num_workers=8)

        # nodes_per_patient = gr.nodes_per_patient(nodes_ady, my_experim.instance)
        # import multiprocessing as multi
        #
        # results = {}
        # my_graphs = {}
        # with multi.Pool(processes=8) as pool:
        #     for p, nodes_ady in nodes_per_patient.items():
        #         results[p] = pool.apply_async(
        #             GraphTool, [my_experim.instance, nodes_ady, False]
        #         )
        #     for p, a in results.items():
        #         my_graphs[p] = a.get()

        # my_graphs = {
        #     p: GraphTool(
        #         instance=my_experim.instance, nodes_ady=nodes_ady, patient_graphs=False
        #     )
        #     for p, nodes_ady in nodes_per_patient.items()
        # }

    def test_create_patient_graph(self):

        time_init = time.time()
        # my_experim = Experiment(self.instance, self.solution)
        my_experim = self.get_solved_experiment("test01.json")
        my_experim = self.get_solved_experiment("test05.json")
        # my_experim = self.get_test_experiment("i15.json")
        my_experim = solvers["graph"](my_experim.instance, my_experim.solution)
        my_experim.solve(dict(msg=True))


if __name__ == "__main__":
    unittest.main()
