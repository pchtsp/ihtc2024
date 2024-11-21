from typing import Union, Type
from ..core import Experiment
from .naive import NAIVE
from .cp_sat import CpSAT
from .graph import Graph

# TODO: timefold imports jpype and it breaks the multiprocessing of python
# from .timefold import TimefoldPy

solvers = dict(naive=NAIVE, cpsat=CpSAT, graph=Graph)


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
