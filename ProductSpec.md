## iPod-RedBook-Audio-Converter — Product Spec (v1)

Build a macOS (Apple Silicon) terminal tool that scans a large NAS music library, generates/maintains an album-level XLSX “decision sheet” in the NAS root, then consumes that sheet to produce a neatly organized iPod-ready output library with **never-upconvert** audio rules, ALAC/AAC outputs (and optional MP3 passthrough), plus a highly informative TUI status dashboard during long runs.  
Compatibility constraint: iPod classic-era technical specs list support for AAC, MP3, Apple Lossless, AIFF, and WAV, so output choices must stay inside that ecosystem. [web:5]

---

## 1) Goals

### 1.1 Primary goals
- Produce an iPod-syncable library optimized for fidelity-per-byte:
  - Lossless: ALAC in `.m4a`
  - Space-saver: AAC in `.m4a`
  - Optional passthrough: MP3 unchanged
- Provide an album-level planning workflow via XLSX so the user can:
  - Accept defaults (e.g., FLAC → ALAC)
  - Override per-album output (e.g., “AAC 256 for this album”)
  - Skip albums
- Provide a detailed, reliable status experience (TUI) so the user can see:
  - What’s happening now
  - What’s queued
  - What changed since last scan
  - What failed and why

### 1.2 Non-goals
- No GUI (desktop app) in v1.
- No direct iPod sync implementation (tool outputs a folder intended for iTunes/Finder sync workflows).
- No FLAC output (tool is a converter/curator for stock iPod compatibility).

---

## 2) Users & environment

- Runs on: macOS on Apple Silicon (e.g., M4 Pro), local SSD available for fast working directory.
- Source: NAS-mounted music library with TBs of mixed formats, inconsistent tags/art.
- Output: a clean folder tree intended to be imported/synced to an iPod.
- Scale expectation: tens of thousands of tracks; scanning and conversion must be incremental and restart-safe.

---

## 3) Compatibility envelope (hard constraints)

### 3.1 Supported-family alignment
The iPod classic technical specifications list audio support for AAC, MP3, Apple Lossless, AIFF, and WAV. [web:5]

### 3.2 Output formats (project constraint)
- Output ALAC only as `.m4a` (Apple Lossless in an MPEG-4 container).
- Output AAC only as `.m4a`.
- MP3 may be passed through unchanged if selected (no MP3 encoding by default).

---

## 4) Audio policy (normative)

### 4.1 Global invariants
1. Never upconvert:
   - Never increase sample rate (e.g., 44.1k → 48/96).
   - Never increase bit depth (e.g., 16 → 24).
   - Never “pad” lower-quality sources upward.
2. Downconvert-only when required (default policy):
   - If source sample rate > 44.1k → downconvert to 44.1k.
   - If source bit depth > 16 → reduce to 16-bit (dither on by default).
   - If source is already ≤16-bit and ≤44.1k → preserve those values when encoding ALAC/AAC.
3. Output codec restriction:
   - Do not emit WAV/AIFF as outputs (convert them to ALAC/AAC).
   - Do not emit FLAC as output.

### 4.2 Source → output mapping
| Source | Default | Allowed overrides | Notes |
|---|---|---|---|
| FLAC | Convert to ALAC `.m4a` | Convert to AAC `.m4a`, or SKIP | Input-only in this tool’s world. |
| WAV | Convert to ALAC `.m4a` | Convert to AAC `.m4a`, or SKIP | WAV is supported by iPod family but excluded from outputs by spec. [web:5] |
| AIFF | Convert to ALAC `.m4a` | Convert to AAC `.m4a`, or SKIP | AIFF is supported by iPod family but excluded from outputs by spec. [web:5] |
| ALAC | Copy through (retag/art allowed) | Downconvert to 16/44.1 if source exceeds | iPod supports Apple Lossless. [web:5] |
| AAC | Copy through (retag/art allowed) | Re-encode if user requests new target | iPod supports AAC family. [web:5] |
| MP3 | Pass through unchanged (optional) | Convert to AAC or SKIP | iPod supports MP3. [web:5] |

