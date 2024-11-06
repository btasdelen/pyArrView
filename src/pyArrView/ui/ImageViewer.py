import logging
import numpy as np
import scipy.io as spio
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('QtAgg')

from PySide6 import QtCore, QtGui, QtWidgets as QTW

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from functools import cache
import numpy.typing as npt

class ImageViewer(QTW.QWidget):

    timer_interval = 100 # [ms]
    current_indices = []
    selected_dims = [0, 1, 2] # Triplet of dimensions 0: y axis, 1: x axis, 2: dynamic axis
    def __init__(self, array: npt.ArrayLike, parent=None):
        """
        Stores off container for later use; sets up the main panel display
        canvas for plotting into with matplotlib. Also prepares the interface
        for working with multi-dimensional data.
        """
        super().__init__(parent)

        logging.info("Image constructor.")
        self.data = array
        self.ndim = array.ndim
        self.current_indices = [slice(0,1) for _ in range(self.ndim)]

        # Main layout
        layout = QTW.QVBoxLayout(self)

        # Dimension controls; Add a widget with a horizontal layout
        cw = QTW.QWidget()
        layout.addWidget(cw)
        controls = QTW.QHBoxLayout(cw)
        controls.setContentsMargins(0,0,0,0)

        # Create a drop-down for the image instance
        self.dim_buttons = []
        self.selected = []
        self.dim_button_grp = QTW.QButtonGroup()
        self.dim_button_grp.setExclusive(True)
        for dim_i in range(self.ndim):
            self.dim_buttons.append(QTW.QPushButton(text=f'{self.data.shape[dim_i]}'))
            self.dim_buttons[dim_i].setCheckable(True)
            self.dim_button_grp.addButton(self.dim_buttons[dim_i], dim_i)
            controls.addWidget(self.dim_buttons[dim_i])
            self.selected.append(QTW.QSpinBox())
            self.selected[dim_i].setSpecialValueText(":")
            controls.addWidget(self.selected[dim_i])
            self.selected[dim_i].valueChanged.connect(self.update_image)

        self.update_indices()
        self.dim_buttons[0].setChecked(True)
        for dim_i in range(self.ndim):
            self.selected[dim_i].setMaximum(self.data.shape[dim_i]-1)
            self.selected[dim_i].setMinimum(-1)

        # TODO: We can disable widgets for singleton dimensions
        # TODO: Add buttons for flipping and rotating the image

        self.animate = QTW.QPushButton()
        self.animate.setCheckable(True)
        pixmapi = QTW.QStyle.StandardPixmap.SP_MediaPlay
        icon = self.style().standardIcon(pixmapi)
        self.animate.setIcon(icon)
        controls.addWidget(self.animate)

        # self.animDim = QTW.QComboBox()
        # for dim in DIMS:
        #     self.animDim.addItem(dim)
        # controls.addWidget(self.animDim)
        controls.addStretch()

        self.animate.clicked.connect(self.animate_frames)
        # self.animDim.currentIndexChanged.connect(self.check_dim)
        self.dim_button_grp.buttonClicked.connect(self.check_dim)

        # Window/level controls; Add a widget with a horizontal layout
        # NOTE: we re-use the local names from above...
        cw = QTW.QWidget()
        layout.addWidget(cw)
        controls = QTW.QHBoxLayout(cw)
        controls.setContentsMargins(0,0,0,0)

        self.windowScaled = QTW.QDoubleSpinBox()
        self.windowScaled.setRange(-2**31, 2**31 - 1)
        self.levelScaled = QTW.QDoubleSpinBox()
        self.levelScaled.setRange(-2**31, 2**31 - 1)
        controls.addWidget(QTW.QLabel("Window:"))
        controls.addWidget(self.windowScaled)
        controls.addWidget(QTW.QLabel("Level:"))
        controls.addWidget(self.levelScaled)
        controls.addStretch()

        self.frameRate = QTW.QDoubleSpinBox()
        self.frameRate.setRange(0.001, 1000)
        self.frameRate.setSuffix(' fps')
        self.frameRate.setValue(10)

        controls.addWidget(QTW.QLabel("Frame Rate:"))
        controls.addWidget(self.frameRate)

        self.frameRate.valueChanged.connect(self.set_timer_interval)

        self.windowScaled.valueChanged.connect(self.window_input)
        self.levelScaled.valueChanged.connect(self.level_input)

        layout.setContentsMargins(0,0,0,0)
        self.fig = Figure(figsize=(6,6),
                          dpi=72,
                          facecolor=(1,1,1),
                          edgecolor=(0,0,0),
                          layout='constrained')

        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.canvas.setSizePolicy(QTW.QSizePolicy.Expanding,
                                  QTW.QSizePolicy.Expanding)
        layout.addWidget(self.canvas)

        self.label_base = "A{:d}/S{:d}/C{:d}/P{:d}/R{:d}/S{:d}"
        self.label = QTW.QLabel("")
        self.label.setMaximumSize(140, 20)

        layout.addWidget(self.label)

        if self.data.shape[0] == 1:
            self.animate.setEnabled(False)

        # logging.info("Container size {}".format(str(self.stack.shape)))
        logging.info("Container size {}".format(str(self.image_shape())))

        # Window/Level support
        self.min = self.current_frame().min()
        self.max = self.current_frame().max()
        self.range = self.max - self.min

        v1 = np.percentile(self.current_frame(),2)
        v2 = np.percentile(self.current_frame(),98)
        self.window = (v2-v1)/self.range
        self.level = (v2+v1)/2/self.range

        self.mloc = None

        # For animation
        self.timer = None

        self.update_image()

        for (cont, var) in ((self.windowScaled, self.window),
                            (self.levelScaled, self.level)):
            cont.blockSignals(True)
            cont.setValue(var * self.range)
            cont.blockSignals(False)


    def image_shape(self):
        return self.data.shape
    
    def check_dim(self, v):
        "Disables animation checkbox for singleton dimensions"
        checkedId = self.dim_button_grp.checkedId()
        # self.animate.setEnabled(self.stack.shape[checkedId] > 1)
        self.animate.setEnabled(bool(self.image_shape()[checkedId] > 1))

    def update_wl(self):
        """
        When only window / level have changed, we don't need to call imshow
        again, just update clim.
        """
        rng = self.window_level()
        self.image.set_clim(*rng)        
        self.canvas.draw()

    def window_input(self, value, **kwargs):
        "Handles changes in window spinbox; scales to our [0..1] range"
        self.window = value / self.range 
        self.update_wl()

    def level_input(self, value):
        "Handles changes in level spinbox; scales to our [0..1] range"
        self.level = value / self.range 
        self.update_wl()

    def mouseMoveEvent(self, event):
        "Provides window/level mouse-drag behavior."
        newx = event.position().x()
        newy = event.position().y()
        if self.mloc is None:
            self.mloc = (newx, newy)
            return 
        
        # Modify mapping and polarity as desired
        self.window = self.window - (newx - self.mloc[0]) * 0.01
        self.level = self.level - (newy - self.mloc[1]) * 0.01

        # Don't invert
        if self.window < 0:
            self.window = 0.0
        if self.window > 2:
            self.window = 2.0

        if self.level < 0:
            self.level = 0.0
        if self.level > 1:
            self.level = 1.0

        # We update the displayed (scaled by self.range) values, but
        # we don't want extra update_image calls
        for (cont, var) in ((self.windowScaled, self.window),
                            (self.levelScaled, self.level)):
            cont.blockSignals(True)
            cont.setValue(var * self.range)
            cont.blockSignals(False)

        self.mloc = (newx, newy)
        self.update_wl()

    def mouseReleaseEvent(self, event):
        "Reset .mloc to indicate we are done with one click/drag operation"
        self.mloc = None

    def mouseDoubleClickEvent(self, event):
        v1 = np.percentile(self.current_frame(),2)
        v2 = np.percentile(self.current_frame(),98)
        self.window = (v2-v1)/self.range
        self.level = (v2+v1)/2/self.range
        self.update_wl()

        for (cont, var) in ((self.windowScaled, self.window),
                    (self.levelScaled, self.level)):
            cont.blockSignals(True)
            cont.setValue(var * self.range)
            cont.blockSignals(False)

    def wheelEvent(self, event):
        "Handle scroll event; could use some time-based limiting."
        dim_i = self.dim_button_grp.checkedId()
        control = self.selected[dim_i]

        num_pixels = event.pixelDelta()
        num_degrees = event.angleDelta() / 8
        delta_steps = 0
        if not num_pixels.isNull():
            delta_steps = num_pixels.y()
        elif not num_degrees.isNull():
            delta_steps = num_degrees.y() / 15

        if delta_steps > 0:
            new_v = control.value() - 1
        elif delta_steps < 0:
            new_v = control.value() + 1
        else:
            return
        control.setValue(max(min(new_v,self.image_shape()[self.dim_button_grp.checkedId()]-1),0))
        # control.setValue(max(min(new_v,self.stack.shape[self.dim_button_grp.checkedId()]-1),0))

    def contextMenuEvent(self, event):
    
        menu = QTW.QMenu(self)
        saveAction = menu.addAction("Save Frame")
        transposeAction = menu.addAction("Transpose")
        plotFrameAction = menu.addAction("Plot Frame")

        action = menu.exec(self.mapToGlobal(event.pos()))

        if action == saveAction:
            savefilepath = QTW.QFileDialog.getSaveFileName(self, "Save image as...", filter="Images (*.png, *.jpg, *.svg, *.eps, *.pdf);;MAT file (*.mat);;NPY file (*.npy)")
            print(savefilepath)
            sel_filter = savefilepath[1]
            if len(savefilepath[0]) != 0:
                if sel_filter == "Images (*.png, *.jpg, *.svg, *.eps, *.pdf)":
                    extent = self.ax.get_window_extent().transformed(self.fig.dpi_scale_trans.inverted())
                    self.fig.savefig(savefilepath[0], bbox_inches=extent)
                elif sel_filter == "MAT file (*.mat)":
                    spio.savemat(savefilepath[0], {'data': self.fetch_image(self.repetition(), self.set(), self.phase(), self.slice(), self.contrast())[self.frame()][self.coil()][0]})
                elif sel_filter == "NPY file (*.npy)":
                    np.save(savefilepath[0], self.fetch_image(self.repetition(), self.set(), self.phase(), self.slice(), self.contrast())[self.frame()][self.coil()][0])
                    
        elif action == transposeAction:
            self.transpose_image()

        elif action == plotFrameAction:
            wl = self.window_level()
            plt.figure()
            plt.imshow(self.current_frame(), 
                           vmin=wl[0],
                           vmax=wl[1],
                           cmap=plt.get_cmap('gray'))
            plt.axis('off')
            plt.title(f'Frame REP{self.repetition()}/SET{self.set()}/PHS{self.phase()}/SLC{self.slice()}/CH{self.coil()}')
            # self.canvas.draw()
            plt.draw()
            plt.show(block=False)

    def window_level(self):
        "Perform calculations of (min,max) display range from window/level"
        return (self.level * self.range 
                  - self.window / 2 * self.range + self.min, 
                self.level * self.range
                  + self.window / 2 * self.range + self.min)

        # return None

    def current_frame(self):
        return self.data[tuple(self.current_indices)].squeeze()
    
    def update_indices(self):
        for dim_i in range(self.ndim):
            if dim_i == self.selected_dims[0] or dim_i == self.selected_dims[1]:
                self.current_indices[dim_i] = slice(0,self.data.shape[dim_i])
                self.selected[dim_i].setValue(-1)
            else:
                self.current_indices[dim_i] = slice(self.selected[dim_i].value(), self.selected[dim_i].value()+1)
    
    def update_image(self):
        """
        Updates the displayed image when a set of indicies (frame/coil/slice)
        is selected. Connected to singals from the related spinboxes.
        """
        self.update_indices()
        wl = self.window_level()
        self.ax.clear()
        self.image = \
            self.ax.imshow(self.current_frame(), 
                            vmin=wl[0],
                            vmax=wl[1],
                            cmap=plt.get_cmap('gray'))
            # self.ax.imshow(self.stack[self.frame()][self.repetition()][self.set()][self.phase()][self.coil()][self.slice()], 
            #                vmin=wl[0],
            #                vmax=wl[1],
            #                cmap=plt.get_cmap('gray'))

        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.canvas.draw()

    def transpose_image(self):
        # TODO
        # self.stack = self.stack.swapaxes(-2,-1)
        self.update_image()

    def set_timer_interval(self, fps):
        self.timer_interval = 1e3/fps

    def animate_frames(self):
        """
        Animation is achieved via a timer that drives the selected animDim
        dimensions' spinbox.
        """
        if self.animate.isChecked() is False:
            if self.timer:
                self.timer.stop()
                self.timer = None
            
            pixmapi = QTW.QStyle.StandardPixmap.SP_MediaPlay
            icon = self.style().standardIcon(pixmapi)
            self.animate.setIcon(icon)
            return
        
        dim_i = self.dim_button_grp.checkedId()

        pixmapi = QTW.QStyle.StandardPixmap.SP_MediaPause
        icon = self.style().standardIcon(pixmapi)
        self.animate.setIcon(icon)

        if self.selected[dim_i].maximum() == 0:
            logging.warning("Cannot animate singleton dimension.")
            self.animate.setChecked(False)
            return

        def increment():
            v = self.selected[dim_i].value()
            m = self.selected[dim_i].maximum()
            self.selected[dim_i].setValue((v+1) % m)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(self.timer_interval)
        self.timer.timeout.connect(increment)
        self.timer.start()

