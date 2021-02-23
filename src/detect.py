# SPDX-License-Identifier: BSD-2-Clause
import base64
import datetime
import hashlib
from dataclasses import dataclass

import cdio
import musicbrainzngs as mb
import pycdio
import util
from PyQt5.QtCore import QThread
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QLabel

mb.set_useragent("fripper", "1.0")


@dataclass
class DiscInfo:
    discid: str
    track_count: int


@dataclass
class TrackInfo:
    artist: str
    album: str
    title: str
    trackno: int


@dataclass
class CDInfo:
    artist: str
    album: str
    tracks: list
    discno: int
    year: int
    set_size: int
    multi_artist: bool
    cover_art: list
    disambiguation: str = ""


class DetectorTask(QThread):
    def __init__(self, dlg, discid):
        QThread.__init__(self)
        self.dlg = dlg
        self.discid = discid
        self.releases = None

    def run(self):
        tracks = None
        if not self.discid:
            try:
                info = get_disc_info()
                self.discid = info.discid
                tracks = info.track_count
            except Exception as e:
                util.show_error(e, message="Error reading disc information")
                return

        self.dlg.message.emit("Getting data from musicbrainz...")

        try:
            self.releases = get_releases(self.discid)
        except Exception:
            util.show_error("Could not find CD info in musicbrainz")
            if not tracks:
                # Happens during testing only. Just set a bogus number
                tracks = 5

            # This isn't very good, especially if the not found disc has multiple
            # artists. UI needs to handle this case properly.
            self.releases = [
                CDInfo(
                    artist="Unknown",
                    album="Unknown",
                    discno=1,
                    year=1980,
                    multi_artist=False,
                    set_size=1,
                    cover_art=None,
                    tracks=[
                        TrackInfo(
                            artist="Unknown",
                            album="Unknown",
                            title="Unknown",
                            trackno=i,
                        )
                        for i in range(1, tracks + 1)
                    ],
                ),
            ]


class DetectionDialog(QDialog):
    message = pyqtSignal(str)

    def __init__(self, discid=None):
        QDialog.__init__(self)

        hbox = QHBoxLayout()
        self.msg = QLabel()
        hbox.addWidget(self.msg)
        hbox.setStretch(0, 1)
        self.setLayout(hbox)

        self._set_message("Detecting the disc...")
        self.task = DetectorTask(self, discid)

        self.task.finished.connect(self._done)
        self.message.connect(self._set_message)

        self.task.start()

    def _set_message(self, msg):
        self.msg.setText(msg)
        self.resize(self.sizeHint())

    def _done(self):
        rels = self.task.releases
        if not rels:
            raise Exception(f"did not find any release for disc")

        if len(rels) > 1:
            self.disc = self._choose_release(rels)
        else:
            self.disc = rels[0]

        self.accept()

    def _choose_release(self, releases):
        chooser = ReleasesDialog(self, releases)
        chooser.exec_()
        return chooser.release


class ReleasesDialog(util.compile_ui("releases.ui")):
    def __init__(self, parent, releases):
        super().__init__(parent)
        self.releases = releases
        self.choice = 0
        self.release = releases[0]
        self.btnOk.clicked.connect(self._done)
        self.lstReleases.itemSelectionChanged.connect(self._release_changed)

        for r in releases:
            alias = f"{r.artist} / {r.album}"
            self.lstReleases.addItem(alias)

        self._set_release()

        util.restore_ui(self, "releases")

    def _release_changed(self):
        sel = self.lstReleases.selectedItems()
        if sel:
            self.choice = self.lstReleases.row(sel[0])
        else:
            self.choice = 0
        self.release = self.releases[self.choice]
        self._set_release()

    def _set_release(self):
        self.lbArtist.setText(self.release.artist)
        self.lbAlbum.setText(self.release.album)
        self.lbYear.setText(str(self.release.year))
        self.lbDisambiguation.setText(self.release.disambiguation)

        start = self.relInfo.indexOf(self.lbTracks) + 1
        end = self.relInfo.count() - 1
        for i in range(start, end):
            item = self.relInfo.itemAt(start)
            item.widget().close()
            self.relInfo.removeItem(item)

        for t in self.release.tracks:
            label = QLabel()
            label.setText(t.title)
            self.relInfo.insertWidget(self.relInfo.count() - 1, label)

    def _done(self):
        util.save_ui(self, "releases")
        self.accept()


