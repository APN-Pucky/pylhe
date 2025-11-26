#!/usr/bin/env python3
"""
CLI tool to display information about LHE files.

This tool analyzes Les Houches Event (LHE) files and displays relevant information
including number of events, process information, particle combinations, etc.
"""

import argparse
import sys
import warnings
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pylhe


def analyze_particle_combinations(events: Iterable[pylhe.LHEEvent]) -> dict[str, Any]:
    """Analyze incoming and outgoing particle combinations."""
    initial_final_combinations: Counter[
        tuple[int, tuple[int, ...], tuple[int, ...]]
    ] = Counter()

    count = 0
    for event in events:
        count += 1
        initial = []
        final = []

        for particle in event.particles:
            if particle.status == -1:  # Incoming particles
                initial.append(particle.id)
            elif particle.status == 1:  # Outgoing particles
                final.append(particle.id)

        # Count initial particles
        initial_tuple = tuple(sorted(initial))

        # Count final particles
        final_tuple = tuple(sorted(final))

        # Count initial -> final combinations
        combination = (event.eventinfo.pid, initial_tuple, final_tuple)
        initial_final_combinations[combination] += 1

    return {"count": count, "combinations": initial_final_combinations}


def print_lheinfo(filepath: str) -> None:
    """Analyze a single LHE file and return summary information."""
    # Read LHE file
    lhefile = pylhe.LHEFile.fromfile(filepath)
    init_info = lhefile.init.initInfo

    # Analyze particle combinations from sample
    particle_analysis = analyze_particle_combinations(lhefile.events)
    num_events = particle_analysis["count"]

    print(f"{filepath}:")

    # Beam information
    print(f"  Beam A: {init_info.beamA} @ {init_info.energyA} GeV")
    print(f"  Beam B: {init_info.beamB} @ {init_info.energyB} GeV")

    # Weight groups
    weight_groups = lhefile.init.weightgroup
    if weight_groups:
        print("  Weight Groups:")
        for name, wg in weight_groups.items():
            print(f"    {name}: {len(wg.weights)} weights")

    # Number of events
    print(f"  Number of events: {num_events}")

    # Process information
    processes = lhefile.init.procInfo
    combinations = particle_analysis["combinations"]
    if processes:
        for _, proc in enumerate(processes):
            print(f"  Process {proc.procId}: {proc.xSection:.3e} ± {proc.error:.3e} pb")

            if combinations:
                for (procid, initial, final), count in combinations.items():
                    if procid == proc.procId:
                        percentage = 100 * count / num_events
                        print(
                            f"    {initial} -> {final}: {count:,} events ({percentage:.1f}%)"
                        )


def main() -> None:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Display information about LHE files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lheinfo file.lhe                    # Analyze single file
  lheinfo *.lhe                       # Analyze multiple files
        """,
    )

    parser.add_argument("files", nargs="+", help="LHE file(s) to analyze")

    args = parser.parse_args()

    # Expand file paths
    file_paths = []
    for pattern in args.files:
        path = Path(pattern)
        if path.exists():
            if path.is_file():
                file_paths.append(str(path))
            else:
                warnings.warn(f"{pattern} is not a file", UserWarning, stacklevel=2)
    if not file_paths:
        print("Error: No valid files found", file=sys.stderr)
        sys.exit(1)

    # Analyze all files
    for filepath in file_paths:
        print_lheinfo(filepath)


if __name__ == "__main__":
    main()
