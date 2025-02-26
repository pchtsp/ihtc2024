import shutil
import sys
from PySide6 import QtWidgets, QtCore, QtGui
from cornflow_client import ApplicationCore
from cornflow_client.constants import (
    SOLUTION_STATUS_FEASIBLE,
    SOLUTION_STATUS_INFEASIBLE,
)

import os
import gui

from typing import Type
import tempfile
from worker import Worker
from worker2 import Worker2

# import faulthandler


class MainWindow_EXCEC(object):

    def __init__(self, App: Type[ApplicationCore], options: dict):
        # handle solving in thread
        self.thread = None
        self.worker = None

        self.my_app = App()
        self.Experiment = self.my_app.get_solver(self.my_app.get_default_solver_name())
        self.Instance = self.my_app.instance
        self.Solution = self.my_app.solution
        self.options = options
        self.app = QtWidgets.QApplication(sys.argv)
        MainWindow = QtWidgets.QMainWindow()

        # set icon
        if getattr(sys, "frozen", False):
            scriptDir = sys._MEIPASS
            self.examplesDir = scriptDir + "/examples/"
        else:
            scriptDir = os.path.dirname(os.path.realpath(__file__))
            self.examplesDir = scriptDir + "/../../../../results/"
        icon_path = os.path.join(scriptDir, "plane.ico")
        MainWindow.setWindowIcon(QtGui.QIcon(icon_path))

        self.ui = gui.Ui_MainWindow()
        self.ui.setupUi(MainWindow)
        self.ui.excel_path.setText("")

        self.instance = None
        self.solution = None

        self.update_ui()

        # menu actions:
        self.ui.actionOpen_from.triggered.connect(self.choose_file)
        self.ui.actionSave.triggered.connect(self.export_solution)
        self.ui.actionSave_As.triggered.connect(self.export_solution_to)
        self.ui.actionExit.triggered.connect(QtCore.QCoreApplication.exit)

        # below buttons:
        self.ui.chooseFile.clicked.connect(self.choose_file)
        self.ui.generateSolution.clicked.connect(self.generate_solution)
        # self.ui.generateSolution_missions.clicked.connect(
        #     self.generate_solution_missions
        # )

        self.ui.checkSolution.clicked.connect(self.check_solution)
        self.ui.exportSolution.clicked.connect(self.export_solution)
        self.ui.exportSolution_to.clicked.connect(self.export_solution_to)
        self.ui.generateReport.clicked.connect(self.generate_report)

        # other
        self.ui.max_time.textEdited.connect(self.update_options)
        self.ui.log_level.currentIndexChanged.connect(self.update_options)
        self.ui.solver.currentIndexChanged.connect(self.update_options)
        self.ui.solver.addItems(self.my_app.solvers.keys())

        # Set up logging to QTextBrowser
        # text_browser_handler = QTextBrowserLogger(self.ui.solution_log)
        # self.options["log_handler"] = text_browser_handler

        MainWindow.show()
        sys.exit(self.app.exec())

    def update_options(self):
        try:
            self.options["timeLimit"] = float(self.ui.max_time.text())
            self.options["debug"] = self.ui.log_level.currentIndex() == 1
            self.options["solver"] = self.ui.solver.currentText()
        except:
            return 0
        return 1

    def update_ui(self):
        self.ui.max_time.setText(str(self.options.get("timeLimit", 60)))
        if self.instance is None:
            self.ui.instCheck.setText("No instance loaded")
            self.ui.instCheck.setStyleSheet("QLabel { color : red; }")
        else:
            self.ui.instCheck.setText("Instance loaded")
            self.ui.instCheck.setStyleSheet("QLabel { color : green; }")
        if self.solution is None:
            self.ui.solCheck.setText("No solution loaded")
            self.ui.solCheck.setStyleSheet("QLabel { color : red; }")
            self.ui.reuse_sol.setEnabled(False)
            self.ui.reuse_sol.setChecked(False)
        else:
            self.ui.solCheck.setText("Solution loaded")
            self.ui.solCheck.setStyleSheet("QLabel { color : green; }")
            self.ui.reuse_sol.setEnabled(True)
            self.ui.reuse_sol.setChecked(True)
        return 1

    def choose_file(self):
        file_name = get_file_dialog(self.examplesDir)
        # we update the examplesDir to the directory of the file
        actual_file_name = file_name[0]
        if not actual_file_name:
            return False
        self.examplesDir = os.path.dirname(actual_file_name)
        # if os.path.isfile(dirName):
        #     dirName = os.path.dirname(dirName)
        # exec.udpdate_case_read_options(self.options, dirName + "/")
        self.ui.excel_path.setText(actual_file_name)
        self.load_template(actual_file_name)
        self.update_ui()
        return True

    def read_dir(self):
        self.load_template(self.ui.excel_path.text())

    def show_message(self, title, text, icon="critical"):
        msg = QtWidgets.QMessageBox()
        if icon == "critical":
            msg.setIcon(QtWidgets.QMessageBox.Critical)
        msg.setText(text)
        msg.setWindowTitle(title)
        retval = msg.exec()
        return

    def load_jsons(self, path):
        try:
            my_instance = self.Instance.from_json(path)
            if my_instance.data:
                self.instance = my_instance
            else:
                raise Exception("No data in instance")
            return 1
        except:
            try:
                my_solution = self.Solution.from_json(path)
                if my_solution.data:
                    self.solution = my_solution
            except Exception as e:
                self.show_message(
                    title="Error reading json",
                    text="There's been an error reading the file:\n{}.".format(e),
                    icon="critical",
                )
                return 0
        return 1

    def load_template(self, file_name):
        base, ext = os.path.splitext(file_name)
        if ext == ".json":
            return self.load_jsons(file_name)

        if not os.path.exists(file_name):
            self.show_message(
                title="Missing files",
                text=f"File {file_name} does not exist.",
            )
            return
        try:
            self.instance = self.Instance.from_excel(file_name)
        except Exception as e:
            self.show_message(
                title="Error reading instance",
                text="There's been an error reading the instance:\n{}.".format(e),
            )
            return
        try:
            self.solution = self.Solution.from_excel(file_name)
        except Exception as e:
            self.show_message(
                title="Error reading solution",
                text="There's been an error reading the solution:\n{}.".format(e),
                icon="information",
            )
            self.solution = None
        return True

    def check_solution(self):
        if not self.solution:
            self.show_message(
                title="Missing files", text="No solution is loaded, can't verify it."
            )
            return
        experiment = self.Experiment(self.instance, self.solution)
        errors = experiment.check_solution()
        errors = {k: v.to_dictdict() for k, v in errors.items()}
        # TODO: show errors in a screen

        return

    def generate_solution(self):
        # faulthandler.enable()
        options = dict(self.options)
        if not self.instance:
            self.show_message(
                title="Loading needed",
                text="No instance loaded, so not possible to solve.",
            )
            return
        if not options.get("solver"):
            self.show_message(
                title="Missing solver",
                text="No solver selected, so not possible to solve.",
            )
            return
        solution = None
        if self.ui.reuse_sol.isChecked():
            solution = self.solution

        tmpdirname = tempfile.mkdtemp()
        options["logPath"] = os.path.join(tmpdirname, "log.txt")
        options["msg"] = True
        self.my_log_tailer = LogTailer(
            options["logPath"], self.ui.solution_log, interval=100
        )
        solution_json_str = None
        if solution is not None:
            solution_json_str = solution.to_json_str()
        self.worker = Worker2(
            self.my_app, self.instance.to_json_str(), solution_json_str, options
        )
        self.worker.setObjectName("test thread")
        self.ui.stopExecution.setEnabled(True)
        self.ui.generateSolution.setEnabled(False)

        self.worker.finished.connect(self.get_solution)
        self.worker.started.connect(self.my_log_tailer.start)
        self.worker.finished.connect(self.my_log_tailer.stop)
        self.ui.stopExecution.clicked.connect(self.worker.kill)

        # new Worker:
        self.worker.start()

        # old Worker:
        # self.thread = QtCore.QThread()
        # self.worker.moveToThread(self.thread)
        # self.worker.finished.connect(self.worker.deleteLater)
        # self.thread.started.connect(self.worker.run)
        # self.worker.finished.connect(self.thread.quit)
        # self.thread.finished.connect(self.thread.deleteLater)
        # self.thread.start()

        return 1

    # def update_log(self, message):
    #     self.ui.solution_log.append(message)
    #     self.ui.solution_log.moveCursor(QtGui.QTextCursor.MoveOperation.End)

    @QtCore.Slot(bool, int, str)
    def get_solution(self, success, sol_status, soldata):
        # print(f"window: {QtCore.QThread.currentThread().objectName()}")
        # print("get_solution_1")
        if not success:
            return 0
        if sol_status != SOLUTION_STATUS_FEASIBLE or not soldata:
            return 0
        self.solution = self.Solution.from_json_str(soldata)
        # print("get_solution_2")
        self.ui.stopExecution.setEnabled(False)
        self.ui.generateSolution.setEnabled(True)
        self.update_ui()
        # print("get_solution_3")
        return 1

    def export_solution_gen(self, output_path):
        if not self.instance or not self.solution:
            self.show_message(
                "Error",
                "No solution can be exported because there is no loaded solution.",
            )
            return 0
        experiment = self.Experiment(self.instance, self.solution)
        try:
            experiment.to_excel(output_path)
        except PermissionError:
            self.show_message(
                "Error",
                "Output file cannot be overwritten.\nCheck it is not open and you have enough permissions.",
            )
            return 0

        self.show_message("Success", "Solution successfully exported.", icon="Success")
        return 1

    def export_solution(self):
        output_path = self.ui.excel_path.text()
        return self.export_solution_gen(output_path)

    def export_solution_to(self):
        file_name = get_file_dialog(self.ui.excel_path.text())
        if not file_name:
            return False
        return self.export_solution_gen(file_name[0])

    def generate_report(self, path=None):
        if not self.instance or not self.solution:
            self.show_message(
                "Error",
                "No solution can be exported because there is no loaded solution.",
            )
            return 0
        experiment = self.Experiment(self.instance, self.solution)
        # we generate the report
        try:
            rep_path = experiment.generate_report("report")
        except Exception as e:
            self.show_message(
                "Error",
                f"A problem occurred generating report: {e}",
            )
            return 0
        if not os.path.exists(rep_path):
            self.show_message(
                "Error",
                f"A problem occurred generating report",
            )
            return 0
        # move report to path
        if not path:
            path = "report.html"
        if os.path.isdir(path):
            path = os.path.join(path, "report.html")
        os.rename(rep_path, path)
        return 1


