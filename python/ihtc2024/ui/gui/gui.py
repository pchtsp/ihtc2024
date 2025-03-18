# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'gui.ui'
##
## Created by: Qt User Interface Compiler version 6.8.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout,
    QHBoxLayout, QLabel, QLayout, QLineEdit,
    QMainWindow, QMenu, QMenuBar, QPushButton,
    QSizePolicy, QSpacerItem, QStatusBar, QTabWidget,
    QTextBrowser, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(837, 594)
        MainWindow.setStyleSheet(u"\n"
"    QMainWindow {\n"
"        background-color: #f0f0f0;\n"
"    }\n"
"    QPushButton {\n"
"        background-color: #4CAF50;\n"
"        color: white;\n"
"        border: none;\n"
"        padding: 10px 20px;\n"
"        text-align: center;\n"
"        text-decoration: none;\n"
"        display: inline-block;\n"
"        font-size: 14px;\n"
"        margin: 4px 2px;\n"
"        transition-duration: 0.4s;\n"
"        cursor: pointer;\n"
"        border-radius: 12px;\n"
"    }\n"
"    QPushButton:hover {\n"
"        background-color: white;\n"
"        color: black;\n"
"        border: 2px solid #4CAF50;\n"
"    }\n"
"    QPushButton:disabled {\n"
"        background-color: #d3d3d3;\n"
"        color: #a9a9a9;\n"
"        border: 1px solid #a9a9a9;\n"
"    }\n"
"    QLabel {\n"
"        font-size: 14px;\n"
"        color: #333;\n"
"    }\n"
"    QLineEdit {\n"
"        padding: 5px;\n"
"        border: 1px solid #ccc;\n"
"        border-radius: 4px;\n"
"    }\n"
"    QComboBox {\n"
"        padding: 5px;"
                        "\n"
"        border: 1px solid #ccc;\n"
"        border-radius: 4px;\n"
"    }\n"
"    QTextBrowser {\n"
"        border: 1px solid #ccc;\n"
"        border-radius: 4px;\n"
"        padding: 5px;\n"
"        background-color: white;\n"
"    }\n"
"   ")
        self.actionOpen_from = QAction(MainWindow)
        self.actionOpen_from.setObjectName(u"actionOpen_from")
        self.actionExit = QAction(MainWindow)
        self.actionExit.setObjectName(u"actionExit")
        self.actionSave = QAction(MainWindow)
        self.actionSave.setObjectName(u"actionSave")
        self.actionSave_As = QAction(MainWindow)
        self.actionSave_As.setObjectName(u"actionSave_As")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.widget = QWidget(self.centralwidget)
        self.widget.setObjectName(u"widget")
        self.verticalLayout_17 = QVBoxLayout(self.widget)
        self.verticalLayout_17.setObjectName(u"verticalLayout_17")
        self.verticalLayout_17.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setSpacing(2)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.chooseFile = QPushButton(self.widget)
        self.chooseFile.setObjectName(u"chooseFile")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.chooseFile.sizePolicy().hasHeightForWidth())
        self.chooseFile.setSizePolicy(sizePolicy)
        font = QFont()
        font.setUnderline(False)
        font.setStrikeOut(False)
        self.chooseFile.setFont(font)

        self.horizontalLayout_3.addWidget(self.chooseFile)

        self.loadTest = QPushButton(self.widget)
        self.loadTest.setObjectName(u"loadTest")
        sizePolicy.setHeightForWidth(self.loadTest.sizePolicy().hasHeightForWidth())
        self.loadTest.setSizePolicy(sizePolicy)

        self.horizontalLayout_3.addWidget(self.loadTest)

        self.exportSolution = QPushButton(self.widget)
        self.exportSolution.setObjectName(u"exportSolution")
        sizePolicy.setHeightForWidth(self.exportSolution.sizePolicy().hasHeightForWidth())
        self.exportSolution.setSizePolicy(sizePolicy)
        self.exportSolution.setFont(font)

        self.horizontalLayout_3.addWidget(self.exportSolution)

        self.exportSolution_to = QPushButton(self.widget)
        self.exportSolution_to.setObjectName(u"exportSolution_to")
        sizePolicy.setHeightForWidth(self.exportSolution_to.sizePolicy().hasHeightForWidth())
        self.exportSolution_to.setSizePolicy(sizePolicy)
        self.exportSolution_to.setFont(font)

        self.horizontalLayout_3.addWidget(self.exportSolution_to)

        self.instCheck = QLabel(self.widget)
        self.instCheck.setObjectName(u"instCheck")
        font1 = QFont()
        font1.setBold(True)
        self.instCheck.setFont(font1)
        self.instCheck.setStyleSheet(u"QLabel { color : red; }")
        self.instCheck.setTextFormat(Qt.TextFormat.AutoText)

        self.horizontalLayout_3.addWidget(self.instCheck)

        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_4)

        self.solCheck = QLabel(self.widget)
        self.solCheck.setObjectName(u"solCheck")
        self.solCheck.setFont(font1)
        self.solCheck.setStyleSheet(u"QLabel { color : red; }")

        self.horizontalLayout_3.addWidget(self.solCheck)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer)


        self.verticalLayout.addLayout(self.horizontalLayout_3)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")

        self.verticalLayout.addLayout(self.horizontalLayout_2)


        self.verticalLayout_17.addLayout(self.verticalLayout)

        self.tabWidget = QTabWidget(self.widget)
        self.tabWidget.setObjectName(u"tabWidget")
        self.Config = QWidget()
        self.Config.setObjectName(u"Config")
        self.horizontalLayout_10 = QHBoxLayout(self.Config)
        self.horizontalLayout_10.setObjectName(u"horizontalLayout_10")
        self.verticalLayout_13 = QVBoxLayout()
        self.verticalLayout_13.setObjectName(u"verticalLayout_13")
        self.formLayout_3 = QFormLayout()
        self.formLayout_3.setObjectName(u"formLayout_3")
        self.formLayout_3.setSizeConstraint(QLayout.SizeConstraint.SetMaximumSize)
        self.formLayout_3.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.max_timeLabel = QLabel(self.Config)
        self.max_timeLabel.setObjectName(u"max_timeLabel")

        self.formLayout_3.setWidget(1, QFormLayout.LabelRole, self.max_timeLabel)

        self.max_time = QLineEdit(self.Config)
        self.max_time.setObjectName(u"max_time")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.max_time.sizePolicy().hasHeightForWidth())
        self.max_time.setSizePolicy(sizePolicy1)

        self.formLayout_3.setWidget(1, QFormLayout.FieldRole, self.max_time)

        self.solverLabel = QLabel(self.Config)
        self.solverLabel.setObjectName(u"solverLabel")

        self.formLayout_3.setWidget(2, QFormLayout.LabelRole, self.solverLabel)

        self.solver = QComboBox(self.Config)
        self.solver.setObjectName(u"solver")
        self.solver.setEditable(True)

        self.formLayout_3.setWidget(2, QFormLayout.FieldRole, self.solver)

        self.log_levelLabel = QLabel(self.Config)
        self.log_levelLabel.setObjectName(u"log_levelLabel")

        self.formLayout_3.setWidget(3, QFormLayout.LabelRole, self.log_levelLabel)

        self.log_level = QComboBox(self.Config)
        self.log_level.setObjectName(u"log_level")
        self.log_level.setEditable(True)

        self.formLayout_3.setWidget(3, QFormLayout.FieldRole, self.log_level)

        self.reuse_solLabel = QLabel(self.Config)
        self.reuse_solLabel.setObjectName(u"reuse_solLabel")

        self.formLayout_3.setWidget(4, QFormLayout.LabelRole, self.reuse_solLabel)

        self.reuse_sol = QCheckBox(self.Config)
        self.reuse_sol.setObjectName(u"reuse_sol")

        self.formLayout_3.setWidget(4, QFormLayout.FieldRole, self.reuse_sol)


        self.verticalLayout_13.addLayout(self.formLayout_3)

        self.horizontalLayout_12 = QHBoxLayout()
        self.horizontalLayout_12.setObjectName(u"horizontalLayout_12")
        self.generateSolution = QPushButton(self.Config)
        self.generateSolution.setObjectName(u"generateSolution")
        sizePolicy.setHeightForWidth(self.generateSolution.sizePolicy().hasHeightForWidth())
        self.generateSolution.setSizePolicy(sizePolicy)

        self.horizontalLayout_12.addWidget(self.generateSolution)

        self.stopExecution = QPushButton(self.Config)
        self.stopExecution.setObjectName(u"stopExecution")
        self.stopExecution.setEnabled(False)
        sizePolicy.setHeightForWidth(self.stopExecution.sizePolicy().hasHeightForWidth())
        self.stopExecution.setSizePolicy(sizePolicy)

        self.horizontalLayout_12.addWidget(self.stopExecution)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_12.addItem(self.horizontalSpacer_2)


        self.verticalLayout_13.addLayout(self.horizontalLayout_12)

        self.solution_log = QTextBrowser(self.Config)
        self.solution_log.setObjectName(u"solution_log")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy2.setHorizontalStretch(1)
        sizePolicy2.setVerticalStretch(1)
        sizePolicy2.setHeightForWidth(self.solution_log.sizePolicy().hasHeightForWidth())
        self.solution_log.setSizePolicy(sizePolicy2)
        font2 = QFont()
        font2.setFamilies([u"Monospace"])
        self.solution_log.setFont(font2)

        self.verticalLayout_13.addWidget(self.solution_log)


        self.horizontalLayout_10.addLayout(self.verticalLayout_13)

        self.tabWidget.addTab(self.Config, "")
        self.Output = QWidget()
        self.Output.setObjectName(u"Output")
        self.horizontalLayout_4 = QHBoxLayout(self.Output)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.verticalLayout_15 = QVBoxLayout()
        self.verticalLayout_15.setObjectName(u"verticalLayout_15")
        self.formLayout = QFormLayout()
        self.formLayout.setObjectName(u"formLayout")
        self.formLayout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.objectiveLabel = QLabel(self.Output)
        self.objectiveLabel.setObjectName(u"objectiveLabel")

        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.objectiveLabel)

        self.objectiveLineEdit = QLineEdit(self.Output)
        self.objectiveLineEdit.setObjectName(u"objectiveLineEdit")
        self.objectiveLineEdit.setReadOnly(True)

        self.formLayout.setWidget(0, QFormLayout.FieldRole, self.objectiveLineEdit)

        self.errorsLabel = QLabel(self.Output)
        self.errorsLabel.setObjectName(u"errorsLabel")

        self.formLayout.setWidget(1, QFormLayout.LabelRole, self.errorsLabel)

        self.errorsLineEdit = QLineEdit(self.Output)
        self.errorsLineEdit.setObjectName(u"errorsLineEdit")
        self.errorsLineEdit.setReadOnly(True)

        self.formLayout.setWidget(1, QFormLayout.FieldRole, self.errorsLineEdit)


        self.verticalLayout_15.addLayout(self.formLayout)

        self.horizontalLayout_14 = QHBoxLayout()
        self.horizontalLayout_14.setObjectName(u"horizontalLayout_14")
        self.checkSolution = QPushButton(self.Output)
        self.checkSolution.setObjectName(u"checkSolution")

        self.horizontalLayout_14.addWidget(self.checkSolution)

        self.generateReport = QPushButton(self.Output)
        self.generateReport.setObjectName(u"generateReport")

        self.horizontalLayout_14.addWidget(self.generateReport)

        self.openReport = QPushButton(self.Output)
        self.openReport.setObjectName(u"openReport")

        self.horizontalLayout_14.addWidget(self.openReport)

        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_14.addItem(self.horizontalSpacer_3)


        self.verticalLayout_15.addLayout(self.horizontalLayout_14)

        self.solution_report = QTextBrowser(self.Output)
        self.solution_report.setObjectName(u"solution_report")
        sizePolicy2.setHeightForWidth(self.solution_report.sizePolicy().hasHeightForWidth())
        self.solution_report.setSizePolicy(sizePolicy2)
        self.solution_report.setFont(font2)

        self.verticalLayout_15.addWidget(self.solution_report)


        self.horizontalLayout_4.addLayout(self.verticalLayout_15)

        self.tabWidget.addTab(self.Output, "")

        self.verticalLayout_17.addWidget(self.tabWidget)


        self.horizontalLayout.addWidget(self.widget)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 837, 23))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menuFile.addAction(self.actionOpen_from)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionSave)
        self.menuFile.addAction(self.actionSave_As)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionExit)

        self.retranslateUi(MainWindow)

        self.chooseFile.setDefault(False)
        self.exportSolution.setDefault(False)
        self.exportSolution_to.setDefault(False)
        self.tabWidget.setCurrentIndex(0)
        self.generateSolution.setDefault(False)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MyOptimApp", None))
        self.actionOpen_from.setText(QCoreApplication.translate("MainWindow", u"Open from...", None))
        self.actionExit.setText(QCoreApplication.translate("MainWindow", u"Exit", None))
        self.actionSave.setText(QCoreApplication.translate("MainWindow", u"Export", None))
        self.actionSave_As.setText(QCoreApplication.translate("MainWindow", u"Export As...", None))
        self.chooseFile.setText(QCoreApplication.translate("MainWindow", u"Open", None))
        self.loadTest.setText(QCoreApplication.translate("MainWindow", u"Test", None))
        self.exportSolution.setText(QCoreApplication.translate("MainWindow", u"Save", None))
        self.exportSolution_to.setText(QCoreApplication.translate("MainWindow", u"Save As", None))
        self.instCheck.setText(QCoreApplication.translate("MainWindow", u"No instance loaded", None))
        self.solCheck.setText(QCoreApplication.translate("MainWindow", u"No solution loaded", None))
