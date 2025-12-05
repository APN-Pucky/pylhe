#!/usr/bin/env python3
"""
CLI tool to validate LHE files and check momentum conservation.

This tool validates that LHE files can be loaded properly and checks
momentum conservation for each event up to a specified precision.
"""

# APN TODO this should also check mother daughter momentum conservations

import argparse
import json
import math
import sys
import warnings
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, TextIO, Union

import yaml  # type: ignore[import-untyped]
from typing_extensions import Self

import pylhe
from pylhe.cli.util import dataclass_with_properties_to_dict


@dataclass
class LHECheckAccumulatedSummary:
    total_files_checked: int
    total_events_with_violations: int
    total_positive_mass_violations: int
    total_onshell_violations: int
    total_total_momentum_violations: int

    @property
    def total_violations(self) -> int:
        return (
            self.total_positive_mass_violations
            + self.total_onshell_violations
            + self.total_total_momentum_violations
        )

    def __add__(
        self, other: "LHECheckAccumulatedSummary"
    ) -> "LHECheckAccumulatedSummary":
        return LHECheckAccumulatedSummary(
            total_files_checked=self.total_files_checked + other.total_files_checked,
            total_events_with_violations=self.total_events_with_violations
            + other.total_events_with_violations,
            total_positive_mass_violations=self.total_positive_mass_violations
            + other.total_positive_mass_violations,
            total_onshell_violations=self.total_onshell_violations
            + other.total_onshell_violations,
            total_total_momentum_violations=self.total_total_momentum_violations
            + other.total_total_momentum_violations,
        )

    def __iadd__(self, other: "LHECheckAccumulatedSummary") -> Self:
        self.total_files_checked += other.total_files_checked
        self.total_events_with_violations += other.total_events_with_violations
        self.total_positive_mass_violations += other.total_positive_mass_violations
        self.total_onshell_violations += other.total_onshell_violations
        self.total_total_momentum_violations += other.total_total_momentum_violations
        return self

    def print(self, *args: Any, **kwargs: Any) -> None:
        strings = []
        strings.append(f"Total files checked: {self.total_files_checked}")
        strings.append(
            f"Total events with violations: {self.total_events_with_violations}"
        )
        strings.append(f"Total violations: {self.total_violations}")
        strings.append(
            f"  Positive mass violations: {self.total_positive_mass_violations}"
        )
        strings.append(f"  On-shell mass violations: {self.total_onshell_violations}")
        strings.append(
            f"  Total momentum violations: {self.total_total_momentum_violations}"
        )

        print("\n".join(strings), *args, **kwargs)


@dataclass
class LHEMomentum:
    px: float
    py: float
    pz: float
    e: float


