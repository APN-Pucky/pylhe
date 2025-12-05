#!/usr/bin/env python3
# ruff: noqa: SIM103
"""
CLI tool to filter LHE files based on various criteria.

This tool filters Les Houches Event (LHE) files based on process ID,
particle PDG IDs (incoming/outgoing), and event numbers.
"""

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Optional

import pylhe


def matches_process_filter(
    event: pylhe.LHEEvent,
    process_ids: Optional[set[int]],
    exclude_process_ids: Optional[set[int]],
) -> bool:
    """Check if event matches process ID filters."""
    if process_ids is not None and event.eventinfo.pid not in process_ids:
        return False
    if exclude_process_ids is not None and event.eventinfo.pid in exclude_process_ids:
        return False
    return True


def matches_particle_filter(
    event: pylhe.LHEEvent,
    incoming_pdgids: Optional[set[int]],
    exclude_incoming_pdgids: Optional[set[int]],
    outgoing_pdgids: Optional[set[int]],
    exclude_outgoing_pdgids: Optional[set[int]],
) -> bool:
    """Check if event matches particle PDG ID filters."""
    # Get incoming particles (status -1)
    incoming_particles = [p for p in event.particles if p.status == -1]
    incoming_ids = {p.id for p in incoming_particles}

    # Get outgoing particles (status 1)
    outgoing_particles = [p for p in event.particles if p.status == 1]
    outgoing_ids = {p.id for p in outgoing_particles}

    # Check incoming particle filters
    if incoming_pdgids is not None and not incoming_ids.intersection(incoming_pdgids):
        return False

    if exclude_incoming_pdgids is not None and incoming_ids.intersection(
        exclude_incoming_pdgids
    ):
        return False

    # Check outgoing particle filters
    if outgoing_pdgids is not None and not outgoing_ids.intersection(outgoing_pdgids):
        return False

    if exclude_outgoing_pdgids is not None and outgoing_ids.intersection(
        exclude_outgoing_pdgids
    ):
        return False
    return True


def matches_event_filter(
    event_index: int,
    include_event_ranges: Optional[list[tuple[int, int]]],
    exclude_event_ranges: Optional[list[tuple[int, int]]],
) -> bool:
    """Check if event matches event number filters."""
    # event_index is 0-based, but user input is 1-based
    event_number = event_index + 1

    # Check include ranges
    if include_event_ranges is not None:
        matches_include = False
        for start, end in include_event_ranges:
            if end == -1:  # Open upper bound
                if event_number >= start:
                    matches_include = True
                    break
            elif start <= event_number <= end:
                matches_include = True
                break
        if not matches_include:
            return False

    # Check exclude ranges
    if exclude_event_ranges is not None:
        for start, end in exclude_event_ranges:
            if end == -1:  # Open upper bound
                if event_number >= start:
                    return False
            elif start <= event_number <= end:
                return False

    return True


