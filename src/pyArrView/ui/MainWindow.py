
import os
import logging
from PySide6 import QtWidgets
from PySide6.QtCore import Signal, Slot

from .ImageViewer import ImageViewer
from matplotlib import colormaps


class MainWindow(QtWidgets.QMainWindow):

    change_cmap = Signal(str)

    def __init__(self, array):
        super().__init__()

        self.setUnifiedTitleAndToolBarOnMac(True)

        self.view_menu = super().menuBar().addMenu("&View")
        self.cmap_menu = self.view_menu.addMenu("&Colormap")
        self.populate_cmap_menu()

        self.help_menu = super().menuBar().addMenu("&Help")
        self.help_menu.addAction("&Usage", self.usage_dialog)
        self.help_menu.addAction("&Shortcuts", self.shortcuts_dialog)
        self.help_menu.addAction("&About", self.about_dialog)
        
        self.setCentralWidget(ImageViewer(parent=self, array=array))

    def usage_dialog(self):
        QtWidgets.QMessageBox.information(self, "Usage", "Usage")

    def shortcuts_dialog(self):
        QtWidgets.QMessageBox.information(self, "Shortcuts", "Shortcuts")
    
    def about_dialog(self):
        QtWidgets.QMessageBox.information(self, "About", "About")

    def populate_cmap_menu(self):
        cmap_list = list(colormaps)

        for cmap in cmap_list:
            action = self.cmap_menu.addAction(cmap)
            action.triggered.connect(self.cmap_change_requested)

    @Slot()
    def cmap_change_requested(self):
        action = self.sender()
        cmap = action.text()
        self.change_cmap.emit(cmap)
