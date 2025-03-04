import shutil
from PySide6 import QtWidgets, QtCore, QtGui
import os


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

    @QtCore.Slot()
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