@dataclass
class LHECheckTotalMomentaViolations:
    incoming: list[LHEMomentum]
    outgoing: list[LHEMomentum]

    @property
    def total_incoming(self) -> LHEMomentum:
        total_px = sum(p.px for p in self.incoming)
        total_py = sum(p.py for p in self.incoming)
        total_pz = sum(p.pz for p in self.incoming)
        total_e = sum(p.e for p in self.incoming)
        return LHEMomentum(px=total_px, py=total_py, pz=total_pz, e=total_e)

    @property
    def total_outgoing(self) -> LHEMomentum:
        total_px = sum(p.px for p in self.outgoing)
        total_py = sum(p.py for p in self.outgoing)
        total_pz = sum(p.pz for p in self.outgoing)
        total_e = sum(p.e for p in self.outgoing)
        return LHEMomentum(px=total_px, py=total_py, pz=total_pz, e=total_e)

    @property
    def differences(self) -> LHEMomentum:
        total_in = self.total_incoming
        total_out = self.total_outgoing
        return LHEMomentum(
            px=abs(total_in.px - total_out.px),
            py=abs(total_in.py - total_out.py),
            pz=abs(total_in.pz - total_out.pz),
            e=abs(total_in.e - total_out.e),
        )

    @property
    def rel_differences(self) -> LHEMomentum:
        diff = self.differences

        refpx = max(
            [abs(p.px) for p in self.incoming + self.outgoing] + [1e-12]
        )  # Prevent division by zero
        refpy = max([abs(p.py) for p in self.incoming + self.outgoing] + [1e-12])
        refpz = max([abs(p.pz) for p in self.incoming + self.outgoing] + [1e-12])
        refe = max([abs(p.e) for p in self.incoming + self.outgoing] + [1e-12])

        return LHEMomentum(
            px=diff.px / refpx,  # Prevent division by zero
            py=diff.py / refpy,
            pz=diff.pz / refpz,
            e=diff.e / refe,
        )

    def is_violation(
        self, absolute_threshold: float, relative_threshold: float
    ) -> bool:
        diffs = self.differences
        rel_diffs = self.rel_differences
        return (
            not (diffs.px < absolute_threshold or rel_diffs.px < relative_threshold)
            or not (diffs.py < absolute_threshold or rel_diffs.py < relative_threshold)
            or not (diffs.pz < absolute_threshold or rel_diffs.pz < relative_threshold)
            or not (diffs.e < absolute_threshold or rel_diffs.e < relative_threshold)
        )

    def print(self, *args: Any, **kwargs: Any) -> LHECheckAccumulatedSummary:
        incoming = self.total_incoming
        outgoing = self.total_outgoing
        diffs = self.differences
        rel_diffs = self.rel_differences

        lines = []
        lines.append(f"  {'Metric':<12} {'px':<12} {'py':<12} {'pz':<12} {'E':<12}")
        lines.append(
            f"  {'-' * 12:<12} {'-' * 12:<12} {'-' * 12:<12} {'-' * 12:<12} {'-' * 12:<12}"
        )

        metrics = [
            ("Incoming", incoming.px, incoming.py, incoming.pz, incoming.e),
            ("Outgoing", outgoing.px, outgoing.py, outgoing.pz, outgoing.e),
            ("Abs Diff", diffs.px, diffs.py, diffs.pz, diffs.e),
            ("Rel Diff", rel_diffs.px, rel_diffs.py, rel_diffs.pz, rel_diffs.e),
        ]

        for metric, px_val, py_val, pz_val, e_val in metrics:
            lines.append(
                f"  {metric:<12} {px_val:<12.4e} {py_val:<12.4e} {pz_val:<12.4e} {e_val:<12.4e}"
            )
        print("\n".join(lines), *args, **kwargs)
        return LHECheckAccumulatedSummary(
            total_files_checked=0,
            total_events_with_violations=0,
            total_positive_mass_violations=0,
            total_onshell_violations=0,
            total_total_momentum_violations=1,
        )


@dataclass
class LHECheckOnShellViolation:
    px: float
    py: float
    pz: float
    e: float
    m: float

    @property
    def p(self) -> float:
        # TODO check fail on negative mass?!
        return math.sqrt(abs(self.e**2 - (self.px**2 + self.py**2 + self.pz**2)))

    @property
    def difference(self) -> float:
        return abs(self.p - self.m)

    @property
    def rel_difference(self) -> float:
        return self.difference / max(
            abs(self.m), abs(self.p), 1e-12
        )  # Prevent division by zero

    def is_violation(
        self, absolute_threshold: float, relative_threshold: float
    ) -> bool:
        return not (
            self.difference < absolute_threshold
            or self.rel_difference < relative_threshold
        )

    def print(self, *args: Any, **kwargs: Any) -> LHECheckAccumulatedSummary:
        lines = []
        lines.append("✗ On-shell mass violation:")
        lines.append(f"    px:  {self.px:>12.4e}")
        lines.append(f"    py:  {self.py:>12.4e}")
        lines.append(f"    pz:  {self.pz:>12.4e}")
        lines.append(f"    e:   {self.e:>12.4e}")
        lines.append(f"    |p|: {self.p:>12.4e}")
        lines.append(f"    m:   {self.m:>12.4e}")
        lines.append(
            f"    ||p| - |m||: {self.difference:.4e} (rel: {self.rel_difference:.4e})"
        )
        print("\n".join(lines), *args, **kwargs)
        return LHECheckAccumulatedSummary(
            total_files_checked=0,
            total_events_with_violations=0,
            total_positive_mass_violations=0,
            total_onshell_violations=1,
            total_total_momentum_violations=0,
        )


