"""Metadata extraction using mutagen."""

import struct
from io import BytesIO
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis


def extract_metadata(path: Path) -> dict:
    """
    Extract metadata from an audio file using mutagen.

    Returns dict with keys:
        - title, artist, album, album_artist
        - track_number, track_total, disc_number, disc_total
        - year
        - compilation (bool)
        - has_embedded_art (bool)
        - art_width, art_height (if embedded art exists)
    """
    result = {
        "title": None,
        "artist": None,
        "album": None,
        "album_artist": None,
        "track_number": None,
        "track_total": None,
        "disc_number": None,
        "disc_total": None,
        "year": None,
        "compilation": False,
        "has_embedded_art": False,
        "art_width": None,
        "art_height": None,
    }

    try:
        audio = MutagenFile(path, easy=False)
        if audio is None:
            return result
    except Exception:
        return result

    # Handle different formats
    if isinstance(audio, MP3):
        result.update(_extract_id3(audio))
    elif isinstance(audio, FLAC):
        result.update(_extract_vorbis(audio))
        result.update(_extract_flac_art(audio))
    elif isinstance(audio, (OggVorbis, OggOpus)):
        result.update(_extract_vorbis(audio))
    elif isinstance(audio, MP4):
        result.update(_extract_mp4(audio))
    elif hasattr(audio, "tags") and audio.tags:
        # Generic fallback
        result.update(_extract_generic(audio))

    return result


def _extract_id3(audio: MP3) -> dict:
    """Extract metadata from ID3 tags."""
    result = {}
    tags = audio.tags

    if not tags:
        return result

    # Map ID3 frames to our keys
    mappings = {
        "TIT2": "title",
        "TPE1": "artist",
        "TALB": "album",
        "TPE2": "album_artist",
    }

    for frame_id, key in mappings.items():
        frame = tags.get(frame_id)
        if frame:
            result[key] = str(frame)

    # Track number (TRCK: "3/12")
    trck = tags.get("TRCK")
    if trck:
        parts = str(trck).split("/")
        try:
            result["track_number"] = int(parts[0])
            if len(parts) > 1:
                result["track_total"] = int(parts[1])
        except ValueError:
            pass

    # Disc number (TPOS: "1/2")
    tpos = tags.get("TPOS")
    if tpos:
        parts = str(tpos).split("/")
        try:
            result["disc_number"] = int(parts[0])
            if len(parts) > 1:
                result["disc_total"] = int(parts[1])
        except ValueError:
            pass

    # Year - try multiple frames
    for frame_id in ("TDRC", "TYER", "TDAT"):
        frame = tags.get(frame_id)
        if frame:
            year_str = str(frame)[:4]
            try:
                result["year"] = int(year_str)
                break
            except ValueError:
                pass

    # Compilation flag (TCMP)
    tcmp = tags.get("TCMP")
    if tcmp:
        result["compilation"] = str(tcmp) == "1"

    # Check for embedded artwork (APIC)
    for key in tags.keys():
        if key.startswith("APIC"):
            apic = tags[key]
            if isinstance(apic, APIC) and apic.data:
                result["has_embedded_art"] = True
                dims = get_image_dimensions_from_data(apic.data)
                if dims:
                    result["art_width"], result["art_height"] = dims
                break

    return result


def _extract_vorbis(audio) -> dict:
    """Extract metadata from Vorbis comments (FLAC, OGG)."""
    result = {}
    tags = audio.tags if hasattr(audio, "tags") else audio

    if not tags:
        return result

    # Standard vorbis comment mappings (case-insensitive)
    def get_tag(names: list[str]) -> str | None:
        for name in names:
            for key in tags.keys():
                if key.upper() == name.upper():
                    val = tags[key]
                    if isinstance(val, list):
                        return str(val[0]) if val else None
                    return str(val)
        return None

    result["title"] = get_tag(["TITLE"])
    result["artist"] = get_tag(["ARTIST"])
    result["album"] = get_tag(["ALBUM"])
    result["album_artist"] = get_tag(["ALBUMARTIST", "ALBUM ARTIST"])

    # Track number
    track = get_tag(["TRACKNUMBER", "TRACK"])
    if track:
        parts = track.split("/")
        try:
            result["track_number"] = int(parts[0])
            if len(parts) > 1:
                result["track_total"] = int(parts[1])
        except ValueError:
            pass

    track_total = get_tag(["TRACKTOTAL", "TOTALTRACKS"])
    if track_total and not result.get("track_total"):
        try:
            result["track_total"] = int(track_total)
        except ValueError:
            pass

    # Disc number
    disc = get_tag(["DISCNUMBER", "DISC"])
    if disc:
        parts = disc.split("/")
        try:
            result["disc_number"] = int(parts[0])
            if len(parts) > 1:
                result["disc_total"] = int(parts[1])
        except ValueError:
            pass

    disc_total = get_tag(["DISCTOTAL", "TOTALDISCS"])
    if disc_total and not result.get("disc_total"):
        try:
            result["disc_total"] = int(disc_total)
        except ValueError:
            pass

    # Year
    date = get_tag(["DATE", "YEAR"])
    if date:
        try:
            result["year"] = int(date[:4])
        except ValueError:
            pass

    # Compilation
    compilation = get_tag(["COMPILATION"])
    if compilation:
        result["compilation"] = compilation.lower() in ("1", "true", "yes")

    return result


