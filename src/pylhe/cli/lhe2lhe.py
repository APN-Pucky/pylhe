#!/usr/bin/env python3
"""
CLI tool to convert LHE files with different compression and weight format options.

This tool allows you to convert Les Houches Event (LHE) files from one format
to another, with options to change compression and weight format.
"""

import argparse
import sys
from pathlib import Path

import pylhe


def convert_lhe_file(
    input_file: str,
    output_file: str,
    compress: bool = False,
    weight_format: str = "rwgt",
) -> None:
    """Convert an LHE file with specified options.

    Args:
        input_file: Path to the input LHE file
        output_file: Path to the output LHE file
        compress: Whether to compress the output file
        weight_format: Weight format to use ('rwgt', 'init-rwgt', or 'none')
    """
    try:
        # Read the input file
        print(f"Reading input file: {input_file}")
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
            err = f"Invalid weight format: {weight_format}"
            raise ValueError(err)

        # Write the output file
        print(f"Writing output file: {output_file}")
        lhefile.tofile(
            output_file,
            gz=compress,
            rwgt=rwgt,
            weights=weights,
        )

        print("Conversion completed successfully!")

    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during conversion: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Convert LHE files with different compression and weight format options",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhe2lhe input.lhe output.lhe                           # Basic conversion
  lhe2lhe input.lhe output.lhe.gz --compress             # Compress output
  lhe2lhe input.lhe output.lhe --weight-format init-rwgt # Use init-rwgt format
  lhe2lhe input.lhe.gz output.lhe --weight-format none   # Remove weights
  lhe2lhe input.lhe output.lhe.gz -c -w rwgt             # Short options

Weight formats:
  rwgt      - Include weights in 'rwgt' format (default)
  init-rwgt - Include weights in 'init-rwgt' format (both rwgt and weights)
  none      - Exclude all weights
        """,
    )

    parser.add_argument("input", help="Input LHE file")
    parser.add_argument("output", help="Output LHE file")

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

    # Validate input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file '{args.input}' does not exist", file=sys.stderr)
        sys.exit(1)

    # Check if output directory exists and create it if needed
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Perform the conversion
    convert_lhe_file(
        args.input,
        args.output,
        args.compress,
        args.weight_format,
    )


if __name__ == "__main__":
    main()
