# SPDX-License-Identifier: BSD-2-Clause
import sys
import traceback

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QMessageBox


class FRipper(QApplication):
    error = pyqtSignal(str)

    def __init__(self, argv):
        super().__init__(argv)
        self.error.connect(self._show_error)

    def show_error(self, message):
        _, e, _ = sys.exc_info()
        traceback.print_exc()

        msg = str(e)
        if message:
            msg = f"{message}\n{e}"

        self.error.emit(msg)

    def _show_error(self, msg):
        QMessageBox.critical(None, "Error", msg)