### 4.3 AAC encoding policy
- Default AAC profile: AAC-LC (compat-first).
- Default AAC bitrate: 256 kbps.
- Allowed AAC bitrates: 128/192/256/320 kbps (validate; reject others).

### 4.4 Bit-depth reduction & dithering
- If reducing >16-bit → 16-bit: apply dither by default.
- Dither mode is configurable; default must be safe and consistent.
- Record applied bit-depth conversion + dither choice in the manifest.

### 4.5 Sample-rate conversion
- If downsampling is required, use a high-quality resampler mode.
- Record original SR and output SR in the manifest.

### 4.6 Gapless handling
- Preserve gapless metadata when present for AAC/ALAC outputs.
- Avoid introducing additional silence where possible.

---

## 5) Metadata & artwork policy (normative)

### 5.1 Required output tags
For each output track, ensure the following tags exist and are consistent at the album level:
- Title
- Artist
- Album
- Album Artist
- Track Number (+ total if available)
- Disc Number (+ total if multi-disc)
- Year (required for GREEN; missing Year is YELLOW by default)
- Compilation flag (when applicable)

### 5.2 Tag mapping rules
- Prefer embedded tags from source.
- Do not invent missing Year; leave blank and mark status.
- Normalization (capitalization, Album Artist unification, etc.) must be opt-in:
  - Global flag `--normalize-tags`, or
  - Album-level action implying normalization.

### 5.3 Artwork rules
- Detect embedded artwork per track.
- Detect common folder images as candidates (e.g., cover/front/folder).
- Output policy:
  - Prefer embedding one consistent cover image into all album output tracks.
  - If multiple candidates are present, mark YELLOW and list candidates in notes.
  - If none exists, mark RED.

---

## 6) Red / Yellow / Green status rules

### 6.1 Tag status
- GREEN: required tags present and consistent across album; Year present.
- YELLOW: minor issues (missing Year, mild inconsistencies).
- RED: missing critical tags or inconsistent numbering/album fields likely to break browsing.

### 6.2 Art status
- GREEN: exactly one unambiguous cover found and meets minimum size threshold (threshold configurable).
- YELLOW: art exists but ambiguous or below recommended threshold.
- RED: no art found.

---

## 7) Decision sheet (XLSX) spec

### 7.1 Storage
- XLSX path default: `{library_root}/ipod_plan.xlsx`
- Sheet write behavior:
  - Write `{xlsx}.tmp` then atomic rename.
  - Keep timestamped backup of previous sheet on rewrite.
  - Refuse to run if a lock file exists (NAS + Excel concurrency).

### 7.2 Tabs
- Albums: primary user control surface, one row per album folder.
- Summary: rollups + schema version.
- Changes (optional): added/removed/changed albums since last scan.

### 7.3 Summary required fields
- schema_version (e.g., "1.0")
- library_root
- created_at / updated_at
- counts:
  - albums total
  - tag_status counts
  - art_status counts
  - default_action counts
  - user_action counts
- scan delta summary (added/removed/changed)

### 7.4 Albums columns (minimum)
| Column | Owner | Type | Description |
|---|---|---|---|
| album_id | tool | string | Stable id for continuity. |
| source_path | tool | path | Album directory. |
| artist | tool | string | Best-effort extracted. |
| album | tool | string | Best-effort extracted. |
| year | tool | string/int | Blank if unknown. |
| track_count | tool | int | Detected. |
| source_formats | tool | string | e.g., "FLAC;MP3". |
| max_sr_hz | tool | int | Max SR observed in album. |
| max_bit_depth | tool | int | Max bit depth observed. |
| default_action | tool | enum | Computed default. |
| user_action | user | enum | Override; blank uses default. |
| aac_target_kbps | user | int | Used when action resolves to AAC. |
| skip | user | bool | Skip this album entirely. |
| tag_status | tool | enum | GREEN/YELLOW/RED. |
| art_status | tool | enum | GREEN/YELLOW/RED. |
| plan_hash | tool | string | Hash of resolved plan inputs. |
| last_built_at | tool | datetime | When last successfully built. |
| error_code | tool | string | Machine-readable error (if any). |
| notes | tool/user | string | Actionable details. |

