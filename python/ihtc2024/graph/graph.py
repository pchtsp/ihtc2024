# installing graph-tool and adding it to venv:
# https://graph-tool.skewed.de/installation.html#debian-ubuntu-gnulinux
# https://jolo.xyz/blog/2018/12/07/installing-graph-tool-with-virtualenv

import graph_tool.all as gr
from pytups import SuperDict

from .node import get_source_node, get_sink_node, get_theater_occupant, Node, TYPE
import logging as log

from typing import Dict, Tuple
import numpy as np
import os
from ..core.instance import Instance


class GraphTool(object):
    refs: Dict[Node, int]
    refs_inv: list[Node]
    g: gr.Graph
    instance: Instance
    patient_graphs: Dict[str, gr.GraphView]
    shift_vp: gr.VertexPropertyMap
    pos_shift_vp: gr.VertexPropertyMap
    type_vp: gr.VertexPropertyMap
    nurse_vp: gr.VertexPropertyMap
    theater_vp: gr.VertexPropertyMap
    room_vp: gr.VertexPropertyMap
    skill_level_vp: gr.VertexPropertyMap
    max_load_vp: gr.VertexPropertyMap
    needs_wl_vp: gr.VertexPropertyMap
    nurse_group: gr.VertexPropertyMap
    edge_changes_group: gr.EdgePropertyMap
    edges: np.ndarray
    weights: gr.EdgePropertyMap
    nodes__n_s: SuperDict[Tuple[str, int], list[int]]
    nodes__r_s: SuperDict[Tuple[str, int], list[int]]
    nodes__pos: SuperDict[int, list[int]]
    _equiv_nurse: Dict[str, int]
    _equiv_room: Dict[str, int]
    _equiv_theater: Dict[str, int]

    def __init__(
        self,
        instance,
        nodes_ady: Dict[Node, list[Node]],
        patient_graphs=True,
        patient_forbidden=False,
        nodes_ady_p=None,
        group_nurses=True,
    ):
        print(f"Process {os.getpid()}, graph creation starts")
        self.instance = instance
        self.sink = get_sink_node(instance)
        self.g = gr.Graph(directed=True)
        edges = [(key, value) for key, values in nodes_ady.items() for value in values]
        edges_arr = np.array(edges)
        nodes = list(nodes_ady.keys())
        nodes.append(self.sink)
        vertices = self.g.add_vertex(len(nodes))
        # nodes = list(set(np.concatenate((edges_arr[:, 0], edges_arr[:, 1]))))
        # vertices = self.g.add_vertex(len(nodes))
        self.refs = SuperDict({node: int(v) for node, v in zip(nodes, vertices)})
        self.inf_weight = 1e6
        # TODO: we should have the same references to node objects to make this work
        # for node, v in zip(nodes, vertices):
        #     node.id = int(v)
        self.refs_inv = nodes

        vectorized_map = np.vectorize(self.refs.get)
        # vectorized_map = np.vectorize(lambda v: self.refs[v])
        edges_list = vectorized_map(edges_arr)
        self.g.add_edge_list(edges_list)

        # graph params:
        self.edges = self.g.get_edges()
        self.nurse_vp = self.g.new_vp("int")
        self.theater_vp = self.g.new_vp("int")
        self.room_vp = self.g.new_vp("int")
        self.weights = self.g.new_ep("int")

        self._equiv_nurse = {k: v for v, k in enumerate(self.instance.get_nurses())}
        self._equiv_nurse[None] = -1
        self._equiv_room = {k: v for v, k in enumerate(self.instance.get_rooms())}
        self._equiv_room[None] = -1
        self._equiv_theater = {
            k: v for v, k in enumerate(self.instance.get_operatingtheaters())
        }
        self._equiv_theater[None] = -1

        self.shift_vp = self.g.new_vp("int")
        self.pos_shift_vp = self.g.new_vp("int")
        self.type_vp = self.g.new_vp("int")
        # workload needs
        self.needs_wl_vp = self.g.new_vp("int")
        # service level needs
        self.skill_level_vp = self.g.new_vp("int", val=0)
        self.max_load_vp = self.g.new_vp("int", val=0)
        # nurse group
        self.nurse_group = self.g.new_vp("int")
        self.edge_changes_group = self.g.new_ep("bool")
        # get a dictionary with a list of nodes for each nurse and shift combination:
        self.nodes__n_s = SuperDict()
        # all nurse nodes per room-shift combination
        self.nodes__r_s = SuperDict()
        # all nurse nodes per shift-position
        self.nodes__pos = SuperDict()
        # all day nodes per shift start
        self.nodes__st = SuperDict()
        # all theater nodes per shift-theater
        self.nodes__s_o = SuperDict()
        # all room nodes per shift-room
        self.nodes__s_r = SuperDict()

        nurse_sl = self.instance.get_nurses().get_property("skill_level")
        nurse_ml = self.instance.get_nurse_shift().get_property("max_load")
        nurse_shifts = self.instance.get_nurse_shift()
        if group_nurses:
            nurse_group = self.instance.get_nurse_groups(nurse_shifts, 1, 1)
        else:
            # all nurses have the same group:
            nurse_group = nurse_sl.vapply(lambda v: 0)

        print("Start registering properties in nodes")
        for v in self.g.vertices():
            node = self.refs_inv[int(v)]
            self.type_vp[v] = node.type
            self.nurse_vp[v] = self._equiv_nurse[node.nurse]
            self.theater_vp[v] = self._equiv_theater[node.theater]
            self.room_vp[v] = self._equiv_room[node.room]
            self.shift_vp[v] = node.shift
            self.pos_shift_vp[v] = node.pos_shift

            vertex_i = self.g.vertex_index[v]

            if node.type == TYPE.NURSE:
                self.skill_level_vp[v] = nurse_sl[node.nurse]
                self.max_load_vp[v] = nurse_ml[node.nurse, node.shift]
                self.nurse_group[v] = nurse_group[node.nurse]

                pos_shift = node.pos_shift
                if pos_shift not in self.nodes__pos:
                    self.nodes__pos[pos_shift] = []
                self.nodes__pos[pos_shift].append(vertex_i)
                nurse_shift = (node.nurse, node.shift)
                room_shift = (node.room, node.shift)
                if nurse_shift not in self.nodes__n_s:
                    self.nodes__n_s[nurse_shift] = []
                self.nodes__n_s[nurse_shift].append(vertex_i)
                if room_shift not in self.nodes__r_s:
                    self.nodes__r_s[room_shift] = []
                self.nodes__r_s[room_shift].append(vertex_i)

            if node.type == TYPE.DAY:
                if node.shift not in self.nodes__st:
                    self.nodes__st[node.shift] = []
                self.nodes__st[node.shift].append(vertex_i)
            if node.type == TYPE.THEATER:
                shift_theater = (node.shift, node.theater)
                if shift_theater not in self.nodes__s_o:
                    self.nodes__s_o[shift_theater] = []
                self.nodes__s_o[shift_theater].append(vertex_i)
            if node.type == TYPE.ROOM:
                shift_room = (node.shift, node.room)
                if shift_room not in self.nodes__s_r:
                    self.nodes__s_r[shift_room] = []
                self.nodes__s_r[shift_room].append(vertex_i)

        # we calculate the edges that change group
        edges_all = self.edges
        targets = edges_all[:, 1]
        sources = edges_all[:, 0]
        type_arr = self.type_vp.get_array()
        nurse_group_arr = self.nurse_group.get_array()
        self.edge_changes_group = (type_arr[sources] == TYPE.NURSE) & (
            nurse_group_arr[targets] != nurse_group_arr[sources]
        )

        # for each patient_occupant, we create a view of the graph
        # that filters the nodes and edges that are not feasible
        # for that patient_occupant
        self.patient_graphs = {}
        self.patient_forbidden = {}
        if patient_graphs or patient_forbidden:
            patients = self.instance.get_patients_occupants()
            print("Start creating patient views")
            log.info("Start creating patient views")
            # I create a cache of edges that should be filtered out
            # for each length of stay
            # this is particularly important for instances with a lot of patients
            edge_mask_out__length = (
                patients.get_property("length_of_stay")
                .values_tl()
                .unique()
                .to_dict(None)
            )
            sink = self.get_sink_node()
            shift_arr: np.ndarray = self.shift_vp.get_array()
            shift_pos_arr: np.ndarray = self.pos_shift_vp.get_array()

            edges_to_sink = targets == sink
            # also, length_of_day determines the number of shifts
            # a patient can only go to the sink from the last shift

            last_horizon_shift = self.instance.get_last_shift_horizon()
            is_not_very_last = shift_arr != last_horizon_shift
            for num in edge_mask_out__length:
                # we filter out edges that:
                # - go to the sink from a node that is not the last shift
                last_shift = num * 3 - 1
                not_last_shift_or_very_last = (
                    shift_pos_arr != last_shift
                ) & is_not_very_last

                filter_edge_out = not_last_shift_or_very_last[sources] & (edges_to_sink)
                edge_mask_out__length[num] = filter_edge_out

            for p, patient_info in patients.items():
                print(f"Patient views: {p}")
                nodes = [self.refs[n] for n in nodes_ady_p[p]]
                l_o_s: int = patient_info["length_of_stay"]
                if patient_forbidden:
                    self.patient_forbidden[p] = SuperDict(
                        nodes_in=nodes, edges_out=edge_mask_out__length[l_o_s]
                    )
                else:
                    self.patient_graphs[p] = self.patient_view2(
                        patient_info, nodes, edge_mask_out__length[l_o_s]
                    )
            log.info("Finish creating patient views")
        # some cache:
        self.__needs__p__s = self.instance.get_patients_occupants_needs().to_dictdict()

        print(f"Process {os.getpid()}, graph creation ends")
        return

    def shortest_path(self, node1=None, node2=None, **kwargs):
        target, source = None, None
        if node1 is not None:
            source = find_vertex(self.g, self.refs, node1)
            if source is None:
                log.error("There was a problem finding node {}".format(node1))
                return None
        if node2 is not None:
            target = find_vertex(self.g, self.refs, node2)
        return gr.shortest_distance(
            self.g, source=source, target=target, dag=True, **kwargs
        )

    def patient_view2(self, patient_info, nodes: list, filter_edge_out: np.array):
        vfilt = self.g.new_vp("bool", val=0)
        sink = self.get_sink_node()
        source = self.get_source_node()
        vfilt.a[nodes] = 1
        vfilt[sink] = 1
        efilt = self.g.new_ep("bool", val=1)
        efilt.a[filter_edge_out] = 0

        # if the patient is not mandatory, we keep the edge from source to sink:
        if patient_info.get("mandatory", True):
            efilt[source, sink] = 0
        else:
            efilt[source, sink] = 1

        return gr.GraphView(
            self.g, vfilt=vfilt, efilt=efilt, skip_vfilt=True, skip_efilt=True
        )

    def filter_feasibility(self, checks, patient_info):
        my_graph = self.patient_graphs[patient_info["id"]]
        vfilt = my_graph.new_vp("bool", val=1)
        node_active = self.get_infeasible_nodes(checks, patient_info)
        vfilt.a[node_active] = 0
        return gr.GraphView(my_graph, vfilt=vfilt, skip_properties=True)

    def get_infeasible_nodes(self, checks, patient_info):
        # these are the properties we want to fill

        # shift_arr = self.shift_vp.get_array()
        type_arr = self.type_vp.get_array()
        # room_arr = self.room_vp.get_array()
        # theater_arr = self.theater_vp.get_array()

        result = np.zeros_like(type_arr, dtype=bool)
        # THIS PART IS SPECIFIC TO CHECKS
        # and basically does not apply for occupants

        # if there's another gender in a room-day, we take out
        # it may be possible that the patient is actually an occupant:
        ban_days = []
        ban_theater_days = []
        ban_room_days = set()
        if not patient_info["is_occupant"]:
            my_gender = patient_info["gender"]
            ban_room_days |= (
                checks["gender"].vfilter(lambda v: my_gender not in v).keys()
            )
            # if there's 0 capacity left in a room-day, we take out
            ban_room_days |= checks["capacity_overuse"].vfilter(lambda v: v == 0).keys()

            surgery_duration = patient_info["surgery_duration"]
            my_surgeon = patient_info["surgeon_id"]
            # if the surgeon has less capacity than duration in some day, we take out those days
            ban_days = (
                checks["surgeon_overtime"]
                .to_dictdict()
                .get(my_surgeon, SuperDict())
                .vfilter(lambda v: surgery_duration > -v)
            )
            ban_theater_days = (
                checks["ot_overtime"].vfilter(lambda v: surgery_duration > -v).keys()
            )
        # my_node = Node(self.instance, shift=39, pos_shift=-1, theater='t1', room='r3', nurse=None, type=TYPE.ROOM, hist_nurses=dict())
        # vfilt.a[self.refs[my_node]]
        for th, d in ban_theater_days:
            my_shift = d * 3
            # my_theater = self._equiv_theater[th]
            result[self.nodes__s_o[my_shift, th]] = 1

            # result |= (
            #     (my_shift == shift_arr)
            #     & (type_arr == TYPE.THEATER)
            #     & (theater_arr == my_theater)
            # )
            # vfilt.a[node_active] = 0

        for d in ban_days:
            my_shift = d * 3
            result[self.nodes__st[my_shift]] = 1
            # result |= (my_shift == shift_arr) & (type_arr == TYPE.DAY)
            # vfilt.a[node_active] = 0

        for r, d in ban_room_days:
            # this ban is for the whole stay.
            # if a patient cannot be in room r in day d
            # it cannot start in that room for the previous length_of_stay days
            # my_room = self._equiv_room[r]
            start_shift = max(0, d - patient_info["length_of_stay"] + 1) * 3
            end_shift = d * 3
            for my_shift in range(start_shift, end_shift + 1, 3):
                result[self.nodes__s_r[my_shift, r]] = 1
            # result |= (
            #     (shift_arr >= start_shift)
            #     & (shift_arr <= end_shift)
            #     & (room_arr == my_room)
            #     & (type_arr == TYPE.ROOM)
            # )
            # vfilt.a[node_active] = 0

        return result

    def nodes_to_pattern(self, checks, patient, experiment, **kwargs):
        patient_info = self.instance.get_patients_occupants()[patient]
        refs_inv = self.refs_inv
        my_id = patient_info["id"]
        # if we stored a filtered graph for this patient, we use it
        graph = self.patient_graphs.get(my_id, self.g)
        # if we, instead, stored a list of forbidden nodes /edges, we use it
        forbidden = self.patient_forbidden.get(my_id)

        # graph = self.filter_feasibility(checks, patient_info)
        wrong_nodes = self.get_infeasible_nodes(checks, patient_info)
        self.weights.a = self.get_weights(checks, patient_info, experiment)
        # targets = self.edges[:, 1]
        source = self.get_source_node()
        target = self.get_sink_node()
        weights = self.instance.get_weights()

        if forbidden is not None:
            # we get the list of good nodes, and we create a
            bad_ones = np.ones_like(wrong_nodes, dtype=bool)
            # mask of good nodes
            bad_ones[forbidden["nodes_in"]] = False
            bad_ones[int(target)] = False
            # then we add it to the mask of bad nodes
            wrong_nodes |= bad_ones
            # the filter edges, we take out
            self.weights.a[forbidden["edges_out"]] = self.inf_weight

        vfilt = graph.new_vp("bool", vals=~wrong_nodes)
        graph = gr.GraphView(graph, vfilt=vfilt)
        # self.weights.a[wrong_nodes[targets]] = self.inf_weight

        if patient_info.get("mandatory", True):
            self.weights[source, target] = self.inf_weight
        else:
            self.weights[source, target] = weights["unscheduled_optional"]

        nodes, edges = gr.shortest_path(
            graph, source=source, target=target, weights=self.weights, dag=True
        )
        path_cost = sum([self.weights[e] for e in edges])
        # if the path includes infeasible nodes, we do not return it
        # TODO: maybe we still want to add the path??
        if path_cost >= self.inf_weight:
            return []
        return [refs_inv[int(n)] for n in nodes]

    def get_nodes_in_window(self, node1, node2):
        # returns a boolean array with length = vertices length
        # TODO maybe implement this
        return (self.nurse_vp.get_array() >= -1) & (self.shift_vp.get_array() >= -1)

    def get_unassigned_scores(self, patient_info):
        edge_unassigned = self.g.new_ep("int")
        # if the patient is mandatory or an occupant
        # there should not be this edge
        if patient_info.get("mandatory", True):
            return edge_unassigned.get_array()
        edge = self.g.edge(self.get_source_node(), self.get_sink_node())
        edge_unassigned[edge] = 1
        return edge_unassigned.get_array()

    def get_age_scores(self, checks, patient_info):
        type_arr = self.type_vp.get_array()
        shifts_array = self.shift_vp.get_array()
        room_array = self.room_vp.get_array()
        age_group = patient_info["age_group"]
        age_groups = self.instance.get_agegroups().get_property("pos")
        p_agegroup = age_groups[age_group]
        potential_errors_age = (
            checks["room_mixed_age"]
            .vapply(lambda v: max(p_agegroup - v[1], v[0] - p_agegroup, 0))
            .vfilter(lambda v: v > 0)
        )
        n_age_diff = np.zeros_like(type_arr)
        # TODO: I can already filter days or rooms based on the patient
        for (room, day), v in potential_errors_age.items():
            my_room = self._equiv_room[room]
            my_shift = day * 3
            relevant_node = (
                (room_array == my_room)
                & (shifts_array == my_shift)
                & (type_arr == TYPE.NURSE)
            )
            n_age_diff[relevant_node] = v
        return n_age_diff

    def get_admission_delay_scores(self, patient_info):
        type_arr = self.type_vp.get_array()
        shift_array = self.shift_vp.get_array()

        n_admission_delay = np.zeros_like(type_arr)
        if not patient_info["is_occupant"]:
            type_day = type_arr == TYPE.DAY
            release_day = patient_info["surgery_release_day"]
            n_admission_delay[type_day] = shift_array[type_day] / 3 - release_day
        return n_admission_delay

    def get_opened_theater_scores(self, checks):
        type_arr = self.type_vp.get_array()
        shift_array = self.shift_vp.get_array()
        theater_arr = self.theater_vp.get_array()
        n_open_theater = np.zeros_like(type_arr)
        # by default, I count theater nodes with 1
        n_open_theater[type_arr == TYPE.THEATER] = 1
        # and then we take out the day-theater combinations
        # that already have an assignment
        # TODO: we do not need to eliminate days that are incompatible
        #  with the patient already
        for op, day in checks["open_operating_theater"]:
            my_shift = day * 3
            my_theater = self._equiv_theater[op]
            relevant_node = (
                (shift_array == my_shift)
                & (theater_arr == my_theater)
                & (type_arr == TYPE.THEATER)
            )
            n_open_theater[relevant_node] = 0
        return n_open_theater

    def get_surgeon_transfer_scores(self, checks, patient_info):
        type_arr = self.type_vp.get_array()
        shift_array = self.shift_vp.get_array()
        theater_arr = self.theater_vp.get_array()

        n_surgeon_transfer = np.zeros_like(type_arr)
        surgeon = patient_info.get("surgeon_id")
        if surgeon is None:
            # if it's an occupant, we do not care
            return n_surgeon_transfer
        n_surgeon_transfer[type_arr == TYPE.THEATER] = 1
        # TODO: we do not need to eliminate days that are incompatible
        #  with the patient already
        my_surgeon_transfer = checks["surgeon_transfer"].to_dictdict()
        for day, ops in my_surgeon_transfer.get(surgeon, {}).items():
            my_shift = day * 3
            for op in ops:
                my_theater = self._equiv_theater[op]
                # if the surgeon is already working in that theater
                # in that day we do not count it
                relevant_node = (
                    # day assigned
                    (shift_array == my_shift)
                    # operating theater
                    & (theater_arr == my_theater)
                    # theater type
                    & (type_arr == TYPE.THEATER)
                )
                n_surgeon_transfer[relevant_node] = 0
        return n_surgeon_transfer

    def get_skill_level_scores(self, checks, patient_info, experiment):
        # all skill levels for each nurse
        skill_levels = self.instance.get_nurses().get_property("skill_level")

        # get the skill level of each nurse in the room and shift
        skill_level__r_s = experiment.get_nurse_assignment_shift().vapply(
            lambda v: skill_levels[v["id"]]
        )
        min_required = min(skill_levels.values())

        # get the level required by patients currently in each room, shift
        # only those above the minimum level (who have no penalty by definition)
        # this is a list of all required levels for each room, shift
        level_required = (
            checks["shift_details"]
            .values_tl()
            .vfilter(lambda v: v["skill_level_required"] > min_required)
            .to_dict("skill_level_required", indices=["room", "shift"])
        )

        # get the skill level of the node (proposed skill level)
        proposed_skill_level = self.skill_level_vp.get_array()

        # I first calculate the new patient's penalties per node
        shift_sl_needs = (
            self.__needs__p__s[patient_info["id"]]
            .get_property("skill_level_required")
            .vfilter(lambda v: v > min_required)
        )

        # we calculate the penalty for the new patient
        new_patient_penalty = np.zeros_like(proposed_skill_level)
        for pos, required in shift_sl_needs.items():
            if pos not in self.nodes__pos:
                continue
            relevant_nodes = self.nodes__pos[pos]
            new_patient_penalty[relevant_nodes] = (
                required - proposed_skill_level[relevant_nodes]
            )
        np.clip(new_patient_penalty, 0, None, out=new_patient_penalty)

        # TODO: this can be improved I think
        #   with numpy broadcasting instead of the second for loop

        # And now I calculate the penalties of changing the nurse of a particular room
        #  for all other patients
        diff_error = np.zeros_like(proposed_skill_level)
        for (r, s), required_l in level_required.items():
            # list of nodes that cover that room and shift:
            relevant_node = self.nodes__r_s[r, s]
            # proposed skill level for each node
            proposed = proposed_skill_level[relevant_node]
            # we iterate over all the required levels in that room and shift
            #  i.e., over each patient currently assigned to that room in that shift
            # for required in required_l:
            #     # penalty of the current assignment for that room and shift
            #     penalty_1 = max(0, required - skill_level__r_s[r, s])
            #     # penalty of the proposed assignment for all nodes
            #     #  that have that room and shift
            #     penalty_2 = required - proposed
            #     np.clip(penalty_2, 0, None, out=penalty_2)
            #     # we calculate the increase in penalties (change in objective function term)
            #     diff_error[relevant_node] += penalty_2 - penalty_1

            # we make two np arrays:
            #  * one has shape (1, # patients in r, s)
            #  * the other has shape (# relevant nodes, 1)
            # we make the difference of both, which broadcasts both dimensions.
            # returns the difference per node-patient.
            # then we get the max 0 of that difference.
            # and we aggregate over patients to have an array (# relevant nodes)
            # and then we aggregate the
            required_arr = np.array(
                [max(0, req - skill_level__r_s[r, s]) for req in required_l]
            )
            required_arr.shape = (1, len(required_arr))
            proposed_arr = proposed[..., np.newaxis]
            dif = required_arr - proposed_arr
            np.clip(dif, 0, None, out=dif)
            diff_error[relevant_node] += dif.sum(axis=1)

        return new_patient_penalty + diff_error

    def get_overwork_scores(self, checks, patient_info):
        # load by room, shift, nurse
        current_workload = (
            checks["shift_details"]
            .values_tl()
            .to_dict("workload_produced", indices=["room", "shift", "nurse"])
            .vapply(sum)
        )

        # get the max workload of the node
        max_load_arr = self.max_load_vp.get_array()
        # n1 means the current nurse that is assigned to the room
        # n2 is the new nurse that would be assigned to the room

        # get the current load on the nurse and shift for each node:
        #  its the current load on the nurse to which we would assign the
        #  room if we use this node
        excess_load_n2 = np.zeros_like(max_load_arr)
        excess_load = checks["nurse_eccessive_workload"]
        for (nurse, shift), excess in excess_load.items():
            excess_load_n2[self.nodes__n_s[nurse, shift]] = excess

        # get the current load on the nurse assigned to the room and shift
        #  this can or not be the same as the nurse in the node
        excess_load_n1 = np.zeros_like(max_load_arr)
        change_load = np.zeros_like(max_load_arr)
        for (room, shift, prev_nurse), load in current_workload.items():
            # we add the load of the current nurse on the node:
            my_rs_nodes = self.nodes__r_s[room, shift]
            my_excess_load = excess_load[prev_nurse, shift]
            excess_load_n1[my_rs_nodes] = my_excess_load
            set_rs = set(my_rs_nodes)
            set_pns = set(self.nodes__n_s[prev_nurse, shift])
            # the load will change symmetrically
            # in the cases where the node has a different
            # nurse than the assigned
            change_load[list(set_rs - set_pns)] = load

        change_load_n2 = np.copy(change_load)
        # we need to add the patient's load now
        shift_wl_needs = (
            self.__needs__p__s[patient_info["id"]]
            .get_property("workload_produced")
            .vfilter(lambda v: v > 0)
        )
        # here we add the patient's load to the change_load_n2
        # because the patient (currently unnassigned) will be assigned to nurse 2
        for pos, load in shift_wl_needs.items():
            if pos not in self.nodes__pos:
                continue
            relevant_nodes = self.nodes__pos[pos]
            change_load_n2[relevant_nodes] += load

        # nurse1 decreases load
        new_excess_load_n1 = excess_load_n1 - change_load
        # nurse2 increases load
        new_excess_load_n2 = excess_load_n2 + change_load_n2

        # negative loads are not penalized, so we clip them to 0
        np.clip(excess_load_n1, 0, None, out=excess_load_n1)
        np.clip(excess_load_n2, 0, None, out=excess_load_n2)

        np.clip(new_excess_load_n1, 0, None, out=new_excess_load_n1)
        np.clip(new_excess_load_n2, 0, None, out=new_excess_load_n2)

        return new_excess_load_n1 + new_excess_load_n2 - excess_load_n1 - excess_load_n2

    def get_continuity_care_scores(self, checks):
        # (1) get arcs where the group of the nurse changes.
        #    this can be calculated once and cached
        # self.edge_changes_group
        # (2) count the number of patients active in that arc
        #    based on the room and shift of the origin node
        # the weight is the number of patients that change group

        # here I need to filter those patients who have pos=0
        # as those patients just started in shift s and are thus
        # not changing nurse, yet.
        # print(checks["shift_details"])
        patients__r_s = (
            checks["shift_details"]
            .values_tl()
            .vfilter(lambda v: v["pos_shift"] > 0)
            .to_dict(None, indices=["room", "shift"])
            .vapply(len)
            # we add 1 to count the unassigned patient
            .vapply(lambda v: v + 1)
        )
        nurse_group = self.nurse_group.get_array()
        weight = np.zeros_like(nurse_group)

        # we update the nodes per room, shift:
        for (r, s), number in patients__r_s.items():
            weight[self.nodes__r_s[r, s]] = number

        targets = self.edges[:, 1]
        # this is projecting the weight of the target to the arc.
        # and filtering to only arcs that change group

        # i.e., it's counting how many patients are continuing
        # in that room and changing nurse group
        my_weights = np.zeros_like(self.edge_changes_group)
        my_weights[self.edge_changes_group] = weight[targets][self.edge_changes_group]
        # my_weights[~self.edge_changes_group] = 0
        return my_weights

    def get_weights(self, checks, patient_info, experiment):
        targets = self.edges[:, 1]

        weights = self.instance.get_weights()
        edge_unassigned = self.get_unassigned_scores(patient_info)
        n_admission_delay = self.get_admission_delay_scores(patient_info)
        n_open_theater = self.get_opened_theater_scores(checks)
        n_surgeon_transfer = self.get_surgeon_transfer_scores(checks, patient_info)
        n_age_diff = self.get_age_scores(checks, patient_info)
        n_continuity_care = self.get_continuity_care_scores(checks)
        n_workload = self.get_overwork_scores(checks, patient_info)
        n_skill_level = self.get_skill_level_scores(checks, patient_info, experiment)
        # TODO: add noise on nodes?
        #  or sample 50% of nodes and apply a 1-value noise
        # noise = np.random.rand(targets.size)

        return (
            n_workload[targets] * weights["nurse_eccessive_workload"]
            + n_continuity_care * weights["continuity_of_care"]
            + n_admission_delay[targets] * weights["patient_delay"]
            + edge_unassigned * weights["unscheduled_optional"]
            + n_skill_level[targets] * weights["room_nurse_skill"]
            + n_age_diff[targets] * weights["room_mixed_age"]
            + n_open_theater[targets] * weights["open_operating_theater"]
            + n_surgeon_transfer[targets] * weights["surgeon_transfer"]
            # a bit of noise in the arcs:
            # + noise
        )

    def get_source_node(self):
        return find_vertex(self.g, self.refs, get_source_node(self.instance))

    def get_sink_node(self):
        return find_vertex(self.g, self.refs, get_sink_node(self.instance))

    def draw(
        self,
        not_show_None=True,
        edge_label=None,
        node_label=None,
        tikz=False,
        filename=None,
        g=None,
    ):
        instance = self.instance
        refs_inv = self.refs_inv
        if g is None:
            g = self.g

        def get_y_node(v):
            node = refs_inv[int(v)]
            if node.type == TYPE.NURSE:
                return self.nurse_vp[v]
            if node.type == TYPE.THEATER:
                return self.theater_vp[v]
            if node.type == TYPE.ROOM:
                return self.room_vp[v]
            if node.type == TYPE.DAY:
                return self.shift_vp[v]
            if node.type == TYPE.DUMMY:
                return 3

        colors = {
            TYPE.NURSE: "#4cb33d",
            TYPE.THEATER: "#00c8c3",
            TYPE.DAY: "#878787",
            TYPE.ROOM: "#EFCC00",
            TYPE.DUMMY: "#31c9ff",
        }

        key = {
            TYPE.NURSE: "nurse",
            TYPE.THEATER: "theater",
            TYPE.DAY: "shift",
            TYPE.ROOM: "room",
            TYPE.DUMMY: "type",
        }

        g_filt = g

        pos = g_filt.new_vp("vector<float>")
        size = g_filt.new_vp("double")
        shape = g_filt.new_vp("string")
        color = g_filt.new_vp("string")
        vertex_text = g_filt.new_vp("string")
        assignment = g_filt.new_ep("string")

        if not edge_label:

            def edge_label(tail):
                a = getattr(tail, key[tail.type])
                if a is None:
                    return ""
                return a

        for e in g_filt.edges():
            assignment[e] = edge_label(refs_inv[e.target()])

        if not node_label:
            node_label = lambda node: node.shift

        for v in g_filt.vertices():
            vertex_text[v] = node_label(refs_inv[v])
            x = refs_inv[v].shift * 2 + refs_inv[v].type
            if refs_inv[v] == get_sink_node(self.instance):
                x = refs_inv[v].shift * 3
            a = refs_inv[v].type
            y = get_y_node(v)
            pos[v] = (x, y)
            size[v] = 20
            shape[v] = "circle"
            color[v] = colors.get(a, "red")

        options = dict(
            pos=pos,
            vertex_text=vertex_text,
            edge_text=assignment,
            vertex_shape=shape,
            vertex_fill_color=color,
            vertex_size=size,
        )
        if not tikz:
            gr.graph_draw(g=g_filt, **options)
        else:
            self.graph_draw_tikz(g=g_filt, **options, filename=filename)

    @staticmethod
    def graph_draw_tikz(
        g, pos, vertex_text, edge_text, vertex_shape, vertex_fill_color, filename
    ):
        import network2tikz as nt
        import webcolors as wc

        nodes = [int(v) for p, v in enumerate(g.vertices())]
        _edges = list(g.edges())
        edges = [(int(e.source()), int(e.target())) for e in _edges]
        visual_style = {}
        visual_style["vertex_color"] = [
            wc.hex_to_rgb(vertex_fill_color[v]) for v in nodes
        ]
        visual_style["edge_label"] = [edge_text[e] for e in _edges]
        visual_style["vertex_label"] = [vertex_text[v] for v in nodes]
        visual_style["layout"] = {
            v: (pos[v][0], np.cbrt(-pos[v][1])) for p, v in enumerate(nodes)
        }
        visual_style["vertex_size"] = 1.5
        visual_style["keep_aspect_ratio"] = False
        visual_style["canvas"] = (10, 10)
        # visual_style['node_opacity'] = 0.5
        nt.plot(network=(nodes, edges), **visual_style, filename=filename)


def find_vertex(graph, refs, node) -> gr.Vertex:
    return graph.vertex(refs[node])


# at initialize time:
# 1 graph for all patients

# during solving:
# for each patient:
# . filter nodes
# . update weights
# . get the shortest path/ pattern for patient
# . apply path if improvement


if __name__ == "__main__":
    pass
