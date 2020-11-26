# SPDX-License-Identifier: BSD-2-Clause
import os

import requests
import util
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QVBoxLayout


def cmd_fmt_variables(
    workdir,
    inf,
    outf,
    ext,
):
    """
    Returns a map with variables for substitution in command templates.
    """
    if inf:
        inf = os.path.join(workdir, inf)
    if outf:
        outf = os.path.join(workdir, outf)

    return {
        "input": inf,
        "output": outf,
        "ext": ext,
    }


def dest_fmt_variables(
    artist,
    album,
    discno,
    trackno,
    track,
    ext,
):
    """
    Returns a map with variables for substitution in destination path templates.
    """
    return {
        "artist": artist,
        "album": album,
        "discno": discno,
        "trackno": trackno,
        "track": track,
        "ext": ext,
    }


class CoverLabel(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.setText("Drop a cover...")
        self.setAcceptDrops(True)
        self.cover_data = None
        self.cover = None
        self._set_cover()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        url = event.mimeData().urls()[0]

        if url.scheme() == "file":
            self.from_file(url.path())
            return

        try:
            res = requests.get(url.toString())
            res.raise_for_status()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error downloading {url}: {e}.")
            return

        self.cover_data = res.content
        self.cover = QPixmap()
        self.cover.loadFromData(self.cover_data)
        self._set_cover()

    def _set_cover(self):
        if not self.cover:
            return

        self.setText("")
        h = self.height()
        w = self.width()
        scaled = self.cover.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(scaled)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._set_cover()

    def from_file(self, path):
        self.cover_data = open(path, "rb").read()
        self.cover = QPixmap()
        self.cover.load(path)
        self._set_cover()


class InfoDialog(util.compile_ui("cdinfo.ui")):
    def __init__(self, disc, config):
        super().__init__()
        self.setWindowModality(Qt.ApplicationModal)

        self.disc = disc
        self.config = config

        vbox = QVBoxLayout()
        self.fCover.setLayout(vbox)

        self.lblCover = CoverLabel(self)
        vbox.addWidget(self.lblCover)
        vbox.setStretch(0, 1)

        btnCover = QPushButton(self)
        btnCover.setText("Open...")
        vbox.addWidget(btnCover)
        btnCover.clicked.connect(self._open_cover)

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

        increment = 1
        self.artists = None
        if disc.multi_artist:
            self.artists = []
            increment = 2

        self.trackNames = []
        for t in disc.tracks:
            idx = t.trackno * increment + 2
            if disc.multi_artist:
                lbl = QLabel(self)
                lbl.setText(f"Artist {t.trackno}")
                le = QLineEdit(self)
                le.setText(t.artist)

                self.infoPane.addWidget(lbl, idx, 0)
                self.infoPane.addWidget(le, idx, 1, 1, 3)
                self.artists.append(le)
                idx += 1

            lbl = QLabel(self)
            lbl.setText(f"Track {t.trackno}")

            le = QLineEdit(self)
            le.setText(t.title)

            self.infoPane.addWidget(lbl, idx, 0)
            self.infoPane.addWidget(le, idx, 1, 1, 3)
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

        cmd_vars = cmd_fmt_variables("workdir", "input", "output", "ext")
        try:
            self.leEncoder.text().format(**cmd_vars)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Invalid encoder command: {e}")
            return

        dest_vars = dest_fmt_variables("artist", "album", 1, 1, "track", "ext")
        try:
            self.leTemplate.text().format(**dest_vars)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Invalid file name template: {e}")
            return

        d = self.disc
        d.artist = self.leArtist.text()
        d.album = self.leAlbum.text()
        d.year = int(self.leYear.text())
        d.cover_art = self.lblCover.cover_data

        if d.multi_artist:
            for i in range(len(d.tracks)):
                d.tracks[i].artist = self.artists[i].text()

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

    def _open_cover(self):
        path, _ = QFileDialog.getOpenFileName(self)
        if path:
            self.lblCover.from_file(path)