### 7.5 Enums (strict validation)
Allowed actions:
- ALAC_PRESERVE (default; downconvert-only when required)
- ALAC_16_44 (force 16/44.1 ALAC even if source is lower/other ≤ constraints; still never-upconvert)
- AAC
- PASS_MP3
- SKIP

Rules:
- Blank user_action => use default_action.
- Unknown user_action => error, refuse apply (or mark row RED + error_code and skip based on `--fail-fast`).

### 7.6 Conditional formatting
- Apply red/yellow/green fills for tag_status and art_status.
- Highlight rows with error_code.

### 7.7 Preserving user edits and schema evolution
- On scan update:
  - Preserve user-owned columns exactly (user_action, aac_target_kbps, skip).
  - Tool may add new columns; must not delete or reorder user columns in a way that breaks workflows.
- Validate schema_version before apply; provide friendly error on mismatch.

---

## 8) Scanning & update behavior

### 8.1 Scan
- Walk library_root and detect album directories.
- Extract per-track technical data (codec, SR, bit depth, duration) and tags/art presence.
- Produce/refresh the XLSX with:
  - album rows
  - defaults pre-filled (e.g., FLAC→ALAC_PRESERVE)
  - tag_status/art_status + notes
  - Changes tab (optional)

### 8.2 Update vs recreate
- `scan` updates in place by default; provide `--recreate` to rebuild sheet from scratch.
- Preserve user overrides on update whenever album_id matches.

---

## 9) Apply (build) behavior

### 9.1 Plan resolution
For each album row:
- If skip = true → skip album.
- Resolve action: if user_action blank → default_action else user_action.
- Validate action and AAC bitrate constraints.
- Expand album-level decision into per-track work items.

### 9.2 Output structure
- Deterministic path template (configurable), example:
  - `{out_root}/{Album Artist}/{Year} - {Album}/{DiscPrefix}{Track:02} {Title}.{ext}`
- Collision policy:
  - If output path collision occurs, append ` [album_id]` or short hash to filename.

### 9.3 Output formats
- ALAC: `.m4a`
- AAC: `.m4a`
- MP3 passthrough: `.mp3` (only if PASS_MP3 resolved)

### 9.4 Atomic writes and verification
Per-track:
1. Write to temp file in output volume.
2. Verify the temp file by probing codec/SR/bit depth/duration and readability.
3. Atomically rename into final path.
4. Update cache + manifests + XLSX last_built_at.

---

## 10) Incremental builds & caching

### 10.1 Track-level cache
Maintain a cache keyed on:
- Source fingerprint (mtime + size; optional content hash)
- Resolved settings (action, AAC bitrate, SR/bit-depth policy, tag/art policy)
- Tool version (to invalidate cache on major behavior changes)

If unchanged and verified output exists → skip work.

### 10.2 Verify-on-skip
If cached “up-to-date” but output probe fails → rebuild.

---

## 11) Error handling & reporting

### 11.1 Error policy
- Default: continue building other albums/tracks; record failures.
- Optional: fail-fast (`--fail-fast`) on first error.

### 11.2 Where errors appear
- Console log
- Structured log (JSON lines)
- XLSX row fields (error_code + notes), plus status degradation where appropriate
- Summary tab rollup

### 11.3 Standard error codes
- DECODE_FAIL
- ENCODE_FAIL
- PROBE_FAIL
- TAG_READ_FAIL
- TAG_WRITE_FAIL
- ART_NOT_FOUND
- ART_AMBIGUOUS
- INVALID_ENUM
- LOCKED_XLSX
- OUTPUT_COLLISION

---

## 12) Manifests & logs

### 12.1 Output manifests
Write in output root:
- manifest.csv (track-level; required)
- manifest.json (optional)

