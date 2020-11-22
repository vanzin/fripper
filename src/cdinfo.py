# SPDX-License-Identifier: BSD-2-Clause
import util
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QLineEdit


class InfoDialog(util.compile_ui("cdinfo.ui")):
    def __init__(self, disc):
        super().__init__()
        self.setWindowModality(Qt.ApplicationModal)

        self.disc = disc

        self.btnGo.clicked.connect(self._go)
        self.btnCancel.clicked.connect(self.reject)

        self.leArtist.setText(disc.artist)
        self.leAlbum.setText(disc.album)
        self.leYear.setText(str(disc.year))
        self.leDisc.setText(str(disc.discno))

        self.cbMultiDisc.setVisible(disc.discs > 1)
        self.cbMultiDisc.setChecked(disc.discs > 1)

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

        d = self.disc
        d.artist = self.leArtist.text()
        d.album = self.leAlbum.text()
        d.year = int(self.leYear.text())

        for i in range(len(d.tracks)):
            d.tracks[i].title = self.trackNames[i].text()

        self.accept()