def filter_lhe_file(
    input_file: str,
    rwgt: bool,
    weights: bool,
    output_file: Optional[str] = None,
    process_ids: Optional[set[int]] = None,
    exclude_process_ids: Optional[set[int]] = None,
    incoming_pdgids: Optional[set[int]] = None,
    exclude_incoming_pdgids: Optional[set[int]] = None,
    outgoing_pdgids: Optional[set[int]] = None,
    exclude_outgoing_pdgids: Optional[set[int]] = None,
    include_event_ranges: Optional[list[tuple[int, int]]] = None,
    exclude_event_ranges: Optional[list[tuple[int, int]]] = None,
) -> None:
    """Filter an LHE file based on the given criteria."""
    try:
        # Read the input LHE file
        if input_file == "-":
            lhefile = pylhe.LHEFile.frombuffer(sys.stdin)
        else:
            lhefile = pylhe.LHEFile.fromfile(input_file)

        # Filter events
        def _generator() -> Iterable[pylhe.LHEEvent]:
            for event_index, event in enumerate(lhefile.events):
                # Apply all filters
                if (
                    matches_process_filter(event, process_ids, exclude_process_ids)
                    and matches_particle_filter(
                        event,
                        incoming_pdgids,
                        exclude_incoming_pdgids,
                        outgoing_pdgids,
                        exclude_outgoing_pdgids,
                    )
                    and matches_event_filter(
                        event_index, include_event_ranges, exclude_event_ranges
                    )
                ):
                    yield event

        # Create filtered LHE file
        filtered_lhefile = pylhe.LHEFile(init=lhefile.init, events=_generator())

        # Output the result
        if output_file:
            filtered_lhefile.tofile(output_file, rwgt=rwgt, weights=weights)
        else:
            # Write to stdout
            filtered_lhefile.write(sys.stdout, rwgt=rwgt, weights=weights)

    except FileNotFoundError:
        if input_file == "-":
            print("Error: Unable to read from stdin", file=sys.stderr)
        else:
            print(f"Error: File '{input_file}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        source = "stdin" if input_file == "-" else f"file '{input_file}'"
        print(f"Error processing {source}: {e}", file=sys.stderr)
        sys.exit(1)


def parse_int_list(value: str) -> set[int]:
    """Parse comma-separated list of integers."""
    try:
        return {int(x.strip()) for x in value.split(",")}
    except ValueError as e:
        err = f"Invalid integer list: {value}"
        raise argparse.ArgumentTypeError(err) from e


def parse_range_list(value: str) -> list[tuple[int, int]]:
    """Parse comma-separated list of integers and ranges.

    Returns list of (start, end) tuples where -1 indicates open bound.

    Supports:
    - Individual numbers: 5 -> [(5, 5)]
    - Ranges: 5-10 -> [(5, 10)] (inclusive)
    - Lower bound: 5- -> [(5, -1)] (from 5 to end)
    - Upper bound: -10 -> [(1, 10)] (from start to 10)
    - Mixed: 1,5-10,15-,20,-25 -> [(1, 1), (5, 10), (15, -1), (20, 20), (1, 25)]
    """
    result = []

    try:
        for vitem in value.split(","):
            item = vitem.strip()

            if "-" not in item:
                # Single number
                num = int(item)
                result.append((num, num))
            elif item.startswith("-"):
                # Upper bound: -N
                upper = int(item[1:])
                result.append((1, upper))
            elif item.endswith("-"):
                # Lower bound: N- (open range)
                lower = int(item[:-1])
                result.append((lower, -1))  # -1 indicates open upper bound
            else:
                # Range: N-M
                parts = item.split("-")
                if len(parts) == 2:
                    lower, upper = int(parts[0]), int(parts[1])
                    if lower > upper:
                        err = f"Invalid range: {item} (start > end)"
                        raise ValueError(err)
                    result.append((lower, upper))
                else:
                    err = f"Invalid range format: {item}"
                    raise ValueError(err)

    except ValueError as e:
        err = f"Invalid range specification: {value} ({e})"
        raise argparse.ArgumentTypeError(err) from e

    return result


def main() -> None:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Filter LHE files based on process ID, particle PDG IDs, and event numbers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhefilter input.lhe -o filtered.lhe --process-p 81,82
  lhefilter input.lhe --PROCESS 91 --incoming 21 --outgoing 11,-11
  lhefilter input.lhe --events 1,5,10 --outgoing 13,-13
  lhefilter input.lhe --EVENTS 7 --incoming 2,-2
  lhefilter input.lhe.gz --out 6,-6 | gzip > filtered.lhe.gz
  lhefilter input.lhe --events 10-20 --outgoing 11,-11
  lhefilter input.lhe --events 50- --EVENTS 55-60
  cat input.lhe | lhefilter --outgoing 11,-11
  zcat input.lhe.gz | lhefilter --process-p 81 --outgoing 13,-13

Process ID filters:
  --process-p ID[,ID...]    Include only events with these process IDs
  --PROCESS/-P ID[,ID...]   Exclude events with these process IDs

Particle PDG ID filters:
  --incoming/-in ID[,ID...] Include events containing these incoming particles
  --INCOMING/-IN ID[,ID...] Exclude events containing these incoming particles
  --outgoing/-out ID[,ID...] Include events containing these outgoing particles
  --OUTGOING/-OUT ID[,ID...] Exclude events containing these outgoing particles

Event filters:
  --events RANGE[,RANGE...] Include events in these ranges (1-indexed)
                            Supports: N (single), N-M (range), N- (from N to end), -M (up to M)
  --EVENTS RANGE[,RANGE...] Exclude events in these ranges (1-indexed)
                            Supports: N (single), N-M (range), N- (from N to end), -M (up to M)

Note: Multiple filters are combined with AND logic.
      PDG ID 0 can be used as wildcard for any particle.
      Open ranges (N-) use -1 internally to represent no upper bound.
        """,
    )

    parser.add_argument(
        "input", nargs="?", default="-", help="Input LHE file (default: stdin)"
    )
    parser.add_argument("-o", "--output", help="Output file (default: write to stdout)")

    # Process ID filters
    parser.add_argument(
        "--process-p",
        type=parse_int_list,
        metavar="ID[,ID...]",
        help="Include only events with these process IDs",
    )
    parser.add_argument(
        "--PROCESS",
        "-P",
        type=parse_int_list,
        metavar="ID[,ID...]",
        help="Exclude events with these process IDs",
    )

    # Incoming particle filters
    parser.add_argument(
        "--incoming",
        "-in",
        type=parse_int_list,
        metavar="PDGID[,PDGID...]",
        help="Include events containing these incoming particles",
    )
    parser.add_argument(
        "--INCOMING",
        "-IN",
        type=parse_int_list,
        metavar="PDGID[,PDGID...]",
        help="Exclude events containing these incoming particles",
    )

    # Outgoing particle filters
    parser.add_argument(
        "--outgoing",
        "-out",
        type=parse_int_list,
        metavar="PDGID[,PDGID...]",
        help="Include events containing these outgoing particles",
    )
    parser.add_argument(
        "--OUTGOING",
        "-OUT",
        type=parse_int_list,
        metavar="PDGID[,PDGID...]",
        help="Exclude events containing these outgoing particles",
    )

    # Event range filters
    parser.add_argument(
        "--events",
        type=parse_range_list,
        metavar="RANGE[,RANGE...]",
        help="Include events in these ranges (1-indexed). Supports: N (single), N-M (range), N- (from N), -M (up to M)",
    )
    parser.add_argument(
        "--EVENTS",
        type=parse_range_list,
        metavar="RANGE[,RANGE...]",
        help="Exclude events in these ranges (1-indexed). Supports: N (single), N-M (range), N- (from N), -M (up to M)",
    )

    parser.add_argument(
        "--rwgt",
        action="store_true",
        help="Use rwgt section if present in the input file",
    )

    parser.add_argument(
        "--no-weights",
        action="store_true",
        help="Do not preserve event weights in output file",
    )

    args = parser.parse_args()

    # Validate input file (skip validation for stdin)
    if args.input != "-":
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file '{args.input}' does not exist", file=sys.stderr)
            sys.exit(1)

    # Call the filtering function
    filter_lhe_file(
        rwgt=args.rwgt,
        weights=not args.no_weights,
        input_file=args.input,
        output_file=args.output,
        process_ids=args.process_p,
        exclude_process_ids=args.PROCESS,
        incoming_pdgids=args.incoming,
        exclude_incoming_pdgids=args.INCOMING,
        outgoing_pdgids=args.outgoing,
        exclude_outgoing_pdgids=args.OUTGOING,
        include_event_ranges=args.events,
        exclude_event_ranges=args.EVENTS,
    )


if __name__ == "__main__":
    main()
