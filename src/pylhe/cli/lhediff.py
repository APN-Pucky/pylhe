#!/usr/bin/env python3
"""
CLI tool to compare and diff two LHE files.

This tool compares two Les Houches Event (LHE) files and reports differences
in their initialization sections, event counts, and optionally event contents.
"""

import argparse
import math
import signal
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
from typing import Any

from typing_extensions import Self

import pylhe

# We do not want a Python Exception on broken pipe, which happens when piping to 'head' or 'less'
signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def diff_lhe_event_infos(
    lheei1: pylhe.LHEEventInfo, lheei2: pylhe.LHEEventInfo
) -> pylhe.LHEEventInfo:
    """
    Compare LHEEventInfo objects from two LHE files and report differences.

    Args:
        lheei1: LHEEventInfo from first file
        lheei2: LHEEventInfo from second file
    """
    return pylhe.LHEEventInfo(
        nparticles=lheei1.nparticles - lheei2.nparticles,
        pid=lheei1.pid - lheei2.pid,
        weight=lheei1.weight - lheei2.weight,
        scale=lheei1.scale - lheei2.scale,
        aqed=lheei1.aqed - lheei2.aqed,
        aqcd=lheei1.aqcd - lheei2.aqcd,
    )


def diff_lhe_particles(
    p1: pylhe.LHEParticle, p2: pylhe.LHEParticle
) -> pylhe.LHEParticle:
    """
    Compare two LHEParticle objects and report differences.

    Args:
        p1: First LHEParticle
        p2: Second LHEParticle
    Returns:
        Dictionary of differing attributes with their values
    """
    return pylhe.LHEParticle(
        id=p1.id - p2.id,
        status=p1.status - p2.status,
        mother1=p1.mother1 - p2.mother1,
        mother2=p1.mother2 - p2.mother2,
        color1=p1.color1 - p2.color1,
        color2=p1.color2 - p2.color2,
        px=p1.px - p2.px,
        py=p1.py - p2.py,
        pz=p1.pz - p2.pz,
        e=p1.e - p2.e,
        m=p1.m - p2.m,
        lifetime=p1.lifetime - p2.lifetime,
        spin=p1.spin - p2.spin,
    )


