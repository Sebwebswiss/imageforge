"""Basic tests for ImageForge converter."""

import pytest
from PIL import Image

from imageforge.converter import (
    FORMATS,
    ConversionResult,
    convert_directory,
    convert_image,
    convert_transparency,
    fix_exif_orientation,
    resize_image,
    resolve_format,
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


class TestOutputFormats:
    """Tests for the export format registry."""

    def test_all_formats_registered(self):
        assert set(FORMATS) == {"webp", "avif", "jpeg", "png"}

    def test_resolve_format_defaults_to_webp(self):
        assert resolve_format("webp").pil_format == "WEBP"

    def test_resolve_format_aliases(self):
        assert resolve_format("jpg") is resolve_format("jpeg")
        assert resolve_format(".PNG") is resolve_format("png")
        assert resolve_format("  WebP  ") is resolve_format("webp")

    def test_resolve_format_rejects_unknown(self):
        with pytest.raises(ValueError, match="Nepodržan format"):
            resolve_format("tiff-out")

    def test_jpeg_declares_no_alpha_support(self):
        assert resolve_format("jpeg").supports_alpha is False
        assert resolve_format("webp").supports_alpha is True
        assert resolve_format("avif").supports_alpha is True
        assert resolve_format("png").supports_alpha is True

    def test_png_save_kwargs_ignore_quality(self):
        assert "quality" not in resolve_format("png").save_kwargs(90)

    @pytest.mark.parametrize("fmt,ext", [("webp", ".webp"), ("avif", ".avif"), ("jpeg", ".jpg")])
    def test_extension_per_format(self, fmt, ext):
        assert resolve_format(fmt).extension == ext


class TestConvertToFormat:
    """Tests for converting to non-default output formats."""

    @pytest.mark.parametrize("fmt", ["webp", "jpeg", "png"])
    def test_directory_conversion_writes_right_extension(self, tmp_path, fmt):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        Image.new("RGB", (400, 300), (10, 120, 200)).save(input_dir / "pic.jpg", "JPEG")

        output_dir = tmp_path / f"out-{fmt}"
        results = convert_directory(input_dir, output_dir, output_format=fmt)

        assert len(results) == 1
        assert results[0].success
        assert results[0].output_format == fmt
        expected = output_dir / ("pic" + resolve_format(fmt).extension)
        assert expected.exists()

    def test_default_output_dir_is_format_aware(self, tmp_path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        Image.new("RGB", (400, 300), (10, 120, 200)).save(input_dir / "pic.jpg", "JPEG")

        convert_directory(input_dir, output_format="avif")

        assert (input_dir / "avif_output" / "pic.avif").exists()

    def test_webp_preserves_alpha_channel(self, sample_png_with_alpha, tmp_path):
        output = tmp_path / "alpha.webp"
        result = convert_image(sample_png_with_alpha, output, output_format="webp")

        assert result.success
        with Image.open(output) as img:
            assert img.mode == "RGBA"

    def test_png_preserves_alpha_channel(self, sample_png_with_alpha, tmp_path):
        output = tmp_path / "alpha.png"
        result = convert_image(sample_png_with_alpha, output, output_format="png")

        assert result.success
        with Image.open(output) as img:
            assert img.mode == "RGBA"

    def test_jpeg_flattens_alpha_to_white(self, tmp_path):
        src = Image.new("RGBA", (100, 100), (255, 0, 0, 0))
        src_path = tmp_path / "clear.png"
        src.save(src_path, "PNG")

        output = tmp_path / "flat.jpg"
        result = convert_image(src_path, output, output_format="jpeg")

        assert result.success
        with Image.open(output) as img:
            assert img.mode == "RGB"
            assert img.getpixel((50, 50)) == (255, 255, 255)

    def test_unknown_format_fails_gracefully(self, sample_image, tmp_path):
        result = convert_image(sample_image, tmp_path / "x.out", output_format="bmp7")

        assert result.success is False
        assert "Nepodržan format" in result.error


class TestRecursiveOutputExclusion:
    """Regression tests: recursive mode must not re-ingest its own output."""

    def test_recursive_skips_default_output_dir(self, tmp_path):
        input_dir = tmp_path / "in"
        sub_dir = input_dir / "sub"
        sub_dir.mkdir(parents=True)

        Image.new("RGB", (400, 300), (200, 50, 50)).save(input_dir / "root.jpg", "JPEG")
        Image.new("RGB", (400, 300), (50, 200, 50)).save(sub_dir / "nested.jpg", "JPEG")

        first = convert_directory(input_dir, recursive=True)
        assert len(first) == 2

        second = convert_directory(input_dir, recursive=True)
        assert len(second) == 2
        assert all(r.error == "skipped" for r in second)

    def test_recursive_skips_custom_output_dir_inside_input(self, tmp_path):
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        Image.new("RGB", (400, 300), (20, 20, 200)).save(input_dir / "pic.jpg", "JPEG")

        output_dir = input_dir / "custom_out"
        convert_directory(input_dir, output_dir, recursive=True)

        again = convert_directory(input_dir, output_dir, recursive=True)
        assert all(r.error == "skipped" for r in again)


class TestOptimizeToSize:
    """Tests for the size-targeting optimization loop."""

    def test_reaches_target_on_noisy_image(self, sample_image, tmp_path):
        output = tmp_path / "small.webp"
        result = convert_image(sample_image, output, max_size_kb=20)

        assert result.success
        assert result.final_size_kb <= 25

    def test_optimize_returns_smallest_attempt(self, sample_image, tmp_path):
        output = tmp_path / "hard.webp"
        result = convert_image(sample_image, output, max_size_kb=1)

        assert result.success
        assert result.width >= 400

    def test_optimize_never_shrinks_below_min_width(self, sample_image, tmp_path):
        output = tmp_path / "floor.webp"
        result = convert_image(sample_image, output, max_size_kb=1)

        assert result.success
        assert result.width >= 400
        assert result.quality >= 30


class TestCompressionDeltaDisplay:
    """The CLI must render growth as +X% and shrinkage as -X%."""

    def test_ratio_is_negative_when_file_grows(self, tmp_path):
        grew = ConversionResult(
            input_path=tmp_path / "a.png",
            output_path=tmp_path / "a.jpg",
            original_size_kb=100,
            final_size_kb=200,
            width=100,
            height=100,
            quality=80,
        )
        assert grew.compression_ratio == -100.0
        assert abs(grew.compression_ratio) == 100.0
