# SPDX-License-Identifier: BSD-2-Clause
import base64
import datetime
import hashlib
from dataclasses import dataclass

import cdio
import musicbrainzngs as mb
import pycdio

mb.set_useragent("fripper", "1.0")


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
    discs: int
    year: int
    cover_art = None


def get_disc_id():
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
    return b64.translate(tbl)


def get_cd_info(discid):
    ret = mb.get_releases_by_discid(discid)
    releases = ret.get("disc", {}).get("release-list")
    if not releases:
        print("no rel")
        return None

    rel = releases[0]

    disc_count = len(rel["medium-list"])
    for disc in rel["medium-list"]:
        if disc["disc-list"][0]["id"] == discid:
            discno = int(disc["position"])
            break
    else:
        print("cannot find disc no")
        return None

    ret = mb.get_release_by_id(rel["id"], includes=["artists", "recordings", "media"])
    rel = ret.get("release")

    album = rel["title"]
    year = datetime.datetime.strptime(rel["date"], "%Y-%m-%d").year

    artists = rel["artist-credit"]
    if len(artists) > 1:
        artist = "Various"
    else:
        artist = artists[0]["artist"]["name"]

    for medium in rel["medium-list"]:
        if int(medium["position"]) == discno:
            tracks = medium["track-list"]
            break
    else:
        print("cannot find tracks")
        return None

    atracks = []
    for t in tracks:
        track = TrackInfo(
            artist=artist,
            album=album,
            title=t["recording"]["title"],
            trackno=int(t["position"]),
        )
        atracks.append(track)

    atracks = sorted(atracks, key=lambda t: t.trackno)

    return CDInfo(
        artist=artist,
        album=album,
        tracks=atracks,
        discno=discno,
        discs=disc_count,
        year=year,
    )


if __name__ == "__main__":
    import sys
    import pprint

    # Some interesting disc IDs:
    # - dCZWjhrnNC_JSgv9lqSZQ_SPc3c- : normal album (Haken - Vector)
    # - x0uC3CqZCMC8_Qr2OsgL59MkmYE- : second disc of double album (Joe Satriani - Live in SF)
    # - kLu3X6F6GwZwCwvdhCVQs4R9iPc- : second disc with data track (The Ocean - Precambrian)
    discid = "dCZWjhrnNC_JSgv9lqSZQ_SPc3c-"

    if sys.argv[-1] == "-d":
        discid = get_disc_id()
        print(f"discid: {discid}")
    elif len(sys.argv) == 2:
        discid = sys.argv[1]

    cd = get_cd_info(discid)
    pprint.pprint(cd.__dict__)
