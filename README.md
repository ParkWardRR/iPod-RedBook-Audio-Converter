# iPod RedBook Audio Converter

Build an iPod library that sounds as good as possible for **Red Book** playback (16-bit / 44.1kHz) without wasting space.

If you use an iPod through a digital dock like the Onkyo ND-S1 (Red Book output), hi‑res files don’t increase playback quality. This tool keeps your iPod library within iPod/Red Book limits by **downscaling lossless sources (e.g., FLAC/hi‑res) when needed**, and never upscales anything.

<img src="https://i.postimg.cc/4nRd11ZY/Conversion.png" width="600" alt="Conversion TUI">

---

## What it does

You point it at your music library, it produces a per-album “plan” file (XLSX/TSV/CSV), and then it builds an iPod-ready output library based on that plan.

It’s designed for people who want:
- Top-quality iPod playback (ALAC 16/44.1 where appropriate)
- Smaller files when hi‑res would be wasted on an iPod/Red Book chain
- Full control per album (keep lossless, choose AAC bitrate, passthrough MP3, or skip)

---

## Key rules (important)

- No upscaling: if a track is 16/44.1 already, it stays there (no fake “hi-res”).
- Downscale only when needed: if the source exceeds iPod/Red Book limits, it is downconverted to 16/44.1 (with proper dithering).
- Output stays iPod-friendly:
  - ALAC for lossless
  - AAC for space savings
  - MP3 passthrough when you already have MP3s

---

## Requirements

| Requirement | Notes |
|---|---|
| Python | 3.12+ |
| FFmpeg | 6+ and available in PATH |

### Install FFmpeg

```bash
# macOS (Homebrew)
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg
```

Quick sanity check:

```bash
python3 --version
ffmpeg -version
```

---

## Install

> These commands assume you want an isolated install in a virtual environment.

```bash
# 1) Clone
git clone https://github.com/ParkWardRR/iPod-RedBook-Audio-Converter.git
cd iPod-RedBook-Audio-Converter

# 2) Create a virtual environment
python3 -m venv .venv

# 3) Activate it
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate     # Windows PowerShell

# 4) Install
pip install -U pip
pip install -e .
```

### Verify install

```bash
ipodrb --version
ipodrb --help
```

---

## Quick Start

### 1) Scan your library → generate a plan

```bash
# XLSX is best if you use Excel/Numbers/LibreOffice
ipodrb scan --library "/path/to/music" --plan plan.xlsx

# TSV is great if you want plain text
ipodrb scan --library "/path/to/music" --plan plan.tsv
```

<img src="https://i.postimg.cc/7br6NNDb/Scanning.png" width="600" alt="Scanning TUI">

### 2) Edit the plan (choose what happens per album)

Open the plan and set the album actions you want:

| Column | What it controls |
|---|---|
| `user_action` | Album action: `ALAC_PRESERVE`, `ALAC_16_44`, `AAC`, `PASS_MP3`, `SKIP` |
| `aac_target_kbps` | AAC bitrate: `128`, `192`, `256`, `320` |
| `skip` | `true` to skip the album |

Tip: the XLSX format includes a Reference tab listing valid values.

### 3) Preview library status (tags + artwork)

```bash
ipodrb status --plan plan.xlsx
```

<img src="https://i.postimg.cc/XX6Jgg3p/Status.png" width="500" alt="Status Output">

### 4) Build your iPod-ready output library

```bash
# Convert with TUI dashboard
ipodrb apply --plan plan.xlsx --out "/path/to/iPod/Music"

# Dry run (no files written)
ipodrb apply --plan plan.xlsx --out "/path/to/iPod/Music" --dry-run

# Force rebuild (ignore cache)
ipodrb apply --plan plan.xlsx --out "/path/to/iPod/Music" --force
```

---

## Output naming (so you can see what happened)

Filenames include tags that show what conversion was applied and whether your main library has a higher-quality source.

