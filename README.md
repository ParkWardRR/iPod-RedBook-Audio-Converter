# iPod RedBook Audio Converter

An iPod library builder that converts and organizes your music for **30-pin iPods and Apple devices** at the practical **"iPod-safe ceiling"**: 16-bit / up to 48 kHz stereo—so you get maximum iPod-compatible sound without wasting storage on hi‑res files your device can't use.

<img src="https://i.postimg.cc/4nRd11ZY/Conversion.png" width="600" alt="Conversion TUI">

Whether you listen through an **analog** iPod chain (headphone jack, or a line‑out dock into an amp) or a digital dock chain (for example, an Onkyo ND‑S1 outputting S/PDIF), going above 16-bit or 48 kHz doesn't improve what the iPod delivers, but it does make files much larger. This tool enforces the iPod-safe ceiling—downconverting hi-res sources only when needed—while **never upscaling** anything.

**Two simple knobs:**

- **16-bit** = how many "volume steps" each snapshot of the waveform can use (more steps = finer detail).
- **44.1–48 kHz** = how many snapshots per second are taken (44,100 or 48,000 snapshots every second).

This project is backed by **FFmpeg**, so it can ingest modern/odd formats and channel layouts (including multichannel sources) and convert them into iPod-friendly files (downmixing to stereo when needed, with proper headroom to prevent clipping).

## Key rules (important)

- **No upscaling**: if a track is already within the iPod-safe ceiling (16-bit, ≤48 kHz), it stays there. No fake "hi-res" inflation.
- **Downscale only when needed**: hi-res sources (bit depth >16 or sample rate >48 kHz) are automatically downconverted to the ceiling, with proper dithering.
- **Audiophile-quality conversion**:
  - High-quality resampling via **soxr** (SoX Resampler)
  - **Triangular high-pass dither** when reducing bit depth (24→16)
  - **Headroom protection** (−3 dB) when downmixing multichannel to stereo
- **Smart defaults**: hi-res albums are automatically flagged for downconversion during scan—no manual spreadsheet edits required.
- **Output stays iPod-friendly**:
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

# CSV is great if you want plain text
ipodrb scan --library "/path/to/music" --plan plan.csv
```

<img src="https://i.postimg.cc/7br6NNDb/Scanning.png" width="600" alt="Scanning TUI">

### 2) Edit the plan (optional—smart defaults already set)

The scan automatically assigns optimal defaults based on each album's audio specs:

| Source Quality | Auto-assigned Default |
|---|---|
| MP3 (any) | `PASS_MP3` (passthrough, no transcoding) |
| Lossless, 16-bit, ≤48 kHz | `ALAC_PRESERVE` (already iPod-safe) |
| Lossless, 24-bit or >48 kHz | `ALAC_16_44` (auto-downconvert to ceiling) |
| Lossy non-MP3 (AAC, OGG, etc.) | `AAC` (re-encode to AAC-LC) |

**For most users, no edits are needed**—hi-res albums are automatically flagged for downconversion.

If you want to override defaults, open the plan and set:

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

Filenames include tags that show what conversion was applied and the source quality in your library.

| Tag | Meaning |
|---|---|
| `[ALAC_PRESERVE_16-44.1k]` | Lossless preserved at original quality (CD quality, no conversion needed) |
| `[ALAC_Converted_24-96k→16-44.1k]` | Downconverted from hi-res lossless (your library has better quality) |
| `[AAC_256k_from_16-44.1k]` | Lossy AAC at 256kbps from CD-quality source |
| `[AAC_256k_from_24-96k]` | Lossy AAC at 256kbps from hi-res source (your library has lossless) |
| `[MP3_PASS]` | MP3 passthrough (copied as-is) |

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
| `--format` | Force `xlsx` or `csv` |
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
| `--target-sample-rate` | Target sample rate: `48000` (default) or `44100` |
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
 
## Platform support

This project has only been tested on **macOS Tahoe (latest)** so far. It *may* work on Linux/Windows, but those platforms are currently untested—please open an issue (and include your OS, Python version, and FFmpeg version) if you hit problems.
 
---

## Sample rate: 48 kHz vs 44.1 kHz

**Default: 16/48 (48 kHz ceiling)**

The default target is 16-bit / 48 kHz. This preserves 48 kHz sources without resampling while still downconverting anything above 48 kHz.

### Which sample rate should you use?

- **If your files originate as 44.1 kHz** (CD rips, most music releases): use `--target-sample-rate 44100` to avoid unnecessary resampling.
- **If your files originate as 48 kHz** (video sources, some pro-audio): keeping 16/48 (the default) is reasonable and should play on many iPod Classics. If you hit skipping or odd behavior, `--target-sample-rate 44100` is the compatibility fallback.

### Can iPods play 48 kHz files?

- Apple's iPod Classic specs mention support for AAC-LC audio "up to 48 kHz" in video contexts, suggesting the hardware can decode 48 kHz audio.
- Community reports indicate iPod Classic can sync and play 48 kHz ALAC files, though behavior may vary by firmware version and playback path.
- Files above 48 kHz are typically rejected or downconverted.

### When to use `--target-sample-rate 44100`

Use the 44.1 kHz option when:

1. **Your library is mostly CD rips**: CD audio is 44.1 kHz—converting to 48 kHz adds an unnecessary resampling step.
2. **Maximum compatibility is needed**: 44.1 kHz is guaranteed to work on all iPod models, firmware versions, and playback paths.
3. **You experience playback issues**: If you hear skips, stutters, or odd behavior with 48 kHz files, fall back to 44.1 kHz.

**Example:**

```bash
# Default (48 kHz ceiling) - good for mixed libraries or 48 kHz sources
ipodrb apply --plan plan.xlsx --out /output

# 44.1 kHz option - for CD-quality libraries or maximum compatibility
ipodrb apply --plan plan.xlsx --out /output --target-sample-rate 44100
```

> **Note:** For 5th gen iPod Classic, if you experience playback issues with 48 kHz files, use `--target-sample-rate 44100` as the compatibility fallback.

---

## Red Book (CD-DA) explained

> [!TIP]
> In this repo, "Red Book" is used loosely to mean the **iPod-safe ceiling**: 16-bit PCM at up to 48 kHz. True Red Book (CD-DA) is 16-bit / 44.1 kHz, but iPod Classic and similar devices support up to 48 kHz. We default to preserving 48 kHz sources to avoid unnecessary resampling, while enforcing a hard ceiling that prevents pointless hi-res storage.

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

