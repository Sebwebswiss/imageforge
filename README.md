# ImageForge

[![Python](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-00FF00.svg)](./LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)

**Professional Image Conversion Toolkit**
*Fast batch conversion to WebP, AVIF, JPEG and PNG with automatic size optimization*

**[🌐 Try the live web demo →](https://sebwebswiss.github.io/imageforge/)** — convert images in your browser, nothing is uploaded to a server.

---

## Why ImageForge?

Modern image formats are **25-35% smaller** than JPEG/PNG at similar quality. ImageForge makes it effortless to convert an entire image library with a single command — and it asks which format you want.

| Metric | Before | After | Improvement |
|---|---|---|---|
| File size | 4.2 MB | 89 KB | **97.9% smaller** |
| Page load | 3.2s | 0.4s | **8x faster** |
| Bandwidth | 100 MB | 3.2 MB | **96.8% savings** |

---

## Features

- **Lightning fast** — batch convert hundreds of images in seconds
- **Pick your format** — WebP, AVIF, JPEG or PNG, chosen interactively or via `--format`
- **Smart size optimization** — automatically reduce quality/dimensions to meet a target file size
- **EXIF orientation fix** — phone photos display correctly (no more rotated images)
- **Transparency handling** — alpha preserved for WebP/AVIF/PNG, flattened to white for JPEG
- **Skip existing** — won't re-convert already processed images
- **Recursive mode** — process entire folder structures with one command
- **Beautiful CLI** — colorful output with progress tracking and statistics
- **Memory efficient** — uses in-memory buffers for fast optimization (no temp files)
- **Python API** — use as a library in your own projects
- **Web demo** — client-side converter, no server, no upload

---

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/Sebwebswiss/imageforge.git
cd imageforge

# Install as a package (recommended)
pip install -e .

# Or just install the dependency and run from source
pip install -r requirements.txt
python -m imageforge ./my-photos
```

### One-Command Usage

```bash
# Convert all images in a folder — ImageForge asks which format you want
imageforge ./my-photos

# Or be explicit (no prompt — ideal for scripts and CI)
imageforge ./my-photos --format webp
```

---

## Usage

### Command Line

```bash
# Basic conversion (asks for format interactively)
imageforge ./photos

# Pick the format explicitly
imageforge ./photos --format avif
imageforge ./photos --format jpeg
imageforge ./photos --format png

# Single image
imageforge photo.jpg -o photo.webp

# Custom output directory
imageforge ./photos -o ./optimized

# Target specific file size (in KB)
imageforge ./photos --max-size 100

# Custom dimensions and quality
imageforge ./photos --width 800 --quality 75

# Include subdirectories
imageforge ./website-images --recursive

# Force re-convert existing files
imageforge ./photos --force
```

### Command Line Options

| Option | Short | Description | Default |
|---|---|---|---|
| `input` | — | Input image file or directory | required |
| `--format` | — | Export format: `webp`, `avif`, `jpeg`, `png` | asks, else `webp` |
| `--output` | `-o` | Output file or directory | `<input>/<format>_output` |
| `--width` | `-w` | Maximum width in pixels | `1200` |
| `--quality` | `-q` | Quality level (1-100), ignored for PNG | `80` |
| `--max-size` | `-s` | Target max file size in KB | `None` |
| `--recursive` | `-r` | Process subdirectories | `False` |
| `--force` | `-f` | Re-convert existing files | `False` |
| `--version` | `-v` | Show version | — |

There is deliberately **no short flag for `--format`**, because `-f` already means `--force`.

### Interactive format selection

Run without `--format` in a terminal and ImageForge asks:

```
  Format izvoza:
  1) WebP  — najmanji za web, podržava prozirnost (zadano)
  2) AVIF  — još manji od WebP-a, sporije kodiranje
  3) JPEG  — univerzalna podrška, bez prozirnosti
  4) PNG   — bez gubitka kvaliteta, najveće datoteke
  Unesi broj ili naziv [webp]:
```

Type a number, a name, or press Enter for the default. When stdin is **not** a terminal (pipes, `cron`, CI) the prompt is skipped automatically and `webp` is used, so scripts never block.

### Output directories

Without `-o`, files land in a folder named after the chosen format:

| Format | Default output folder |
|---|---|
| `webp` | `<input>/webp_output` |
| `avif` | `<input>/avif_output` |
| `jpeg` | `<input>/jpeg_output` |
| `png` | `<input>/png_output` |

---

## Python API

Use ImageForge as a library in your own projects:

```python
from pathlib import Path
from imageforge.converter import convert_image, convert_directory

# Convert a single image
result = convert_image(
    input_path=Path("photo.jpg"),
    output_path=Path("photo.webp"),
    max_width=1200,
    quality=80,
    max_size_kb=150,      # Auto-optimize to meet this target
    output_format="webp",  # webp | avif | jpeg | png
)

print(f"Saved {result.saved_kb} KB ({result.compression_ratio}% compression)")
print(f"{result.width}x{result.height} @ quality {result.quality}")