def get_disc_info():
    # See: https://musicbrainz.org/doc/Disc_ID_Calculation for algorithm
    # Some of the stuff described in that doc is already handled by the cdio library. Only
    # the leadout adjustment based on the LBA address of data tracks is missing.
    d = cdio.Device(driver_id=pycdio.DRIVER_UNKNOWN)
    drive_name = d.get_device()

    if d.get_disc_mode() != "CD-DA":
        raise Exception("Not an audio disc.")

    first = pycdio.get_first_track_num(d.cd)
    count = d.get_num_tracks()
    last = first

    tracks = {}
    leadout = None
    for i in range(first, first + count):
        t = d.get_track(i)
        if t.get_format() == "audio":
            tracks[i] = t.get_lba()
            last = i
        elif leadout is None:
            leadout = t.get_lba() - 11400

    if leadout is None:
        leadout = d.get_track(pycdio.CDROM_LEADOUT_TRACK).get_lba()
    tracks[0] = leadout

    data = [
        f"{first:02X}",
        f"{last:02X}",
    ]

    for i in range(100):
        offset = tracks.get(i, 0)
        data.append(f"{offset:08X}")

    sha = hashlib.sha1()
    sha.update("".join(data).encode("utf-8"))

    b64 = base64.b64encode(sha.digest()).decode("utf-8")
    tbl = str.maketrans("+/=", "._-")
    return DiscInfo(
        discid=b64.translate(tbl),
        track_count=count,
    )


def get_releases(discid):
    ret = mb.get_releases_by_discid(discid)
    releases = ret.get("disc", {}).get("release-list")
    if not releases:
        raise Exception(f"no release found for {discid}")
    return [get_cd_info(r, discid) for r in releases]


def get_cd_info(rel, discid):
    discno = None
    album = rel.get("title")
    for medium in rel["medium-list"]:
        for disc in medium["disc-list"]:
            if disc["id"] == discid:
                discno = int(medium["position"])
                album = medium.get("title", album)
                break
        if discno:
            break
    else:
        raise Exception("could not find disc no")

    relid = rel["id"]
    ret = mb.get_release_by_id(
        relid, includes=["artists", "recordings", "media", "artist-credits"]
    )
    rel = ret.get("release")

    date = rel["date"]
    fmts = [
        "%Y-%m-%d",
        "%Y-%m",
        "%Y",
    ]
    for fmt in fmts:
        try:
            year = datetime.datetime.strptime(date, fmt).year
            break
        except:
            pass
    else:
        print(f"Can't figure out album year: {date}")
        year = 1900

    set_size = rel["medium-count"]
    for medium in rel["medium-list"]:
        if int(medium["position"]) == discno:
            tracks = medium["track-list"]
            break
    else:
        raise Exception("cannot find tracks")

    atracks = []
    found_artists = set()
    for t in tracks:
        artists = t["artist-credit"]
        if len(artists) > 1:
            artist = "Various"
        else:
            artist = artists[0]["artist"]["name"]
            found_artists.add(artist)

        track = TrackInfo(
            artist=artist,
            album=album,
            title=t.get("title") or t["recording"]["title"],
            trackno=int(t["position"]),
        )
        atracks.append(track)

    album_artist = "Various"
    if len(found_artists) == 1:
        album_artist = list(found_artists)[0]

    atracks = sorted(atracks, key=lambda t: t.trackno)

    cover_art = None
    if rel.get("cover-art-archive").get("artwork") == "true":
        try:
            art = mb.get_image_list(relid)
            pos = 0
            for img in art["images"]:
                if not "Front" in img.get("types", []):
                    continue

                if not cover_art or pos == discno:
                    cover_art = util.http_get(img["image"])

                if pos == discno:
                    break

                pos += 1
        except Exception as e:
            util.print_error()
            pass

    return CDInfo(
        artist=album_artist,
        album=album,
        tracks=atracks,
        discno=discno,
        year=year,
        set_size=set_size,
        multi_artist=len(found_artists) > 1,
        cover_art=cover_art,
        disambiguation=rel.get("disambiguation"),
    )


if __name__ == "__main__":
    import sys
    import pprint

    # Some interesting disc IDs:
    # - dCZWjhrnNC_JSgv9lqSZQ_SPc3c- : normal album (Haken - Vector)
    # - x0uC3CqZCMC8_Qr2OsgL59MkmYE- : second disc of double album (Joe Satriani - Live in SF)
    # - kLu3X6F6GwZwCwvdhCVQs4R9iPc- : second disc with data track (The Ocean - Precambrian)
    # - SCP4nE6BDCTkQnHMzs6LiBuHCdg- : multiple artists (Merry Axemas)
    # - VsCC5lu9uDTPZO5uUG6BiQ_OziI- : re-issued + bonus tracks (King Diamond - Abigail)
    # - 5vdHnGO7X5GvTQvzRhwMhGxW6_0- : release with a lot of stuff (Kate Bush - Hounds of Love)
    # - RBiq_Z3vfD7L_dPbTCeeM3BL5mU- : part of a "remasters" collection (Judas Priest - Turbo)
    discid = "dCZWjhrnNC_JSgv9lqSZQ_SPc3c-"

    if sys.argv[-1] == "-d":
        discid = get_disc_info().discid
        print(f"discid: {discid}")
    elif len(sys.argv) == 2:
        discid = sys.argv[1]

    rels = get_releases(discid)
    for r in rels:
        if r.cover_art:
            r.cover_art = True
        pprint.pprint(r.__dict__)
