# SPDX-License-Identifier: BSD-2-Clause
import os

import cdio
import pycdio
import requests
from PyQt5 import uic
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

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
    QApplication.instance().show_error(message)


def print_error():
    import traceback

    traceback.print_exc()


def http_get(url):
    res = requests.get(url)
    res.raise_for_status()
    return res.content


def eject():
    try:
        d = cdio.Device(driver_id=pycdio.DRIVER_UNKNOWN)
        d.eject_media()
    except:
        print_error()
