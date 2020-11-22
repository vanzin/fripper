# SPDX-License-Identifier: BSD-2-Clause
import tempfile
import threading
import time
from dataclasses import dataclass

import cdinfo
import util
from PyQt5.QtCore import QThread
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QDialog

EXT = "mp3"


@dataclass
class Config:
    target: str = None
    encoder: str = None
    template: str = None


class RipperDialog(util.compile_ui("ripper.ui")):
    def __init__(self, disc, config, workdir):
        super().__init__()
        self.disc = disc

        count = len(disc.tracks)
        self.pbEncoder.setMinimum(0)
        self.pbEncoder.setMaximum(count)
        self._set_progress(self.lEncoderCompleted, 0)

        self.pbRipper.setMinimum(0)
        self.pbRipper.setMaximum(len(disc.tracks))
        self._set_progress(self.lRipperCompleted, 0)

        self.btnCancel.clicked.connect(self._cancel)

        self.rip_thread = RipperThread(disc, config, workdir, self)
        self.rip_thread.progress.connect(self._rip_progress)

        self.encoder_thread = EncodeThread(disc, config, workdir, self)
        self.encoder_thread.progress.connect(self._encode_progress)
        self.rip_thread.progress.connect(self.encoder_thread.enqueue)

        self.rip_done = 0
        self.encode_done = 0

        self.rip_thread.start()
        self.encoder_thread.start()

        self.encoded = []

    def _completed(self, done, target):
        return f"{done}/{target}"

    def _cancel(self):
        # TODO
        self.reject()

    def _set_progress(self, label, done):
        target = len(self.disc.tracks)
        label.setText(f"{done}/{target}")

    def _rip_progress(self, fname):
        self.rip_done += 1
        self.pbRipper.setValue(self.rip_done)
        self._set_progress(self.lRipperCompleted, self.rip_done)

    def _encode_progress(self, fname):
        self.encode_done += 1
        self.pbEncoder.setValue(self.encode_done)
        self._set_progress(self.lEncoderCompleted, self.encode_done)

        self.encoded.append(fname)
        if self.encode_done == len(self.disc.tracks):
            self.accept()


class RipperThread(QThread):
    progress = pyqtSignal(str)

    def __init__(self, disc, config, workdir, ripper):
        QThread.__init__(self)
        self.disc = disc
        self.config = config
        self.workdir = workdir
        self.ripper = ripper

    def run(self):
        for t in self.disc.tracks:
            time.sleep(1)
            target = f"track{t.trackno}.wav"
            self.progress.emit(target)


class EncodeThread(QThread):
    progress = pyqtSignal(str)

    def __init__(self, disc, config, workdir, ripper):
        QThread.__init__(self)
        self.disc = disc
        self.config = config
        self.workdir = workdir
        self.ripper = ripper

        self.queue = []
        self.lock = threading.Lock()
        self.event = threading.Event()

    def run(self):
        done = 0
        while done < len(self.disc.tracks):
            self.event.wait()
            with self.lock:
                next = self.queue[0]
                del self.queue[0]
                self.event.clear()

            time.sleep(1)
            target = f"{next}.{EXT}"
            # TODO: encode / tag next
            self.progress.emit(target)

    def enqueue(self, next):
        with self.lock:
            self.queue.append(next)
            self.event.set()


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

    with tempfile.TemporaryDirectory() as workdir:
        ripper = RipperDialog(disc, config, workdir)
        ripper.exec_()

        # TODO: move encoded files to destination
        print("TODO: commit output")

    app.quit()
