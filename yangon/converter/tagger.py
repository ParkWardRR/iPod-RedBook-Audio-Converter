"""Tag and artwork writing for output files."""

from pathlib import Path

from mutagen.id3 import APIC, ID3, TALB, TCON, TDRC, TIT2, TPE1, TPE2, TRCK, TPOS
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover

from yangon.models.plan import TrackJob


def write_tags_and_artwork(
    output_path: Path,
    job: TrackJob,
) -> None:
    """
    Write metadata tags and artwork to output file.

    Handles both MP4 (M4A/ALAC/AAC) and MP3 formats.

    Args:
        output_path: Path to output file
        job: Track job with tags and artwork info
    """
    ext = output_path.suffix.lower()

    if ext == ".m4a":
        _write_mp4_tags(output_path, job)
    elif ext == ".mp3":
        _write_mp3_tags(output_path, job)


def _write_mp4_tags(output_path: Path, job: TrackJob) -> None:
    """Write tags to MP4/M4A file."""
    audio = MP4(output_path)

    tags = job.tags

    # Standard MP4 tag mappings
    if tags.get("title"):
        audio["\xa9nam"] = [tags["title"]]
    if tags.get("artist"):
        audio["\xa9ART"] = [tags["artist"]]
    if tags.get("album"):
        audio["\xa9alb"] = [tags["album"]]
    if tags.get("album_artist"):
        audio["aART"] = [tags["album_artist"]]
    if tags.get("year"):
        audio["\xa9day"] = [str(tags["year"])]

    # Track number
    track_num = tags.get("track_number")
    track_total = tags.get("track_total")
    if track_num:
        audio["trkn"] = [(track_num, track_total or 0)]

    # Disc number
    disc_num = tags.get("disc_number")
    disc_total = tags.get("disc_total")
    if disc_num:
        audio["disk"] = [(disc_num, disc_total or 0)]

    # Compilation flag
    if tags.get("compilation"):
        audio["cpil"] = True

    # Artwork
    if job.artwork_source and job.artwork_source.exists():
        artwork_data = job.artwork_source.read_bytes()
        # Detect format
        if artwork_data[:3] == b"\xff\xd8\xff":
            fmt = MP4Cover.FORMAT_JPEG
        elif artwork_data[:8] == b"\x89PNG\r\n\x1a\n":
            fmt = MP4Cover.FORMAT_PNG
        else:
            fmt = MP4Cover.FORMAT_JPEG  # Default
        audio["covr"] = [MP4Cover(artwork_data, imageformat=fmt)]

    audio.save()


def _write_mp3_tags(output_path: Path, job: TrackJob) -> None:
    """Write tags to MP3 file."""
    try:
        audio = MP3(output_path, ID3=ID3)
    except Exception:
        # If no ID3 tag exists, create one
        audio = MP3(output_path)
        audio.add_tags()

    tags = job.tags
    id3 = audio.tags

    # Standard ID3 frames
    if tags.get("title"):
        id3.add(TIT2(encoding=3, text=[tags["title"]]))
    if tags.get("artist"):
        id3.add(TPE1(encoding=3, text=[tags["artist"]]))
    if tags.get("album"):
        id3.add(TALB(encoding=3, text=[tags["album"]]))
    if tags.get("album_artist"):
        id3.add(TPE2(encoding=3, text=[tags["album_artist"]]))
    if tags.get("year"):
        id3.add(TDRC(encoding=3, text=[str(tags["year"])]))

    # Track number
    track_num = tags.get("track_number")
    track_total = tags.get("track_total")
    if track_num:
        if track_total:
            id3.add(TRCK(encoding=3, text=[f"{track_num}/{track_total}"]))
        else:
            id3.add(TRCK(encoding=3, text=[str(track_num)]))

    # Disc number
    disc_num = tags.get("disc_number")
    disc_total = tags.get("disc_total")
    if disc_num:
        if disc_total:
            id3.add(TPOS(encoding=3, text=[f"{disc_num}/{disc_total}"]))
        else:
            id3.add(TPOS(encoding=3, text=[str(disc_num)]))

    # Artwork
    if job.artwork_source and job.artwork_source.exists():
        artwork_data = job.artwork_source.read_bytes()
        # Detect MIME type
        if artwork_data[:3] == b"\xff\xd8\xff":
            mime = "image/jpeg"
        elif artwork_data[:8] == b"\x89PNG\r\n\x1a\n":
            mime = "image/png"
        else:
            mime = "image/jpeg"

        id3.add(APIC(
            encoding=3,
            mime=mime,
            type=3,  # Cover (front)
            desc="Cover",
            data=artwork_data,
        ))

    audio.save()
