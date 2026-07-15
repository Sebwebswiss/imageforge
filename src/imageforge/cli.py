"""
Command-line interface for ImageForge.

Provides colorful, user-friendly CLI with progress tracking and statistics.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, List

from . import __version__
from .converter import ConversionResult, convert_directory, convert_image


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
  ║   {MAGENTA}ImageSharp{CYAN} {WHITE}v{__version__}{CYAN}{BOLD}                          ║
  ║   {DIM}Professional Image Conversion Toolkit{RESET}{CYAN}{BOLD}       ║
  ║                                               ║
  ╚═══════════════════════════════════════════════╝{RESET}
"""
    print(banner)


def print_result(result: ConversionResult, index: int) -> None:
    """Print formatted conversion result for a single file."""
    if result.error == "skipped":
        print(f"  {YELLOW}⊘{RESET}  {DIM}{result.input_path.name}{RESET} {DIM}(already converted){RESET}")
        return

    if not result.success:
        print(f"  {RED}✗{RESET}  {result.input_path.name}: {RED}{result.error}{RESET}")
        return

    ratio = result.compression_ratio
    color = GREEN if ratio > 50 else YELLOW if ratio > 20 else RED
    print(
        f"  {GREEN}✓{RESET}  {WHITE}{result.input_path.name}{RESET}"
        f" → {result.output_path.name}"
        f"  {result.final_size_kb:.1f} KB"
        f"  {color}(-{ratio}%){RESET}"
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

    output_path = Path(args.output).resolve() if args.output else None

    if input_path.is_file():
        if output_path is None:
            output_path = input_path.parent / "webp_output" / (input_path.stem + ".webp")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"\n{BOLD}  Converting:{RESET} {input_path.name}\n")

        result = convert_image(
            input_path=input_path,
            output_path=output_path,
            max_width=args.width,
            quality=args.quality,
            max_size_kb=args.max_size,
            skip_existing=not args.force,
        )
        results = [result]
    else:
        print(f"\n{BOLD}  Scanning:{RESET} {input_path}\n")

        results = convert_directory(
            input_dir=input_path,
            output_dir=output_path,
            max_width=args.width,
            quality=args.quality,
            max_size_kb=args.max_size,
            skip_existing=not args.force,
            recursive=args.recursive,
        )

    for i, result in enumerate(results, 1):
        print_result(result, i)

    if results:
        print_summary(results)
    else:
        print(f"\n  {YELLOW}No supported images found.{RESET}\n")


def main(argv: Optional[List[str]] = None) -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="imageforge",
        description=f"{CYAN}ImageSharp{RESET} - Professional image to WebP conversion with smart optimization.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{BOLD}Examples:{RESET}
  %(prog)s ./photos                          Convert all images in ./photos
  %(prog)s ./photos -o ./optimized           Custom output directory
  %(prog)s photo.jpg                         Convert a single image
  %(prog)s ./photos --max-size 100           Target 100KB max file size
  %(prog)s ./photos --width 800 --quality 75 Custom dimensions and quality
  %(prog)s ./site --recursive                Include subdirectories

{BOLD}Supported formats:{RESET}
  JPEG, PNG, BMP, TIFF, GIF → WebP
""",
    )

    parser.add_argument(
        "input",
        help="Input image file or directory containing images",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file or directory (default: <input>/webp_output)",
    )
    parser.add_argument(
        "-w", "--width",
        type=int,
        default=1200,
        metavar="PX",
        help="Maximum width in pixels (default: 1200)",
    )
    parser.add_argument(
        "-q", "--quality",
        type=int,
        default=80,
        metavar="1-100",
        help="WebP quality level (default: 80)",
    )
    parser.add_argument(
        "-s", "--max-size",
        type=int,
        default=None,
        metavar="KB",
        help="Target max file size in KB with auto-optimization",
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Process subdirectories recursively",
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Re-convert even if output file exists",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args(argv)
    print_banner()
    cmd_convert(args)


if __name__ == "__main__":
    main()
