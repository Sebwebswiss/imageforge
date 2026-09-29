"""
Core conversion engine for ImageForge.

Handles image processing, resizing, optimization, and format conversion.
"""

from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

SUPPORTED_FORMATS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".webp"})


class OutputFormat:
    """Describes a supported export format and how Pillow should encode it."""

    def __init__(
        self,
        name: str,
        extension: str,
        pil_format: str,
        supports_alpha: bool = True,
        lossless: bool = False,
    ):
        self.name = name
        self.extension = extension
        self.pil_format = pil_format
        self.supports_alpha = supports_alpha
        self.lossless = lossless

    def save_kwargs(self, quality: int, method: int = 4) -> Dict[str, int]:
        """Build the Pillow save() keyword arguments for this format."""
        if self.name == "png":
            return {"compress_level": 9}
        if self.name == "jpeg":
            return {"quality": quality, "optimize": True, "progressive": True}
        if self.name == "avif":
            return {"quality": quality}
        return {"quality": quality, "method": method}

    def __repr__(self) -> str:
        return f"<OutputFormat {self.name}>"


FORMATS: Dict[str, OutputFormat] = {
    "webp": OutputFormat("webp", ".webp", "WEBP"),
    "avif": OutputFormat("avif", ".avif", "AVIF"),
    "jpeg": OutputFormat("jpeg", ".jpg", "JPEG", supports_alpha=False),
    "png": OutputFormat("png", ".png", "PNG", lossless=True),
}

FORMAT_CHOICES = tuple(FORMATS)
DEFAULT_FORMAT = "webp"

FORMAT_LABELS = {
    "webp": "WebP  — najmanji za web, podržava prozirnost (preporučeno)",
    "avif": "AVIF  — još manji od WebP-a, sporije kodiranje",
    "jpeg": "JPEG  — univerzalna podrška, bez prozirnosti",
    "png": "PNG  — bez gubitka kvaliteta, najveći fajlovi",
}


def resolve_format(name: str) -> OutputFormat:
    """
    Resolve a user-supplied format name into an OutputFormat.

    Raises:
        ValueError: If the format name is not supported.
    """
    key = (name or DEFAULT_FORMAT).strip().lower().lstrip(".")
    if key == "jpg":
        key = "jpeg"
    if key == "tif":
        key = "tiff"
    if key not in FORMATS:
        raise ValueError(f"Unsupported format '{name}'. Choose one of: {', '.join(FORMAT_CHOICES)}")
    return FORMATS[key]


class ConversionResult:
    """Stores results from a single image conversion operation."""

    def __init__(
        self,
        input_path: Path,
        output_path: Path,
        original_size_kb: float,
        final_size_kb: float,
        width: int,
        height: int,
        quality: int,
        success: bool = True,
        error: Optional[str] = None,
        output_format: str = DEFAULT_FORMAT,
    ):
        self.input_path = input_path
        self.output_path = output_path
        self.original_size_kb = original_size_kb
        self.final_size_kb = final_size_kb
        self.width = width
        self.height = height
        self.quality = quality
        self.success = success
        self.error = error
        self.output_format = output_format

    @property
    def compression_ratio(self) -> float:
        """Calculate compression percentage."""
        if self.original_size_kb == 0:
            return 0.0
        return round((1 - self.final_size_kb / self.original_size_kb) * 100, 1)

    @property
    def saved_kb(self) -> float:
        """Calculate kilobytes saved."""
        return round(self.original_size_kb - self.final_size_kb, 1)

    @property
    def saved_mb(self) -> float:
        """Calculate megabytes saved."""
        return round(self.saved_kb / 1024, 2)

    def __repr__(self) -> str:
        status = "OK" if self.success else f"FAIL: {self.error}"
        return f"<ConversionResult {self.input_path.name} → {self.output_path.name} [{status}]>"


def fix_exif_orientation(img: Image.Image) -> Image.Image:
    """
    Correct image orientation based on EXIF metadata.

    Phone cameras often store orientation data that needs to be applied
    for the image to display correctly.
    """
    try:
        from PIL import ExifTags

        exif = img.getexif()
        if not exif:
            return img

        orientation_tag = None
        for key, value in ExifTags.TAGS.items():
            if value == "Orientation":
                orientation_tag = key
                break

        if orientation_tag and orientation_tag in exif:
            orientation = exif[orientation_tag]
            rotation_map = {3: 180, 6: 270, 8: 90}
            if orientation in rotation_map:
                img = img.rotate(rotation_map[orientation], expand=True)
    except Exception:
        pass

    return img