@dataclass
class LHECheckPositiveMassViolation:
    px: float
    py: float
    pz: float
    e: float

    @property
    def p2(self) -> float:
        return self.px**2 + self.py**2 + self.pz**2

    @property
    def e2(self) -> float:
        return self.e**2

    @property
    def m2(self) -> float:
        return self.e2 - self.p2

    def is_violation(self) -> bool:
        return self.p2 > self.e2

    def print(self, *args: Any, **kwargs: Any) -> LHECheckAccumulatedSummary:
        lines = []
        lines.append("✗ Positive mass violation:")
        lines.append(f"    px:  {self.px:>12.4e}")
        lines.append(f"    py:  {self.py:>12.4e}")
        lines.append(f"    pz:  {self.pz:>12.4e}")
        lines.append(f"    e:   {self.e:>12.4e}")
        lines.append(f"    p²:  {self.p2:>12.4e}")
        lines.append(f"    e²:  {self.e2:>12.4e}")
        lines.append(f"    m²:  {self.m2:>12.4e} (negative - unphysical)")
        print("\n".join(lines), *args, **kwargs)
        return LHECheckAccumulatedSummary(
            total_files_checked=0,
            total_events_with_violations=0,
            total_positive_mass_violations=1,
            total_onshell_violations=0,
            total_total_momentum_violations=0,
        )


@dataclass
class LHECheckParticleViolation:
    particle_index: int
    on_shell_violations: Optional[LHECheckOnShellViolation]
    positive_mass_violation: Optional[LHECheckPositiveMassViolation]

    @property
    def total_violations(self) -> int:
        return sum(
            v is not None
            for v in [self.on_shell_violations, self.positive_mass_violation]
        )

    def print(self, *args: Any, **kwargs: Any) -> LHECheckAccumulatedSummary:
        ret = LHECheckAccumulatedSummary(
            total_files_checked=0,
            total_events_with_violations=0,
            total_positive_mass_violations=0,
            total_onshell_violations=0,
            total_total_momentum_violations=0,
        )
        print(f"✗ Particle {self.particle_index} violations:", *args, **kwargs)
        if self.on_shell_violations is not None:
            ret += self.on_shell_violations.print(*args, **kwargs)
        if self.positive_mass_violation is not None:
            ret += self.positive_mass_violation.print(*args, **kwargs)
        return ret


@dataclass
class LHECheckEventViolation:
    event_index: int
    particle_violations: list[LHECheckParticleViolation]
    total_momentum_violations: Optional[LHECheckTotalMomentaViolations]

    @property
    def total_violations(self) -> int:
        count = sum(p.total_violations for p in self.particle_violations)
        if self.total_momentum_violations is not None:
            count += 1
        return count

    def print(self, *args: object, **kwargs: object) -> LHECheckAccumulatedSummary:
        ret = LHECheckAccumulatedSummary(
            total_files_checked=0,
            total_events_with_violations=0,
            total_positive_mass_violations=0,
            total_onshell_violations=0,
            total_total_momentum_violations=0,
        )
        print(f"✗ Event {self.event_index} violations:")
        for pviolation in self.particle_violations:
            ret += pviolation.print(*args, **kwargs)
        if self.total_momentum_violations is not None:
            ret += self.total_momentum_violations.print(*args, **kwargs)
        return ret


