#!/usr/bin/env python3
import argparse
from collections.abc import Iterable
from pathlib import Path

import pylhe


def lhe_unstack(lhefile_path: str) -> list[pylhe.LHEFile]:
    """
    Split LHE file by process ID using two-pass approach for memory safety.

    First pass: identify all process IDs present in the file
    Second pass: create generators that filter events for each process ID
    """
    # Read init section
    lhefile = pylhe.LHEFile.fromfile(lhefile_path)
    lhe_init = lhefile.init

    # Create separate LHE files for each process ID found
    result_files = []
    for proc_info in lhe_init.procInfo:

        def _events_for_process(target_proc_id: int) -> Iterable[pylhe.LHEEvent]:
            """Generator that yields only events for the target process ID."""
            # We open the file again each time to avoid memory issues
            for event in pylhe.LHEFile.fromfile(lhefile_path).events:
                if event.eventinfo.pid == target_proc_id:
                    yield event

        newinit = pylhe.LHEInit(
            lhe_init.initInfo,
            [proc_info],
            lhe_init.weightgroup,
            LHEVersion=lhe_init.LHEVersion,
        )
        # Create new LHE file with filtered events
        newlhef = pylhe.LHEFile(
            init=newinit, events=_events_for_process(proc_info.procId)
        )
        result_files.append(newlhef)

    return result_files


def main() -> None:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Takes a single LHE file and splits the different processes into separate LHE files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lheunstack file.lhe                      # Split single file into separate process files
        """,
    )

    parser.add_argument("file", help="LHE file to analyze")

    args = parser.parse_args()

    # Split the LHE file by process ID
    lhe_files = lhe_unstack(args.file)

    input_path = Path(args.file)

    for lhef in lhe_files:
        # Get the process ID from the first event to name the file
        proc_id = lhef.init.procInfo[0].procId

        output_filename = f"{input_path.stem}_proc{proc_id}{input_path.suffix}"
        lhef.tofile(output_filename)
        print(f"Created {output_filename}")


if __name__ == "__main__":
    main()