def _extract_flac_art(audio: FLAC) -> dict:
    """Extract artwork info from FLAC pictures."""
    result = {}

    if audio.pictures:
        for pic in audio.pictures:
            if isinstance(pic, Picture) and pic.data:
                result["has_embedded_art"] = True
                if pic.width and pic.height:
                    result["art_width"] = pic.width
                    result["art_height"] = pic.height
                else:
                    dims = get_image_dimensions_from_data(pic.data)
                    if dims:
                        result["art_width"], result["art_height"] = dims
                break

    return result


def _extract_mp4(audio: MP4) -> dict:
    """Extract metadata from MP4/M4A tags."""
    result = {}
    tags = audio.tags

    if not tags:
        return result

    # MP4 tag mappings
    mappings = {
        "\xa9nam": "title",
        "\xa9ART": "artist",
        "\xa9alb": "album",
        "aART": "album_artist",
        "\xa9day": "year",
    }

    for tag_key, result_key in mappings.items():
        if tag_key in tags:
            val = tags[tag_key]
            if isinstance(val, list):
                val = val[0] if val else None
            if val:
                if result_key == "year":
                    try:
                        result["year"] = int(str(val)[:4])
                    except ValueError:
                        pass
                else:
                    result[result_key] = str(val)

    # Track number (trkn: tuple (track, total))
    if "trkn" in tags:
        trkn = tags["trkn"]
        if trkn and isinstance(trkn, list) and trkn[0]:
            track_tuple = trkn[0]
            if isinstance(track_tuple, tuple):
                if len(track_tuple) >= 1 and track_tuple[0]:
                    result["track_number"] = track_tuple[0]
                if len(track_tuple) >= 2 and track_tuple[1]:
                    result["track_total"] = track_tuple[1]

    # Disc number (disk: tuple (disc, total))
    if "disk" in tags:
        disk = tags["disk"]
        if disk and isinstance(disk, list) and disk[0]:
            disc_tuple = disk[0]
            if isinstance(disc_tuple, tuple):
                if len(disc_tuple) >= 1 and disc_tuple[0]:
                    result["disc_number"] = disc_tuple[0]
                if len(disc_tuple) >= 2 and disc_tuple[1]:
                    result["disc_total"] = disc_tuple[1]

    # Compilation (cpil)
    if "cpil" in tags:
        result["compilation"] = bool(tags["cpil"])

    # Artwork (covr)
    if "covr" in tags:
        covers = tags["covr"]
        if covers:
            cover = covers[0]
            if isinstance(cover, (bytes, MP4Cover)):
                data = bytes(cover)
                result["has_embedded_art"] = True
                dims = get_image_dimensions_from_data(data)
                if dims:
                    result["art_width"], result["art_height"] = dims

    return result


def _extract_generic(audio) -> dict:
    """Generic metadata extraction for other formats."""
    result = {}
    tags = audio.tags

    if not tags:
        return result

    # Try common tag names
    for key in tags.keys():
        key_upper = key.upper()
        val = tags[key]
        if isinstance(val, list):
            val = val[0] if val else None
        if not val:
            continue
        val = str(val)

        if "TITLE" in key_upper:
            result["title"] = val
        elif "ARTIST" in key_upper and "ALBUM" not in key_upper:
            result["artist"] = val
        elif "ALBUM" in key_upper and "ARTIST" not in key_upper:
            result["album"] = val

    return result


def get_image_dimensions(path: Path) -> tuple[int, int] | None:
    """
    Get image dimensions without fully loading the image.

    Returns (width, height) or None if unable to determine.
    """
    try:
        with open(path, "rb") as f:
            data = f.read(32)  # Read header
            return get_image_dimensions_from_data(data, read_more=lambda n: f.read(n))
    except Exception:
        return None


def get_image_dimensions_from_data(
    data: bytes,
    read_more=None,
) -> tuple[int, int] | None:
    """
    Get image dimensions from raw image data.

    Supports JPEG, PNG, GIF, BMP without PIL.
    """
    if len(data) < 24:
        return None

    # PNG
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        try:
            width = struct.unpack(">I", data[16:20])[0]
            height = struct.unpack(">I", data[20:24])[0]
            return (width, height)
        except struct.error:
            pass

    # JPEG
    if data[:2] == b"\xff\xd8":
        try:
            # Need to find SOF marker
            # This is simplified - may need more data
            if read_more:
                full_data = data + read_more(65536)
            else:
                full_data = data

            i = 2
            while i < len(full_data) - 9:
                if full_data[i] != 0xFF:
                    break
                marker = full_data[i + 1]
                # SOF markers (0xC0-0xCF except 0xC4, 0xC8, 0xCC)
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    height = struct.unpack(">H", full_data[i + 5 : i + 7])[0]
                    width = struct.unpack(">H", full_data[i + 7 : i + 9])[0]
                    return (width, height)
                # Skip marker
                length = struct.unpack(">H", full_data[i + 2 : i + 4])[0]
                i += 2 + length
        except (struct.error, IndexError):
            pass

    # GIF
    if data[:6] in (b"GIF87a", b"GIF89a"):
        try:
            width = struct.unpack("<H", data[6:8])[0]
            height = struct.unpack("<H", data[8:10])[0]
            return (width, height)
        except struct.error:
            pass

    # BMP
    if data[:2] == b"BM":
        try:
            width = struct.unpack("<I", data[18:22])[0]
            height = abs(struct.unpack("<i", data[22:26])[0])
            return (width, height)
        except struct.error:
            pass

    # Fall back to PIL if available
    try:
        from PIL import Image

        img = Image.open(BytesIO(data))
        return img.size
    except Exception:
        pass

    return None
