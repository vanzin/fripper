# SPDX-License-Identifier: BSD-2-Clause
import base64
import datetime
import hashlib
import re
import subprocess
from dataclasses import dataclass

import musicbrainzngs as mb

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


def get_disc_id():
    # See: https://musicbrainz.org/doc/Disc_ID_Calculation for algorithm
    # Uses cd-info instead of cd-record; track info looks like:
    #   1: 00:02:00  000000 audio  false  no    2        no
    tre = re.compile(r"\s*([0-9]+):\s[0-9]+:[0-9]+:[0-9]+\s+([0-9]+)\s+(.*?)\s+.*")

    tracks = {}
    leadout = None
    has_data = False
    first = -1
    last = -1

    toc = subprocess.check_output(
        [
            "cd-info",
            "--no-device-info",
            "--no-analyze",
            "--no-disc-mode",
            "--no-xa",
            "--no-header",
        ]
    )
    for line in toc.decode("utf-8").split("\n"):
        m = tre.match(line)
        if not m:
            continue

        trackno = int(m.group(1))
        offset = int(m.group(2)) + 150
        ttype = m.group(3)

        if ttype == "leadout":
            if leadout is None:
                leadout = offset
        elif ttype == "audio":
            if first == -1:
                first = trackno
            last = trackno
            tracks[trackno] = offset
        else:
            leadout = offset - 11400

    data = [
        f"{first:02X}",
        f"{last:02X}",
    ]

    tracks[0] = leadout

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
