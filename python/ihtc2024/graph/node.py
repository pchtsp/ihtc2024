from ..core.instance import Instance

import pytups.superdict as sd
from pytups import TupList
import random as rn
import orjson as json
from typing import Dict
import numpy as np


class TYPE(object):
    THEATER = 1
    DAY = 0
    ROOM = 2
    NURSE = 3
    DUMMY = -1


nextType = {
    TYPE.DUMMY: TYPE.DAY,
    TYPE.DAY: TYPE.THEATER,
    TYPE.THEATER: TYPE.ROOM,
    TYPE.NURSE: TYPE.NURSE,
}


class Node(object):
    """
    corresponds to an assignment to a patient in a shift.
    shift number
    pos_shift
    operating theater
    room
    nurse
    type
    previous nurses: dict(nurse: 1)
    """

    type: int
    nurse: str | None
    shift: int
    room: str | None
    theater: str | None
    pos_shift: int
    hist_nurses: Dict[str, int] | None

    def __init__(
        self,
        instance: Instance,
        shift: int,
        pos_shift: int,
        theater: str | None,
        room: str | None,
        nurse: str | None,
        type: int,
        hist_nurses: Dict[str, int] | None,
    ):
        self.instance = instance
        self.shift = shift
        self.pos_shift = pos_shift
        # after the first shift, we do not care the theater that was chosen
        if type == TYPE.THEATER:
            self.theater = theater
        else:
            self.theater = None
        self.room = room
        self.nurse = nurse
        self.type = type
        # we make a copy of the nurses assigned to the patient
        if hist_nurses is not None:
            self.hist_nurses = hist_nurses.copy()
        else:
            self.hist_nurses = hist_nurses
        # we accumulate the nurses assigned to the patient
        if type == TYPE.NURSE:
            self.hist_nurses[nurse] = 1
        data = self.get_data()
        self.jsondump = json.dumps(data, option=json.OPT_SORT_KEYS)
        self.hash = hash(self.jsondump)

        # backups / cache
        self.__nurses__s = None
        self.__patients_occupants = None
        self.__lengths_of_stay = None
        self.__last_shift = None

    def __repr__(self):
        # theater + room + first shift => (shift-> nurse)
        # pos_shift = self.pos_shift if self.pos_shift >= 0 else 0
        if self.type == TYPE.NURSE:
            nurses = list(self.hist_nurses.keys())
            assignment = (
                f"nu:{self.shift}/{self.pos_shift}->{self.nurse}@{self.room}{nurses}"
            )
        elif self.type == TYPE.THEATER:
            assignment = f"th:{self.theater}"
        elif self.type == TYPE.ROOM:
            assignment = f"room:{self.room}"
        elif self.type == TYPE.DUMMY:
            if self.shift == -1:
                assignment = "source"
            else:
                assignment = "sink"
        else:
            assignment = f"start:{self.shift}"
        return repr(assignment)

    def __hash__(self):
        return self.hash

    def __eq__(self, other):
        return self.jsondump == other.jsondump

    def get_nurses_by_shift(self):
        if self.__nurses__s is None:
            self.__nurses__s = (
                self.instance.get_nurse_shift().keys_tl().to_dict().vapply(set)
            )
        return self.__nurses__s

    def get_patients_occupants(self):
        if self.__patients_occupants is None:
            self.__patients_occupants = self.instance.get_patients_occupants()
        return self.__patients_occupants

    def get_last_shift_horizon(self):
        if self.__last_shift is None:
            self.__last_shift = self.instance.get_last_shift_horizon()
        return self.__last_shift

    def get_lengths_of_stay(self):
        if self.__lengths_of_stay is None:
            self.__lengths_of_stay = (
                self.get_patients_occupants()
                .get_property("length_of_stay")
                .values_tl()
                .unique2()
                .vapply(lambda v: v * 3 - 1)
                .to_set()
            )
        return self.__lengths_of_stay

    def get_data(self) -> dict:
        return {
            "shift": self.shift,
            "pos_shift": self.pos_shift,
            "theater": self.theater,
            "room": self.room,
            "nurse": self.nurse,
            "type": self.type,
            "hist_nurses": self.hist_nurses,
        }

    @classmethod
    def from_node(cls, node: "Node", **kwargs):
        """
        :param Node node: another node to copy from
        :param kwargs: replacement properties for new node
        :return:
        """
        new_node = cls(
            shift=kwargs.get("shift", node.shift),
            pos_shift=kwargs.get("pos_shift", node.pos_shift),
            theater=kwargs.get("theater", node.theater),
            room=kwargs.get("room", node.room),
            nurse=kwargs.get("nurse", node.nurse),
            type=kwargs.get("type", node.type),
            hist_nurses=node.hist_nurses,
            instance=node.instance,
        )
        # we initialize the cache parameters:
        new_node.__nurses__s = node.__nurses__s
        new_node.__patients_occupants = node.__patients_occupants
        new_node.__lengths_of_stay = node.__lengths_of_stay
        new_node.__last_shift = node.__last_shift

        return new_node

    def get_adjacent_shift(self, max_nurses):
        nurses__s = self.get_nurses_by_shift()
        if self.pos_shift >= 0:
            new_shift = self.shift + 1
            pos_shift = self.pos_shift + 1
        else:
            new_shift = self.shift
            pos_shift = 0
        my_nurses = nurses__s[new_shift]
        if len(self.hist_nurses) == max_nurses:
            my_nurses &= self.hist_nurses.keys()
        if len(my_nurses) == 0:
            my_nurses = [list(nurses__s[new_shift])[0]]
        return [
            Node.from_node(
                self, nurse=n, shift=new_shift, pos_shift=pos_shift, type=TYPE.NURSE
            )
            for n in my_nurses
        ]

    def get_adjacency_rooms(self):
        # since we're in a generic graph, all rooms are available in theory:
        return [
            Node.from_node(self, room=r, type=TYPE.ROOM)
            for r in self.instance.get_rooms()
        ]
        # rooms__p = self.instance.get_patients_occupants_available_rooms()
        # return [
        #     Node.from_node(self, room=r, type=TYPE.ROOM) for r in rooms__p[self.patient]
        # ]

    def get_adjacency_days(self):
        # since we're in a generic graph, all days are available in theory:
        get_first = self.instance.get_first_shift_of_day
        possible_starts = self.instance.get_horizon_days()
        shifts = [get_first(d) for d in possible_starts]
        return [Node.from_node(self, shift=d, type=TYPE.DAY) for d in shifts]
        # possible_starts = self.instance.get_patient_occupants_available_starts()

        # shifts = [get_first(d) for d in possible_starts[self.patient]]
        # return [Node.from_node(self, shift=d, type=TYPE.DAY) for d in shifts]

    def get_adjacency_theaters(self):
        # TODO: maybe not all theaters are available all days
        #  if I get the min_surgery_duration for anyone that started in day d
        #  we can filter availability
        theaters = self.instance.get_operatingtheaters().keys_tl()
        # None should only available be for occupants:
        theaters += [None]
        return [Node.from_node(self, theater=th, type=TYPE.THEATER) for th in theaters]
        # my_day = self.instance.get_day_from_shift(self.shift)
        # patient_info = self.get_patient_info()
        # if patient_info["is_occupant"]:
        #     # we do not assign a theater, but we still need to continue
        #     return [Node.from_node(self, theater=None, type=TYPE.THEATER)]
        # surgery_duration = patient_info["surgery_duration"]
        #
        # capacity = self.instance.get_operatingtheater_capacity()
        #
        # theater_per_day = (
        #     capacity.vfilter(lambda v: v["availability"] >= surgery_duration)
        #     .values_tl()
        #     .to_dict("operating_theater", indices="day")
        # )
        # return [
        #     Node.from_node(self, theater=th, type=TYPE.THEATER)
        #     for th in theaters
        # ]

    def get_adjacency_list(self, sink_node, my_lengths, max_nurses):
        all_last_pos_shift = []
        max_post_shift = 1000
        if self.type == TYPE.NURSE:
            all_last_pos_shift = my_lengths[self.shift - self.pos_shift, self.room]
            max_post_shift = max(all_last_pos_shift)
        last_shift = self.get_last_shift_horizon()
        # if I'm at the last shift of the stay, we go to the sink node
        # or if I reach the last shift of the horizon
        if self.pos_shift == max_post_shift or self.shift == last_shift:
            adjacent = [sink_node]
        elif self.type == TYPE.DUMMY:
            adjacent = self.get_adjacency_days()
        elif self.type == TYPE.DAY:
            adjacent = self.get_adjacency_theaters()
        elif self.type == TYPE.THEATER:
            adjacent = self.get_adjacency_rooms()
        else:
            # type=room or type=nurse
            adjacent = self.get_adjacent_shift(max_nurses)
        # if len(adjacent) > max_neighbors:
        #     adjacent = rn.sample(adjacent, max_neighbors)
        # after sampling, we consider adding the optional arc
        pos_shift_may_be_last = (
            self.pos_shift in all_last_pos_shift and self.type == TYPE.NURSE
        )
        patient_may_be_skipped = self.type == TYPE.DUMMY
        if pos_shift_may_be_last or patient_may_be_skipped:
            if adjacent[0] != sink_node:
                adjacent = adjacent + [sink_node]
        return adjacent

    def walk_over_nodes(self, cache_neighbors=None, max_neighbors=5, max_nurses=10):
        """

        :param node: node from where we start the DFS
        :return: all arcs
        """
        # calculate [starts, room]: max length triplets.
        patients = self.instance.get_patients_occupants()
        optional = patients.vfilter(lambda v: not v.get("mandatory", True)).keys()
        starts = self.instance.get_patient_occupants_available_starts()
        # only sample the optional
        starts_sampled_in_shift = (
            starts.kvapply(
                lambda k, v: (
                    rn.sample(v, k=min(max_neighbors, len(v))) if k in optional else v
                )
            )
            .vapply(sorted)
            .vapply(lambda v: [vv * 3 for vv in v])
        )
        room_ban = self.instance.get_patient_room_ban()
        rooms = self.instance.get_rooms()
        # we translate the lengths into shifts...
        lengths = patients.get_property("length_of_stay").vapply(lambda v: v * 3 - 1)
        my_domain = [
            (t, r, lengths[p])
            for p, _range in starts_sampled_in_shift.items()
            for t in _range
            for r in rooms
            if (p, r) not in room_ban
        ]
        my_lengths = TupList(my_domain).unique2().to_dict(2).vapply(sorted)

        remaining_nodes = [self]
        # we store the neighbors of visited nodes, not to recalculate them
        if not cache_neighbors:
            cache_neighbors = sd.SuperDict()
        # given that cache_neighbors could already exist,
        #  we generate our own list of actual visited nodes
        i = 0
        last_node = get_sink_node(self.instance)

        while len(remaining_nodes) and i < 12e6:
            if i % 10000 == 0:
                print(
                    f"Iteration {i}, remaining: {len(remaining_nodes)}, visited: {len(cache_neighbors)}"
                )
            i += 1
            node = remaining_nodes.pop()
            # we need to make a copy of the path
            if node == last_node:
                # if last_node reached, go back
                continue
            # we're not in the last_node.
            neighbors = cache_neighbors.get(node)
            if neighbors is None:
                # I don't have any cache of the node.
                # I'll get neighbors and do cache
                cache_neighbors[node] = neighbors = node.get_adjacency_list(
                    last_node, my_lengths, max_nurses
                )
                # since the node is new, we want to visit its neighbors
                remaining_nodes += neighbors
            # log.debug("iteration: {}, remaining: {}, stored: {}".format(i, len(remaining_nodes), len(cache_neighbors)))
        return cache_neighbors


def get_source_node(instance):

    return Node(
        instance=instance,
        shift=-1,
        pos_shift=-1,
        theater=None,
        room=None,
        nurse=None,
        type=TYPE.DUMMY,
        hist_nurses=dict(),
    )


def get_sink_node(instance):

    return Node(
        instance=instance,
        shift=instance.get_last_shift_horizon() + 1,
        pos_shift=-1,
        theater=None,
        room=None,
        nurse=None,
        type=TYPE.DUMMY,
        hist_nurses=None,
    )
