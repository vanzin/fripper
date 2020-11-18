# SPDX-License-Identifier: BSD-2-Clause
import datetime
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
    year: int


def get_cd_info(discid):
    ret = mb.get_releases_by_discid(discid)
    releases = ret.get("disc", {}).get("release-list")
    if not releases:
        print("no rel")
        return None

    rel = releases[0]["id"]

    ret = mb.get_release_by_id(rel, includes=["artists", "recordings", "media"])
    rel = ret.get("release")

    album = rel["title"]
    year = datetime.datetime.strptime(rel["date"], "%Y-%m-%d").year

    artists = rel["artist-credit"]
    if len(artists) > 1:
        artist = "Various"
    else:
        artist = artists[0]["artist"]["name"]

    medium = rel["medium-list"][0]
    discno = int(medium["position"])
    tracks = medium["track-list"]
    atracks = []
    for t in tracks:
        track = TrackInfo(
            artist=artist,
            album=album,
            title=t["recording"]["title"],
            trackno=int(t["position"]),
        )
        atracks.append(track)

    return CDInfo(
        artist=artist,
        album=album,
        tracks=atracks,
        discno=discno,
        year=year,
    )


if __name__ == "__main__":
    import pprint

    cd = get_cd_info("dCZWjhrnNC_JSgv9lqSZQ_SPc3c-")
    pprint.pprint(cd.__dict__)
