# SPDX-License-Identifier: BSD-2-Clause
import util


class InfoDialog(util.compile_ui("cdinfo.ui")):
    def __init__(self, disc):
        super().__init__()
        self.disc = disc

        self.btnCancel.clicked.connect(self.close)
