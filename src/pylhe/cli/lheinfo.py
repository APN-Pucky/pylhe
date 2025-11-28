#!/usr/bin/env python3
"""
CLI tool to display information about LHE files.

This tool analyzes Les Houches Event (LHE) files and displays relevant information
including number of events, process information, particle combinations, etc.
"""

import argparse
import json
import sys
import warnings
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, Union

import yaml  # type: ignore[import-untyped]

import pylhe
from pylhe.cli.util import dataclass_with_properties_to_dict


@dataclass
class LHEChannel:
    """Information about a single channel in an LHE file."""

    incoming_pdgid: list[int]
    outgoing_pdgid: list[int]
    num_events: int


@dataclass
class LHEProcess:
    """Information about a single process in an LHE file."""

    procId: int
    xSection: float
    error: float
    channels: list[LHEChannel]


@dataclass
class LHEInfo:
    """Information about a single LHE file."""

    filepath: str
    beamA: int
    energyA: float
    beamB: int
    energyB: float
    weight_groups: dict[str, int]
    num_events: int
    negative_weighted_events: int
    process_info: list[LHEProcess]

    @property
    def negative_weighted_events_ratio(self) -> float:
        """Ratio of negative weighted events to total events."""
        return (
            self.negative_weighted_events / self.num_events
            if self.num_events > 0
            else 0.0
        )

    def __str__(self) -> str:
        lines = []
        lines.append("-" * 60)
        lines.append(f"File: {self.filepath}")

        # Beam information
        lines.append(f"Beam A: {self.beamA} @ {self.energyA} GeV")
        lines.append(f"Beam B: {self.beamB} @ {self.energyB} GeV")
        # Weight groups
        if self.weight_groups:
            lines.append("  Weight Groups:")
            for name, count in self.weight_groups.items():
                lines.append(f"    {name}: {count} weights")
        # Number of events
        lines.append(
            f"Number of events: {self.num_events} (negative: {self.negative_weighted_events_ratio:.2%})"
        )

        # Process information
        processes = self.process_info
        if processes:
            for proc in processes:
                lines.append(
                    f"Process {proc.procId} cross-section: ({proc.xSection:.3e} +- {proc.error:.3e}) pb"
                )

                channels = proc.channels
                if channels:
                    # Sort channels by num_events in descending order
                    sorted_channels = sorted(
                        channels, key=lambda ch: ch.num_events, reverse=True
                    )
                    for channel in sorted_channels:
                        percentage = 100 * channel.num_events / self.num_events
                        lines.append(
                            f"  {channel.incoming_pdgid} -> {channel.outgoing_pdgid}: {channel.num_events:,} events ({percentage:.1f}%)"
                        )

        return "\n".join(lines)


def get_lheinfo(filepath_or_fileobj: Union[str, TextIO]) -> LHEInfo:
    # Read LHE file
    if isinstance(filepath_or_fileobj, str):
        lhefile = pylhe.LHEFile.fromfile(filepath_or_fileobj)
        file_display_name = filepath_or_fileobj
    else:
        lhefile = pylhe.LHEFile.frombuffer(filepath_or_fileobj)
        file_display_name = "<stdin>"
    init_info = lhefile.init.initInfo

    initial_final_combinations: Counter[
        tuple[int, tuple[int, ...], tuple[int, ...]]
    ] = Counter()

    num_events = 0
    num_negative_weighted_events = 0
    for event in lhefile.events:
        num_events += 1
        if event.eventinfo.weight < 0:
            num_negative_weighted_events += 1
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

    return LHEInfo(
        filepath=file_display_name,
        beamA=init_info.beamA,
        energyA=init_info.energyA,
        beamB=init_info.beamB,
        energyB=init_info.energyB,
        weight_groups={
            name: len(wg.weights) for name, wg in lhefile.init.weightgroup.items()
        },
        num_events=num_events,
        negative_weighted_events=num_negative_weighted_events,
        process_info=[
            LHEProcess(
                procId=proc.procId,
                xSection=proc.xSection,
                error=proc.error,
                channels=[
                    LHEChannel(
                        incoming_pdgid=list(incoming_pdgid),
                        outgoing_pdgid=list(outgoing_pdgid),
                        num_events=count,
                    )
                    for (
                        pid,
                        incoming_pdgid,
                        outgoing_pdgid,
                    ), count in initial_final_combinations.items()
                    if pid == proc.procId
                ],
            )
            for proc in lhefile.init.procInfo
        ],
    )


@dataclass
class LHESummary:
    """Summary information from multiple LHE files."""

    files: list[LHEInfo]

    @property
    def total_events(self) -> int:
        total_events = 0
        for lheinfo in self.files:
            total_events += lheinfo.num_events
        return total_events

    @property
    def total_negative_weighted_events(self) -> int:
        total_negative_weighted_events = 0
        for lheinfo in self.files:
            total_negative_weighted_events += lheinfo.negative_weighted_events
        return total_negative_weighted_events

    @property
    def negative_weighted_events_ratio(self) -> float:
        """Ratio of negative weighted events to total events."""
        return (
            self.total_negative_weighted_events / self.total_events
            if self.total_events > 0
            else 0.0
        )

    def __str__(self) -> str:
        lines = []
        for lheinfo in self.files:
            lines.append(str(lheinfo))
        lines.append("=" * 60)
        lines.append(
            f"Total number of events: {self.total_events} (negative: {self.negative_weighted_events_ratio:.2%})"
        )
        lines.append("=" * 60)
        return "\n".join(lines)


def get_lhesummary(
    filepaths_or_fileobjs: list[Union[str, TextIO]],
) -> LHESummary:
    lheinfos = []
    # Analyze all files
    for filepath_or_fileobj in filepaths_or_fileobjs:
        lheinfo = get_lheinfo(filepath_or_fileobj)
        lheinfos.append(lheinfo)

    return LHESummary(files=lheinfos)


def main() -> None:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Display information about LHE files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lheinfo file.lhe                      # Analyze single file (plain format)
  cat file.lhe | lheinfo                # Read from stdin
  lheinfo *.lhe                         # Analyze multiple files
  lheinfo file1.lhe --format=json       # Output results in JSON format
  lheinfo file1.lhe --format=yaml       # Output results in YAML format
        """,
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="LHE file(s) to analyze (or read from stdin if not provided)",
    )

    parser.add_argument(
        "--format",
        choices=["plain", "json", "yaml"],
        default="plain",
        help="Output format (default: plain)",
    )

    args = parser.parse_args()

    # Check if reading from stdin
    use_stdin = not args.files and not sys.stdin.isatty()

    file_inputs: list[Union[str, TextIO]] = []
    if use_stdin:
        # Read from stdin
        file_inputs += [sys.stdin]
    else:
        # Expand file paths
        for pattern in args.files:
            path = Path(pattern)
            if path.exists():
                if path.is_file():
                    file_inputs.append(str(path))
                else:
                    warnings.warn(f"{pattern} is not a file", UserWarning, stacklevel=2)
        if not file_inputs:
            print("Error: No valid files found and no stdin data", file=sys.stderr)
            sys.exit(1)

    summary = get_lhesummary(file_inputs)
    if args.format == "json":
        print(
            json.dumps(
                dataclass_with_properties_to_dict(summary),
                indent=2,
            )
        )
    elif args.format == "yaml":
        print(
            yaml.dump(
                dataclass_with_properties_to_dict(summary),
                sort_keys=False,
            )
        )
    else:
        print(str(summary))


if __name__ == "__main__":
    main()
