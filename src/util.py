# SPDX-License-Identifier: BSD-2-Clause
import os

from PyQt5 import uic
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QMessageBox

SETTINGS = QSettings("vanzin.org", "fripper")
TEST_MODE = False


def icon(name):
    return os.path.join(os.path.dirname(__file__), "icons", name)


def compile_ui(src):
    path = os.path.join(os.path.dirname(__file__), "ui", src)
    form, qtclass = uic.loadUiType(path)

    class _WidgetBase(form, qtclass):
        def __init__(self, parent=None):
            qtclass.__init__(self, parent)
            form.__init__(self)
            self.setupUi(self)

    return _WidgetBase


def restore_ui(widget, name):
    data = SETTINGS.value(f"{name}/geometry")
    if data:
        widget.restoreGeometry(data)

    data = SETTINGS.value(f"{name}/windowState")
    if data:
        widget.restoreState(data)


def save_ui(widget, name):
    SETTINGS.setValue(f"{name}/geometry", widget.saveGeometry())
    if hasattr(widget, "saveState"):
        SETTINGS.setValue(f"{name}/windowState", widget.saveState())


def show_error(e, message=None):
    print_error()
    msg = str(e)
    if message:
        msg = f"{message}\n{e}"
    QMessageBox.critical(None, "Error", msg)


def print_error():
    import traceback

    traceback.print_exc()
