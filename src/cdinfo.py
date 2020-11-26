# SPDX-License-Identifier: BSD-2-Clause
import os

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
    track,
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
        "trackno": track.trackno,
        "input": inf,
        "output": outf,
        "ext": ext,
    }


def dest_fmt_variables(disc, track, ext):
    """
    Returns a map with variables for substitution in destination path templates.
    """
    trackno = track.trackno
    if len(disc.tracks) >= 10:
        trackno = f"{track.trackno:02}"

    return {
        "artist": disc.artist,
        "album": disc.album,
        "discno": disc.discno,
        "trackno": trackno,
        "track": track.title,
        "ext": ext,
    }


class CoverLabel(QLabel):
    def __init__(self, parent, cover):
        super().__init__(parent)
        self.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.setText("Drop a cover...")
        self.setAcceptDrops(True)
        self.cover_data = cover
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
            self.cover_data = util.http_get(url.toString())
            self._set_cover()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error downloading {url}: {e}.")

    def _set_cover(self):
        if not self.cover_data:
            return

        self.cover = QPixmap()
        self.cover.loadFromData(self.cover_data)

        size = self.cover.size()
        self.setToolTip(f"{size.width()}px x {size.height()}px")
        self._scale_cover()

    def _scale_cover(self):
        if not self.cover:
            return

        h = self.height()
        w = self.width()
        scaled = self.cover.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(scaled)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._scale_cover()

    def from_file(self, path):
        self.cover_data = open(path, "rb").read()
        self._set_cover()


class InfoDialog(util.compile_ui("cdinfo.ui")):
    def __init__(self, disc, config):
        super().__init__()
        self.setWindowModality(Qt.ApplicationModal)

        self.disc = disc
        self.config = config

        vbox = QVBoxLayout()
        self.fCover.setLayout(vbox)

        self.lblCover = CoverLabel(self, disc.cover_art)
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

        cmd_vars = cmd_fmt_variables(
            self.disc.tracks[0], "workdir", "input", "output", "ext"
        )
        try:
            self.leEncoder.text().format(**cmd_vars)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Invalid encoder command: {e}")
            return

        dest_vars = dest_fmt_variables(self.disc, self.disc.tracks[0], "ext")
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
