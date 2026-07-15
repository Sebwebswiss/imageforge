"""Basic tests for ImageForge converter."""

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from imageforge.converter import (
    ConversionResult,
    convert_image,
    convert_directory,
    fix_exif_orientation,
    convert_transparency,
    resize_image,
)


@pytest.fixture
def sample_image(tmp_path):
    """Create a sample JPEG image for testing."""
    img = Image.new("RGB", (2000, 1500), color=(100, 150, 200))
    path = tmp_path / "test_image.jpg"
    img.save(path, "JPEG", quality=90)
    return path


@pytest.fixture
def sample_png_with_alpha(tmp_path):
    """Create a sample RGBA PNG image for testing."""
    img = Image.new("RGBA", (800, 600), color=(100, 150, 200, 128))
    path = tmp_path / "test_alpha.png"
    img.save(path, "PNG")
    return path


class TestConversionResult:
    """Tests for ConversionResult class."""

    def test_compression_ratio(self, tmp_path):
        result = ConversionResult(
            input_path=tmp_path / "in.jpg",
            output_path=tmp_path / "out.webp",
            original_size_kb=1000,
            final_size_kb=100,
            width=800,
            height=600,
            quality=80,
        )
        assert result.compression_ratio == 90.0
        assert result.saved_kb == 900
        assert result.saved_mb == 0.88

    def test_compression_ratio_zero_size(self, tmp_path):
        result = ConversionResult(
            input_path=tmp_path / "in.jpg",
            output_path=tmp_path / "out.webp",
            original_size_kb=0,
            final_size_kb=0,
            width=800,
            height=600,
            quality=80,
        )
        assert result.compression_ratio == 0.0


class TestImageProcessing:
    """Tests for image processing functions."""

    def test_resize_image(self):
        img = Image.new("RGB", (2000, 1500))
        resized = resize_image(img, 1000)
        assert resized.size[0] == 1000
        assert resized.size[1] == 750

    def test_resize_image_no_change(self):
        img = Image.new("RGB", (800, 600))
        resized = resize_image(img, 1000)
        assert resized.size == (800, 600)

    def test_convert_transparency(self):
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
        rgb = convert_transparency(img)
        assert rgb.mode == "RGB"
        assert rgb.size == (100, 100)

    def test_fix_exif_orientation_no_exif(self):
        img = Image.new("RGB", (100, 100))
        result = fix_exif_orientation(img)
        assert result.size == (100, 100)


class TestConvertImage:
    """Tests for the main convert_image function."""

    def test_basic_conversion(self, sample_image, tmp_path):
        output = tmp_path / "output.webp"
        result = convert_image(sample_image, output)

        assert result.success
        assert result.error is None
        assert output.exists()
        assert result.compression_ratio > 0

    def test_skip_existing(self, sample_image, tmp_path):
        output = tmp_path / "output.webp"
        result1 = convert_image(sample_image, output)
        result2 = convert_image(sample_image, output)

        assert result1.success
        assert result2.error == "skipped"

    def test_max_size_optimization(self, sample_image, tmp_path):
        output = tmp_path / "output.webp"
        result = convert_image(sample_image, output, max_size_kb=50)

        assert result.success
        assert result.final_size_kb <= 55  # Allow small margin

    def test_rgba_conversion(self, sample_png_with_alpha, tmp_path):
        output = tmp_path / "output.webp"
        result = convert_image(sample_png_with_alpha, output)

        assert result.success
        assert output.exists()


class TestConvertDirectory:
    """Tests for batch directory conversion."""

    def test_batch_conversion(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        for i in range(3):
            img = Image.new("RGB", (800, 600), color=(i * 50, 100, 200))
            img.save(input_dir / f"image_{i}.jpg", "JPEG")

        output_dir = tmp_path / "output"
        results = convert_directory(input_dir, output_dir)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert output_dir.exists()

    def test_recursive(self, tmp_path):
        input_dir = tmp_path / "input"
        sub_dir = input_dir / "sub"
        sub_dir.mkdir(parents=True)

        img = Image.new("RGB", (800, 600))
        img.save(input_dir / "root.jpg", "JPEG")
        img.save(sub_dir / "nested.jpg", "JPEG")

        output_dir = tmp_path / "output"
        results = convert_directory(input_dir, output_dir, recursive=True)

        assert len(results) == 2
