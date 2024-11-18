# installing graph-tool and adding it to venv:
# https://git.skewed.de/count0/graph-tool/wikis/installation-instructions
# https://jolo.xyz/blog/2018/12/07/installing-graph-tool-with-virtualenv

import graph_tool.all as gr
from pytups import SuperDict

from .node import get_source_node, get_sink_node, get_theater_occupant, Node, TYPE
import logging as log

from typing import Dict
import numpy as np


class GraphTool(object):
    refs: Dict[Node, int]
    refs_inv: Dict[int, Node]
    g: gr.Graph

    def __init__(self, instance, nodes_ady: Dict[Node, Node]):
        self.instance = instance
        self.sink = get_sink_node(instance)
        self.g = gr.Graph(directed=True)
        edges = [(key, value) for key, values in nodes_ady.items() for value in values]
        edges_arr = np.array(edges)
        nodes = list(set(np.concatenate((edges_arr[:, 0], edges_arr[:, 1]))))
        vertices = self.g.add_vertex(len(nodes))
        self.refs = SuperDict({node: int(v) for node, v in zip(nodes, vertices)})
        self.refs_inv = self.refs.reverse()

        vectorized_map = np.vectorize(self.refs.get)
        edges_list = vectorized_map(edges_arr)
        self.g.add_edge_list(edges_list)

        # delete nodes with infinite distance to sink:
        self.g.set_reversed(is_reversed=True)
        distances = self.shortest_path(node1=self.sink)
        max_dist = instance.get_horizon_size_shifts() + 5

        remove = self.g.new_vp("bool", val=True)
        remove.a[distances.get_array() > max_dist] = False
        # nodes_to_remove = [v for v in self.g.vertices() if remove[v]]
        # nodes_to_remove = [n for n in self.g.vertices() if distances[n] > max_dist]
        self.g.set_reversed(is_reversed=False)
        self.g = gr.GraphView(self.g, vfilt=remove)
        # self.g.remove_vertex(nodes_to_remove, fast=True)
        self.g.shrink_to_fit()
        self.g.reindex_edges()

        # graph params:
        self.weights = self.g.new_ep("int")
        self.edges = self.g.get_edges()
        self.nurse_vp = self.g.new_vp("int")
        self.theater_vp = self.g.new_vp("int")
        self.room_vp = self.g.new_vp("int")

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
        # get a dictionary with a list of nodes for each nurse and shift combination:
        self.nodes__n_s = SuperDict()
        self.nodes__r_s = SuperDict()
        self.nodes__pos = SuperDict()

        nurse_sl = self.instance.get_nurses().get_property("skill_level")
        nurse_ml = self.instance.get_nurse_shift().get_property("max_load")

        for v in self.g.vertices():
            node = self.refs_inv[v]
            self.type_vp[v] = node.type
            self.nurse_vp[v] = self._equiv_nurse[node.nurse]
            self.theater_vp[v] = self._equiv_theater[node.theater]
            self.room_vp[v] = self._equiv_room[node.room]
            self.shift_vp[v] = node.shift
            self.pos_shift_vp[v] = node.pos_shift

            if node.type != TYPE.NURSE:
                continue
            self.skill_level_vp[v] = nurse_sl[node.nurse]
            self.max_load_vp[v] = nurse_ml[node.nurse, node.shift]

            vertex_i = self.g.vertex_index[v]
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

        # for each patient_occupant, we create a view of the graph
        # that filters the nodes and edges that are not feasible
        # for that patient_occupant

        self.patient_graphs = self.instance.get_patients_occupants().vapply(
            self.patient_view
        )
        # some cache:
        self.__needs__p__s = self.instance.get_patients_occupants_needs().to_dictdict()

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

    def patient_view(self, patient_info):
        vfilt = self.g.new_vp("bool", val=0)
        efilt = self.g.new_ep("bool", val=1)

        # THIS PART IS SPECIFIC TO THE INSTANCE (patient)
        # we can potentially generate it once and store it in a dictionary per patient
        shift_arr = self.shift_vp.get_array()
        shift_pos_arr = self.pos_shift_vp.get_array()
        av_start = self.instance.get_patient_occupants_available_starts()[
            patient_info["id"]
        ]
        sink = self.get_sink_node()
        source = self.get_source_node()
        type_arr = self.type_vp.get_array()
        room_arr = self.room_vp.get_array()
        # we only allow start shifts in the range:
        start_arr = shift_arr - shift_pos_arr
        first_av_shift = av_start[0] * 3
        last_av_shift = av_start[-1] * 3
        starts_in_range = (start_arr >= first_av_shift) & (start_arr <= last_av_shift)
        # if the type is nurse, we only allow those that start in the range
        vfilt.a[starts_in_range | (type_arr != TYPE.NURSE)] = 1
        # if not source or sink, we cannot have a shift before the available start
        vfilt.a[(shift_arr < first_av_shift)] = 0
        # if not nurse or dummy, we cannot have a shift after the last start
        vfilt.a[(shift_arr > last_av_shift) & (type_arr != TYPE.NURSE)] = 0
        # we make sure that source and sink are always available:
        vfilt[source] = 1
        vfilt[sink] = 1

        if patient_info["is_occupant"]:
            # we only permit their room
            room_id = self.instance.get_occupants()[patient_info["id"]]["room_id"]
            my_room = self._equiv_room[room_id]
            vfilt.a[(room_arr != my_room) & (type_arr == TYPE.ROOM)] = 0
        else:
            # we take out the ban rooms for the patient
            ban_rooms = (
                self.instance.get_patient_room_ban()
                .keys_tl()
                .to_dict(1)
                .get(patient_info["id"], [])
            )

            for r in ban_rooms:
                my_room = self._equiv_room[r]
                vfilt.a[room_arr == my_room] = 0

        theater_occupant = find_vertex(
            self.g, self.refs, get_theater_occupant(self.instance)
        )
        # if occupant, then theater can only be None (-1)
        if patient_info["is_occupant"]:
            # if the type is theater, then it must be value -1
            vfilt.a[
                (self.theater_vp.get_array() != -1)
                & (self.type_vp.get_array() == TYPE.THEATER)
            ] = 0
        else:
            # if patient, we take out the None (-1) option
            vfilt[theater_occupant] = 0

        edges_all = self.edges
        targets = edges_all[:, 1]
        sources = edges_all[:, 0]
        # also, length_of_day determines the number of shifts
        # a patient can only go to the sink from the last shift
        last_shift = patient_info["length_of_stay"] * 3 - 1
        last_horizon_shift = self.instance.get_last_shift_horizon()
        incomplete_stay_before_end = (shift_pos_arr != last_shift) & (
            shift_arr != last_horizon_shift
        )
        efilt.a[(targets == sink) & incomplete_stay_before_end[sources]] = 0

        # if the patient is not mandatory, we keep the edge from source to sink:
        if not patient_info.get("mandatory", True):
            efilt[source, sink] = 1

        # we delete nodes that go over the length of stay
        vfilt.a[shift_pos_arr > last_shift] = 0

        return gr.GraphView(self.g, vfilt=vfilt, efilt=efilt)

    def filter_feasibility(self, checks, patient_info):
        # these are the properties we want to fill
        my_graph = self.patient_graphs[patient_info["id"]]
        vfilt = my_graph.new_vp("bool", val=1)
        efilt = my_graph.new_ep("bool", val=1)

        shift_arr = self.shift_vp.get_array()
        type_arr = self.type_vp.get_array()
        room_arr = self.room_vp.get_array()
        theater_arr = self.theater_vp.get_array()

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
            my_theater = self._equiv_theater[th]
            node_active = (
                (my_shift == shift_arr)
                & (type_arr == TYPE.THEATER)
                & (theater_arr == my_theater)
            )
            vfilt.a[node_active] = 0

        for d in ban_days:
            my_shift = d * 3
            node_active = (my_shift == shift_arr) & (type_arr == TYPE.DAY)
            vfilt.a[node_active] = 0

        for r, d in ban_room_days:
            # this ban is for the whole stay.
            # if a patient cannot be in room r in day d
            # it cannot start in that room for the previous length_of_stay days
            my_room = self._equiv_room[r]
            start_shift = max(0, d - patient_info["length_of_stay"] + 1) * 3
            end_shift = d * 3
            node_active = (
                (shift_arr >= start_shift)
                & (shift_arr <= end_shift)
                & (room_arr == my_room)
                & (type_arr == TYPE.ROOM)
            )
            vfilt.a[node_active] = 0

        return gr.GraphView(my_graph, vfilt=vfilt, efilt=efilt)

    def nodes_to_pattern(
        self, node1, node2, checks, mask, patient, experiment, **kwargs
    ):
        if node1 is None:
            node1 = get_source_node(self.instance)
        if node2 is None:
            node2 = get_sink_node(self.instance)

        patient_info = self.instance.get_patients_occupants()[patient]
        refs = self.refs
        refs_inv = self.refs_inv
        graph = self.filter_feasibility(checks, patient_info)

        weights = self.get_weights(
            node1, node2, checks, patient_info, graph, experiment
        )

        source = find_vertex(graph, refs, node1)
        target = find_vertex(graph, refs, node2)
        nodes, edges = gr.shortest_path(
            graph, source=source, target=target, weights=weights, dag=True
        )
        return [refs_inv[n] for n in nodes]

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
        skill_levels = self.instance.get_nurses().get_property("skill_level")
        # get the skill level of the current nurse in that room
        skill_level__r_s = experiment.get_nurse_assignment_shift().vapply(
            lambda v: skill_levels[v["id"]]
        )
        min_required = min(skill_levels.values())

        # get the level required by patients currently in each room, shift
        # only those above the minimum level (who have no penalty by definition)
        level_required = (
            checks["shift_details"]
            .values_tl()
            .vfilter(lambda v: v["skill_level_required"] > min_required)
            .to_dict("skill_level_required", indices=["room", "shift"])
        )

        # get the skill level of the node (proposed skill level)
        proposed_skill_level = self.skill_level_vp.get_array()

        # I first calculate the new patients penalties per node
        diff_error = np.zeros_like(proposed_skill_level)
        shift_sl_needs = (
            self.__needs__p__s[patient_info["id"]]
            .get_property("skill_level_required")
            .vfilter(lambda v: v > 0)
        )
        new_patient_penalty = np.zeros_like(proposed_skill_level)
        for pos, required in shift_sl_needs.items():
            relevant_nodes = self.nodes__pos[pos]
            new_patient_penalty[relevant_nodes] = (
                required - proposed_skill_level[relevant_nodes]
            )
        new_patient_penalty[new_patient_penalty < 0] = 0
        # And now I calculate the penalties of changing the nurse of a particular room
        for (r, s), required_l in level_required.items():
            # TODO: relevant nodes can be potentially filtered by the patient graph
            # list nodes that cover that room and shift:
            relevant_node = self.nodes__r_s[r, s]
            for required in required_l:
                # penalty of the current assignment for that room and shift
                penalty_1 = max(0, required - skill_level__r_s[r, s])
                # penalty of the proposed assignment for all nodes
                #  that have that room and shift
                penalty_2 = required - proposed_skill_level[relevant_node]
                penalty_2[penalty_2 < 0] = 0
                # we calculate the increase in penalties (change in objective function term)
                diff_error[relevant_node] += penalty_2 - penalty_1
        return new_patient_penalty + diff_error

    def get_overwork_scores(self, checks, patient_info, graph):
        # load by room, shift, nurse
        current_workload = (
            checks["shift_details"]
            .values_tl()
            .to_dict("workload_produced", indices=["room", "shift", "nurse"])
            .vapply(sum)
        )

        # get the max workload of the node
        max_load_arr = self.max_load_vp.get_array()
        excess_load_n1 = np.zeros_like(max_load_arr)
        excess_load_n2 = np.zeros_like(max_load_arr)
        current_penalty_n2 = np.zeros_like(max_load_arr)
        current_penalty_n1 = np.zeros_like(max_load_arr)
        new_penalty_n1 = np.zeros_like(max_load_arr)
        new_penalty_n2 = np.zeros_like(max_load_arr)
        change_load = np.zeros_like(max_load_arr)
        # get the current load on nurse and shift:

        excess_load = checks["nurse_eccessive_workload"]
        for (nurse, shift), excess in excess_load.items():
            excess_load_n2[self.nodes__n_s[nurse, shift]] = excess
        for (room, shift, prev_nurse), load in current_workload.items():
            # we add the load of the current nurse on the node:
            my_rs_nodes = self.nodes__r_s[room, shift]
            my_excess_load = excess_load[prev_nurse, shift]
            excess_load_n1[my_rs_nodes] = my_excess_load
            set_rs = set(self.nodes__r_s[room, shift])
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
        for pos, load in shift_wl_needs.items():
            relevant_nodes = self.nodes__pos[pos]
            change_load_n2[relevant_nodes] += load

        # nurse1 decreases load
        new_excess_load_n1 = excess_load_n1 - change_load
        # nurse2 increases load
        new_excess_load_n2 = excess_load_n2 + change_load_n2
        current_penalty_n1[excess_load_n1 > 0] = excess_load_n1[excess_load_n1 > 0]
        current_penalty_n2[excess_load_n2 > 0] = excess_load_n2[excess_load_n2 > 0]
        new_penalty_n1[new_excess_load_n1 > 0] = new_excess_load_n1[
            new_excess_load_n1 > 0
        ]
        new_penalty_n2[new_excess_load_n2 > 0] = new_excess_load_n2[
            new_excess_load_n2 > 0
        ]

        return new_penalty_n1 + new_penalty_n2 - current_penalty_n1 - current_penalty_n2

    def get_continuity_care_scores(self):
        # we look for the last nodes before the sink
        # and apply the cost when entering them
        n_continuity_care = self.g.new_vp("int")
        last_nodes = self.g.vertex(self.get_sink_node()).in_neighbors()
        for node in last_nodes:
            n_continuity_care[node] = len(self.refs_inv[node].hist_nurses)
        return n_continuity_care.get_array()

    def get_weights(self, node1, node2, checks, patient_info, graph, experiment):
        nodes_window = self.get_nodes_in_window(node1, node2)
        edges_all = self.edges
        targets = edges_all[:, 1]
        sources = edges_all[:, 0]
        relevant_edge = nodes_window[sources] & nodes_window[targets]

        weights = self.instance.get_weights()
        edge_unassigned = self.get_unassigned_scores(patient_info)
        n_admission_delay = self.get_admission_delay_scores(patient_info)
        n_open_theater = self.get_opened_theater_scores(checks)
        n_surgeon_transfer = self.get_surgeon_transfer_scores(checks, patient_info)
        n_age_diff = self.get_age_scores(checks, patient_info)
        n_workload = self.get_overwork_scores(checks, patient_info, graph)
        n_skill_level = self.get_skill_level_scores(checks, patient_info, experiment)
        # TODO: here we need to calculate how changing a nurse affects the other patients
        # n_continuity_care = self.get_continuity_care_scores()

        out_weights = self.g.new_ep("int")
        out_weights.a[relevant_edge] = (
            n_workload[targets][relevant_edge] * weights["nurse_eccessive_workload"]
            # + n_continuity_care[targets][relevant_edge] * weights["continuity_of_care"]
            + n_admission_delay[targets][relevant_edge] * weights["patient_delay"]
            + edge_unassigned[relevant_edge] * weights["unscheduled_optional"]
            + n_skill_level[targets][relevant_edge] * weights["room_nurse_skill"]
            + n_age_diff[targets][relevant_edge] * weights["room_mixed_age"]
            + n_open_theater[targets][relevant_edge] * weights["open_operating_theater"]
            + n_surgeon_transfer[targets][relevant_edge] * weights["surgeon_transfer"]
        )
        return out_weights

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
            node = refs_inv[v]
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
        # if not_show_None:
        #     keep_node = g.new_vp("bool")
        #     for v in g.vertices():
        #         if refs_inv[v].rut is None and first <= refs_inv[v].period <= last:
        #             keep_node[v] = 0
        #         else:
        #             keep_node[v] = 1
        #     g_filt = gr.GraphView(g, vfilt=keep_node)

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


def find_vertex(graph, refs, node):
    return graph.vertex(refs[node])


# at initialize time:
# 1 graph for all patients

# during solving:
# for each patient:
# . filter nodes
# . update weights
# . get the shortest path/ pattern for patient
# . apply path if improvement


def patient_to_graph(instance, max_neighbors, max_nurses):
    print(f"Graph started")
    nodes_ady = SuperDict()
    source = get_source_node(instance)
    nodes_ady = source.walk_over_nodes(
        nodes_ady, max_neighbors=max_neighbors, max_nurses=max_nurses
    )
    graph = GraphTool(instance=instance, nodes_ady=nodes_ady)
    return graph


if __name__ == "__main__":
    pass
