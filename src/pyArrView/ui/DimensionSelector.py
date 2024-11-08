from PySide6.QtWidgets import QPushButton, QButtonGroup, QWidget, QSpinBox, QHBoxLayout, QVBoxLayout
from PySide6.QtCore import Qt, Signal, Slot, QSignalBlocker

# Controls the dimension selection using buttons
# Controls the selected indices for each dimension using QSpinBox
class DimensionSelector(QWidget):
    dim_buttons = []
    button_group = QButtonGroup()
    selected_dimensions = [] # 0: row, 1: column, 2: dynamic
    dim_spinboxes = []
    current_indices = []
    indicesUpdatedSignal = Signal()
    layout = QHBoxLayout()
    def __init__(self, shape, parent=None):
        super().__init__(parent)
        self.ndims = len(shape)
        self.shape = shape
        self.current_indices = [slice(0, 1) for _ in range(self.ndims)]
        self.setLayout(self.layout)

        if self.ndims == 1:
            self.selected_dimensions = [0, 0, 0]
        elif self.ndims == 2:
            self.selected_dimensions = [0, 1, 0]
        else:
            self.selected_dimensions = [0, 1, 2]


        for dim_i in range(self.ndims):
            btn = DimButton(text=f'{shape[dim_i]}', dim_id=dim_i)
            btn.roleChangedSignal.connect(self.set_selected_dimensions)
            self.button_group.addButton(btn, dim_i)
            self.dim_spinboxes.append(DimSpinBox(dim_i))
            self.dim_spinboxes[dim_i].idxUpdatedSignal.connect(self.update_idx_selection)
            self.dim_spinboxes[dim_i].setMaximum(shape[dim_i]-1)
            self.dim_spinboxes[dim_i].setMinimum(-1)
            self.dim_spinboxes[dim_i].setSpecialValueText(":")
            l_ = QVBoxLayout()
            l_.addWidget(self.dim_spinboxes[dim_i])
            l_.addWidget(btn)
            self.layout.addLayout(l_)

        # Initialize the first and second dimension as row and column, third as the dynamic dimension
        self.dim_spinboxes[0].setValue(-1)
        self.dim_spinboxes[1].setValue(-1)

        self.button_group.button(self.selected_dimensions[0]).set_role(0)
        self.button_group.button(self.selected_dimensions[1]).set_role(1)
        self.button_group.button(self.selected_dimensions[2]).set_role(2)


    @Slot(int, int, bool)
    def update_idx_selection(self, value, dim_i, emit=True):
        '''Updates the selected indices for each dimension. Checks if the value is :, if so, changes the row or column dimension'''

        if value != -1:
            self.current_indices[dim_i] = slice(value, value+1)
        else:
            self.current_indices[dim_i] = slice(0, self.shape[dim_i])
        if emit:
            self.indicesUpdatedSignal.emit()

    def update_multiple_idx_selection(self, values, dims):
        for idx, dim_i in enumerate(dims):
            if values[idx] != -1:
                self.current_indices[dim_i] = slice(values[idx], values[idx]+1)
            else:
                self.current_indices[dim_i] = slice(0, self.shape[dim_i])
        self.indicesUpdatedSignal.emit()


    def set_selected_dimensions(self, source):
        '''Sets the selected dimension for each role. It will change the the previous dimension with the role to -1.
        '''

        dim_i = source.dim_id
        role = source.role
        if role != -1:
            prev_btn_id = self.selected_dimensions[role] 
            self.selected_dimensions[role] = source.dim_id
            if prev_btn_id != dim_i:
                self.button_group.button(prev_btn_id).set_role(-1)
                # Need to do the signal block trick to avoid asking plot to update before we are done with it.
                with QSignalBlocker(self.dim_spinboxes[prev_btn_id]):
                    self.dim_spinboxes[prev_btn_id].setValue(0)
                self.update_idx_selection(0, prev_btn_id, False)
            if role == 0 or role == 1:
                with QSignalBlocker(self.dim_spinboxes[dim_i]):
                    self.dim_spinboxes[dim_i].setValue(-1)
                self.update_idx_selection(-1, dim_i, False)

            self.indicesUpdatedSignal.emit()

    def dynamic_dimension(self):
        return self.selected_dimensions[2]

    def get_current_slices(self):
        return tuple(self.current_indices)

class DimButton(QPushButton):
    roleChangedSignal = Signal(QPushButton)
    def __init__(self, text, dim_id: int, parent=None):
        super().__init__(text, parent)
        self.setCheckable(False)
        self.set_role(-1)
        self.setContextMenuPolicy(Qt.PreventContextMenu)
        self.dim_id = dim_id

    def set_role(self, role):
        self.role = role
        if role == 0:
            self.setStyleSheet('background-color: red; color: white')
        elif role == 1:
            self.setStyleSheet('background-color: green; color: white')
        elif role == 2:
            self.setStyleSheet('background-color: blue; color: white')
        else:
            self.setStyleSheet('background-color: white; color: black')

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.set_role(0)
        elif event.button() == Qt.RightButton:
            self.set_role(1)
        elif event.button() == Qt.MiddleButton:
            self.set_role(2)
        super().mousePressEvent(event)
        self.roleChangedSignal.emit(self)

class DimSpinBox(QSpinBox):
    idxUpdatedSignal = Signal(int, int)
    def __init__(self, dim_id: int, parent=None):
        super().__init__(parent)
        self.dim_id = dim_id
        self.setContextMenuPolicy(Qt.PreventContextMenu)
        self.valueChanged.connect(self.update_idx_selection)

    def update_idx_selection(self, value):
        self.idxUpdatedSignal.emit(value, self.dim_id)