@dataclass
class LHEAccumulatedDiff:
    ndiff: int

    def __add__(self, other: "LHEAccumulatedDiff") -> "LHEAccumulatedDiff":
        """Add two LHEAccumulatedDiff objects together."""
        return LHEAccumulatedDiff(ndiff=self.ndiff + other.ndiff)

    def __iadd__(self, other: "LHEAccumulatedDiff") -> Self:
        """In-place addition for LHEAccumulatedDiff objects."""
        self.ndiff += other.ndiff
        return self

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print the number of differences."""
        print(f"Total differences: {self.ndiff}", *args, **kwargs)


@dataclass
class LHEDiff:
    """Generic dataclass to store differences between old and new values."""

    old: Any
    new: Any

    def print(self, *args: Any, **kwargs: Any) -> LHEAccumulatedDiff:
        print(f"{self.old} -> {self.new}", *args, **kwargs)
        return LHEAccumulatedDiff(ndiff=1)


@dataclass
class LHEInitDiff:
    """Dataclass to store differences in LHE initialization sections."""

    diffs: dict[str, LHEDiff]

    def print(self, *args: Any, end: str = "\n", **kwargs: Any) -> LHEAccumulatedDiff:
        lhead = LHEAccumulatedDiff(ndiff=0)
        for key, diff in self.diffs.items():
            print(f"{key}: ", *args, end="", **kwargs)
            lhead += diff.print(*args, end=end, **kwargs)
        return lhead


def diff_lhe_init(
    lhei1: pylhe.LHEInit,
    lhei2: pylhe.LHEInit,
    check_init: bool,
    check_weights: bool,
    absolute_tolerance: float,
    relative_tolerance: float,
) -> LHEInitDiff:
    """
    Compare LHEInitInfo objects from two LHE files and report differences.

    Args:
        lheii1: LHEInitInfo from first file
        lheii2: LHEInitInfo from second file
        check_init: Whether to check initialization section
        check_weights: Whether to check weight groups and weights
        absolute_tolerance: Absolute tolerance for numeric comparisons
        relative_tolerance: Relative tolerance for numeric comparisons
    """
    diffs = {}
    if check_init:
        if lhei1.initInfo.beamA != lhei2.initInfo.beamA:
            diffs["beamA"] = LHEDiff(old=lhei1.initInfo.beamA, new=lhei2.initInfo.beamA)
        if not math.isclose(
            lhei1.initInfo.energyA,
            lhei2.initInfo.energyA,
            rel_tol=relative_tolerance,
            abs_tol=absolute_tolerance,
        ):
            diffs["energyA"] = LHEDiff(
                old=lhei1.initInfo.energyA, new=lhei2.initInfo.energyA
            )
        if lhei1.initInfo.beamB != lhei2.initInfo.beamB:
            diffs["beamB"] = LHEDiff(old=lhei1.initInfo.beamB, new=lhei2.initInfo.beamB)
        if not math.isclose(
            lhei1.initInfo.energyB,
            lhei2.initInfo.energyB,
            rel_tol=relative_tolerance,
            abs_tol=absolute_tolerance,
        ):
            diffs["energyB"] = LHEDiff(
                old=lhei1.initInfo.energyB, new=lhei2.initInfo.energyB
            )
        if lhei1.initInfo.PDFgroupA != lhei2.initInfo.PDFgroupA:
            diffs["PDFgroupA"] = LHEDiff(
                old=lhei1.initInfo.PDFgroupA, new=lhei2.initInfo.PDFgroupA
            )
        if lhei1.initInfo.PDFgroupB != lhei2.initInfo.PDFgroupB:
            diffs["PDFgroupB"] = LHEDiff(
                old=lhei1.initInfo.PDFgroupB, new=lhei2.initInfo.PDFgroupB
            )
        if lhei1.initInfo.PDFsetA != lhei2.initInfo.PDFsetA:
            diffs["PDFsetA"] = LHEDiff(
                old=lhei1.initInfo.PDFsetA, new=lhei2.initInfo.PDFsetA
            )
        if lhei1.initInfo.PDFsetB != lhei2.initInfo.PDFsetB:
            diffs["PDFsetB"] = LHEDiff(
                old=lhei1.initInfo.PDFsetB, new=lhei2.initInfo.PDFsetB
            )
        if lhei1.initInfo.weightingStrategy != lhei2.initInfo.weightingStrategy:
            diffs["weightingStrategy"] = LHEDiff(
                old=lhei1.initInfo.weightingStrategy,
                new=lhei2.initInfo.weightingStrategy,
            )
        if lhei1.initInfo.numProcesses != lhei2.initInfo.numProcesses:
            diffs["numProcesses"] = LHEDiff(
                old=lhei1.initInfo.numProcesses, new=lhei2.initInfo.numProcesses
            )

        for proc1, proc2 in zip(lhei1.procInfo, lhei2.procInfo):
            if not math.isclose(
                proc1.xSection,
                proc2.xSection,
                rel_tol=relative_tolerance,
                abs_tol=absolute_tolerance,
            ):
                diffs[f"process_{proc1.procId}_xSection"] = LHEDiff(
                    old=proc1.xSection, new=proc2.xSection
                )
            if not math.isclose(
                proc1.error,
                proc2.error,
                rel_tol=relative_tolerance,
                abs_tol=absolute_tolerance,
            ):
                diffs[f"process_{proc1.procId}_error"] = LHEDiff(
                    old=proc1.error, new=proc2.error
                )
            if not math.isclose(
                proc1.unitWeight,
                proc2.unitWeight,
                rel_tol=relative_tolerance,
                abs_tol=absolute_tolerance,
            ):
                diffs[f"process_{proc1.procId}_unitWeight"] = LHEDiff(
                    old=proc1.unitWeight, new=proc2.unitWeight
                )
            if proc1.procId != proc2.procId:
                diffs[f"process_{proc1.procId}_procId"] = LHEDiff(
                    old=proc1.procId, new=proc2.procId
                )

        if check_weights:
            if len(lhei1.weightgroup) != len(lhei2.weightgroup):
                diffs["num_weight_groups"] = LHEDiff(
                    old=len(lhei1.weightgroup), new=len(lhei2.weightgroup)
                )
            for (nwg1, wg1), (nwg2, wg2) in zip(
                lhei1.weightgroup.items(), lhei2.weightgroup.items()
            ):
                if nwg1 != nwg2:
                    diffs[f"weight_group_key_{nwg1}"] = LHEDiff(old=nwg1, new=nwg2)
                if len(wg1.attrib) != len(wg2.attrib):
                    diffs[f"weight_group_{nwg1}_num_attrib"] = LHEDiff(
                        old=len(wg1.attrib), new=len(wg2.attrib)
                    )
                for (k1, v1), (k2, v2) in zip(wg1.attrib.items(), wg2.attrib.items()):
                    if k1 != k2:
                        diffs[f"weight_group_{nwg1}_attrib_key_{k1}"] = LHEDiff(
                            old=k1, new=k2
                        )
                    if v1 != v2:
                        diffs[f"weight_group_{nwg1}_attrib_value_{k1}"] = LHEDiff(
                            old=v1, new=v2
                        )
                if len(wg1.weights) != len(wg2.weights):
                    diffs[f"weight_group_{nwg1}_num_weights"] = LHEDiff(
                        old=len(wg1.weights), new=len(wg2.weights)
                    )
                for (n1, lhewi1), (n2, lhwi2) in zip(
                    wg1.weights.items(), wg2.weights.items()
                ):
                    if n1 != n2:
                        diffs[f"weight_group_{nwg1}_weight_key_{n1}"] = LHEDiff(
                            old=n1, new=n2
                        )
                    if lhewi1.name != lhwi2.name:
                        diffs[f"weight_group_{nwg1}_weight_{n1}_name"] = LHEDiff(
                            old=lhewi1.name, new=lhwi2.name
                        )
                    if lhewi1.index != lhwi2.index:
                        diffs[f"weight_group_{nwg1}_weight_{n1}_index"] = LHEDiff(
                            old=lhewi1.index, new=lhwi2.index
                        )
                    if len(lhewi1.attrib) != len(lhwi2.attrib):
                        diffs[f"weight_group_{nwg1}_weight_{n1}_num_attrib"] = LHEDiff(
                            old=len(lhewi1.attrib), new=len(lhwi2.attrib)
                        )
                    for (ak1, av1), (ak2, av2) in zip(
                        lhewi1.attrib.items(), lhwi2.attrib.items()
                    ):
                        if ak1 != ak2:
                            diffs[
                                f"weight_group_{nwg1}_weight_{n1}_attrib_key_{ak1}"
                            ] = LHEDiff(old=ak1, new=ak2)
                        if av1 != av2:
                            diffs[
                                f"weight_group_{nwg1}_weight_{n1}_attrib_value_{ak1}"
                            ] = LHEDiff(old=av1, new=av2)

        if lhei1.LHEVersion != lhei2.LHEVersion:
            diffs["LHEVersion"] = LHEDiff(old=lhei1.LHEVersion, new=lhei2.LHEVersion)

    return LHEInitDiff(diffs=diffs)


@dataclass
class LHEEventDiff:
    """Dataclass to store differences in LHE initialization sections."""

    event_index: int
    diffs: dict[str, LHEDiff]

    def print(self, *args: Any, end: str = "\n", **kwargs: Any) -> LHEAccumulatedDiff:
        lhead = LHEAccumulatedDiff(ndiff=0)
        for key, diff in self.diffs.items():
            print(f"{key}: ", *args, end="", **kwargs)
            lhead += diff.print(*args, end=end, **kwargs)
        return lhead


def diff_lhe_events(
    events1: Iterable[pylhe.LHEEvent],
    events2: Iterable[pylhe.LHEEvent],
    check_events: bool,
    abs_tol: float,
    rel_tol: float,
) -> Iterable[LHEEventDiff]:
    for j, (event1, event2) in enumerate(zip_longest(events1, events2), start=1):
        diffs = {}
        if event1 is None:
            diffs[f"event_{j}"] = LHEDiff(old="missing", new="present")
            yield LHEEventDiff(event_index=j, diffs=diffs)
            continue
        if event2 is None:
            diffs[f"event_{j}"] = LHEDiff(old="present", new="missing")
            yield LHEEventDiff(event_index=j, diffs=diffs)
            continue
        if check_events:
            if event1.eventinfo.nparticles != event2.eventinfo.nparticles:
                diffs[f"event_{j}_eventinfo_nparticles"] = LHEDiff(
                    old=event1.eventinfo.nparticles, new=event2.eventinfo.nparticles
                )
            if event1.eventinfo.pid != event2.eventinfo.pid:
                diffs[f"event_{j}_eventinfo_pid"] = LHEDiff(
                    old=event1.eventinfo.pid, new=event2.eventinfo.pid
                )
            if not math.isclose(
                event1.eventinfo.weight,
                event2.eventinfo.weight,
                abs_tol=abs_tol,
                rel_tol=rel_tol,
            ):
                diffs[f"event_{j}_eventinfo_weight"] = LHEDiff(
                    old=event1.eventinfo.weight, new=event2.eventinfo.weight
                )
            if not math.isclose(
                event1.eventinfo.scale,
                event2.eventinfo.scale,
                abs_tol=abs_tol,
                rel_tol=rel_tol,
            ):
                diffs[f"event_{j}_eventinfo_scale"] = LHEDiff(
                    old=event1.eventinfo.scale, new=event2.eventinfo.scale
                )
            if not math.isclose(
                event1.eventinfo.aqed,
                event2.eventinfo.aqed,
                abs_tol=abs_tol,
                rel_tol=rel_tol,
            ):
                diffs[f"event_{j}_eventinfo_aqed"] = LHEDiff(
                    old=event1.eventinfo.aqed, new=event2.eventinfo.aqed
                )
            if not math.isclose(
                event1.eventinfo.aqcd,
                event2.eventinfo.aqcd,
                abs_tol=abs_tol,
                rel_tol=rel_tol,
            ):
                diffs[f"event_{j}_eventinfo_aqcd"] = LHEDiff(
                    old=event1.eventinfo.aqcd, new=event2.eventinfo.aqcd
                )

            if len(event1.particles) != len(event2.particles):
                diffs[f"event_{j}_num_particles"] = LHEDiff(
                    old=len(event1.particles), new=len(event2.particles)
                )
            for i, (p1, p2) in enumerate(
                zip(event1.particles, event2.particles), start=1
            ):
                if p1.id != p2.id:
                    diffs[f"event_{j}_particle_{i}_id"] = LHEDiff(old=p1.id, new=p2.id)
                if p1.status != p2.status:
                    diffs[f"event_{j}_particle_{i}_status"] = LHEDiff(
                        old=p1.status, new=p2.status
                    )
                if p1.mother1 != p2.mother1:
                    diffs[f"event_{j}_particle_{i}_mother1"] = LHEDiff(
                        old=p1.mother1, new=p2.mother1
                    )
                if p1.mother2 != p2.mother2:
                    diffs[f"event_{j}_particle_{i}_mother2"] = LHEDiff(
                        old=p1.mother2, new=p2.mother2
                    )
                if p1.color1 != p2.color1:
                    diffs[f"event_{j}_particle_{i}_color1"] = LHEDiff(
                        old=p1.color1, new=p2.color1
                    )
                if p1.color2 != p2.color2:
                    diffs[f"event_{j}_particle_{i}_color2"] = LHEDiff(
                        old=p1.color2, new=p2.color2
                    )
                if not math.isclose(p1.px, p2.px, abs_tol=abs_tol, rel_tol=rel_tol):
                    diffs[f"event_{j}_particle_{i}_px"] = LHEDiff(old=p1.px, new=p2.px)
                if not math.isclose(p1.py, p2.py, abs_tol=abs_tol, rel_tol=rel_tol):
                    diffs[f"event_{j}_particle_{i}_py"] = LHEDiff(old=p1.py, new=p2.py)
                if not math.isclose(p1.pz, p2.pz, abs_tol=abs_tol, rel_tol=rel_tol):
                    diffs[f"event_{j}_particle_{i}_pz"] = LHEDiff(old=p1.pz, new=p2.pz)
                if not math.isclose(p1.e, p2.e, abs_tol=abs_tol, rel_tol=rel_tol):
                    diffs[f"event_{j}_particle_{i}_e"] = LHEDiff(old=p1.e, new=p2.e)
                if not math.isclose(p1.m, p2.m, abs_tol=abs_tol, rel_tol=rel_tol):
                    diffs[f"event_{j}_particle_{i}_m"] = LHEDiff(old=p1.m, new=p2.m)
                if not math.isclose(
                    p1.lifetime, p2.lifetime, abs_tol=abs_tol, rel_tol=rel_tol
                ):
                    diffs[f"event_{j}_particle_{i}_lifetime"] = LHEDiff(
                        old=p1.lifetime, new=p2.lifetime
                    )
                if not math.isclose(p1.spin, p2.spin, abs_tol=abs_tol, rel_tol=rel_tol):
                    diffs[f"event_{j}_particle_{i}_spin"] = LHEDiff(
                        old=p1.spin, new=p2.spin
                    )

        if diffs:
            yield LHEEventDiff(event_index=j, diffs=diffs)


@dataclass
class LHEFileDiff:
    """Dataclass to store differences between two LHE files."""

    lheinitdiff: LHEInitDiff
    lheeventdiffs: Iterable[LHEEventDiff]

    def print(self, *args: Any, **kwargs: Any) -> LHEAccumulatedDiff:
        ret = LHEAccumulatedDiff(ndiff=0)
        ret += self.lheinitdiff.print(*args, **kwargs)
        for event_diff in self.lheeventdiffs:
            ret += event_diff.print(*args, **kwargs)
        return ret


def diff_lhe_files(
    file1: str,
    file2: str,
    init: bool = True,
    weights: bool = True,
    events: bool = True,
    abs_tol: float = 0.0,
    rel_tol: float = 0.0,
) -> LHEFileDiff:
    """
    Compare two LHE files and report differences.

    Args:
        file1: Path to first LHE file
        file2: Path to second LHE file
        abs_tol: Absolute tolerance for numeric comparisons
        rel_tol: Relative tolerance for numeric comparisons
    """
    # Read initialization sections
    lhefile1 = pylhe.LHEFile.fromfile(file1)
    lhefile2 = pylhe.LHEFile.fromfile(file2)

    lheinitdiff = diff_lhe_init(
        lhefile1.init, lhefile2.init, init, weights, abs_tol, rel_tol
    )
    lheeventdiff = diff_lhe_events(
        lhefile1.events, lhefile2.events, events, abs_tol, rel_tol
    )

    return LHEFileDiff(lheinitdiff, lheeventdiff)


def main() -> None:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Compare and diff two LHE files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhediff file1.lhe file2.lhe                              # Basic comparison (init + event counts)
  lhediff file1.lhe file2.lhe --detailed                   # Detailed event-by-event comparison
  lhediff file1.lhe file2.lhe --detailed -n 100            # Compare only first 100 events
  lhediff file1.lhe file2.lhe --abs-tol 1e-10              # Allow small absolute differences
  lhediff file1.lhe file2.lhe --rel-tol 1e-6 --abs-tol 1e-12  # Use both relative and absolute tolerance
  lhediff original.lhe merged.lhe --detailed --rel-tol 1e-10  # Check merge with numeric tolerance
        """,
    )

    parser.add_argument("file1", help="First LHE file to compare")

    parser.add_argument("file2", help="Second LHE file to compare")

    parser.add_argument(
        "--abs-tol",
        "-a",
        type=float,
        default=1e-6,
        help="Absolute tolerance for numeric comparisons (default: 1e-6)",
    )

    parser.add_argument(
        "--rel-tol",
        "-r",
        type=float,
        default=1e-6,
        help="Relative tolerance for numeric comparisons (default: 1e-6)",
    )

    parser.add_argument(
        "--no-init",
        "-ni",
        action="store_true",
        default=False,
        help="Don't compare initialization sections (default: False)",
    )

    parser.add_argument(
        "--no-events",
        "-ne",
        action="store_true",
        default=False,
        help="Don't compare events (default: False)",
    )

    parser.add_argument(
        "--no-weights",
        "-nw",
        action="store_true",
        default=False,
        help="Don't compare weight groups and weights in detail (default: True)",
    )

    args = parser.parse_args()

    # Validate arguments
    for file_path in [args.file1, args.file2]:
        path = Path(file_path)
        if not path.exists():
            print(f"Error: File '{file_path}' does not exist", file=sys.stderr)
            sys.exit(1)
        if not path.is_file():
            print(f"Error: '{file_path}' is not a file", file=sys.stderr)
            sys.exit(1)

    # Compare the files
    lhefilediff = diff_lhe_files(
        args.file1,
        args.file2,
        init=not args.no_init,
        weights=not args.no_weights,
        events=not args.no_events,
        abs_tol=args.abs_tol,
        rel_tol=args.rel_tol,
    )

    lhead = lhefilediff.print()

    if lhead.ndiff != 0:
        print("=" * 60)
        lhead.print()

    # We terminate based on printed string being empty, since that means no differences and events can only be looped once
    sys.exit(0 if lhead.ndiff == 0 else 1)


if __name__ == "__main__":
    main()
