# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import dataclass

import cdinfo
import util
from PyQt5.QtWidgets import QDialog


@dataclass
class Config:
    target: str = None
    encoder: str = None
    template: str = None


def rip(app, disc):
    config = Config(
        target=util.SETTINGS.value("fripper/target"),
        encoder=util.SETTINGS.value("fripper/encoder"),
        template=util.SETTINGS.value("fripper/template"),
    )

    info = cdinfo.InfoDialog(disc, config)
    if info.exec_() == QDialog.Rejected:
        app.quit()
        return

    util.SETTINGS.setValue("fripper/target", config.target)
    util.SETTINGS.setValue("fripper/encoder", config.encoder)
    util.SETTINGS.setValue("fripper/template", config.template)

    print("TODO: rip it")
    app.quit()