#if QT_CONFIG(tooltip)
        self.Config.setToolTip(QCoreApplication.translate("MainWindow", u"<html><head/><body><p>configuration</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.max_timeLabel.setText(QCoreApplication.translate("MainWindow", u"Max solving time", None))
        self.max_time.setText(QCoreApplication.translate("MainWindow", u"60", None))
        self.max_time.setPlaceholderText(QCoreApplication.translate("MainWindow", u"60", None))
        self.solverLabel.setText(QCoreApplication.translate("MainWindow", u"Solver", None))
        self.log_levelLabel.setText(QCoreApplication.translate("MainWindow", u"Logging level", None))
        self.log_level.setCurrentText(QCoreApplication.translate("MainWindow", u"INFO", None))
        self.reuse_solLabel.setText(QCoreApplication.translate("MainWindow", u"Reuse previous solution", None))
        self.generateSolution.setText(QCoreApplication.translate("MainWindow", u"Generate plan", None))
        self.stopExecution.setText(QCoreApplication.translate("MainWindow", u"Stop execution", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.Config), QCoreApplication.translate("MainWindow", u"Solve", None))
        self.objectiveLabel.setText(QCoreApplication.translate("MainWindow", u"Objective", None))
        self.errorsLabel.setText(QCoreApplication.translate("MainWindow", u"Errors", None))
        self.checkSolution.setText(QCoreApplication.translate("MainWindow", u"Check solution", None))
        self.generateReport.setText(QCoreApplication.translate("MainWindow", u"Generate report", None))
        self.openReport.setText(QCoreApplication.translate("MainWindow", u"Open report", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.Output), QCoreApplication.translate("MainWindow", u"Statistics", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"File", None))
    # retranslateUi

