# SPDX-License-Identifier: BSD-2-Clause
import os
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass

import cdinfo
import util
from PyQt5.QtCore import QThread
from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QMessageBox
from mutagen import id3
from mutagen.mp3 import MP3

CDPARANOIA_CMD = "cdparanoia --abort-on-skip --never-skip=10 {trackno} {output}"
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
        self.setWindowModality(Qt.ApplicationModal)
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
        self.encoder_thread.output.connect(lambda l: self._output(self.tbEncoder, l))
        self.rip_thread.progress.connect(self.encoder_thread.enqueue)

        self._cancelled = False
        self._done = 0
        self.errors = []
        self.error.connect(self._error)

        self.rip_done = 0
        self.encode_done = 0

        self.rip_thread.start()
        self.encoder_thread.start()

        self.encoded = []
        util.restore_ui(self, "ripper")

    def _completed(self, done, target):
        return f"{done}/{target}"

    def _cancel(self):
        self.rip_thread.stop()
        self.encoder_thread.stop()
        self._cancelled = True

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
        self.rip_thread.stop()
        self.encoder_thread.stop()

    def _child_done(self):
        self._done += 1
        if self._done != 2:
            return

        util.save_ui(self, "ripper")

        if self._cancelled:
            self.reject()
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
        self.active = True

    def _exec(self, track, cmd, inf, outf):
        variables = cdinfo.cmd_fmt_variables(track, self.workdir, inf, outf, EXT)
        cmd = shlex.split(cmd)
        for i in range(len(cmd)):
            cmd[i] = cmd[i].format(**variables)

        if util.TEST_MODE:
            time.sleep(1)

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
            return True
        except Exception as e:
            util.print_error()
            if self.active:
                self.ripper.error.emit(str(e))
            return False

    def stop(self):
        self.active = False
        if self.proc:
            self.proc.terminate()


class RipperThread(TaskThread):
    def run(self):
        for t in self.disc.tracks:
            if not self.active:
                break
            target = f"track{t.trackno}.wav"

            cmd = CDPARANOIA_CMD
            if util.TEST_MODE:
                cmd = "touch {output}"

            self.output.emit(f"==== Ripping track {t.trackno} - {t.title}")
            if not self._exec(t, cmd, None, target):
                break
            self.output.emit(f"--- Done.")
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

            next = self.dequeue()
            while next:
                if not self.encode(next, self.disc.tracks[done]):
                    return
                done += 1
                next = self.dequeue()

    def encode(self, source, track):
        self.output.emit(f"==== Encoding track {track.trackno} - {track.title}")

        target = f"{source}.{EXT}"
        if not self._exec(track, self.config.encoder, source, target):
            return False

        self.output.emit(f"--- Tagging...")
        try:
            self.tag(target, track)
        except Exception as e:
            util.print_error()
            self.ripper.error.emit(f"error tagging {target}: {e}")
            return False

        self.output.emit(f"--- Done.")
        self.progress.emit(target)
        return True

    def tag(self, target, track):
        mp3 = MP3(os.path.join(self.workdir, target))

        if not mp3.tags:
            mp3.add_tags()

        tags = mp3.tags
        tags.add(id3.TALB(encoding=id3.Encoding.UTF8, text=self.disc.album))
        tags.add(id3.TPE1(encoding=id3.Encoding.UTF8, text=self.disc.artist))
        tags.add(id3.TIT2(encoding=id3.Encoding.UTF8, text=track.title))
        tags.add(id3.TRCK(encoding=id3.Encoding.UTF8, text=str(track.trackno)))
        tags.add(id3.TDRC(encoding=id3.Encoding.UTF8, text=str(self.disc.year)))

        tpos = str(self.disc.discno)
        if self.disc.set_size > 1:
            tpos = f"{self.disc.discno}/{self.disc.set_size}"
        tags.add(id3.TPOS(encoding=id3.Encoding.UTF8, text=tpos))

        if self.disc.cover_art:
            tags.add(id3.APIC(encoding=id3.Encoding.UTF8, data=self.disc.cover_art))

        mp3.save()

    def dequeue(self):
        next = None
        with self.lock:
            if self.queue:
                next = self.queue[0]
                del self.queue[0]
            self.event.clear()
        return next

    def enqueue(self, next):
        with self.lock:
            self.queue.append(next)
            self.event.set()

    def stop(self):
        with self.lock:
            self.event.set()
        super().stop()


def commit_files(staging, target):
    if util.TEST_MODE:
        print(f"committing {staging} to {target}")

    for name in os.listdir(staging):
        src = os.path.join(staging, name)
        dst = os.path.join(target, name)

        if os.path.isdir(src):
            if not util.TEST_MODE and not os.path.isdir(dst):
                os.mkdir(dst)
            commit_files(src, dst)
        else:
            if os.path.exists(dst):
                raise Exception(f"cannot write target {dst}: already exists")
            if util.TEST_MODE:
                print(f"  {src} -> {dst}")
            else:
                shutil.move(src, dst)


def rename_files(disc, ripped, target, template):
    if len(disc.tracks) != len(ripped):
        QMessageBox.critical(None, "Error", "Inconsistent state after ripping disc.")
        return

    for i in range(len(ripped)):
        t = disc.tracks[i]
        src = ripped[i]

        variables = cdinfo.dest_fmt_variables(disc, t, EXT)

        expanded = template.format(**variables)
        if util.TEST_MODE:
            print(f"{src} -> {expanded}")
        dest = os.path.join(target, expanded)

        if i == 0:
            os.makedirs(os.path.dirname(dest))
        shutil.move(src, dest)


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

        if info.rip_as_multi_disc:
            disc.album = f"{disc.album} (Disc {disc.discno})"

        encoded = [os.path.join(workdir, x) for x in ripper.encoded]
        staging = tempfile.mkdtemp(dir=workdir)
        rename_files(disc, encoded, staging, config.template)
        commit_files(staging, config.target)

    QMessageBox.information(None, "fripper", "Encoding done!")
    util.eject()
    app.quit()
