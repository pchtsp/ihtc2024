from ihtc2024 import Experiment, solvers
import os, sys
from ihtc2024.graph.graph import GraphTool
import ihtc2024.graph as gr
from ihtc2024.graph.node import get_source_node
from pytups import SuperDict
import time


tests_dir = os.path.dirname(__file__)
root_dir = os.path.join(tests_dir, "../")
my_paths = [root_dir]
for __my_path in my_paths:
    sys.path.insert(1, __my_path)
PATH_TO_VALIDATOR = os.path.join(root_dir, "../../validator/IHTP_Validator")
from .tests import BaseTestInstance


class TestInstance(BaseTestInstance):

    def test_group_nurses(self):
        nurse_shifts = self.instance.get_nurse_shift()
        groups = self.instance.get_nurse_groups(nurse_shifts, 0.05, 0.015)
        print(f"nurses: {len(groups)}")
        print(f"groups: {len(groups.values_tl().unique2())}")

    def test_group_nurses_larger(self):
        # my_experim = self.get_solved_experiment("test05.json")
        my_experim = self.get_test_experiment("i29.json")
        nurse_shifts = my_experim.instance.get_nurse_shift()
        groups = self.instance.get_nurse_groups(nurse_shifts, 5, 1)
        print(f"nurses: {len(groups)}")
        print(f"groups: {len(groups.values_tl().unique2())}")
        # members = groups.vfilter(lambda v: v==4)
        # nurse_shifts.kfilter(lambda k: k[0]=='n015').vapply(lambda v: v['shift_pos']).values_tl()
        # nurse_shifts.kfilter(lambda k: k[0]=='n016').vapply(lambda v: v['shift_pos']).values_tl()
        # nurse_shifts.kfilter(lambda k: k[0]=='n063').vapply(lambda v: v['shift_pos']).values_tl()
        groups.vapply(lambda v: [v]).list_reverse()


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
        # my_experim = self.get_solved_experiment("test01.json")
        my_experim = self.get_test_experiment("i19.json")
        # my_experim = self.get_test_experiment("i01.json")
        # my_experim = self.get_test_experiment("i15.json")
        nodes_ady = gr.get_nodes_ady_par(my_experim.instance, num_workers=8)
        nodes_per_patient = gr.nodes_per_patient(nodes_ady, my_experim.instance)
        my_graph = GraphTool(
            instance=my_experim.instance,
            nodes_ady=nodes_ady,
            nodes_ady_p=nodes_per_patient,
        )

    def test_create_patient_graph(self):

        time_init = time.time()
        # my_experim = Experiment(self.instance, self.solution)
        # my_experim = self.get_solved_experiment("test01.json")
        # my_experim = self.get_solved_experiment("test05.json")
        my_experim = self.get_test_experiment("i15.json")
        # my_experim = self.get_test_experiment("i19.json")
        my_experim = solvers["graph"](my_experim.instance, my_experim.solution)
        my_experim.solve(dict(msg=True, timeLimit=60))