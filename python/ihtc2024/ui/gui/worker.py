from PySide6 import QtCore
from cornflow_client.constants import (
    STATUS_OPTIMAL,
    STATUS_INFEASIBLE,
    STATUS_UNDEFINED,
    SOLUTION_STATUS_FEASIBLE,
    SOLUTION_STATUS_INFEASIBLE,
)
import time
import copy
import sys
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


class Worker(QtCore.QObject):
    def __init__(self, my_app, instance, solution, options, *args, **kwargs):
        QtCore.QObject.__init__(self, *args, **kwargs)
        self.abort = False
        self.is_running = True

        self.__instance = my_app.instance.from_json_str(instance)
        self.solution = None
        if solution is not None:
            self.solution = my_app.solution.from_json_str(solution)
        self.options = options
        self.my_app = my_app
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
            my_solver = self.my_app.get_solver(self.options.get("solver"))
            experiment = my_solver(self.__instance, self.solution)
            status = experiment.solve(self.options)
            self.solution = experiment.solution
            # for i in range(100):
            #     if self.abort:
            #         self.killed.emit()
            #         self.status.emit("Task killed!")
            #         break
            #     print(i)  # Simulate a long-running task
            #     time.sleep(1)
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

    # def calculate_progress(self):
    #     self.processed = self.processed + 1
    #     percentage_new = (self.processed * 100) / self.feature_count
    #     if percentage_new > self.percentage:
    #         self.percentage = percentage_new
    #         self.progress.emit(self.percentage)

    def kill(self):
        self.abort = True

    error = QtCore.Signal(str)
    progress = QtCore.Signal(int)
    status = QtCore.Signal(str)
    killed = QtCore.Signal()
    started = QtCore.Signal()
    finished = QtCore.Signal(bool, int, str)
    log_message = QtCore.Signal(str)