# Convert an entire directory
results = convert_directory(
    input_dir=Path("./photos"),
    output_dir=Path("./optimized"),
    max_size_kb=100,
    recursive=True,
    output_format="avif",
)

# Get statistics
total_saved = sum(r.saved_kb for r in results if r.success)
print(f"Total saved: {total_saved} KB ({total_saved/1024:.1f} MB)")
```

### API reference

| Function / attribute | Description |
|---|---|
| `convert_image(...)` | Convert one file, returns a `ConversionResult` |
| `convert_directory(...)` | Convert a directory, returns `list[ConversionResult]` |
| `resolve_format(name)` | Resolve `"webp"`/`"jpg"`/`".png"` → `OutputFormat` |
| `FORMATS` | Registry of all supported output formats |
| `result.saved_kb` / `result.saved_mb` | Space saved |
| `result.compression_ratio` | Percent smaller (negative if the file grew) |
| `result.output_format` | Format actually used |
| `result.error` | `"skipped"`, or a message on failure |

---

## Examples

### Batch Processing Output

```
  ╔═══════════════════════════════════════════════╗
  ║                                               ║
  ║   ImageForge v1.1.0                           ║
  ║   Alat za profesionalnu konverziju slika        ║
  ║                                               ║
  ╚═══════════════════════════════════════════════╝

  Skeniranje: /home/user/photos  → WEBP

  ✓  hero.jpg → hero.webp  89.2 KB  (-96.2%)
  ✓  logo.png → logo.webp  12.4 KB  (-94.1%)
  ⊘  banner.jpg (već konvertovano)
  ✓  background.png → background.webp  45.8 KB  (-97.3%)
  ✓  team-photo.jpg → team-photo.webp  128.4 KB  (-89.7%)

──────────────────────────────────────────────────
  Sažetak
──────────────────────────────────────────────────
  Konvertovano:  4  │  Preskočeno:  1  │  Neuspjelo:  0
  Original:    8,450 KB (8.3 MB)
  Rezultat:    276 KB (0.3 MB)
  Ušteda:      8,174 KB (8.0 MB)
──────────────────────────────────────────────────

  Datoteke su zapisane u: /home/user/photos/webp_output
```

### Supported Formats

| Input | Output |
|---|---|
| JPEG / JPG | WebP, AVIF, JPEG, PNG |
| PNG | WebP, AVIF, JPEG, PNG |
| BMP | WebP, AVIF, JPEG, PNG |
| TIFF / TIF | WebP, AVIF, JPEG, PNG |
| GIF | WebP, AVIF, JPEG, PNG |

Notes:

- **Transparency** is preserved when exporting to WebP, AVIF or PNG. JPEG has no alpha channel, so images are flattened onto a white background.
- **AVIF** gives the smallest files but is significantly slower to encode. It requires Pillow 11.3+ built with libavif.
- **PNG** is lossless, so `--quality` does not apply; ImageForge uses maximum compression instead.

---

## How It Works

1. **Scan** — finds all supported images in the target directory
2. **Skip** — leaves already-converted files alone (unless `--force`)
3. **EXIF Fix** — corrects orientation from phone cameras
4. **Transparency** — preserves alpha, or flattens it for JPEG
5. **Resize** — scales down images exceeding max width (preserves aspect ratio)
6. **Optimize** — if `--max-size` is set, iteratively adjusts quality, then dimensions
7. **Save** — writes the converted file to the output directory

The optimization loop keeps in-memory buffers and caches each resize by width, so lowering quality never re-runs the expensive LANCZOS resample. It uses in-memory `BytesIO` for fast iteration without disk I/O overhead.

---

## Project Structure

```
imageforge/
├── docs/
│   └── index.html         # Live web demo (GitHub Pages)
├── src/
│   └── imageforge/
│       ├── __init__.py      # Package metadata
│       ├── __main__.py      # Module entry point
│       ├── converter.py     # Core conversion engine
│       └── cli.py           # Command-line interface
├── tests/                   # Test suite
├── README.md                # This file
├── CONTRIBUTING.md          # Contribution guidelines
├── LICENSE                  # MIT License
├── requirements.txt         # Dependencies
└── pyproject.toml           # Python packaging config
```

---

## Development

```bash
pip install -e ".[dev]"

pytest              # run the test suite
ruff check src tests
black src tests
```

---

## Requirements

- **Python** 3.8 or higher
- **Pillow** (PIL Fork) — image processing library
- AVIF export additionally needs a Pillow build with libavif support

---

## Contributing

Contributions are welcome! Whether it's:

- Bug reports
- Feature requests
- Code improvements
- Documentation updates

Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

---

## License

This project is licensed under the MIT License — see [LICENSE](./LICENSE) for details.

---

## Acknowledgments

- [Pillow](https://python-pillow.org/) — Python imaging library
- [WebP](https://developers.google.com/speed/webp/) — Google's modern image format
- Built with Python and a passion for performance

---

**Made with Python**
*If this project helped you, consider giving it a star!*
