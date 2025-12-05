#!/usr/bin/env python3
"""
CLI tool to convert LHE files with different compression and weight format options.

This tool allows you to convert Les Houches Event (LHE) files from one format
to another, with options to change compression and weight format.
"""

import argparse
import signal
import sys
from pathlib import Path
from typing import Optional

import pylhe

# We do not want a Python Exception on broken pipe, which happens when piping to 'head' or 'less'
signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def convert_lhe_file(
    input_file: str,
    output_file: Optional[str] = None,
    compress: bool = False,
    weight_format: str = "rwgt",
) -> tuple[int, str]:
    """Convert an LHE file with specified options.

    Args:
        input_file: Path to the input LHE file
        output_file: Path to the output LHE file (None for stdout)
        compress: Whether to compress the output file
        weight_format: Weight format to use ('rwgt', 'init-rwgt', or 'none')
    """
    try:
        # Read the input file
        if input_file == "-":
            lhefile = pylhe.LHEFile.frombuffer(sys.stdin)
        else:
            lhefile = pylhe.LHEFile.fromfile(input_file)

        # Determine weight options based on format
        if weight_format == "rwgt":
            rwgt = True
            weights = False
        elif weight_format == "init-rwgt":
            rwgt = True
            weights = True
        elif weight_format == "none":
            rwgt = False
            weights = False
        else:
            return 1, f"Error: Invalid weight format: {weight_format}"

        # Write the output file
        if output_file is None:
            if compress:
                return (
                    1,
                    f"Error: Compression option ignored when writing to stdout (use `lhe2lhe {input_file} | gzip`)",
                )
            lhefile.write(
                sys.stdout,
                rwgt=rwgt,
                weights=weights,
            )
        else:
            lhefile.tofile(
                output_file,
                gz=compress,
                rwgt=rwgt,
                weights=weights,
            )

    except FileNotFoundError:
        if input_file == "-":
            return 1, "Error: Unable to read from stdin"
        return 1, f"Error: Input file '{input_file}' not found"
    except Exception as e:
        source = "stdin" if input_file == "-" else f"input file '{input_file}'"
        return 1, f"Error during conversion from {source}: {e}"
    return 0, "Conversion successful"


def main() -> None:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Convert LHE files with different compression and weight format options",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhe2lhe input.lhe                                       # Convert to stdout
  lhe2lhe input.lhe output.lhe                           # Basic conversion
  lhe2lhe input.lhe output.lhe.gz --compress             # Compress output
  lhe2lhe input.lhe output.lhe --weight-format init-rwgt # Use init-rwgt format
  lhe2lhe input.lhe.gz output.lhe --weight-format none   # Remove weights
  lhe2lhe input.lhe output.lhe.gz -c -w rwgt             # Short options
  lhe2lhe input.lhe | gzip > output.lhe.gz               # Pipe to compress
  cat input.lhe | lhe2lhe                                 # Convert from stdin to stdout
  lhe2lhe < input.lhe > output.lhe                       # Redirect stdin/stdout

Weight formats:
  rwgt      - Include weights in 'rwgt' format (default)
  init-rwgt - Include weights in 'init-rwgt' format (both rwgt and weights)
  none      - Exclude all weights
        """,
    )

    parser.add_argument(
        "input", nargs="?", default="-", help="Input LHE file (default: stdin)"
    )
    parser.add_argument("output", nargs="?", help="Output LHE file (default: stdout)")

    parser.add_argument(
        "--compress",
        "-c",
        action="store_true",
        help="Compress the output file (ignored if output filename ends with .gz/.gzip)",
    )

    parser.add_argument(
        "--weight-format",
        "-w",
        choices=["rwgt", "init-rwgt", "none"],
        default="rwgt",
        help="Weight format to use in output (default: rwgt)",
    )

    args = parser.parse_args()

    # Validate input file exists (skip validation for stdin)
    if args.input != "-":
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file '{args.input}' does not exist", file=sys.stderr)
            sys.exit(1)

    # Check if output directory exists and create it if needed
    if args.output is not None:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Perform the conversion
    retcode, message = convert_lhe_file(
        args.input,
        args.output,
        args.compress,
        args.weight_format,
    )
    if retcode != 0:
        print(message, file=sys.stderr)
        sys.exit(retcode)


if __name__ == "__main__":
    main()
