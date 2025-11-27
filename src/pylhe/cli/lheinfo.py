#!/usr/bin/env python3
"""
CLI tool to display information about LHE files.

This tool analyzes Les Houches Event (LHE) files and displays relevant information
including number of events, process information, particle combinations, etc.
"""

import argparse
import inspect
import json
import sys
import warnings
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any, Union

import yaml  # type: ignore[import-untyped]

import pylhe


def dataclass_with_properties_to_dict(obj: object) -> Union[object, dict[Any, Any]]:
    """Custom serialization function of dataclasses including @property values."""
    if is_dataclass(obj):
        result = {}
        # Include real dataclass fields
        for f in fields(obj):
            value = getattr(obj, f.name)
            result[f.name] = dataclass_with_properties_to_dict(value)
        # Include @property values
        for name, _ in inspect.getmembers(type(obj), lambda m: isinstance(m, property)):
            if name not in result:
                try:
                    value = getattr(obj, name)
                    result[name] = dataclass_with_properties_to_dict(value)
                except Exception:
                    pass
        return result
    if isinstance(obj, (list, tuple, set)):
        return type(obj)(dataclass_with_properties_to_dict(v) for v in obj)
    if isinstance(obj, dict):
        return {k: dataclass_with_properties_to_dict(v) for k, v in obj.items()}
    return obj


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


def get_lheinfo(filepath: str) -> LHEInfo:
    # Read LHE file
    lhefile = pylhe.LHEFile.fromfile(filepath)
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
        filepath=filepath,
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


def print_lheinfo(lheinfo: LHEInfo, format: str = "plain") -> None:
    """Analyze a single LHE file and return summary information."""
    if format == "json":
        print(json.dumps(dataclass_with_properties_to_dict(lheinfo), indent=2))
    elif format == "yaml":
        print(
            yaml.dump(
                dataclass_with_properties_to_dict(lheinfo), default_flow_style=False
            )
        )
    else:
        print("-" * 60)
        print(f"File: {lheinfo.filepath}")

        # Beam information
        print(f"Beam A: {lheinfo.beamA} @ {lheinfo.energyA} GeV")
        print(f"Beam B: {lheinfo.beamB} @ {lheinfo.energyB} GeV")
        ## Weight groups
        # weight_groups = lheinfo.weight_groups
        # if weight_groups:
        #    print("  Weight Groups:")
        #    for name, count in weight_groups.items():
        #        print(f"    {name}: {count} weights")
        # Number of events
        print(
            f"Number of events: {lheinfo.num_events} (negative: {lheinfo.negative_weighted_events_ratio:.2%})"
        )

        # Process information
        processes = lheinfo.process_info
        if processes:
            for _, proc in enumerate(processes):
                print(
                    f"Process {proc.procId} cross-section: ({proc.xSection:.3e} +- {proc.error:.3e}) pb"
                )

                channels = proc.channels
                if channels:
                    # Sort channels by num_events in descending order
                    sorted_channels = sorted(
                        channels, key=lambda ch: ch.num_events, reverse=True
                    )
                    for _, channel in enumerate(sorted_channels):
                        percentage = 100 * channel.num_events / lheinfo.num_events
                        print(
                            f"  {channel.incoming_pdgid} -> {channel.outgoing_pdgid}: {channel.num_events:,} events ({percentage:.1f}%)"
                        )


@dataclass
class LHEInfos:
    """Merged information from multiple LHE files."""

    num_events: int
    negative_weighted_events: int

    @property
    def negative_weighted_events_ratio(self) -> float:
        """Ratio of negative weighted events to total events."""
        return (
            self.negative_weighted_events / self.num_events
            if self.num_events > 0
            else 0.0
        )


def get_lheinfos(lheinfos: Iterable[LHEInfo]) -> LHEInfos:
    total_events = 0
    total_negative_weighted_events = 0
    for lheinfo in lheinfos:
        total_events += lheinfo.num_events
        total_negative_weighted_events += lheinfo.negative_weighted_events
    return LHEInfos(
        num_events=total_events,
        negative_weighted_events=total_negative_weighted_events,
    )


def print_lheinfos(lheinfos: LHEInfos, format: str = "plain") -> None:
    """Print summary information from multiple LHE files."""
    if format == "json":
        print(json.dumps(dataclass_with_properties_to_dict(lheinfos), indent=2))
    elif format == "yaml":
        print(
            yaml.dump(
                dataclass_with_properties_to_dict(lheinfos), default_flow_style=False
            )
        )
    else:
        print("=" * 60)
        print(
            f"Total number of events: {lheinfos.num_events} (negative: {lheinfos.negative_weighted_events_ratio:.2%})"
        )
        print("=" * 60)


@dataclass
class LHESummary:
    """Summary information from multiple LHE files."""

    files: list[LHEInfo]

    @property
    def summary(self) -> LHEInfos:
        return get_lheinfos(self.files)


def get_lhesummary(file_paths: list[str]) -> LHESummary:
    lheinfos = []
    # Analyze all files
    for filepath in file_paths:
        lheinfo = get_lheinfo(filepath)
        lheinfos.append(lheinfo)

    return LHESummary(files=lheinfos)


def print_lhesummary(lhesummary: LHESummary, format: str = "plain") -> None:
    """Print summary information from multiple LHE files."""
    if format == "json":
        print(json.dumps(dataclass_with_properties_to_dict(lhesummary), indent=2))
    elif format == "yaml":
        print(
            yaml.dump(
                dataclass_with_properties_to_dict(lhesummary), default_flow_style=False
            )
        )
    else:
        for lheinfo in lhesummary.files:
            print_lheinfo(lheinfo, format="plain")
        print_lheinfos(lhesummary.summary, format="plain")


def main() -> None:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Display information about LHE files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lheinfo file.lhe                      # Analyze single file (plain format)
  lheinfo *.lhe                         # Analyze multiple files
  lheinfo file1.lhe --format=json       # Output results in JSON format
  lheinfo file1.lhe --format=yaml       # Output results in YAML format
        """,
    )

    parser.add_argument("files", nargs="+", help="LHE file(s) to analyze")

    parser.add_argument(
        "--format",
        choices=["plain", "json", "yaml"],
        default="plain",
        help="Output format (default: plain)",
    )

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

    summary = get_lhesummary(file_paths)
    print_lhesummary(summary, format=args.format)


if __name__ == "__main__":
    main()