@dataclass
class LHECheck:
    file: str
    check_events: Iterable[LHECheckEventViolation]

    def print(self, *args: Any, **kwargs: Any) -> LHECheckAccumulatedSummary:
        ret = LHECheckAccumulatedSummary(
            total_events_with_violations=0,
            total_positive_mass_violations=0,
            total_onshell_violations=0,
            total_total_momentum_violations=0,
            total_files_checked=1,
        )
        print("-" * 60, *args, **kwargs)
        print(f"File: {self.file}", *args, **kwargs)
        for event in self.check_events:
            ret += event.print(*args, **kwargs)
        return ret


def get_lhecheck(
    filepath_or_fileobj: Union[str, TextIO],
    absolute_threshold: float,
    relative_threshold: float,
    check_momentum: bool,
    check_mass: bool,
    check_onshell: bool,
) -> LHECheck:
    # Read LHE file
    if isinstance(filepath_or_fileobj, str):
        lhefile = pylhe.LHEFile.fromfile(filepath_or_fileobj)
        file_display_name = filepath_or_fileobj
    else:
        lhefile = pylhe.LHEFile.frombuffer(filepath_or_fileobj)
        file_display_name = "<stdin>"

    def _generator() -> Iterable[LHECheckEventViolation]:
        for event_index, event in enumerate(lhefile.events, start=1):
            lhecheck_event = LHECheckEventViolation(
                event_index=event_index,
                particle_violations=[],
                total_momentum_violations=None,
            )
            lhe_check_total_momenta = LHECheckTotalMomentaViolations(
                incoming=[
                    LHEMomentum(
                        px=particle.px, py=particle.py, pz=particle.pz, e=particle.e
                    )
                    for particle in event.particles
                    if particle.status == -1
                ],  # Incoming
                outgoing=[
                    LHEMomentum(
                        px=particle.px, py=particle.py, pz=particle.pz, e=particle.e
                    )
                    for particle in event.particles
                    if particle.status == 1
                ],  # Outgoing
            )
            if check_momentum and lhe_check_total_momenta.is_violation(
                absolute_threshold, relative_threshold
            ):
                lhecheck_event.total_momentum_violations = lhe_check_total_momenta

            for particle_index, particle in enumerate(event.particles, start=1):
                lhe_particle_check = LHECheckParticleViolation(
                    particle_index=particle_index,
                    on_shell_violations=None,
                    positive_mass_violation=None,
                )
                if check_mass:
                    lhe_check_mass = LHECheckPositiveMassViolation(
                        px=particle.px, py=particle.py, pz=particle.pz, e=particle.e
                    )
                    if lhe_check_mass.is_violation():
                        lhe_particle_check.positive_mass_violation = lhe_check_mass
                if check_onshell and particle.status in [
                    -1,
                    1,
                ]:  # Incoming or outgoing particles
                    lhe_check_onshell = LHECheckOnShellViolation(
                        px=particle.px,
                        py=particle.py,
                        pz=particle.pz,
                        e=particle.e,
                        m=particle.m,
                    )
                    if lhe_check_onshell.is_violation(
                        absolute_threshold, relative_threshold
                    ):
                        lhe_particle_check.on_shell_violations = lhe_check_onshell
                if lhe_particle_check.total_violations > 0:
                    lhecheck_event.particle_violations.append(lhe_particle_check)
            if lhecheck_event.total_violations > 0:
                yield lhecheck_event

    return LHECheck(
        file=file_display_name,
        check_events=_generator(),
    )


@dataclass
class LHECheckSummary:
    files: list[LHECheck]

    def print(self, *args: Any, **kwargs: Any) -> LHECheckAccumulatedSummary:
        ret = LHECheckAccumulatedSummary(
            total_files_checked=0,
            total_events_with_violations=0,
            total_positive_mass_violations=0,
            total_onshell_violations=0,
            total_total_momentum_violations=0,
        )
        for lhecheck in self.files:
            ret += lhecheck.print(*args, **kwargs)
        return ret