def convert_transparency(img: Image.Image, keep_alpha: bool = False) -> Image.Image:
    """
    Handle transparency for the target output format.

    WebP, AVIF and PNG can store an alpha channel, so the image is passed
    through untouched. Formats without alpha support (JPEG) get flattened
    onto a white background.

    Args:
        img: Source image, possibly in a palette or alpha mode.
        keep_alpha: True when the output format supports transparency.

    Returns:
        An image in a mode the target format can encode.
    """
    if img.mode in ("RGBA", "LA", "PA", "P"):
        if keep_alpha:
            return img.convert("RGBA") if img.mode != "RGBA" else img

        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        if img.mode in ("RGBA", "LA"):
            background.paste(img, mask=img.split()[-1])
        else:
            background.paste(img)
        return background
    return img


def resize_image(img: Image.Image, max_width: int) -> Image.Image:
    """
    Resize image if wider than max_width, maintaining aspect ratio.

    Uses LANCZOS resampling for highest quality downscaling.
    """
    if img.size[0] <= max_width:
        return img

    ratio = max_width / img.size[0]
    new_height = int(img.size[1] * ratio)
    return img.resize((max_width, new_height), Image.Resampling.LANCZOS)


def optimize_to_size(
    img: Image.Image,
    target_kb: float,
    initial_width: int,
    initial_quality: int,
    min_width: int = 400,
    min_quality: int = 30,
    output_format: OutputFormat = None,
) -> Tuple[bytes, int, int, int, float]:
    """
    Iteratively optimize image to meet target file size.

    Uses in-memory BytesIO for fast iteration without disk I/O. Resizes are
    cached per width and quality is searched with a binary-search-like step
    instead of a linear -5 scan, so reaching a target takes far fewer encodes
    than a naive quality sweep.

    Args:
        img: Source image (already EXIF-corrected and in an encodable mode).
        target_kb: Target maximum size in kilobytes.
        initial_width: Starting maximum width.
        initial_quality: Starting quality (1-100).
        min_width: Do not shrink below this width.
        min_quality: Do not drop below this quality.
        output_format: Target format; defaults to WebP.

    Returns:
        Tuple of (image_bytes, final_width, final_height, final_quality, final_size_kb)
    """
    output_format = output_format or FORMATS[DEFAULT_FORMAT]
    current_width = initial_width
    current_quality = initial_quality

    resize_cache: Dict[int, Image.Image] = {}
    best = None

    def encode(width: int, quality: int) -> Tuple[bytes, float]:
        if width not in resize_cache:
            resize_cache[width] = resize_image(img, width)
        buffer = BytesIO()
        resize_cache[width].save(
            buffer, output_format.pil_format, **output_format.save_kwargs(quality, method=6)
        )
        data = buffer.getvalue()
        return data, len(data) / 1024

    while True:
        data, size_kb = encode(current_width, current_quality)

        if size_kb <= target_kb:
            return (
                data,
                resize_cache[current_width].size[0],
                resize_cache[current_width].size[1],
                current_quality,
                size_kb,
            )

        if best is None or size_kb < best[4]:
            best = (
                data,
                resize_cache[current_width].size[0],
                resize_cache[current_width].size[1],
                current_quality,
                size_kb,
            )

        if current_quality > min_quality:
            current_quality = max(min_quality, current_quality - 10)
        elif current_width > min_width:
            next_width = max(min_width, int(current_width * 0.8))
            current_quality = min(initial_quality, 75)
            if next_width >= current_width:
                next_width = max(min_width, current_width - 100)
            current_width = next_width
        else:
            return best


