# Yangon

**iPod-compatible audio library converter with spreadsheet-based album planning**

Convert your high-resolution music library to iPod-compatible formats while maintaining full control over every album's conversion settings. Yangon scans your library, generates a decision spreadsheet, and applies your choices with a professional TUI dashboard.

<!-- TODO: Add screenshot of main TUI dashboard during conversion -->
<!-- ![TUI Dashboard](YOUR_IMAGE_HOST_URL/dashboard.png) -->

---

## Features

### Smart Library Scanning
- Automatically detects albums from directory structure
- Analyzes audio formats, sample rates, and bit depths via FFprobe
- Evaluates metadata quality (tags and artwork) with traffic-light status

### Spreadsheet-Based Workflow
- **XLSX** (Excel) - Full formatting with conditional highlighting and reference sheets
- **TSV** (Tab-separated) - Edit in any text editor, handles commas in metadata
- **CSV** (Comma-separated) - Universal compatibility

<!-- TODO: Add screenshot of XLSX plan file in Excel showing album decisions -->
<!-- ![XLSX Plan](YOUR_IMAGE_HOST_URL/xlsx-plan.png) -->

### Audio Processing
- **ALAC** - Lossless Apple codec, preserves or downconverts to Red Book (16-bit/44.1kHz)
- **AAC** - Lossy encoding at 128/192/256/320 kbps
- **MP3 Passthrough** - Copy existing MP3 files unchanged
- **Never-upconvert policy** - Only downconverts when source exceeds target specs
- **Proper dithering** - Uses SoXR triangular dither for bit-depth reduction

### Professional TUI
- Real-time progress tracking with ETA
- Per-album and per-track status
- Error summary and activity log
- Compact mode for small terminals

<!-- TODO: Add screenshot of compact TUI mode -->
<!-- ![Compact TUI](YOUR_IMAGE_HOST_URL/compact-tui.png) -->

### Performance
- Parallel scanning with ThreadPoolExecutor (I/O-bound)
- Parallel conversion with ProcessPoolExecutor (CPU-bound)
- SQLite caching for incremental builds
- Skip already-converted tracks automatically

---

## Requirements

- **Python 3.12+**
- **FFmpeg 6+** (must be in PATH)

### Installing FFmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows (via Chocolatey)
choco install ffmpeg
```

---

## Installation

### Using a Virtual Environment (Recommended)

```bash
# Clone the repository
git clone https://github.com/ParkWardRR/iPod-RedBook-Audio-Converter.git
cd iPod-RedBook-Audio-Converter

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install yangon
pip install -e .
```

### Verify Installation

```bash
yangon --version
yangon --help
```

---

## Quick Start

### 1. Scan Your Library

```bash
# Generate XLSX plan (recommended for Excel users)
yangon scan --library /path/to/music --plan plan.xlsx

# Generate TSV plan (recommended for text editor users)
yangon scan --library /path/to/music --plan plan.tsv
```

<!-- TODO: Add screenshot of scan command output -->
<!-- ![Scan Output](YOUR_IMAGE_HOST_URL/scan-output.png) -->

### 2. Review and Edit the Plan

Open the generated plan file and set your preferences:

| Column | Description |
|--------|-------------|
| `user_action` | Override the default action (ALAC_PRESERVE, ALAC_16_44, AAC, PASS_MP3, SKIP) |
| `aac_bitrate_kbps` | Set AAC bitrate (128, 192, 256, 320) |
| `skip` | Set to `true` to skip this album |

The XLSX format includes a **Reference** tab with all valid action values and their descriptions.

### 3. Check Status

```bash
yangon status --plan plan.xlsx
```

Shows summary of albums by tag status, art status, and selected actions.

### 4. Apply Conversions

```bash
# Convert with TUI dashboard
yangon apply --plan plan.xlsx --out /path/to/ipod/Music

# Dry run (preview without converting)
yangon apply --plan plan.xlsx --out /path/to/ipod/Music --dry-run

# Force rebuild all (ignore cache)
yangon apply --plan plan.xlsx --out /path/to/ipod/Music --force
```

<!-- TODO: Add screenshot of apply command with progress -->
<!-- ![Apply Progress](YOUR_IMAGE_HOST_URL/apply-progress.png) -->

---

## Command Reference

### `yangon scan`

Scan a music library and generate a plan file.

```bash
yangon scan --library PATH --plan PATH [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-l, --library PATH` | Path to music library root (required) |
| `-p, --plan PATH` | Output plan file path (required) |
| `-f, --format` | Force format: `xlsx`, `tsv`, or `csv` |
| `--recreate` | Discard existing user edits |
| `--threads N` | Parallel scan threads (default: 32) |
| `--no-tui` | Disable TUI progress display |
| `--compact` | Use compact 3-line TUI |

### `yangon apply`

Apply plan decisions and convert audio files.

```bash
yangon apply --plan PATH --out PATH [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-p, --plan PATH` | Plan file path (required) |
| `-o, --out PATH` | Output directory (required) |
| `--dry-run` | Preview without writing files |
| `--fail-fast` | Stop on first error |
| `--force` | Ignore cache, rebuild all |
| `--threads N` | Parallel conversion threads (default: CPU count) |
| `--no-tui` | Disable TUI progress display |
| `--compact` | Use compact 3-line TUI |

### `yangon status`

Display summary from a plan file.

```bash
yangon status --plan PATH
```

---

## Audio Actions

| Action | Description |
|--------|-------------|
| `ALAC_PRESERVE` | Convert to ALAC, preserve source sample rate/bit depth (downconvert if >44.1kHz/16-bit) |
| `ALAC_16_44` | Convert to ALAC, force 16-bit/44.1kHz Red Book standard |
| `AAC` | Convert to AAC lossy (set bitrate in `aac_bitrate_kbps` column) |
| `PASS_MP3` | Copy MP3 files unchanged |
| `SKIP` | Do not process this album |

---

## Status Indicators

### Tag Status
| Status | Meaning |
|--------|---------|
| GREEN | All required tags present and consistent |
| YELLOW | Missing year or minor inconsistencies |
| RED | Missing title/album or track numbering issues |

### Art Status
| Status | Meaning |
|--------|---------|
| GREEN | Cover art found, 300x300 pixels or larger |
| YELLOW | Art exists but small or ambiguous |
| RED | No artwork found |

---

## Output Structure

Converted files are organized as:

```
{output}/
  {Album Artist}/
    {Year} - {Album}/
      {Disc}{Track:02} {Title}.m4a
```

A `manifest.csv` is generated in the output root with details of all converted tracks.

---

## Plan File Formats

### XLSX (Excel)
- Conditional formatting highlights status columns
- Reference tab documents all valid actions
- Best for users who prefer spreadsheet editing

### TSV (Tab-Separated Values)
- Plain text, editable in any text editor
- Handles commas in artist/album names without escaping
- Metadata stored in `#` comment lines at top

### CSV (Comma-Separated Values)
- Universal compatibility
- Some editors handle embedded commas better than others

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check yangon/
```

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