manifest.csv fields (minimum):
- album_id
- source_path
- output_path
- resolved_action
- codec
- bitrate_kbps (if applicable)
- sample_rate_hz
- bit_depth
- duration_seconds
- output_size_bytes
- tag_status
- art_status
- error_code

### 12.2 Logs
- Human log: concise progress + errors.
- Structured log: JSONL events (scan/update/apply, per-track results).

---

## 13) CLI interface

### 13.1 Commands
- `ipodprep scan --library <path> --xlsx <path>`
- `ipodprep apply --xlsx <path> --out <path>`
- `ipodprep status --xlsx <path>`

### 13.2 Common flags
- `--dry-run`
- `--force`
- `--fail-fast` / default continue
- `--threads N`
- `--normalize-tags`
- `--recreate` (scan)

---

## 14) TUI status requirement (add-on, v1)

### 14.1 Requirement
Provide an optional terminal UI (“dashboard”) during `scan`, `apply`, and `status` to display a detailed live view while work runs.

### 14.2 Framework guidance
Use a common TUI approach:
- Option A (lighter): Rich-style live panels/tables/progress.
- Option B (full TUI): a widget-based TUI framework.

### 14.3 TUI must display (minimum)
- Overall run phase + elapsed time + ETA.
- Multi-task progress:
  - scanning
  - decoding
  - encoding
  - tag writing
  - artwork embedding
  - verification
- Current album/track being processed.
- Queue depth (remaining tracks/jobs).
- Rolling event feed (last N events).
- Error pane:
  - count by error_code
  - last N errors with album_id + short message

### 14.4 TUI interactions (minimum)
- `q`: exit TUI view without killing the job (job continues in background mode for that run).
- Toggle views: All events vs Errors-only.
- Optional filter box: by artist/album substring.

### 14.5 TUI parity constraint
TUI is a view layer only; it must reflect the same counters/events used for logs, manifest.csv, and XLSX annotations so results are identical with or without TUI.

---

## 15) Defaults (v1)
- Default action:
  - If album contains FLAC/WAV/AIFF/ALAC: ALAC_PRESERVE
  - If album is MP3-only: PASS_MP3
- Default AAC bitrate: 256 kbps
- Dither: enabled when reducing bit depth
- Error behavior: continue and annotate (fail-fast optional)

---

## 16) Open decisions to finalize
- Artwork GREEN threshold (min pixel size) + whether to auto-resize on output.
- Whether MP3 passthrough is enabled by default or must be explicitly selected.
- Whether normalization writes are allowed without per-album confirmation when `--normalize-tags` is set.

## 17) Considerations for file input types: 
- category,format,extensions,notes\ninput,FLAC,.flac,"needs rate/ch/bitdepth; transcode"\ninput,Ogg Vorbis,.ogg,"needs rate/ch/bitdepth; transcode"\ninput,Opus,.opus,"needs rate/ch/bitdepth; transcode"\ninput,WMA,.wma,"needs rate/ch/bitdepth; transcode"\ninput,RealAudio,.ra,"needs rate/ch/bitdepth; transcode"\ninput,RealMedia,.rm,"needs rate/ch/bitdepth; transcode"\ninput,AU/NeXT/Sun,".au,.snd","needs rate/ch/bitdepth; normalize"\ninput,VOC,.voc,"needs rate/ch/bitdepth; resample"\ninput,Tracker MOD,.mod,"needs rate/ch/bitdepth; render to PCM"\ninput,Tracker S3M,.s3m,"needs rate/ch/bitdepth; render to PCM"\ninput,Tracker XM,.xm,"needs rate/ch/bitdepth; render to PCM"\ninput,Tracker IT,.it,"needs rate/ch/bitdepth; render to PCM"\ninput,MIDI,".mid,.midi","needs rate/ch/bitdepth; synthesize"\ninput,Shorten,.shn,"needs rate/ch/bitdepth; transcode"\ninput,Monkey's Audio,.ape,"needs rate/ch/bitdepth; transcode"\ninput,Raw PCM,".pcm,.raw","needs rate/ch/bitdepth; user-supplied"


