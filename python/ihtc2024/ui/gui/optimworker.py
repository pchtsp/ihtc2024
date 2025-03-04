from PySide6 import QtCore
from cornflow_client.constants import (
    STATUS_UNDEFINED,
    SOLUTION_STATUS_INFEASIBLE,
)
import copy
import logging


class SignalLogger(logging.Handler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def emit(self, record):
        msg: str = self.format(record)
        self.signal.emit(msg)


class StreamLogger:
    def __init__(self, signal):
        self.signal = signal

    def write(self, message):
        if message.strip():
            self.signal.emit(message)

    def flush(self):
        pass


class Worker2(QtCore.QThread):
    error = QtCore.Signal(str)
    progress = QtCore.Signal(int)
    status = QtCore.Signal(str)
    killed = QtCore.Signal()
    started = QtCore.Signal()
    finished = QtCore.Signal(bool, int, str)
    log_message = QtCore.Signal(str)

    def __init__(self, my_app, instance, solution, options, *args, **kwargs):
        QtCore.QThread.__init__(self, *args, **kwargs)
        self.abort = False
        self.is_running = True

        self.__instance = my_app.instance.from_json_str(instance)
        self.solution = None
        if solution is not None:
            self.solution = my_app.solution.from_json_str(solution)
        self.options = dict(options)
        self.my_app = my_app
        self.solver_name: str = self.options.get("solver")
        self.my_callback_obj = None
        # self.text_browser_handler = SignalLogger(self.log_message)

    def run(self):
        status = dict(status=STATUS_UNDEFINED, status_sol=SOLUTION_STATUS_INFEASIBLE)
        soldata = ""
        success = False
        try:
            # sys.stdout = StreamLogger(self.log_message)
            # self.options["log_handler"] = self.text_browser_handler
            self.status.emit("Task started!")
            self.started.emit()
            my_solver = self.my_app.get_solver(self.solver_name)
            if self.solver_name in ["cpsat2step", "cpsat"]:
                self.my_callback_obj = my_solver.getStopOnUser_callback()
                self.options["stop_condition"] = self.my_callback_obj
            else:
                self.my_callback_obj = my_solver.getStopOnUser_callback()
                self.options["stop_condition"] = self.my_callback_obj

            experiment = my_solver(self.__instance, self.solution)
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
            self.finished.emit(success, status["status_sol"], copy.deepcopy(soldata))
            # sys.stdout = sys.__stdout__  # Restore stdout

    def kill(self):
        self.abort = True
        if self.my_callback_obj:
            self.my_callback_obj.stop()
            self.killed.emit()
