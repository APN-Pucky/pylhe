#!/usr/bin/env python3
"""
CLI tool to split LHE files into multiple smaller files.

This tool splits Les Houches Event (LHE) files into multiple output files
with approximately equal numbers of events distributed among them.
"""

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

import pylhe


def split_lhe_file(
    input_file: str,
    output_base: str,
    num_files: int,
    rwgt: bool = True,
    weights: bool = True,
) -> None:
    """
    Split an LHE file into multiple output files.

    Args:
        input_file: Path to the input LHE file
        output_base: Base name for output files including .lhe or .lhe.gz extension
        num_files: Number of output files to create
        rwgt: Whether to use rwgt section if present in the input file
        weights: Whether to preserve event weights in output
    """
    # Read the LHE file
    try:
        lhefile = pylhe.LHEFile.fromfile(input_file)
        total_events = pylhe.LHEFile.count_events(input_file)
        print(f"Read LHE file {input_file} with {total_events} events.")
    except Exception as e:
        print(f"Error reading input file '{input_file}': {e}", file=sys.stderr)
        sys.exit(1)

    # events per file
    events_per_file = total_events // num_files + (
        1 if total_events % num_files != 0 else 0
    )

    # Create iterator from events
    events_iter = iter(lhefile.events)

    def _generator() -> Iterable[pylhe.LHEEvent]:
        for _ in range(events_per_file):
            try:
                yield next(events_iter)
            except StopIteration:
                break

    for i in range(num_files):
        output_filename = f"{Path(output_base).stem}_{i}{Path(output_base).suffix}"
        new_file = pylhe.LHEFile(init=lhefile.init, events=_generator())
        new_file.tofile(output_filename, rwgt=rwgt, weights=weights)
        print(f"Wrote {output_filename} with ~{events_per_file} events.")


def main() -> None:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Split LHE events from input file into multiple output files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhesplit input.lhe output.lhe 3           # Split into output_0.lhe, output_1.lhe, output_2.lhe
  lhesplit events.lhe split.lhe.gz 5        # Split into split_0.lhe.gz, split_1.lhe.gz, ... (compressed)
  lhesplit input.lhe events.lhe 2           # Split into events_0.lhe, events_1.lhe
  lhesplit input.lhe output.lhe 4 --no-weights  # Split without preserving event weights
        """,
    )

    parser.add_argument("input_file", help="Input LHE file to split")

    parser.add_argument(
        "output_base",
        help="Base name for output files including .lhe or .lhe.gz extension",
    )

    parser.add_argument(
        "num_files", type=int, help="Number of files to split the events between"
    )

    parser.add_argument(
        "--no-weights",
        action="store_true",
        help="Do not preserve event weights in output files",
    )

    parser.add_argument(
        "--rwgt",
        action="store_true",
        help="Use rwgt section if present in the input file",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.num_files < 2:
        print("Error: Number of files must be >= 2", file=sys.stderr)
        sys.exit(1)

    # Check if input file exists
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Input file '{args.input_file}' does not exist", file=sys.stderr)
        sys.exit(1)

    if not input_path.is_file():
        print(f"Error: '{args.input_file}' is not a file", file=sys.stderr)
        sys.exit(1)

    # Split the file
    split_lhe_file(
        args.input_file,
        args.output_base,
        args.num_files,
        rwgt=args.rwgt,
        weights=not args.no_weights,
    )


if __name__ == "__main__":
    main()
