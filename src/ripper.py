# SPDX-License-Identifier: BSD-2-Clause
import cdinfo
from PyQt5.QtWidgets import QDialog


def rip(app, disc):
    info = cdinfo.InfoDialog(disc)
    if info.exec_() == QDialog.Rejected:
        app.quit()
        return

    print("TODO: rip it")
    app.quit()
