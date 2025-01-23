from typing import Union, Type
from ..core import Experiment
from .naive import NAIVE
from .cp_sat import CpSAT
from .cp_sat_2step import CpSAT2Step
from .graph import Graph
from .graph_tw import GraphTW

# TODO: timefold imports jpype and it breaks the multiprocessing of python
# from .timefold import TimefoldPy

solvers = dict(
    naive=NAIVE, cpsat=CpSAT, graph=Graph, graph_tw=GraphTW, cpsat2step=CpSAT2Step
)


def get_solver(name: str = "milp_solver") -> Union[Type[Experiment], None]:
    """
    Conventionally, we accept two formats
    - class name inherited from Experiment, e.g. "milp_solver"
    - class name + "." + engine name, e.g. "milp_solver.PULP_CBC_CMD"
    """
    if "." in name:
        solver, _ = name.split(".")
    else:
        solver = name
    return solvers.get(solver)
