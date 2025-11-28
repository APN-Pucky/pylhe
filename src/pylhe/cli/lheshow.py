#!/usr/bin/env python3
"""
CLI tool to display specific events or init block from LHE files.

This tool allows you to view individual events or the initialization block
from Les Houches Event (LHE) files.
"""

import argparse
import sys
from pathlib import Path

import pylhe


def show_event(filepath: str, event_number: int) -> None:
    """Show a specific event from an LHE file.

    Args:
        filepath: Path to the LHE file
        event_number: Event number to display (1-indexed)
    """
    try:
        lhefile = pylhe.LHEFile.fromfile(filepath)

        target_index = event_number

        if target_index < 0:
            print(
                f"Error: Event number must be positive (got {event_number})",
                file=sys.stderr,
            )
            sys.exit(1)

        # Iterate through events to find the target
        i = 0
        for i, event in enumerate(lhefile.events, start=1):
            if i == target_index:
                print(event.tolhe())
                return

        # If we get here, the event number was too high
        print(
            f"Error: Event {event_number} not found in file. File has {i} events.",
            file=sys.stderr,
        )
        sys.exit(1)

    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)


def show_init(filepath: str) -> None:
    """Show the init block from an LHE file.

    Args:
        filepath: Path to the LHE file
    """
    try:
        lhefile = pylhe.LHEFile.fromfile(filepath)
        print(lhefile.init.tolhe())

    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Display specific events or init block from LHE files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lheshow file.lhe --event 45           # Show the 45th event
  lheshow file.lhe --init               # Show the init block
  lheshow file.lhe.gz --event 1         # Show first event from gzipped file
        """,
    )

    parser.add_argument("file", help="LHE file to read from")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--event", type=int, metavar="N", help="Show the Nth event (1-indexed)"
    )
    group.add_argument("--init", action="store_true", help="Show the init block")

    args = parser.parse_args()

    # Validate file path
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File '{args.file}' does not exist", file=sys.stderr)
        sys.exit(1)

    if not file_path.is_file():
        print(f"Error: '{args.file}' is not a file", file=sys.stderr)
        sys.exit(1)

    # Execute the requested action
    if args.event is not None:
        show_event(str(file_path), args.event)
    elif args.init:
        show_init(str(file_path))


if __name__ == "__main__":
    main()
