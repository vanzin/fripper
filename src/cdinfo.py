# SPDX-License-Identifier: BSD-2-Clause
import util
from PyQt5.QtCore import Qt


class InfoDialog(util.compile_ui("cdinfo.ui")):
    def __init__(self, disc):
        super().__init__()
        self.setWindowModality(Qt.ApplicationModal)

        self.disc = disc

        self.btnGo.clicked.connect(self._go)
        self.btnCancel.clicked.connect(self.reject)

    def _go(self):
        # TODO
        self.accept()
