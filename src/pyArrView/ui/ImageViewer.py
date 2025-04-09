import logging
from typing import Literal
import numpy as np
import scipy.io as spio
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('QtAgg')

from PySide6 import QtCore, QtWidgets as QTW

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
# from matplotlib.backends.backend_qt5 import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib import animation
import numpy.typing as npt
from .DimensionSelector import DimensionSelector
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMainWindow
from PySide6.QtGui import QIcon
from .utils import complex2rgb

class ImageViewer(QTW.QWidget):

    timer_interval = 100 # [ms]
    dim_selector = None
    view_type: Literal['Magnitude', 'Real', 'Imag', 'Phase', 'Complex'] = 'Magnitude'
    cmap = 'gray'

    do_transpose = False
    do_vflip = False
    do_hflip = False
    nrot = 0

    wdw = 1.0
    level = 0.5

    def __init__(self, array: npt.ArrayLike, parent: QMainWindow):
        """
        Stores off container for later use; sets up the main panel display
        canvas for plotting into with matplotlib. Also prepares the interface
        for working with multi-dimensional data.
        """
        super().__init__(parent)

        logging.info("Image constructor.")
        self.data = array
        self.ndim = array.ndim

        # Connect parent signals
        parent.change_cmap.connect(self.change_cmap)
        parent.save_video.connect(self.save_movie)

        # Main layout
        layout = QTW.QVBoxLayout(self)

        # Dimension controls; Add a widget with a horizontal layout
        cw = QTW.QWidget()
        layout.addWidget(cw)
        controls = QTW.QHBoxLayout(cw)
        controls.setContentsMargins(0,0,0,0)

        # Create a drop-down for the image instance
        self.dim_selector = DimensionSelector(self.data.shape)
        self.dim_selector.indicesUpdatedSignal.connect(self.update_image)
        controls.addWidget(self.dim_selector)

        # TODO: We can disable widgets for singleton dimensions

        self.animate = QTW.QPushButton()
        self.animate.setCheckable(True)
        pixmapi = QTW.QStyle.StandardPixmap.SP_MediaPlay
        icon = self.style().standardIcon(pixmapi)
        self.animate.setIcon(icon)
        controls.addWidget(self.animate)

        controls.addStretch()

        self.animate.clicked.connect(self.animate_frames)

        # Window/level controls; Add a widget with a horizontal layout
        # NOTE: we re-use the local names from above...
        cw = QTW.QWidget()
        layout.addWidget(cw)
        controls = QTW.QHBoxLayout(cw)
        controls.setContentsMargins(0,0,0,0)

        # TODO: We don't have int32 anymore, scale can be estimated from the data itself.
        self.windowScaled = QTW.QDoubleSpinBox()
        self.windowScaled.setRange(-2**31, 2**31 - 1)
        self.levelScaled = QTW.QDoubleSpinBox()
        self.levelScaled.setRange(-2**31, 2**31 - 1)
        self.windowScaled.valueChanged.connect(self.window_input)
        self.levelScaled.valueChanged.connect(self.level_input)
        controls.addWidget(QTW.QLabel("Window:"))
        controls.addWidget(self.windowScaled)
        controls.addWidget(QTW.QLabel("Level:"))
        controls.addWidget(self.levelScaled)
        controls.addStretch()

        # Frame rate controls.
        self.frameRate = QTW.QDoubleSpinBox()
        self.frameRate.setRange(0.001, 1000)
        self.frameRate.setSuffix(' fps')
        self.frameRate.setValue(10)
        self.frameRate.valueChanged.connect(self.set_timer_interval)

        controls.addWidget(QTW.QLabel("Frame Rate:"))
        controls.addWidget(self.frameRate)


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
        # layout.addWidget(NavigationToolbar(self.canvas, self)) # TODO: This toolbar provides nice features, but coincides with contrast adjustments  mouse drag. Can be activated if fixed.

        self.label_base = "A{:d}/S{:d}/C{:d}/P{:d}/R{:d}/S{:d}"
        self.label = QTW.QLabel("")
        self.label.setMaximumSize(140, 20)

        layout.addWidget(self.label)

        if self.data.shape[0] == 1:
            self.animate.setEnabled(False)

        # Image view mode: Magnitude, Real, Imaginary, Phase, Complex
        self.viewmode_box = QTW.QComboBox()
        if np.iscomplexobj(array):
            self.viewmode_box.addItems(['Complex', 'Magnitude', 'Phase', 'Real', 'Imag'])
            self.viewmode_box.setCurrentText('Magnitude')
        else:
            self.viewmode_box.addItems(['Real', 'Magnitude'])
            self.viewmode_box.setCurrentText('Real')

        self.viewmode_box.currentTextChanged.connect(self.update_image)
        controls.addWidget(self.viewmode_box)

        # Add quick operations
        # TODO: What if we don't have these icons on the system? Need local fallback icons. Maybe from arrShow project?
        icon_rot_ccw = QIcon.fromTheme("object-rotate-left")
        icon_rot_cw = QIcon.fromTheme("object-rotate-right")
        icon_flip_h = QIcon.fromTheme("object-flip-horizontal")
        icon_flip_v = QIcon.fromTheme("object-flip-vertical")

        self.transpose_btn = QTW.QPushButton(".T")
        self.transpose_btn.setCheckable(True)
        self.transpose_btn.clicked.connect(self.update_image)
        self.transpose_btn.setToolTip("Transpose")
        controls.addWidget(self.transpose_btn)
        self.fliph_btn = QTW.QPushButton()
        self.fliph_btn.setIcon(icon_flip_h)
        self.fliph_btn.setCheckable(True)
        self.fliph_btn.clicked.connect(self.update_image)
        self.fliph_btn.setToolTip("Flip Horizontally")
        controls.addWidget(self.fliph_btn)
        self.flipv_btn = QTW.QPushButton()
        self.flipv_btn.setIcon(icon_flip_v)
        self.flipv_btn.setCheckable(True)
        self.flipv_btn.clicked.connect(self.update_image)
        self.flipv_btn.setToolTip("Flip Vertically")
        controls.addWidget(self.flipv_btn)

        self.rot_cw_btn = QTW.QPushButton()
        self.rot_cw_btn.setIcon(icon_rot_cw)
        self.rot_cw_btn.clicked.connect(self.rot_img_cw)
        self.rot_cw_btn.setToolTip("Rotate Clockwise")
        controls.addWidget(self.rot_cw_btn)
        self.rot_ccw_btn = QTW.QPushButton()
        self.rot_ccw_btn.setIcon(icon_rot_ccw)
        self.rot_ccw_btn.clicked.connect(self.rot_img_ccw)
        self.rot_ccw_btn.setToolTip("Rotate Counter-Clockwise")
        controls.addWidget(self.rot_ccw_btn)

        logging.info("Container size {}".format(str(self.image_shape())))

        # Window/Level support
        self.auto_level()

        self.mloc = None

        # For animation
        self.timer = None

        self.update_image()

        for (cont, var) in ((self.windowScaled, self.wdw),
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

    def rot_img_cw(self):
        self.nrot -= 1
        self.update_image()
    def rot_img_ccw(self):
        self.nrot += 1
        self.update_image()

    
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
        self.wdw = value / self.range 
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
        self.wdw = self.wdw - (newx - self.mloc[0]) * 0.01
        self.level = self.level - (newy - self.mloc[1]) * 0.01

        # Don't invert
        if self.wdw < 0:
            self.wdw = 0.0
        if self.wdw > 2:
            self.wdw = 2.0

        if self.level < 0:
            self.level = 0.0
        if self.level > 1:
            self.level = 1.0

        # We update the displayed (scaled by self.range) values, but
        # we don't want extra update_image calls
        for (cont, var) in ((self.windowScaled, self.wdw),
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
        cimg = self.prep_image_to_display()
        v1 = np.percentile(cimg,2)
        v2 = np.percentile(cimg,98)
        self.wdw = (v2-v1)/self.range
        self.level = (v2+v1)/2/self.range
        self.update_wl()

        for (cont, var) in ((self.windowScaled, self.wdw),
                    (self.levelScaled, self.level)):
            cont.blockSignals(True)
            cont.setValue(var * self.range)
            cont.blockSignals(False)

    def wheelEvent(self, event):
        "Handle scroll event; could use some time-based limiting."
        dim_i = self.dim_selector.dynamic_dimension()
        control = self.dim_selector.dim_spinboxes[dim_i]

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
        control.setValue(max(min(new_v,self.image_shape()[dim_i]-1),0))

    def contextMenuEvent(self, event):
    
        menu = QTW.QMenu(self)
        saveAction = menu.addAction("Save Frame")
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
                    spio.savemat(savefilepath[0], {'data': self.current_frame()})
                elif sel_filter == "NPY file (*.npy)":
                    np.save(savefilepath[0], self.current_frame())
                    

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

    def auto_level(self, v1=2, v2=98):
        cimg = self.prep_image_to_display()

        self.min = cimg.min()
        self.max = cimg.max()
        self.range = self.max - self.min
        
        v1 = np.percentile(cimg,v1)
        v2 = np.percentile(cimg,v2)
        self.wdw = (v2-v1)/self.range
        self.level = (v2+v1)/2/self.range

    def window_level(self):
        "Perform calculations of (min,max) display range from window/level"
        return (self.level * self.range 
                  - self.wdw / 2 * self.range + self.min, 
                self.level * self.range
                  + self.wdw / 2 * self.range + self.min)

        # return None

    def current_frame(self):
        return self.data[self.dim_selector.get_current_slices()].squeeze()
    
    def prep_image_to_display(self, cimg=None):
        """
        Prepares the image to be displayed by applying the selected view type
        and any transformations (transpose, flip, rotate).
        """
        if cimg is None:
            cimg = self.current_frame()
        
        view_type = self.viewmode_box.currentText()
        if view_type == 'Magnitude':
            cimg = np.abs(cimg)
        elif view_type == 'Real':
            cimg = np.real(cimg)
        elif view_type == 'Imag':
            cimg = np.imag(cimg)
        elif view_type == 'Phase':
            cimg = np.angle(cimg)
        elif view_type == 'Complex':
            cimg, _ = complex2rgb(cimg, clim=self.window_level())
    
        if self.transpose_btn.isChecked():
            cimg = cimg.T
        if self.flipv_btn.isChecked():
            cimg = np.flipud(cimg)
        if self.fliph_btn.isChecked():
            cimg = np.fliplr(cimg)
        if self.nrot != 0:
            cimg = np.rot90(cimg, self.nrot, axes=(0,1))

        return cimg
    
    @Slot(str)
    def change_cmap(self, cmap):
        self.cmap = cmap
        self.update_image()

    @Slot()
    def update_image(self):
        """
        Updates the displayed image when a set of indicies (frame/coil/slice)
        is selected. Connected to singals from the related spinboxes.
        """
        # TODO: Add support for third dimension with montage.
        # TODO: Add support for image modifiers (transpose, flip, rotate, fft, etc.)
        # TODO: Add support for 1D plots.
        # TODO: Add support for ROI selection.
        cframe = self.prep_image_to_display()
        wl = self.window_level()
        self.ax.clear()
        self.image = \
            self.ax.imshow(cframe, 
                            vmin=wl[0],
                            vmax=wl[1],
                            cmap=self.cmap)

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
        
        dim_i = self.dim_selector.dynamic_dimension()

        pixmapi = QTW.QStyle.StandardPixmap.SP_MediaPause
        icon = self.style().standardIcon(pixmapi)
        self.animate.setIcon(icon)

        if self.dim_selector.dim_spinboxes[dim_i].maximum() == 0:
            logging.warning("Cannot animate singleton dimension.")
            self.animate.setChecked(False)
            return

        def increment():
            v = self.dim_selector.dim_spinboxes[dim_i].value()
            m = self.dim_selector.dim_spinboxes[dim_i].maximum()
            self.dim_selector.dim_spinboxes[dim_i].setValue((v+1) % m)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(self.timer_interval)
        self.timer.timeout.connect(increment)
        self.timer.start()

    @Slot()
    def save_movie(self):
        dim_i = self.dim_selector.dynamic_dimension()
        framerate = self.frameRate.value()

        # Open a save file dialog to ask for the filename
        options = QTW.QFileDialog.Options()
        options |= QTW.QFileDialog.DontUseNativeDialog
        movie_filename, _ = QTW.QFileDialog.getSaveFileName(
            self,
            "Save Movie As...",
            f"movie_{dim_i}_{framerate}fps.mp4",
            "MP4 Files (*.mp4);;All Files (*)",
            options=options
        )

        if not movie_filename:
            logging.info("Save movie operation canceled.")
            return

        logging.info(f"Saving the movie from dim {dim_i} with frame rate {framerate} fps as the filename {movie_filename}")

        fig = plt.figure(frameon=False)
        w,h = self.current_frame().shape[0:2]
        dpi = 96
        w /= dpi
        h /= dpi
        fig.set_dpi(dpi)
        fig.set_size_inches(w,h)
        ax = plt.Axes(fig, [0., 0., 1., 1.])
        ax.set_axis_off()
        fig.add_axes(ax)
        im_ax = []

        n_frames = self.dim_selector.dim_spinboxes[dim_i].maximum()
        self.data[self.dim_selector.get_current_slices()].squeeze()
        slcs = self.dim_selector.get_current_slices()
        for ii in range(n_frames):
            slcs_ = (*slcs[:dim_i], slice(ii, ii+1), *slcs[dim_i+1:])
            im_ = self.data[slcs_].squeeze()
            im_ = self.prep_image_to_display(im_)
            ima_ = ax.imshow(im_, cmap='gray', animated=True, vmin=self.window_level()[0], vmax=self.window_level()[1], aspect='equal')
            im_ax.append([ima_])

        ani = animation.ArtistAnimation(fig, im_ax, interval=1e3/framerate, blit=True)
        MWriter = animation.FFMpegWriter(fps=framerate)
        ani.save(movie_filename, writer=MWriter)
        logging.info(f"Movie saved as {movie_filename}")