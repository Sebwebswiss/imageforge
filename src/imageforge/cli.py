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
    width = 47
    title = f"ImageForge v{__version__}"
    tagline = "Alat za profesionalnu konverziju slika"
    blank = " " * width
    title_pad = " " * (width - 3 - len(title))
    tagline_pad = " " * (width - 3 - len(tagline))

    banner = f"""
{CYAN}{BOLD}  ╔{'═' * width}╗
  ║{blank}║
  ║   {MAGENTA}ImageForge{CYAN} {WHITE}v{__version__}{title_pad}{CYAN}{BOLD}║
  ║   {DIM}{tagline}{tagline_pad}{RESET}{CYAN}{BOLD}║
  ║{blank}║
  ╚{'═' * width}╝{RESET}
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

    print(f"\n{BOLD}  Format izvoza:{RESET}")
    for i, key in enumerate(FORMAT_CHOICES, 1):
        marker = f" {GREEN}(zadano){RESET}" if key == DEFAULT_FORMAT else ""
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
            f"{DIM}(već konvertovano){RESET}"
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
    print(f"{BOLD}  Sažetak{RESET}")
    print(f"{'─' * 50}")
    print(f"  Konvertovano:  {GREEN}{len(successful)}{RESET}", end="")
    print(f"  │  Preskočeno:  {YELLOW}{len(skipped)}{RESET}", end="")
    print(f"  │  Neuspjelo:  {RED}{len(failed)}{RESET}")
    print(f"  Original:      {total_original:,.0f} KB ({total_original/1024:.1f} MB)")
    print(f"  Rezultat:      {total_final:,.0f} KB ({total_final/1024:.1f} MB)")
    print(f"  {GREEN}Ušteda:       {total_saved:,.0f} KB ({total_saved/1024:.1f} MB){RESET}")
    print(f"{'─' * 50}\n")


def cmd_convert(args: argparse.Namespace) -> None:
    """Handle the convert command."""
    input_path = Path(args.input).resolve()

    if not input_path.exists():
        print(f"\n  {RED}Greška:{RESET} '{args.input}' ne postoji.\n")
        sys.exit(1)

    output_format = args.format or prompt_format()

    try:
        fmt = resolve_format(output_format)
    except ValueError as exc:
        print(f"\n  {RED}Greška:{RESET} {exc}\n")
        sys.exit(2)

    output_path = Path(args.output).resolve() if args.output else None
    user_chose_output = output_path is not None

    if input_path.is_file():
        if output_path is None:
            output_path = (
                input_path.parent / f"{fmt.name}_output" / (input_path.stem + fmt.extension)
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(
            f"\n{BOLD}  Konvertovanje:{RESET} {input_path.name}  {DIM}→{RESET} {fmt.name.upper()}"
        )

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
        print(f"\n{BOLD}  Skeniranje:{RESET} {input_path}  {DIM}→{RESET} {fmt.name.upper()}")

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
            print(f"  {DIM}Datoteke su zapisane u:{RESET} {target}\n")
    else:
        print(f"\n  {YELLOW}Nije pronađena nijedna podržana slika.{RESET}\n")


def main(argv: Optional[List[str]] = None) -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="imageforge",
        description=(
            f"{CYAN}ImageForge{RESET} - Professional image conversion " "with smart optimization."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{BOLD}Primjeri:{RESET}
  %(prog)s ./photos                          Konvertira sve slike iz ./photos (pita format)
  %(prog)s ./photos --format avif            Izvoz u AVIF
  %(prog)s ./photos --format jpeg            Izvoz u JPEG
  %(prog)s photo.jpg -o out.webp             Konvertovanje jedne slike
  %(prog)s ./photos --max-size 100           Cilj: najviše 100 KB po datoteci
  %(prog)s ./photos --width 800 --quality 75 Vlastite dimenzije i kvalitet
  %(prog)s ./site --recursive                Uključuje podmape

{BOLD}Podržani formati:{RESET}
  JPEG, PNG, BMP, TIFF, GIF → WebP (zadano), AVIF, JPEG, PNG
""",
    )

    parser.add_argument(
        "input",
        help="Ulazna slika ili mapa sa slikama",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Izlazna datoteka ili mapa (zadano: <input>/<format>_output)",
    )
    parser.add_argument(
        "--format",
        choices=FORMAT_CHOICES,
        default=None,
        metavar="{" + ",".join(FORMAT_CHOICES) + "}",
        help=(
            f"Format izvoza (zadano: {DEFAULT_FORMAT}; "
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
        help="Ciljana veličina datoteke u KB uz automatsku optimizaciju",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Obradi podmape rekurzivno",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Konvertira ponovno iako izlazna datoteka postoji",
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
