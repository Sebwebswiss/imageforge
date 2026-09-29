"""
Command-line interface for ImageForge.

Provides colorful, user-friendly CLI with progress tracking and statistics.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .converter import (
    DEFAULT_FORMAT,
    FORMAT_CHOICES,
    FORMAT_LABELS,
    ConversionResult,
    convert_directory,
    convert_image,
    resolve_format,
)

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
RESET = "\033[0m"


def print_banner() -> None:
    """Print application banner."""
    banner = f"""
{CYAN}{BOLD}  ╔═══════════════════════════════════════════════╗
  ║                                               ║
  ║   {MAGENTA}ImageForge{CYAN} {WHITE}v{__version__}{CYAN}{BOLD}                          ║
  ║   {DIM}Professional Image Conversion Toolkit{RESET}{CYAN}{BOLD}       ║
  ║                                               ║
  ╚═══════════════════════════════════════════════╝{RESET}
"""
    print(banner)


def prompt_format() -> str:
    """
    Ask the user which export format to use.

    Falls back to the default format when stdin is not interactive (pipes,
    CI, cron) so that scripts never block.
    """
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return DEFAULT_FORMAT

    print(f"\n{BOLD}  Export format:{RESET}")
    for i, key in enumerate(FORMAT_CHOICES, 1):
        marker = f" {GREEN}(default){RESET}" if key == DEFAULT_FORMAT else ""
        print(f"  {CYAN}{i}{RESET}) {FORMAT_LABELS[key]}{marker}")

    while True:
        raw = input(f"  {BOLD}Unesi broj ili naziv{RESET} [{DEFAULT_FORMAT}]: ").strip()
        if not raw:
            return DEFAULT_FORMAT

        lowered = raw.lower()
        if lowered.isdigit() and 1 <= int(lowered) <= len(FORMAT_CHOICES):
            return FORMAT_CHOICES[int(lowered) - 1]
        if lowered in FORMAT_CHOICES:
            return lowered
        if lowered in ("jpg", "jpe"):
            return "jpeg"

        print(f"  {RED}Nepoznat format '{raw}'.{RESET} Pokušaj ponovno.")


def print_result(result: ConversionResult, index: int) -> None:
    """Print formatted conversion result for a single file."""
    if result.error == "skipped":
        print(
            f"  {YELLOW}⊘{RESET}  {DIM}{result.input_path.name}{RESET} "
            f"{DIM}(already converted){RESET}"
        )
        return

    if not result.success:
        print(f"  {RED}✗{RESET}  {result.input_path.name}: {RED}{result.error}{RESET}")
        return

    ratio = result.compression_ratio
    color = GREEN if ratio > 50 else YELLOW if ratio > 20 else RED
    delta = f"-{abs(ratio):.1f}%" if ratio >= 0 else f"+{abs(ratio):.1f}%"
    print(
        f"  {GREEN}✓{RESET}  {WHITE}{result.input_path.name}{RESET}"
        f" → {result.output_path.name}"
        f"  {result.final_size_kb:.1f} KB"
        f"  {color}({delta}){RESET}"
    )


def print_summary(results: List[ConversionResult]) -> None:
    """Print detailed summary statistics."""
    successful = [r for r in results if r.success and r.error != "skipped"]
    skipped = [r for r in results if r.error == "skipped"]
    failed = [r for r in results if not r.success]

    total_original = sum(r.original_size_kb for r in results)
    total_final = sum(r.final_size_kb for r in results)
    total_saved = total_original - total_final

    print(f"\n{BOLD}{'─' * 50}{RESET}")
    print(f"{BOLD}  Summary{RESET}")
    print(f"{'─' * 50}")
    print(f"  Converted:  {GREEN}{len(successful)}{RESET}", end="")
    print(f"  │  Skipped:  {YELLOW}{len(skipped)}{RESET}", end="")
    print(f"  │  Failed:  {RED}{len(failed)}{RESET}")
    print(f"  Original:   {total_original:,.0f} KB ({total_original/1024:.1f} MB)")
    print(f"  Final:      {total_final:,.0f} KB ({total_final/1024:.1f} MB)")
    print(f"  {GREEN}Saved:      {total_saved:,.0f} KB ({total_saved/1024:.1f} MB){RESET}")
    print(f"{'─' * 50}\n")


def cmd_convert(args: argparse.Namespace) -> None:
    """Handle the convert command."""
    input_path = Path(args.input).resolve()

    if not input_path.exists():
        print(f"\n  {RED}Error:{RESET} '{args.input}' does not exist.\n")
        sys.exit(1)

    output_format = args.format or prompt_format()

    try:
        fmt = resolve_format(output_format)
    except ValueError as exc:
        print(f"\n  {RED}Error:{RESET} {exc}\n")
        sys.exit(2)

    output_path = Path(args.output).resolve() if args.output else None
    user_chose_output = output_path is not None

    if input_path.is_file():
        if output_path is None:
            output_path = (
                input_path.parent / f"{fmt.name}_output" / (input_path.stem + fmt.extension)
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"\n{BOLD}  Converting:{RESET} {input_path.name}  {DIM}→{RESET} {fmt.name.upper()}")

        result = convert_image(
            input_path=input_path,
            output_path=output_path,
            max_width=args.width,
            quality=args.quality,
            max_size_kb=args.max_size,
            skip_existing=not args.force,
            output_format=fmt.name,
        )
        results = [result]
    else:
        print(f"\n{BOLD}  Scanning:{RESET} {input_path}  {DIM}→{RESET} {fmt.name.upper()}")

        results = convert_directory(
            input_dir=input_path,
            output_dir=output_path,
            max_width=args.width,
            quality=args.quality,
            max_size_kb=args.max_size,
            skip_existing=not args.force,
            recursive=args.recursive,
            output_format=fmt.name,
        )

    for i, result in enumerate(results, 1):
        print_result(result, i)

    if results:
        print_summary(results)
        if not user_chose_output:
            target = (
                input_path / f"{fmt.name}_output"
                if input_path.is_dir()
                else input_path.parent / f"{fmt.name}_output"
            )
            print(f"  {DIM}Files written to:{RESET} {target}\n")
    else:
        print(f"\n  {YELLOW}No supported images found.{RESET}\n")


def main(argv: Optional[List[str]] = None) -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="imageforge",
        description=(
            f"{CYAN}ImageForge{RESET} - Professional image conversion " "with smart optimization."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{BOLD}Examples:{RESET}
  %(prog)s ./photos                          Convert all images in ./photos (asks format)
  %(prog)s ./photos --format avif            Export as AVIF
  %(prog)s ./photos --format jpeg            Export as JPEG
  %(prog)s photo.jpg -o out.webp             Convert a single image
  %(prog)s ./photos --max-size 100           Target 100KB max file size
  %(prog)s ./photos --width 800 --quality 75 Custom dimensions and quality
  %(prog)s ./site --recursive                Include subdirectories

{BOLD}Supported formats:{RESET}
  JPEG, PNG, BMP, TIFF, GIF → WebP (default), AVIF, JPEG, PNG
""",
    )

    parser.add_argument(
        "input",
        help="Input image file or directory containing images",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file or directory (default: <input>/<format>_output)",
    )
    parser.add_argument(
        "--format",
        choices=FORMAT_CHOICES,
        default=None,
        metavar="{" + ",".join(FORMAT_CHOICES) + "}",
        help=(
            f"Export format (default: {DEFAULT_FORMAT}; "
            "asks interactively when omitted in a terminal)"
        ),
    )
    parser.add_argument(
        "-w",
        "--width",
        type=int,
        default=1200,
        metavar="PX",
        help="Maximum width in pixels (default: 1200)",
    )
    parser.add_argument(
        "-q",
        "--quality",
        type=int,
        default=80,
        metavar="1-100",
        help="Quality level (default: 80; ignored for PNG)",
    )
    parser.add_argument(
        "-s",
        "--max-size",
        type=int,
        default=None,
        metavar="KB",
        help="Target max file size in KB with auto-optimization",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Process subdirectories recursively",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Re-convert even if output file exists",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args(argv)
    print_banner()
    cmd_convert(args)


if __name__ == "__main__":
    main()
