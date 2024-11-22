from ..core.instance import Instance
from pytups import TupList, SuperDict
import orjson as json
from typing import Dict
import os
import multiprocessing as multi


class TYPE(object):
    THEATER = 1
    DAY = 0
    ROOM = 2
    NURSE = 3
    DUMMY = -1


ALL_TYPES = [TYPE.THEATER, TYPE.DAY, TYPE.ROOM, TYPE.NURSE, TYPE.DUMMY]


class Node(object):
    """
    corresponds to an assignment to a patient in a shift.
    shift number
    pos_shift
    operating theater
    room
    nurse
    type
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
        # if type == TYPE.NURSE:
        #     self.hist_nurses[nurse] = 1
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
            assignment = f"th:{self.theater}:{self.shift}"
        elif self.type == TYPE.ROOM:
            assignment = f"room:{self.room}:{self.shift}"
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

    def copy(self):
        return Node.from_node(
            self,
            hist_nurses=dict(self.hist_nurses),
            instance=self.instance.copy(),
            keep_cache=False,
        )

    @classmethod
    def from_node(cls, node: "Node", keep_cache=True, **kwargs):
        """
        :param Node node: another node to copy from
        :param keep_cache: if we want to keep the cache of the node
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
            hist_nurses=kwargs.get("hist_nurses", node.hist_nurses),
            instance=kwargs.get("instance", node.instance),
        )
        if keep_cache:
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
        starts = self.instance.get_patient_occupants_available_starts()
        starts_in_shift = set(d * 3 for p, days in starts.items() for d in days)
        return [Node.from_node(self, shift=s, type=TYPE.DAY) for s in starts_in_shift]

    def get_adjacency_theaters(self):
        # TODO: maybe not all theaters are available all days
        #  if I get the min_surgery_duration for anyone that started in day d
        #  we can filter availability
        theaters = self.instance.get_operatingtheaters().keys_tl()
        # None should only available be for occupants:
        # but occupants only have it on the first shift
        if self.shift == 0:
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
        pos_shift_may_be_last = (
            self.pos_shift in all_last_pos_shift and self.type == TYPE.NURSE
        )
        patient_may_be_skipped = self.type == TYPE.DUMMY
        if pos_shift_may_be_last or patient_may_be_skipped:
            if adjacent[0] != sink_node:
                adjacent = adjacent + [sink_node]
        return adjacent

    def walk_over_nodes(self, cache_neighbors=None, max_neighbors=None, max_nurses=10):
        """

        :param node: node from where we start the DFS
        :return: all arcs
        """
        patients = self.instance.get_patients_occupants()
        starts = self.instance.get_patient_occupants_available_starts()
        starts_in_shift = starts.vapply(sorted).vapply(lambda v: [vv * 3 for vv in v])
        room_ban = self.instance.get_patient_room_ban()
        rooms = self.instance.get_rooms()
        # we translate the lengths into shifts...
        lengths = patients.get_property("length_of_stay").vapply(lambda v: v * 3 - 1)
        my_domain = [
            (t, r, lengths[p])
            for p, _range in starts_in_shift.items()
            for t in _range
            for r in rooms
            if (p, r) not in room_ban
        ]
        my_lengths = TupList(my_domain).unique2().to_dict(2).vapply(sorted)

        remaining_nodes = [self]
        # we store the neighbors of visited nodes, not to recalculate them
        if not cache_neighbors:
            cache_neighbors = SuperDict()
        # given that cache_neighbors could already exist,
        #  we generate our own list of actual visited nodes
        i = 0
        last_node = get_sink_node(self.instance)

        while len(remaining_nodes) and i < 12e6:
            if i % 10000 == 0:
                # if i % 10 == 0:
                print(
                    f"Process {os.getpid()}, Iteration {i}, remaining: {len(remaining_nodes)}, visited: {len(cache_neighbors)}"
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
        print(f"Process {os.getpid()}: finished")
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


def get_theater_occupant(instance):
    return Node(
        instance=instance,
        shift=0,
        pos_shift=-1,
        theater=None,
        room=None,
        nurse=None,
        type=TYPE.THEATER,
        hist_nurses=dict(),
    )


def get_nodes_ady(instance, **kwargs):
    source = get_source_node(instance)
    return source.walk_over_nodes(**kwargs)


def get_nodes_ady_par(instance, num_workers=4, **kwargs):
    # TODO: watch out with importing timefold and python-java code
    source = get_source_node(instance)
    day_nodes = source.get_adjacency_days()
    nodes_ady = SuperDict()
    with multi.Pool(processes=num_workers) as pool:
        results = pool.map(Node.walk_over_nodes, day_nodes)
    for a in results:
        nodes_ady.update(a)
    nodes_ady[source] = day_nodes + [get_sink_node(instance)]
    return nodes_ady


def nodes_per_patient(
    nodes_ady: SuperDict[Node, list[Node]], instance: Instance
) -> SuperDict:
    # TODO: test this
    nodes = nodes_ady.keys()
    nodes_ady = nodes_ady.vapply(set)
    day_range = instance.get_patient_occupants_available_starts()
    patients = instance.get_patients_occupants()
    length_p = patients.get_property("length_of_stay")
    _by_start = SuperDict({r * 3: set() for d in day_range.values() for r in d})
    # this only applies to source:
    _by_start[-1] = set()
    _by_room = SuperDict({r: set() for r in instance.get_rooms()})
    _by_room[None] = set()
    _by_type = SuperDict({r: set() for r in ALL_TYPES})
    _by_shift = SuperDict(
        {r: set() for r in range(instance.get_last_shift_horizon() + 1)}
    )
    # positions at or before a certain length of stay
    all_positions = range(max(length_p.values()) * 3)
    _by_pos = SuperDict({r: set() for r in all_positions})
    # we want to count the shifts before the nurse
    _by_pos[-1] = set()
    for v in nodes:
        if v.pos_shift >= 0:
            _by_start[v.shift - v.pos_shift].add(v)
        else:
            # nodes without pos_shift still have start_shift=shift
            _by_start[v.shift].add(v)
        # we want to store those with pos_shift == -1
        _by_pos[v.pos_shift].add(v)
        _by_room[v.room].add(v)
        _by_type[v.type].add(v)
        if v.shift > 0:
            _by_shift[v.shift].add(v)

    _by_length = SuperDict({r: set() for r in length_p.values()})
    days = sorted(_by_length.keys())
    day_pos = 0
    len_days = len(days)
    for pos in all_positions:
        if pos / 3 >= days[day_pos]:
            day_pos += 1
        for dd_pos in range(day_pos, len_days):
            _by_length[days[dd_pos]] |= _by_pos[pos]

    for k, v in _by_length.items():
        v |= _by_pos[-1]

    # here we've done all the preprocessing.
    # we can now, iterate (or parallelize) by patient
    prep_data = {
        "_by_start": _by_start,
        "_by_room": _by_room,
        "_by_type": _by_type,
        "_by_length": _by_length,
        "_by_pos": _by_pos,
        "day_range": day_range,
        "length_p": length_p,
    }
    my_nodes_ady = SuperDict()
    results = {}
    with multi.Manager() as manager:
        # Create a shared object
        shared_object = manager.dict(nodes_ady)
        shared_object1 = manager.dict(prep_data)

        # Create a pool of worker processes
        with multi.Pool(processes=4) as pool:
            # Pass the shared object to the worker processes
            # pool.map(worker, [shared_object] * 4)
            for p, patient_info in patients.items():
                results[p] = pool.apply_async(
                    get_nodes_ady_per_patient,
                    [instance, shared_object, patient_info, shared_object1],
                )
            for p, a in results.items():
                my_nodes_ady[p] = a.get()
    # for p, patient_info in patients.items():
    #     my_nodes_ady[p] = get_nodes_ady_per_patient(
    #         instance, nodes_ady, patient_info, prep_data
    #     )

    return my_nodes_ady


def init(big_object_arg, big_object_arg2):
    global nodes_ady, prep_data
    nodes_ady = big_object_arg
    prep_data = big_object_arg2


def apply_patient(instance, patient_info):
    global nodes_ady, prep_data
    return get_nodes_ady_per_patient(instance, nodes_ady, patient_info, prep_data)


def get_nodes_ady_per_patient(
    instance: Instance,
    nodes_ady: SuperDict[Node, set[Node]],
    patient_info: SuperDict,
    prep_data: dict[str, any],
) -> SuperDict[Node, list[Node]]:
    print(f"Process {os.getpid()}, Patient {patient_info['id']}, start nodes_ady")
    _by_start = prep_data["_by_start"]
    _by_room = prep_data["_by_room"]
    _by_type = prep_data["_by_type"]
    _by_length = prep_data["_by_length"]
    _by_pos = prep_data["_by_pos"]
    day_range = prep_data["day_range"]
    length_p = prep_data["length_p"]

    sink = get_sink_node(instance)
    source = get_source_node(instance)
    theater_occupant = get_theater_occupant(instance)
    patient = patient_info["id"]
    # if the type is nurse, we only allow those that start in the range
    # if not source or sink, we cannot have a shift before the available start
    # if not nurse or dummy, we cannot have a shift after the last start
    all_sets = [_by_start[d * 3] for d in day_range[patient]]
    my_nodes = set.union(*all_sets)
    if patient_info["is_occupant"]:
        # if occupant, we only permit their room
        my_room = instance.get_occupants()[patient]["room_id"]
        # only filter if type==room or type=nurse
        # which means room is my room or None
        possible = _by_room[my_room] | _by_room[None]
        my_nodes &= possible
    else:
        # if not occupant, we take out the ban rooms for the patient
        ban_rooms = (
            instance.get_patient_room_ban()
            .keys_tl()
            .to_dict(1)
            .get(patient_info["id"], [])
        )
        if len(ban_rooms) > 0:
            forbidden = set.union(*[_by_room[r] for r in ban_rooms])
            my_nodes -= forbidden

    if patient_info["is_occupant"]:
        # if occupant, then theater can only be None (-1)
        my_nodes -= _by_type[TYPE.THEATER]
        my_nodes.add(theater_occupant)
    else:
        # if patient, we take out the None (-1) option
        my_nodes -= {theater_occupant}

    # also, length_of_day determines the number of shifts
    # we delete nodes that go over the length of stay
    my_nodes &= _by_length[length_p[patient]]

    # we make sure that source is always available:
    #  sink has no edges so it's not on the list
    my_nodes |= {source}

    # we now get the arcs to edit them
    my_nodes_ady = nodes_ady.filter(my_nodes)

    # also, length_of_day determines the number of shifts
    last_horizon_shift = instance.get_last_shift_horizon()
    last_shift = patient_info["length_of_stay"] * 3 - 1
    for node, neighbors in my_nodes_ady.items():
        # we filter all neighbors to be inside the set of nodes
        #  this takes out the sink node
        my_nodes_ady[node] = neighbors & my_nodes
        # a patient can only go to the sink from the last shift
        # or at the end of the planning horizon
        if node.pos_shift == last_shift or node.shift == last_horizon_shift:
            my_nodes_ady[node].add(sink)

    # if the patient is not mandatory, we keep the edge from source to sink:
    #  if it's mandatory we take out the sink
    sink_connected = sink in my_nodes_ady[source]
    if patient_info.get("mandatory", True):
        if sink_connected:
            my_nodes_ady[source].remove(sink)
    else:
        if not sink_connected:
            my_nodes_ady[source].add(sink)
    print(f"Process {os.getpid()}, Patient {patient_info['id']}, ends nodes_ady")
    return my_nodes_ady
