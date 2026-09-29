"""Tests for the ImageForge command-line interface."""

import re
import sys

import pytest
from PIL import Image

from imageforge.cli import main, prompt_format

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def plain(text):
    """Strip ANSI colour codes so assertions can match on literal text."""
    return ANSI.sub("", text)


@pytest.fixture
def photo(tmp_path):
    """Create a single source image for CLI runs."""
    path = tmp_path / "photo.jpg"
    Image.new("RGB", (600, 400), (180, 90, 30)).save(path, "JPEG")
    return path


def run_cli(args, capsys):
    """Run main() and return (exit_code, colour-stripped stdout)."""
    code = 0
    try:
        main(args)
    except SystemExit as exit_info:
        code = exit_info.code or 0
    return code, plain(capsys.readouterr().out)


class TestFormatSelection:
    """--format flag and the interactive fallback."""

    def test_explicit_format_flag(self, photo, tmp_path, capsys):
        out = tmp_path / "out.avif"
        code, stdout = run_cli([str(photo), "-o", str(out), "--format", "avif"], capsys)

        assert code == 0
        assert out.exists()
        assert "AVIF" in stdout

    def test_invalid_format_rejected_by_argparse(self, photo, tmp_path, capsys):
        with pytest.raises(SystemExit) as exit_info:
            main([str(photo), "-o", str(tmp_path / "x"), "--format", "tiff"])
        assert exit_info.value.code == 2

    def test_prompt_falls_back_when_not_interactive(self, monkeypatch):
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
        assert prompt_format() == "webp"

    def test_prompt_falls_back_when_stdout_not_tty(self, monkeypatch):
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False, raising=False)
        assert prompt_format() == "webp"

    @pytest.mark.parametrize(
        "typed,expected",
        [("1", "webp"), ("2", "avif"), ("3", "jpeg"), ("4", "png")],
    )
    def test_prompt_accepts_number(self, monkeypatch, typed, expected):
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
        monkeypatch.setattr("builtins.input", lambda _prompt="": typed)
        assert prompt_format() == expected

    def test_prompt_accepts_name_and_empty_default(self, monkeypatch):
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)

        monkeypatch.setattr("builtins.input", lambda _prompt="": "avif")
        assert prompt_format() == "avif"

        monkeypatch.setattr("builtins.input", lambda _prompt="": "")
        assert prompt_format() == "webp"

    def test_prompt_rejects_garbage_then_accepts(self, monkeypatch, capsys):
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)

        answers = iter(["nonsense", "jpeg"])
        monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

        assert prompt_format() == "jpeg"
        assert "Nepoznat format" in plain(capsys.readouterr().out)


class TestOutputReporting:
    """Growth must be shown as +X%, never as --X%."""

    def test_growth_rendered_with_single_plus(self, tmp_path, capsys):
        solid = tmp_path / "solid.png"
        Image.new("RGB", (64, 64), (12, 34, 56)).save(solid, "PNG")

        out = tmp_path / "grown.jpg"
        code, stdout = run_cli(
            [str(solid), "-o", str(out), "--format", "jpeg", "-q", "100"], capsys
        )

        assert code == 0
        assert out.stat().st_size > solid.stat().st_size
        assert "(+" in stdout
        assert "--" not in stdout

    def test_reports_output_directory(self, photo, tmp_path, capsys):
        code, stdout = run_cli([str(photo), "--format", "png"], capsys)

        assert code == 0
        assert "png_output" in stdout

    def test_missing_input_exits_with_error(self, tmp_path, capsys):
        code, stdout = run_cli([str(tmp_path / "nope.jpg")], capsys)
        assert code == 1
        assert "ne postoji" in stdout


class TestBatchOutputReporting:
    """Directory runs report per-file and summary lines."""

    def test_recursive_batch_summary(self, tmp_path, capsys):
        input_dir = tmp_path / "photos"
        (input_dir / "sub").mkdir(parents=True)
        Image.new("RGB", (500, 400), (10, 10, 10)).save(input_dir / "one.jpg", "JPEG")
        Image.new("RGB", (500, 400), (250, 250, 250)).save(input_dir / "sub" / "two.jpg", "JPEG")

        code, stdout = run_cli([str(input_dir), "-r", "--format", "webp"], capsys)

        assert code == 0
        assert "Konvertovano:  2" in stdout
        assert "Neuspjelo:  0" in stdout
