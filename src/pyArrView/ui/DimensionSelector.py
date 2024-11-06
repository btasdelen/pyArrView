from PySide6.QtWidgets import QPushButton, QButtonGroup
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

class DimensionSelector(QButtonGroup):
    dim_buttons = []
    selected_dimensions = [] # 0: row, 1: column, 2: dynamic
    def __init__(self, shape, parent=None):
        super().__init__(parent)
        self.ndims = len(shape)
        self.shape = shape

        if self.ndims == 1:
            self.selected_dimensions = [0, 0, 0]
        elif self.ndims == 2:
            self.selected_dimensions = [0, 1, 0]
        else:
            self.selected_dimensions = [0, 1, 2]

        for dim_i in range(self.ndims):
            self.dim_buttons.append(QPushButton(text=f'{shape[dim_i]}'))
            self.dim_buttons[dim_i].setCheckable(True)
            self.addButton(self.dim_buttons[dim_i], dim_i)
            self.dim_buttons[dim_i].clicked.connect(lambda dim_i=dim_i: self.onButtonClicked(dim_i))

    def onButtonClicked(self, dim_i):
        role = self.dim_buttons[dim_i].role

        # if buttons == Qt.LeftButton:
        #     self.selected_dimensions[0] = dim_i
        # elif buttons == Qt.RightButton:
        #     self.selected_dimensions[1] = dim_i
        #     role = 1
        # elif buttons == Qt.MiddleButton:
        #     self.selected_dimensions[2] = dim_i
        #     role = 2
        
        self.set_button_style(self.dim_buttons[dim_i], role)

    def set_button_style(self, button, role):
        if role == 0:
            button.setStyleSheet('background-color: red')
        elif role == 1:
            button.setStyleSheet('background-color: green')
        elif role == 2:
            button.setStyleSheet('background-color: blue')

class DimButton(QPushButton):
    def __init__(self, text, dim_id: int, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.set_role(-1)
        self.setContextMenuPolicy(Qt.PreventContextMenu)
        self.dim_id = dim_id

    def set_role(self, role):
        self.role = role
        if role == 0:
            self.setStyleSheet('background-color: red')
        elif role == 1:
            self.setStyleSheet('background-color: green')
        elif role == 2:
            self.setStyleSheet('background-color: blue')
        else:
            self.setStyleSheet('background-color: white')

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.set_role(0)
        elif event.button() == Qt.RightButton:
            self.set_role(1)
        elif event.button() == Qt.MiddleButton:
            self.set_role(2)
        super().mousePressEvent(event)