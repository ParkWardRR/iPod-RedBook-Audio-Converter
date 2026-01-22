# iPod RedBook Audio Converter

An iPod library builder that converts and organizes your music for **30-pin iPods and Apple devices** at the practical ceiling of "Red Book" quality: \(16\)-bit / \(44.1\) kHz stereo—so you get maximum iPod-compatible sound without wasting storage on hi‑res files your chain can't use.

<img src="https://i.postimg.cc/4nRd11ZY/Conversion.png" width="600" alt="Conversion TUI">

Whether you listen through an **analog** iPod chain (headphone jack, or a line‑out dock into an amp) or a digital dock chain (for example, an Onkyo ND‑S1 outputting S/PDIF in Red Book format), going above \(16/44.1\) doesn't improve what the iPod delivers in that Red Book context, but it does make files much larger. This tool targets \(16/44.1\) when needed (it downconverts sources that exceed it), and it never upscales anything—so you meet the limit, but don't exceed it.

\(16/44.1\) is just a shorthand for “CD-quality audio,” and it’s two simple knobs:

- \(16\)-bit = how many “volume steps” each snapshot of the waveform can use (more steps = finer detail).
- \(44.1\) kHz = how many snapshots per second are taken (\(44{,}100\) snapshots every second).

This project is backed by **FFmpeg**, so it can ingest modern/odd formats and channel layouts (including multichannel sources) and convert them into iPod-friendly files (for example, downmixing to stereo when appropriate), while still enforcing the “don’t exceed \(16/44.1\)” goal for Red Book-focused playback and storage efficiency.

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

# CSV is great if you want plain text
ipodrb scan --library "/path/to/music" --plan plan.csv
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
| `--target-sample-rate` | Target sample rate: `44100` (default) or `48000` |
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

## Sample rate: 44.1 kHz vs 48 kHz

**Default: 16/44.1 (recommended for maximum compatibility)**

The default target is 16-bit / 44.1 kHz because it matches the Red Book CD standard and ensures the best compatibility across all iPod models and firmware versions.

### Can iPods play 48 kHz files?

- Apple's iPod Classic specs mention support for AAC-LC audio "up to 48 kHz" in video contexts, suggesting the hardware can decode 48 kHz audio.
- Community reports indicate iPod Classic can sync and play 48 kHz ALAC files, though behavior may vary by firmware version and playback path.
- Files above 48 kHz are typically rejected or downconverted.

### Should you use `--target-sample-rate 48000`?

**For most users: No.** Stick with the default 44.1 kHz for these reasons:

1. **Source is usually 44.1 kHz**: Most music (CDs, commercial downloads) is mastered at 44.1 kHz. Converting 44.1 → 48 kHz adds an unnecessary resampling step with no quality benefit.

2. **Maximum compatibility**: 44.1 kHz is guaranteed to work on all iPod models, firmware versions, and playback paths (headphone jack, line-out, digital dock).

3. **No audible difference**: When listening via the iPod's analog outputs (headphone jack or line-out dock), there's no perceptible quality difference between 44.1 and 48 kHz.

**When 48 kHz makes sense:**

- Your source files are **already at 48 kHz** (common for video soundtracks or certain pro-audio formats), and you want to avoid the 48 → 44.1 conversion step.
- You've verified that your specific iPod model and playback setup handles 48 kHz files reliably.

**Example:**

```bash
# Default (44.1 kHz) - recommended for music libraries
ipodrb apply --plan plan.xlsx --out /output

# 48 kHz option - only if your sources are 48 kHz and iPod is verified compatible
ipodrb apply --plan plan.xlsx --out /output --target-sample-rate 48000
```

> **Note:** For 5th gen iPod Classic specifically, 44.1 kHz is the safest choice to avoid potential playback issues like skips or stutters.

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