| Tag | Meaning |
|---|---|
| `[ALAC]` | Lossless at CD quality or below |
| `[ALAC 24-96k→16-44.1k]` | Downconverted from hi-res lossless (your library has better than the iPod copy) |
| `[AAC 256k]` | Lossy AAC from CD-quality source |
| `[AAC 256k 24-96k]` | Lossy AAC from hi-res source (your library has lossless) |
| `[MP3]` | MP3 passthrough |

---

## Output structure

```text
{output}/
  {Album Artist}/
    {Year} - {Album}/
      {Track:02} {Title} [TAG].m4a
```

A `manifest.csv` is written at the output root with details of all processed tracks.

---

## Command reference

### `scan`
```bash
ipodrb scan --library PATH --plan PATH [OPTIONS]
```

| Option | Description |
|---|---|
| `--library PATH` | Music library root (required) |
| `--plan PATH` | Plan output path (required) |
| `--format` | Force `xlsx`, `tsv`, or `csv` |
| `--recreate` | Discard existing user edits |
| `--threads N` | Scan threads (default: 32) |
| `--no-tui` | Disable TUI |
| `--compact` | Compact TUI |

### `apply`
```bash
ipodrb apply --plan PATH --out PATH [OPTIONS]
```

| Option | Description |
|---|---|
| `--plan PATH` | Plan path (required) |
| `--out PATH` | Output directory (required) |
| `--dry-run` | Preview only |
| `--fail-fast` | Stop on first error |
| `--force` | Ignore cache |
| `--threads N` | Conversion threads (default: CPU count) |
| `--no-tui` | Disable TUI |
| `--compact` | Compact TUI |

### `status`
```bash
ipodrb status --plan PATH
```

---

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
``` 

---

## Red Book (CD-DA) explained

> [!TIP]
> In this repo, "Red Book" means **CD-quality audio**: 16-bit / 44.1 kHz PCM—the baseline format defined for audio CDs.

### What "Red Book" is
"Red Book" is the colloquial name for the original **Compact Disc Digital Audio (CD‑DA)** specification created by Philips and Sony and published in 1980.
It defines the *logical* audio format for an audio CD: two-channel, 16-bit PCM sampled at 44.1 kHz.
In standards terms, CD‑DA is covered by IEC 60908 ("Audio recording — Compact disc digital audio system").

### Why 44.1 kHz and 16-bit?
A 44.1 kHz sampling rate supports audio up to 22.05 kHz by the Nyquist–Shannon theorem, which was chosen to cover the traditional "20 Hz–20 kHz" audible range.
Historically, 44.1 kHz was inherited from early studio-to-mastering workflows that used PCM adaptors based on video recorders, and that legacy carried into the CD specification.

### Core technical parameters

| Parameter | Red Book value |
|---|---|
| Channels | 2-channel stereo PCM |
| Bit depth | 16-bit linear PCM |
| Sample rate | 44.1 kHz |
| Audio data rate | 1,411.2 kbps (2 × 44,100 × 16) |
| Track count (typical limit) | Up to 99 tracks |
| Disc/play time (historical target) | ~74 minutes |

### A short history (high level)

| Year | What happened |
|---:|---|
| 1979–1980 | Philips and Sony aligned on key CD‑DA choices like 44.1 kHz sampling and 16-bit quantization during joint development meetings. |
| 1980 | The CD‑DA spec was published (the "Red Book" document). |
| 1999 | IEC 60908 was published as an IEC standard defining CD‑DA interchangeability parameters for discs and players. |

<details>
<summary><strong>Where the name comes from (Rainbow Books)</strong></summary>

"Red Book" is named after the color of its cover and is part of the broader "Rainbow Books" family of CD-related specifications.
Different colors historically correspond to different CD formats (audio CD, CD-ROM, recordable variants, etc.).

</details>


---

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## Acknowledgments

- [FFmpeg](https://ffmpeg.org/) - Audio processing engine
- [Rich](https://github.com/Textualize/rich) - Beautiful terminal formatting
- [Click](https://click.palletsprojects.com/) - CLI framework
- [Mutagen](https://mutagen.readthedocs.io/) - Audio metadata handling
- [openpyxl](https://openpyxl.readthedocs.io/) - Excel file support

