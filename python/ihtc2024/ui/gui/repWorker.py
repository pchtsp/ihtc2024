from base_worker import BaseWorker, StreamLogger
import sys
from PySide6 import QtCore
from ihtc2024.core.tools import stdout_redirected


class RepWorker(BaseWorker):
    finished = QtCore.Signal(bool, str)

    def run(self):
        rep_path = ""
        success = False
        try:
            path_of_log = "log.txt"
            with open(path_of_log, "a") as f, stdout_redirected(f, sys.stderr):
                Experiment = self.my_app.get_solver(
                    self.my_app.get_default_solver_name()
                )
                experiment = Experiment(self.instance, self.solution)
                # self.options["log_handler"] = self.text_browser_handler
                self.status.emit("Task started!")
                self.started.emit()
                rep_path = experiment.generate_report("report")
        except:
            import traceback

            self.error.emit(traceback.format_exc())
            self.status.emit("Task failed!")
            success = False

        else:
            success = True
            self.status.emit("Task finished!")
        finally:
            self.finished.emit(success, rep_path)
            sys.stdout = sys.__stdout__  # Restore stdout
