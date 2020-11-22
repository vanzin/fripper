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


class RipperDialog(util.compile_ui("ripper.ui")):
    def __init__(self, disc, config):
        super().__init__()

        count = len(disc.tracks)
        self.pbEncoder.setMinimum(0)
        self.pbEncoder.setMaximum(count)
        self.lEncoderCompleted.setText(self._completed(0, count))

        self.pbRipper.setMinimum(0)
        self.pbRipper.setMaximum(len(disc.tracks))
        self.lRipperCompleted.setText(self._completed(0, count))

        self.btnCancel.clicked.connect(self._cancel)

    def _completed(self, done, target):
        return f"{done}/{target}"

    def _cancel(self):
        # TODO
        self.reject()


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

    ripper = RipperDialog(disc, config)
    ripper.exec_()

    print("TODO: rip it")
    app.quit()
