# SPDX-License-Identifier: BSD-2-Clause
import os

from PyQt5 import uic
from PyQt5.QtCore import QSettings

SETTINGS = QSettings("vanzin.org", "fripper")


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