#
# class QTextBrowserLogger(logging.Handler):
#     text_browser: QtWidgets.QTextBrowser
#
#     def __init__(self, text_browser):
#         super().__init__()
#         self.text_browser = text_browser
#
#     def emit(self, record):
#         msg = self.format(record)
#         self.text_browser.append(msg)
#         self.text_browser.moveCursor(QtGui.QTextCursor.MoveOperation.End)


def get_file_dialog(my_dir: str):
    QFileDialog = QtWidgets.QFileDialog
    options = QFileDialog.Options()
    options |= QFileDialog.DontUseNativeDialog
    return QFileDialog.getOpenFileName(
        caption="Choose an Excel file to load",
        dir=my_dir,
        options=options,
        filter="All Files (*);;Excel files (*.xlsx *.xlsm);;Json files (*.json)",
    )


class LogTailer(QtCore.QObject):
    def __init__(
        self,
        file_path,
        text_browser: QtWidgets.QTextBrowser,
        interval=1000,
        parent=None,
    ):
        super().__init__(parent)
        self.file_path = file_path
        self.text_browser = text_browser
        self.text_browser.clear()
        self.interval = interval
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_log)
        self.last_position = 0

    @QtCore.Slot()
    def start(self):
        # print("start called")
        self.timer.start(self.interval)

    @QtCore.Slot()
    def stop(self):
        # print("stop called")
        self.timer.stop()
        # we delete the directory of the log
        my_dir = os.path.dirname(self.file_path)
        if os.path.exists(my_dir):
            shutil.rmtree(my_dir)

    def update_log(self):
        # print("update_log called")
        if not os.path.exists(self.file_path):
            # print(f"File {self.file_path} does not exist")
            return
        with open(self.file_path, "r") as file:
            file.seek(self.last_position)
            content = file.read()
            # lines = file.readlines()
            self.last_position = file.tell()
            if content:
                # self.text_browser.append("".join(lines))
                self.text_browser.insertPlainText(content)
                self.text_browser.moveCursor(QtGui.QTextCursor.MoveOperation.End)


if __name__ == "__main__":
    # to compile desktop_app.gui, we need the following:
    # pyuic5 -o filename.py file.ui
    # if we add -x flag we make it executable
    # example: pyuic5 desktop_app/gui.ui -o desktop_app/gui.py
    # for pyside2:
    # Migration to pyside2:
    # https://www.learnpyqt.com/blog/pyqt5-vs-pyside2/
    # pyside6-uic ihtc2024/ui/gui/gui.ui -o ihtc2024/ui/gui/gui.py

    from ihtc2024 import IntegratedHealtcareTimetable as App

    MainWindow_EXCEC(App, {})