def get_lhechecksummary(
    filepaths_or_fileobjs: list[Union[str, TextIO]],
    absolute_threshold: float,
    relative_threshold: float,
    check_momentum: bool,
    check_mass: bool,
    check_onshell: bool,
) -> LHECheckSummary:
    lhechecks = []
    for filepath_or_fileobj in filepaths_or_fileobjs:
        lhecheck = get_lhecheck(
            filepath_or_fileobj,
            absolute_threshold,
            relative_threshold,
            check_momentum,
            check_mass,
            check_onshell,
        )
        lhechecks.append(lhecheck)
    return LHECheckSummary(files=lhechecks)


def print_lhecheck_summary(
    lhecheck_summary: LHECheckSummary, format: str = "plain"
) -> None:
    """Print LHE check summary in the specified format."""
    if format == "json":
        print(json.dumps(dataclass_with_properties_to_dict(lhecheck_summary), indent=2))
    elif format == "yaml":
        print(
            yaml.dump(
                dataclass_with_properties_to_dict(lhecheck_summary),
                default_flow_style=False,
            )
        )
    else:
        print(str(lhecheck_summary))


def main() -> None:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Validate LHE files and check momentum conservation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lhecheck file.lhe                        # Check with default thresholds (1e-6)
  cat file.lhe | lhecheck                   # Read from stdin
  lhecheck file.lhe -a 1e-8                # Check with higher absolute precision
  lhecheck file.lhe -r 1e-8                # Check with higher relative precision
  lhecheck *.lhe -v                        # Check multiple files with verbose output
  lhecheck file.lhe --format=json          # Output results in JSON format
  lhecheck file.lhe --format=yaml          # Output results in YAML format
  lhecheck file.lhe --no-momentum          # Skip momentum conservation checks
  lhecheck file.lhe --no-onshell           # Skip on-shell mass checks
  lhecheck file.lhe -a 1e-10 -r 1e-8 -v    # Custom thresholds with verbose output
  cat file.lhe | lhecheck -v --format=json  # Read from stdin with verbose JSON output
        """,
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="LHE file(s) to validate (or read from stdin if not provided)",
    )
    parser.add_argument(
        "-a",
        "--absolute",
        type=float,
        default=1e-6,
        help="Absolute threshold for momentum conservation (default: 1e-6)",
    )
    parser.add_argument(
        "-r",
        "--relative",
        type=float,
        default=1e-6,
        help="Relative threshold for momentum conservation (default: 1e-6)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed information during validation",
    )
    parser.add_argument(
        "--format",
        choices=["plain", "json", "yaml"],
        default="plain",
        help="Output format (default: plain)",
    )
    parser.add_argument(
        "--no-momentum",
        action="store_true",
        help="Skip total momentum conservation checks",
    )
    parser.add_argument(
        "--no-onshell",
        action="store_true",
        help="Skip on-shell mass checks",
    )

    parser.add_argument(
        "--no-mass",
        action="store_true",
        help="Skip positive mass checks",
    )

    args = parser.parse_args()

    # Validate threshold arguments
    if args.absolute <= 0:
        print("Error: Absolute threshold must be positive", file=sys.stderr)
        sys.exit(1)
    if args.relative <= 0:
        print("Error: Relative threshold must be positive", file=sys.stderr)
        sys.exit(1)

    # Check if reading from stdin
    use_stdin = not args.files and not sys.stdin.isatty()

    file_inputs: list[Union[str, TextIO]] = []
    if use_stdin:
        # Read from stdin
        if args.verbose:
            print("Reading LHE data from stdin...", file=sys.stderr)

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
            else:
                warnings.warn(f"{pattern} not found", UserWarning, stacklevel=2)

        if not file_inputs:
            print("Error: No valid files found and no stdin data", file=sys.stderr)
            sys.exit(1)

    lhecheck_summary = get_lhechecksummary(
        file_inputs,
        args.absolute,
        args.relative,
        check_momentum=not args.no_momentum,
        check_mass=not args.no_mass,
        check_onshell=not args.no_onshell,
    )
    lheas = lhecheck_summary.print()
    print("=" * 60)
    lheas.print()

    # Exit with appropriate code
    sys.exit(0 if lheas.total_violations == 0 else 1)


if __name__ == "__main__":
    main()
