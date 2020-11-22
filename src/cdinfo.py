# SPDX-License-Identifier: BSD-2-Clause
import util
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QMessageBox


class InfoDialog(util.compile_ui("cdinfo.ui")):
    def __init__(self, disc, config):
        super().__init__()
        self.setWindowModality(Qt.ApplicationModal)

        self.disc = disc
        self.config = config

        self.btnGo.clicked.connect(self._go)
        self.btnCancel.clicked.connect(self.reject)
        self.btnTarget.clicked.connect(self._get_target)

        self.leArtist.setText(disc.artist)
        self.leAlbum.setText(disc.album)
        self.leYear.setText(str(disc.year))
        self.leDisc.setText(str(disc.discno))

        self.cbMultiDisc.setVisible(disc.discs > 1)
        self.cbMultiDisc.setChecked(disc.discs > 1)

        self.leTarget.setText(config.target)
        self.leEncoder.setText(config.encoder)
        self.leTemplate.setText(config.template)

        self.trackNames = []
        for t in disc.tracks:
            lbl = QLabel(self)
            lbl.setText(f"Track {t.trackno}")

            le = QLineEdit(self)
            le.setText(t.title)

            self.infoPane.addWidget(lbl, t.trackno + 2, 0)
            self.infoPane.addWidget(le, t.trackno + 2, 1, 1, 3)
            self.trackNames.append(le)

        util.restore_ui(self, "cdinfo")

    @property
    def rip_as_multi_disc(self):
        return self.cbMultiDisc.isChecked()

    def _go(self):
        util.save_ui(self, "cdinfo")

        config = {
            "Target directory": self.leTarget,
            "Encoder": self.leEncoder,
            "Template": self.leTemplate,
        }
        for k, v in config.items():
            if not v.text():
                QMessageBox.critical(self, "Error", f"{k} is required.")
                return

        d = self.disc
        d.artist = self.leArtist.text()
        d.album = self.leAlbum.text()
        d.year = int(self.leYear.text())

        for i in range(len(d.tracks)):
            d.tracks[i].title = self.trackNames[i].text()

        self.config.target = self.leTarget.text()
        self.config.encoder = self.leEncoder.text()
        self.config.template = self.leTemplate.text()
        self.accept()

    def _get_target(self):
        path = QFileDialog.getExistingDirectory(self)
        if path:
            self.leTarget.setText(path)
