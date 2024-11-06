#!/usr/bin/env python
from PySide6 import QtCore
import pyArrView.ui as ui
import sys
import logging
import numpy.typing as npt
import numpy as np

from PySide6 import QtWidgets

_cache = []
def av(array: npt.ArrayLike, title: str = "pyArrView"):
    logging.basicConfig(
        format='[%(levelname)s] %(message)s',
        level='INFO'
    )

    if QtWidgets.QApplication.instance() is None:
        _cache.append(QtWidgets.QApplication(sys.argv))

    main = ui.MainWindow(array)
    main.setWindowTitle(title)
    main.setAttribute(QtCore.Qt.WA_DeleteOnClose)
    main.destroyed.connect(lambda: _cache.remove(main))
    _cache.append(main)
    main.resize(800, 600)
    main.show()


if __name__ == '__main__':
    input = np.random.rand(10, 10, 10, 10, 10)
    av(input)