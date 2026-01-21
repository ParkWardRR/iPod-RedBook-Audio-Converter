# yangon

iPod-compatible audio library converter with XLSX-based album planning.

## Features

- Scan NAS music libraries and generate XLSX decision sheets
- Convert audio to iPod-compatible formats (ALAC, AAC, MP3 passthrough)
- Never-upconvert audio policy (only downconvert when needed)
- Incremental builds with SQLite caching
- Rich TUI dashboard for progress tracking
- RED/YELLOW/GREEN status for tags and artwork

## Requirements

- Python 3.12+
- FFmpeg 6+ (must be in PATH)

## Installation

```bash
pip install -e .
```

## Usage

### Scan a library

```bash
yangon scan --library /path/to/music --xlsx /path/to/plan.xlsx
```

### Apply decisions

```bash
yangon apply --xlsx /path/to/plan.xlsx --out /path/to/output
```

### View status

```bash
yangon status --xlsx /path/to/plan.xlsx
```

## License

MIT
