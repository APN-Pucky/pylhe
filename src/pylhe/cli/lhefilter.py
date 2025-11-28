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
    include_events: Optional[set[int]],
    exclude_events: Optional[set[int]],
) -> bool:
    """Check if event matches event number filters."""
    # event_index is 0-based, but user input is 1-based
    event_number = event_index + 1

    if include_events is not None and event_number not in include_events:
        return False
    if exclude_events is not None and event_number in exclude_events:
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
    include_events: Optional[set[int]] = None,
    exclude_events: Optional[set[int]] = None,
) -> None:
    """Filter an LHE file based on the given criteria."""
    try:
        # Read the input LHE file
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
                        event_index, include_events, exclude_events
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
        print(f"Error: File '{input_file}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error processing file '{input_file}': {e}", file=sys.stderr)
        sys.exit(1)


def parse_int_list(value: str) -> set[int]:
    """Parse comma-separated list of integers."""
    try:
        return {int(x.strip()) for x in value.split(",")}
    except ValueError as e:
        err = f"Invalid integer list: {value}"
        raise argparse.ArgumentTypeError(err) from e


def main() -> None:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Filter LHE files based on process ID, particle PDG IDs, and event numbers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhefilter input.lhe -o filtered.lhe --process-p 81,82
  lhefilter input.lhe --PROCESS 91 --incoming 21 --outgoing 11,-11
  lhefilter input.lhe --event 1,5,10 --outgoing 13,-13
  lhefilter input.lhe --EVENT 7 --incoming 2,-2
  lhefilter input.lhe.gz --out 6,-6 | gzip > filtered.lhe.gz

Process ID filters:
  --process-p ID[,ID...]    Include only events with these process IDs
  --PROCESS/-P ID[,ID...]   Exclude events with these process IDs

Particle PDG ID filters:
  --incoming/-in ID[,ID...] Include events containing these incoming particles
  --INCOMING/-IN ID[,ID...] Exclude events containing these incoming particles
  --outgoing/-out ID[,ID...] Include events containing these outgoing particles
  --OUTGOING/-OUT ID[,ID...] Exclude events containing these outgoing particles

Event number filters:
  --event N[,N...]          Include only these event numbers (1-indexed)
  --EVENT N[,N...]          Exclude these event numbers (1-indexed)

Note: Multiple filters are combined with AND logic.
      PDG ID 0 can be used as wildcard for any particle.
        """,
    )

    parser.add_argument("input", help="Input LHE file")
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

    # Event number filters
    parser.add_argument(
        "--event",
        type=parse_int_list,
        metavar="N[,N...]",
        help="Include only these event numbers (1-indexed)",
    )
    parser.add_argument(
        "--EVENT",
        type=parse_int_list,
        metavar="N[,N...]",
        help="Exclude these event numbers (1-indexed)",
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

    # Validate input file
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
        include_events=args.event,
        exclude_events=args.EVENT,
    )


if __name__ == "__main__":
    main()
