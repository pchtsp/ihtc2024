from cornflow_client.constants import (
    STATUS_UNDEFINED,
    SOLUTION_STATUS_INFEASIBLE,
)
from base_worker import BaseWorker
from PySide6 import QtCore


class OptimWorker(BaseWorker):
    options: dict
    finished = QtCore.Signal(bool, int, str)

    def __init__(self, my_app, instance, solution, options: dict, *args, **kwargs):
        BaseWorker.__init__(self, my_app, instance, solution, *args, **kwargs)
        self.solver_name: str = options.get("solver")
        self.my_callback_obj = None
        self.options = dict(options)

    def run(self):
        status = dict(status=STATUS_UNDEFINED, status_sol=SOLUTION_STATUS_INFEASIBLE)
        soldata = ""
        success = False
        try:
            self.status.emit("Task started!")
            self.started.emit()
            my_solver = self.my_app.get_solver(self.solver_name)
            if self.solver_name in ["cpsat2step", "cpsat"]:
                self.my_callback_obj = my_solver.getStopOnUser_callback()
                self.options["stop_condition"] = self.my_callback_obj
            else:
                self.my_callback_obj = my_solver.getStopOnUser_callback()
                self.options["stop_condition"] = self.my_callback_obj

            experiment = my_solver(self._instance, self.solution)
            status = experiment.solve(self.options)
            self.solution = experiment.solution

        except:
            import traceback

            self.error.emit(traceback.format_exc())
            success = False

        else:
            success = True
            self.status.emit("Task finished!")
        finally:
            if self.solution is not None:
                soldata = self.solution.to_json_str()
            self.finished.emit(success, status["status_sol"], soldata)

    def kill(self):
        self.abort = True
        if self.my_callback_obj:
            self.my_callback_obj.stop()
            self.killed.emit()
