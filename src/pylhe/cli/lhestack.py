#!/usr/bin/env python3
"""
CLI tool to stack multiple LHE files into a single file.

This tool is the inverse of lheunstack. It takes multiple LHE files
(typically split by process ID) and combines them into a single LHE file
with a merged initialization section containing all process information.
"""

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

import pylhe


def check_init_consistency(init_files: list[pylhe.LHEInit]) -> bool:
    """
    Check if LHE initialization sections are consistent for stacking.

    For stacking, we require the initInfo and weightgroup to be identical,
    but procInfo can differ (that's what we're combining).

    Args:
        init_files: List of LHEInit objects to check

    Returns:
        True if init sections are consistent for stacking
    """
    if len(init_files) < 2:
        return True

    reference_init = init_files[0]

    for i, init in enumerate(init_files[1:], 1):
        # Check initInfo compatibility (beam info, etc.)
        if reference_init.initInfo != init.initInfo:
            print(
                f"Error: File {i + 1} has different beam/run information",
                file=sys.stderr,
            )
            return False

        # Check weightgroup compatibility
        if reference_init.weightgroup != init.weightgroup:
            print(
                f"Error: File {i + 1} has different weight group configuration",
                file=sys.stderr,
            )
            return False

    return True


def stack_lhe_files(
    input_files: list[str],
    output_file: str,
    new_ids: bool = False,
    rwgt: bool = True,
    weights: bool = True,
) -> None:
    """
    Stack multiple LHE files into a single output file.

    Combines process information from all input files into a single
    initialization section, then merges all events.

    Args:
        input_files: List of paths to input LHE files
        output_file: Path to the output LHE file
        new_ids: Whether to remap process IDs to ensure uniqueness
        rwgt: Whether to preserve rwgt weights in output
        weights: Whether to preserve event weights in output
    """
    # Read all input files and their initialization sections
    lhefiles: list[pylhe.LHEFile] = []
    init_sections = []
    all_proc_info = []

    print(f"Reading {len(input_files)} input files...")

    def map_ids(a: int, b: int, max_b: int) -> int:
        if not new_ids:
            return a
        return a * max_b + b

    for index, input_file in enumerate(input_files):
        lhefile = pylhe.LHEFile.fromfile(input_file)

        lhefiles.append(lhefile)
        init_sections.append(lhefile.init)

        newprocs = []
        # map process IDs to ensure uniqueness
        for proc in lhefile.init.procInfo:
            newproc = pylhe.LHEProcInfo(
                xSection=proc.xSection,
                error=proc.error,
                unitWeight=proc.unitWeight,
                procId=proc.procId,
            )
            newproc.procId = map_ids(proc.procId, index, len(input_files))
            newprocs.append(newproc)
        all_proc_info.extend(newprocs)

    # Check initialization section consistency
    print("Checking initialization section consistency...")
    if not check_init_consistency(init_sections):
        print(
            "Error: Input files have incompatible initialization sections.",
            file=sys.stderr,
        )
        print(
            "Files must have matching beam info and weight groups to be stacked.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Initialization sections are compatible.")

    # Check for duplicate process IDs
    proc_ids = [proc.procId for proc in all_proc_info]
    if len(proc_ids) != len(set(proc_ids)):
        print(
            "Warning: Duplicate process IDs found. This may indicate files weren't properly unstacked.",
            file=sys.stderr,
        )

    # Create merged initialization section
    reference_init = init_sections[0]
    merged_init = pylhe.LHEInit(
        reference_init.initInfo,
        all_proc_info,  # Combined process information
        reference_init.weightgroup,
        LHEVersion=reference_init.LHEVersion,
    )

    # Create merged file with events from all input files
    def stacked_events() -> Iterable[pylhe.LHEEvent]:
        """Generator that yields events from all input files in sequence."""
        for index, lhefile in enumerate(lhefiles):
            for e in lhefile.events:
                e.eventinfo.pid = map_ids(e.eventinfo.pid, index, len(input_files))
                yield e

    # Create output file
    stacked_file = pylhe.LHEFile(init=merged_init, events=stacked_events())

    # Write the stacked file
    stacked_file.tofile(output_file, rwgt=rwgt, weights=weights)
    print(f"Successfully wrote stacked file: {output_file}")


def main() -> None:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Stack multiple LHE files into a single file (inverse of lheunstack)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhestack file_proc81.lhe file_proc82.lhe combined.lhe        # Stack process files
  lhestack split_*.lhe merged.lhe                             # Stack all split files
  lhestack a.lhe b.lhe c.lhe stacked.lhe --no-weights        # Stack without preserving weights
  lhestack proc1.lhe proc2.lhe result.lhe.gz --rwgt          # Include rwgt weights, compressed output
        """,
    )

    parser.add_argument(
        "input_files",
        nargs="+",
        help="Input LHE files to stack (typically split by process ID)",
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
        "--new-ids", action="store_true", help="Remap process IDs to ensure uniqueness"
    )

    parser.add_argument(
        "--rwgt",
        action="store_true",
        help="Use rwgt section if present in the input files",
    )

    args = parser.parse_args()

    # Validate arguments
    if len(args.input_files) < 2:
        print(
            "Error: At least 2 input files are required for stacking", file=sys.stderr
        )
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

    # Stack the files
    stack_lhe_files(
        args.input_files,
        args.output_file,
        new_ids=args.new_ids,
        rwgt=args.rwgt,
        weights=not args.no_weights,
    )


if __name__ == "__main__":
    main()
