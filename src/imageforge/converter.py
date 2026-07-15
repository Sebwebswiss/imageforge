"""
Core conversion engine for ImageForge.

Handles image processing, resizing, optimization, and format conversion.
"""

import os
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, List

from PIL import Image


SUPPORTED_FORMATS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".webp"})


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


def convert_transparency(img: Image.Image) -> Image.Image:
    """
    Convert images with transparency to RGB with white background.

    WebP supports transparency, but for web use a white background
    often produces smaller files.
    """
    if img.mode in ("RGBA", "LA", "PA", "P"):
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
    target_kb: int,
    initial_width: int,
    initial_quality: int,
    min_width: int = 400,
    min_quality: int = 30,
) -> Tuple[bytes, int, int, int, int]:
    """
    Iteratively optimize image to meet target file size.

    Uses in-memory BytesIO for fast iteration without disk I/O.

    Returns:
        Tuple of (image_bytes, final_width, final_height, final_quality, final_size_kb)
    """
    current_width = initial_width
    current_quality = initial_quality

    while True:
        resized = resize_image(img, current_width)

        buffer = BytesIO()
        resized.save(buffer, "WEBP", quality=current_quality, method=6)
        size_kb = buffer.tell() / 1024

        if size_kb <= target_kb:
            return buffer.getvalue(), resized.size[0], resized.size[1], current_quality, size_kb

        if current_quality > min_quality:
            current_quality -= 5
        elif current_width > min_width:
            current_width -= 100
            current_quality = min(initial_quality, 75)
        else:
            return buffer.getvalue(), resized.size[0], resized.size[1], current_quality, size_kb


def convert_image(
    input_path: Path,
    output_path: Path,
    max_width: int = 1200,
    quality: int = 80,
    max_size_kb: Optional[int] = None,
    skip_existing: bool = True,
) -> ConversionResult:
    """
    Convert a single image to optimized WebP format.

    Args:
        input_path: Path to the source image file.
        output_path: Destination path for the WebP output.
        max_width: Maximum allowed width in pixels.
        quality: Initial WebP quality (1-100).
        max_size_kb: Target maximum file size. If set, auto-optimizes quality/dimensions.
        skip_existing: Skip conversion if output file already exists.

    Returns:
        ConversionResult with details about the operation.
    """
    original_size_kb = input_path.stat().st_size / 1024

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
        )

    try:
        with Image.open(input_path) as img:
            img = fix_exif_orientation(img)
            img = convert_transparency(img)

            if max_size_kb:
                img_bytes, width, height, final_quality, final_size_kb = optimize_to_size(
                    img, max_size_kb, max_width, quality
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(img_bytes)
            else:
                img = resize_image(img, max_width)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(output_path, "WEBP", quality=quality, method=4)
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
        )


def convert_directory(
    input_dir: Path,
    output_dir: Optional[Path] = None,
    max_width: int = 1200,
    quality: int = 80,
    max_size_kb: Optional[int] = None,
    skip_existing: bool = True,
    recursive: bool = False,
) -> List[ConversionResult]:
    """
    Batch convert all supported images in a directory.

    Args:
        input_dir: Source directory containing images.
        output_dir: Destination directory. Defaults to <input_dir>/webp_output.
        max_width: Maximum width in pixels.
        quality: WebP quality (1-100).
        max_size_kb: Target max file size in KB for auto-optimization.
        skip_existing: Skip already converted images.
        recursive: Process subdirectories recursively.

    Returns:
        List of ConversionResult objects for all processed images.
    """
    if output_dir is None:
        output_dir = input_dir / "webp_output"

    output_dir.mkdir(parents=True, exist_ok=True)

    if recursive:
        image_files = sorted(
            f for f in input_dir.rglob("*")
            if f.suffix.lower() in SUPPORTED_FORMATS and f.is_file()
        )
    else:
        image_files = sorted(
            f for f in input_dir.iterdir()
            if f.suffix.lower() in SUPPORTED_FORMATS and f.is_file()
        )

    results: List[ConversionResult] = []

    for input_path in image_files:
        if recursive:
            relative = input_path.parent.relative_to(input_dir)
            file_output_dir = output_dir / relative
        else:
            file_output_dir = output_dir

        output_name = input_path.stem + ".webp"
        output_path = file_output_dir / output_name

        result = convert_image(
            input_path=input_path,
            output_path=output_path,
            max_width=max_width,
            quality=quality,
            max_size_kb=max_size_kb,
            skip_existing=skip_existing,
        )
        results.append(result)

    return results