def convert_image(
    input_path: Path,
    output_path: Path,
    max_width: int = 1200,
    quality: int = 80,
    max_size_kb: Optional[float] = None,
    skip_existing: bool = True,
    output_format: str = DEFAULT_FORMAT,
) -> ConversionResult:
    """
    Convert a single image to an optimized WebP (or other) format.

    Args:
        input_path: Path to the source image file.
        output_path: Destination path for the converted output.
        max_width: Maximum allowed width in pixels.
        quality: Initial quality (1-100); ignored for lossless formats.
        max_size_kb: Target maximum file size. If set, auto-optimizes
            quality and/or dimensions to reach it.
        skip_existing: Skip conversion if the output file already exists.
        output_format: Target format name (webp, avif, jpeg, png).

    Returns:
        ConversionResult with details about the operation.
    """
    original_size_kb = input_path.stat().st_size / 1024

    try:
        fmt = resolve_format(output_format)
    except ValueError as exc:
        return ConversionResult(
            input_path=input_path,
            output_path=output_path,
            original_size_kb=original_size_kb,
            final_size_kb=0,
            width=0,
            height=0,
            quality=quality,
            success=False,
            error=str(exc),
        )

    if skip_existing and output_path.exists():
        final_size_kb = output_path.stat().st_size / 1024
        return ConversionResult(
            input_path=input_path,
            output_path=output_path,
            original_size_kb=original_size_kb,
            final_size_kb=final_size_kb,
            width=0,
            height=0,
            quality=quality,
            success=True,
            error="skipped",
            output_format=fmt.name,
        )

    try:
        with Image.open(input_path) as img:
            img.load()
            img = fix_exif_orientation(img)
            img = convert_transparency(img, keep_alpha=fmt.supports_alpha)

            output_path.parent.mkdir(parents=True, exist_ok=True)

            if max_size_kb:
                img_bytes, width, height, final_quality, final_size_kb = optimize_to_size(
                    img, max_size_kb, max_width, quality, output_format=fmt
                )
                with open(output_path, "wb") as f:
                    f.write(img_bytes)
            else:
                img = resize_image(img, max_width)
                img.save(output_path, fmt.pil_format, **fmt.save_kwargs(quality))
                width, height = img.size
                final_size_kb = output_path.stat().st_size / 1024
                final_quality = quality

            return ConversionResult(
                input_path=input_path,
                output_path=output_path,
                original_size_kb=original_size_kb,
                final_size_kb=final_size_kb,
                width=width,
                height=height,
                quality=final_quality,
                success=True,
                output_format=fmt.name,
            )

    except Exception as e:
        return ConversionResult(
            input_path=input_path,
            output_path=output_path,
            original_size_kb=original_size_kb,
            final_size_kb=0,
            width=0,
            height=0,
            quality=quality,
            success=False,
            error=str(e),
            output_format=fmt.name,
        )


def convert_directory(
    input_dir: Path,
    output_dir: Optional[Path] = None,
    max_width: int = 1200,
    quality: int = 80,
    max_size_kb: Optional[float] = None,
    skip_existing: bool = True,
    recursive: bool = False,
    output_format: str = DEFAULT_FORMAT,
) -> List[ConversionResult]:
    """
    Batch convert all supported images in a directory.

    Args:
        input_dir: Source directory containing images.
        output_dir: Destination directory. Defaults to <input_dir>/webp_output.
        max_width: Maximum width in pixels.
        quality: Quality level (1-100); ignored for lossless formats.
        max_size_kb: Target max file size in KB for auto-optimization.
        skip_existing: Skip already converted images.
        recursive: Process subdirectories recursively.
        output_format: Target format name (webp, avif, jpeg, png).

    Returns:
        List of ConversionResult objects for all processed images.
    """
    input_dir = Path(input_dir)
    if output_dir is None:
        output_dir = input_dir / f"{resolve_format(output_format).name}_output"
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        fmt = resolve_format(output_format)
    except ValueError as exc:
        return [
            ConversionResult(
                input_path=input_dir,
                output_path=output_dir,
                original_size_kb=0,
                final_size_kb=0,
                width=0,
                height=0,
                quality=quality,
                success=False,
                error=str(exc),
            )
        ]

    if recursive:
        candidates = input_dir.rglob("*")
    else:
        candidates = input_dir.iterdir()

    output_resolved = output_dir.resolve()
    image_files = []
    for f in candidates:
        if f.suffix.lower() not in SUPPORTED_FORMATS or not f.is_file():
            continue
        try:
            if output_resolved in f.resolve().parents or f.resolve() == output_resolved:
                continue
        except OSError:
            continue
        image_files.append(f)

    image_files.sort()

    results: List[ConversionResult] = []

    for input_path in image_files:
        if recursive:
            relative = input_path.parent.relative_to(input_dir)
            file_output_dir = output_dir / relative
        else:
            file_output_dir = output_dir

        output_name = input_path.stem + fmt.extension
        output_path = file_output_dir / output_name

        result = convert_image(
            input_path=input_path,
            output_path=output_path,
            max_width=max_width,
            quality=quality,
            max_size_kb=max_size_kb,
            skip_existing=skip_existing,
            output_format=fmt.name,
        )
        results.append(result)

    return results
