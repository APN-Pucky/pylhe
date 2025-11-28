#!/usr/bin/env python3
"""
CLI tool to merge LHE files with identical initialization sections.

This tool merges multiple Les Houches Event (LHE) files into a single output file,
but only if all input files have exactly the same initialization section.
This ensures the merged file maintains physical consistency.
"""

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

import pylhe


def check_init_compatibility(init_files: list[pylhe.LHEInit]) -> bool:
    """
    Check if all LHEInit objects are identical.

    Args:
        init_files: List of LHEInit objects to compare

    Returns:
        True if all init sections are identical, False otherwise
    """
    if len(init_files) < 2:
        return True

    reference_init = init_files[0]

    return all(reference_init == init for init in init_files[1:])


def merge_lhe_files(
    input_files: list[str],
    output_file: str,
    rwgt: bool = True,
    weights: bool = True,
) -> None:
    """
    Merge multiple LHE files into a single output file.

    Args:
        input_files: List of paths to input LHE files
        output_file: Path to the output LHE file
        rwgt: Whether to preserve rwgt weights in output
        weights: Whether to preserve event weights in output
    """
    # Read all input files and their initialization sections
    lhefiles = []
    init_sections = []
    total_events = 0

    print(f"Reading {len(input_files)} input files...")

    for input_file in input_files:
        try:
            lhefile = pylhe.LHEFile.fromfile(input_file)
            event_count = pylhe.LHEFile.count_events(input_file)
            print(f"  {input_file}: {event_count} events")

            lhefiles.append(lhefile)
            init_sections.append(lhefile.init)
            total_events += event_count

        except Exception as e:
            print(f"Error reading input file '{input_file}': {e}", file=sys.stderr)
            sys.exit(1)

    # Check that all initialization sections are identical
    print("Checking initialization section compatibility...")
    if not check_init_compatibility(init_sections):
        print(
            "Error: Input files have different initialization sections.",
            file=sys.stderr,
        )
        print(
            "All files must have identical <init> blocks to be merged.", file=sys.stderr
        )
        sys.exit(1)

    print("All initialization sections are compatible.")

    # Create merged file with events from all input files
    def merged_events() -> Iterable[pylhe.LHEEvent]:
        """Generator that yields events from all input files in sequence."""
        for lhefile in lhefiles:
            yield from lhefile.events

    # Create output file
    merged_file = pylhe.LHEFile(init=lhefiles[0].init, events=merged_events())

    # Write the merged file
    print(f"Writing merged file with {total_events} total events...")
    merged_file.tofile(output_file, rwgt=rwgt, weights=weights)
    print(f"Successfully wrote merged file: {output_file}")


def main() -> None:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Merge LHE files with identical initialization sections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhemerge input1.lhe input2.lhe input3.lhe output.lhe         # Merge 3 files into output.lhe
  lhemerge split_*.lhe merged.lhe.gz                          # Merge all split files (compressed)
  lhemerge file1.lhe file2.lhe result.lhe --no-weights       # Merge without preserving weights
  lhemerge a.lhe b.lhe c.lhe combined.lhe --rwgt              # Include rwgt weights
        """,
    )

    parser.add_argument(
        "input_files",
        nargs="+",
        help="Input LHE files to merge (must have identical initialization sections)",
    )

    parser.add_argument(
        "output_file",
        help="Output LHE file path (can include .gz extension for compression)",
    )

    parser.add_argument(
        "--no-weights",
        action="store_true",
        help="Do not preserve event weights in output file",
    )

    parser.add_argument(
        "--rwgt",
        action="store_true",
        help="Use rwgt section if present in the input files",
    )

    args = parser.parse_args()

    # Validate arguments
    if len(args.input_files) < 2:
        print("Error: At least 2 input files are required for merging", file=sys.stderr)
        sys.exit(1)

    # Check that all input files exist
    for input_file in args.input_files:
        input_path = Path(input_file)
        if not input_path.exists():
            print(f"Error: Input file '{input_file}' does not exist", file=sys.stderr)
            sys.exit(1)
        if not input_path.is_file():
            print(f"Error: '{input_file}' is not a file", file=sys.stderr)
            sys.exit(1)

    # Check for duplicate input files
    if len(set(args.input_files)) != len(args.input_files):
        print("Error: Duplicate input files detected", file=sys.stderr)
        sys.exit(1)

    # Merge the files
    merge_lhe_files(
        args.input_files,
        args.output_file,
        rwgt=args.rwgt,
        weights=not args.no_weights,
    )


if __name__ == "__main__":
    main()
