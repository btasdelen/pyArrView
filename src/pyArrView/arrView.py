#!/usr/bin/env python
import sys
import logging
import numpy.typing as npt
import numpy as np
import multiprocessing as mp
import atexit
from queue import Empty

# Global process and queue
_qt_process = None
_command_queue = None

def _qt_process_main(command_queue):
    """Main function for the Qt process."""
    from PySide6.QtCore import Qt, QTimer
    from PySide6 import QtWidgets
    import pyArrView.ui as ui
    
    # Create Qt application in this process's main thread
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    windows = []
    
    def check_commands():
        """Check for new window creation commands."""
        try:
            while True:
                cmd = command_queue.get_nowait()
                if cmd is None:  # Shutdown signal
                    # Close all windows first
                    for w in windows[:]:
                        w.close()
                    # Quit the application
                    app.quit()
                    return
                
                cmd_type, array, title = cmd
                if cmd_type == 'create':
                    main = ui.MainWindow(array)
                    main.setWindowTitle(title)
                    main.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                    main.destroyed.connect(lambda w=main: windows.remove(w) if w in windows else None)
                    windows.append(main)
                    main.resize(800, 600)
                    main.show()
                    main.raise_()
                    main.activateWindow()
        except Empty:
            pass
    
    # Check for commands periodically
    timer = QTimer()
    timer.timeout.connect(check_commands)
    timer.start(10)  # Check every 10ms for faster response
    
    # Run the Qt event loop
    sys.exit(app.exec())

def _ensure_qt_process():
    """Ensure the Qt process is running."""
    global _qt_process, _command_queue
    
    if _qt_process is None or not _qt_process.is_alive():
        _command_queue = mp.Queue()
        _qt_process = mp.Process(target=_qt_process_main, args=(_command_queue,), daemon=True)
        _qt_process.start()

def _cleanup():
    """Clean up Qt process on exit."""
    global _qt_process, _command_queue
    
    # Since the process is daemon, it will be killed when main exits
    # Just try to send shutdown signal but don't wait
    if _qt_process is not None and _qt_process.is_alive():
        try:
            _command_queue.put(None, block=False)
        except Exception:
            pass

atexit.register(_cleanup)

def av(array: npt.ArrayLike, title: str = "pyArrView"):
    """
    Create a new pyArrView window in a non-blocking way.
    Multiple windows can be created by calling this function multiple times.
    
    Args:
        array: N-dimensional array to visualize
        title: Window title
    """
    logging.basicConfig(
        format='[%(levelname)s] %(message)s',
        level='INFO'
    )

    _ensure_qt_process()
    
    # Convert to numpy array if needed
    array = np.asarray(array)
    
    # Send command to create window in Qt process (array will be pickled)
    _command_queue.put(('create', array, title))


if __name__ == '__main__':
    input = np.random.rand(10, 10, 10, 10, 10)
    av(input)