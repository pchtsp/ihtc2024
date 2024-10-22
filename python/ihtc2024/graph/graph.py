# installing graph-tool and adding it to venv:
# https://git.skewed.de/count0/graph-tool/wikis/installation-instructions
# https://jolo.xyz/blog/2018/12/07/installing-graph-tool-with-virtualenv

import graph_tool.all as gr
from pytups import SuperDict

from .node import get_source_node, get_sink_node, Node, TYPE
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
        self.skill_deficit = self.g.new_vp("int")

        # needs_patient = self.instance.get_patients_occupants_needs().to_dictdict()[
        #     self.patient
        # ]
        # needs_wl = needs_patient.get_property("workload_produced")
        # needs_sl = needs_patient.get_property("skill_level_required")
        # nurse_sl = self.instance.get_nurses().get_property("skill_level")

        for v in self.g.vertices():
            node = self.refs_inv[v]
            self.type_vp[v] = node.type
            self.nurse_vp[v] = self._equiv_nurse[node.nurse]
            self.theater_vp[v] = self._equiv_theater[node.theater]
            self.room_vp[v] = self._equiv_room[node.room]
            self.shift_vp[v] = node.shift
            self.pos_shift_vp[v] = node.pos_shift
            # if node.type == TYPE.NURSE:
            #     self.skill_deficit[v] = max(
            #         0, needs_sl[node.pos_shift] - nurse_sl[node.nurse]
            #     )
            #     self.needs_wl_vp[v] = needs_wl[node.pos_shift]
            # else:
            #     self.skill_deficit[v] = 0
            #     self.needs_wl_vp[v] = 0

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

    def filter_feasibility(self, checks, patient_info):
        # by default, we allow all nodes:
        vfilt = self.g.new_vp("bool", val=1)
        my_gender = patient_info["gender"]

        # if there's another gender in a room-day, we take out
        ban_room_days = checks["gender"].vfilter(lambda v: my_gender not in v).keys()
        # if there's 0 capacity left in a room-day, we take out
        ban_room_days |= checks["capacity_overuse"].vfilter(lambda v: v == 0).keys()

        # it may be possible that the patient is actually an occupant:
        ban_days = []
        if not patient_info["is_occupant"]:
            surgery_duration = patient_info["surgery_duration"]
            my_surgeon = patient_info["surgeon_id"]
            # if the surgeon has less capacity than duration in some day, we take out those days
            ban_days = (
                checks["surgeon_overtime"]
                .to_dictdict()
                .get(my_surgeon, {})
                .vfilter(lambda v: -surgery_duration < v)
            )

        room_arr = self.room_vp.get_array()
        shift_arr = self.shift_vp.get_array()
        type_arr = self.type_vp.get_array()

        for d in ban_days:
            my_shift = d * 3
            node_active = (my_shift == shift_arr) & (type_arr == TYPE.DAY)
            vfilt.a[node_active] = 0

        for r, d in ban_room_days:
            my_room = self._equiv_room[r]
            my_shift = d * 3
            node_active = (
                (my_shift == shift_arr)
                & (room_arr == my_room)
                & (type_arr == TYPE.ROOM)
            )
            vfilt.a[node_active] = 0

        return gr.GraphView(self.g, vfilt=vfilt)

    def nodes_to_pattern(self, node1, node2, checks, mask, patient, **kwargs):
        if node1 is None:
            node1 = get_source_node(self.instance)
        if node2 is None:
            node2 = get_sink_node(self.instance)

        patient_info = self.instance.get_patients_occupants()[patient]
        refs = self.refs
        refs_inv = self.refs_inv
        graph = self.filter_feasibility(checks, patient_info)

        weights = self.get_weights(node1, node2, checks, patient_info)

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

    def get_overwork_scores(self, checks, patient_info):
        current_workload = checks["workload_room"]
        nurse_assignment = current_workload.keys_tl().to_dict(2, is_list=False)
        room_workload = (
            current_workload.to_tuplist().to_dict(3, indices=[0, 1]).vapply(sum)
        )
        # nurse_eccessive_workload
        # this is the remaining workload:
        excess_workload = checks["nurse_eccessive_workload"]
        excess_workload_current = excess_workload.vapply(lambda v: max(v, 0))
        needs_by_pos = self.instance.get_patients_occupants_needs().to_dictdict()[
            patient_info["id"]
        ]
        workload_by_pos = needs_by_pos.get_property("workload_produced")

        def overwork_change_when_assigning_room(nurse, shift, room, pos_shift):
            # returns the change in workload when assigning nurse to room
            # it's possible there's no workload in that room
            room_workload_for_nurse1 = room_workload.get((room, shift), 0)
            room_workload_for_nurse2 = -room_workload_for_nurse1
            # it's possible there's no nurse assigned to that room:
            prev_nurse = nurse_assignment.get((room, shift))
            if prev_nurse is None or prev_nurse == nurse:
                # if the nurse is already assigned to the room, no extra workload
                # if no nurse is assigned to that room, then the workload is 0
                room_workload_for_nurse1 = 0
                diff_overwork_nurse2 = 0
            else:
                # if the nurse is not assigned to the room, we need to calculate the workload of the previous nurse
                diff_overwork_nurse2 = (
                    max(
                        excess_workload[prev_nurse, shift] + room_workload_for_nurse2, 0
                    )
                    - excess_workload_current[prev_nurse, shift]
                )
            diff_overwork_nurse1 = (
                max(
                    0,
                    # initial workload
                    excess_workload[nurse, shift]
                    # workload of the new room
                    + room_workload_for_nurse1
                    # workload of the new patient
                    + workload_by_pos[pos_shift],
                )
                - excess_workload_current[nurse, shift]
            )

            return diff_overwork_nurse1 + diff_overwork_nurse2

        workload_vp = self.g.new_vp("int")
        for v in self.g.vertices():
            node = self.refs_inv[v]
            if node.type != TYPE.NURSE:
                continue
            data = dict(
                nurse=node.nurse,
                shift=node.shift,
                room=node.room,
                pos_shift=node.pos_shift,
            )
            workload_vp[v] = overwork_change_when_assigning_room(**data)
        return workload_vp.get_array()

    def get_continuity_care_scores(self):
        # we look for the last nodes before the sink
        # and apply the cost when entering them
        n_continuity_care = self.g.new_vp("int")
        last_nodes = self.g.vertex(self.get_sink_node()).in_neighbors()
        for node in last_nodes:
            n_continuity_care[node] = len(self.refs_inv[node].hist_nurses)
        return n_continuity_care.get_array()

    def get_weights(self, node1, node2, checks, patient_info):
        nodes_window = self.get_nodes_in_window(node1, node2)
        edges_all = self.edges
        targets = edges_all[:, 1]
        sources = edges_all[:, 0]
        relevant_edge = nodes_window[sources] & nodes_window[targets]

        weights = self.instance.get_weights()
        edge_unassigned = self.get_unassigned_scores()
        n_admission_delay = self.get_admission_delay_scores()
        n_open_theater = self.get_opened_theater_scores(checks)
        n_surgeon_transfer = self.get_surgeon_transfer_scores(checks)
        n_age_diff = self.get_age_scores(checks)
        n_workload = self.get_overwork_scores(checks)
        n_continuity_care = self.get_continuity_care_scores()

        # TODO:
        #  skill level is more complicated, we need to check all patients in the target room
        # minimum skill level
        n_skill_level = self.skill_deficit.get_array()

        out_weights = self.g.new_ep("int")
        out_weights.a[relevant_edge] = (
            n_workload[targets][relevant_edge] * weights["nurse_eccessive_workload"]
            + n_continuity_care[targets][relevant_edge] * weights["continuity_of_care"]
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
    ):
        instance = self.instance
        refs_inv = self.refs_inv
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
