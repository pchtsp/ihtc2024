from PySide6 import QtCore
import logging
from cornflow_client import ApplicationCore


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
        print("writing message")
        if message.strip():
            self.signal.emit(message)

    def flush(self):
        pass


class BaseWorker(QtCore.QThread):
    error = QtCore.Signal(str)
    progress = QtCore.Signal(int)
    status = QtCore.Signal(str)
    killed = QtCore.Signal()
    started = QtCore.Signal()
    finished = QtCore.Signal(bool)
    log_message = QtCore.Signal(str)

    def __init__(
        self, my_app: ApplicationCore, instance: str, solution: str, *args, **kwargs
    ):
        QtCore.QThread.__init__(self, *args, **kwargs)
        self.abort = False
        self.is_running = True

        self._instance = my_app.instance.from_json_str(instance)
        self.solution = None
        if solution is not None:
            self.solution = my_app.solution.from_json_str(solution)
        self.my_app = my_app
        # self.text_browser_handler = SignalLogger(self.log_message)

    def run(self):
        # sys.stdout = StreamLogger(self.log_message)
        # self.options["log_handler"] = self.text_browser_handler
        # sys.stdout = sys.__stdout__  # Restore stdout

        raise NotImplementedError()

    def kill(self):
        raise NotImplementedError()
