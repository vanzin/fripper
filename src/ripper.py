# SPDX-License-Identifier: BSD-2-Clause
import os
import shlex
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass

import cdinfo
import util
from PyQt5.QtCore import QThread
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QMessageBox

EXT = "mp3"


@dataclass
class Config:
    target: str = None
    encoder: str = None
    template: str = None


class RipperDialog(util.compile_ui("ripper.ui")):
    error = pyqtSignal(str)

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
        self.rip_thread.finished.connect(self._child_done)
        self.rip_thread.output.connect(lambda l: self._output(self.tbRipper, l))

        self.encoder_thread = EncodeThread(disc, config, workdir, self)
        self.encoder_thread.progress.connect(self._encode_progress)
        self.encoder_thread.finished.connect(self._child_done)
        self.rip_thread.progress.connect(self.encoder_thread.enqueue)

        self._done = 0
        self.errors = []
        self.error.connect(self._error)

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

    def _error(self, msg):
        self.errors.append(msg)

    def _child_done(self):
        self._done += 1
        if self._done != 2:
            return

        if not self.errors:
            self.accept()
            return

        errs = ["Errors occurred during ripping / encoding:"] + self.errors
        msg = "\n".join(errs)
        QMessageBox.critical(self, "Error", msg)
        self.reject()

    def _output(self, tbox, line):
        tbox.appendPlainText(line)


class TaskThread(QThread):
    progress = pyqtSignal(str)
    output = pyqtSignal(str)

    def __init__(self, disc, config, workdir, ripper):
        QThread.__init__(self)
        self.disc = disc
        self.config = config
        self.workdir = workdir
        self.ripper = ripper
        self.proc = None

    def _exec(self, track, cmd, inf, outf):
        if inf:
            inf = os.path.join(self.workdir, inf)
        if outf:
            outf = os.path.join(self.workdir, outf)

        variables = {
            "artist": self.disc.artist,
            "album": self.disc.album,
            "discno": self.disc.discno,
            "trackno": track.trackno,
            "track": track.title,
            "input": inf,
            "output": outf,
            "ext": EXT,
        }
        cmd = shlex.split(cmd)
        for i in range(len(cmd)):
            cmd[i] = cmd[i].format(**variables)
        print(f"exec {cmd}")

        try:
            self.proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8"
            )

            for line in self.proc.stdout:
                self.output.emit(line)

            ec = self.proc.wait()
            if ec != 0:
                raise Exception(f"process {cmd[0]} exited with {ec}")

            self.proc = None
        except Exception as e:
            self.ripper.error.emit(str(e))


class RipperThread(TaskThread):
    def run(self):
        for t in self.disc.tracks:
            time.sleep(1)
            target = f"track{t.trackno}.wav"
            self._exec(t, "echo {track}", None, target)
            self.progress.emit(target)


class EncodeThread(TaskThread):
    def __init__(self, disc, config, workdir, ripper):
        super().__init__(disc, config, workdir, ripper)
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
            done += 1

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
