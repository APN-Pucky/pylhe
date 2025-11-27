#!/usr/bin/env python3
"""
CLI tool to validate LHE files and check momentum conservation.

This tool validates that LHE files can be loaded properly and checks
momentum conservation for each event up to a specified precision.
"""

import argparse
import json
import math
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore[import-untyped]

import pylhe
from pylhe.cli.util import dataclass_with_properties_to_dict


@dataclass
class LHEMomentum:
    px: float
    py: float
    pz: float
    e: float


@dataclass
class LHECheckTotalMomentaViolations:
    event_index: int

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

    def __str__(self) -> str:
        incoming = self.total_incoming
        outgoing = self.total_outgoing
        diffs = self.differences
        rel_diffs = self.rel_differences

        lines = []
        lines.append(f"Event {self.event_index}:")
        lines.append(
            f"  {'Component':<10} {'Incoming':<12} {'Outgoing':<12} {'Abs Diff':<12} {'Rel Diff':<12}"
        )
        lines.append(
            f"  {'-' * 10:<10} {'-' * 12:<12} {'-' * 12:<12} {'-' * 12:<12} {'-' * 12:<12}"
        )

        components = [
            ("px", incoming.px, outgoing.px, diffs.px, rel_diffs.px),
            ("py", incoming.py, outgoing.py, diffs.py, rel_diffs.py),
            ("pz", incoming.pz, outgoing.pz, diffs.pz, rel_diffs.pz),
            ("E", incoming.e, outgoing.e, diffs.e, rel_diffs.e),
        ]

        for comp, inc_val, out_val, diff_val, rel_diff_val in components:
            lines.append(
                f"  {comp:<10} {inc_val:<12.4e} {out_val:<12.4e} {diff_val:<12.4e} {rel_diff_val:<12.4e}"
            )

        return "\n".join(lines)


@dataclass
class LHECheckOnShellViolation:
    event_index: int
    particle_index: int

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

    def __str__(self) -> str:
        lines = []
        lines.append(f"Event {self.event_index}, Particle {self.particle_index}:")
        lines.append(f"    px:  {self.px:>12.4e}")
        lines.append(f"    py:  {self.py:>12.4e}")
        lines.append(f"    pz:  {self.pz:>12.4e}")
        lines.append(f"    e:   {self.e:>12.4e}")
        lines.append(f"    |p|: {self.p:>12.4e}")
        lines.append(f"    m:   {self.m:>12.4e}")
        lines.append(
            f"    ||p| - |m||: {self.difference:.4e} (rel: {self.rel_difference:.4e})"
        )
        return "\n".join(lines)


@dataclass
class LHECheck:
    file: str
    on_shell_violations: list[LHECheckOnShellViolation]
    total_momentum_violations: list[LHECheckTotalMomentaViolations]

    def __str__(self) -> str:
        lines = []
        lines.append("-" * 60)
        lines.append(f"File: {self.file}")

        num_onshell_violations = len(self.on_shell_violations)
        num_momentum_violations = len(self.total_momentum_violations)

        if num_onshell_violations == 0 and num_momentum_violations == 0:
            lines.append("✓ All events pass validation")
            return "\n".join(lines)

        if num_onshell_violations > 0:
            lines.append(f"✗ On-shell violations: {num_onshell_violations}")
            for osviolation in self.on_shell_violations:
                lines.append(f"  {osviolation!s}")

        if num_momentum_violations > 0:
            lines.append(f"✗ Total momentum violations: {num_momentum_violations}")
            for violation in self.total_momentum_violations:
                lines.append(str(violation))

        return "\n".join(lines)


def get_lhecheck(
    filepath: str,
    absolute_threshold: float,
    relative_threshold: float,
    check_momentum: bool = True,
    check_onshell: bool = True,
) -> LHECheck:
    # Read LHE file
    lhefile = pylhe.LHEFile.fromfile(filepath)
    lhecheck = LHECheck(
        file=filepath, on_shell_violations=[], total_momentum_violations=[]
    )

    for event_index, event in enumerate(lhefile.events, start=1):
        particle_index = 0
        lhe_check_total_momenta = LHECheckTotalMomentaViolations(
            event_index=event_index,
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
            lhecheck.total_momentum_violations.append(lhe_check_total_momenta)

        if check_onshell:
            for particle in event.particles:
                particle_index += 1
                if particle.status in [-1, 1]:  # Incoming or outgoing particles
                    lhe_check_onshell = LHECheckOnShellViolation(
                        event_index=event_index,
                        particle_index=particle_index,
                        px=particle.px,
                        py=particle.py,
                        pz=particle.pz,
                        e=particle.e,
                        m=particle.m,
                    )
                    if lhe_check_onshell.is_violation(
                        absolute_threshold, relative_threshold
                    ):
                        lhecheck.on_shell_violations.append(lhe_check_onshell)

    return lhecheck


@dataclass
class LHECheckSummary:
    files: list[LHECheck]

    @property
    def total_violations(self) -> int:
        return sum(
            len(lhecheck.on_shell_violations) + len(lhecheck.total_momentum_violations)
            for lhecheck in self.files
        )

    @property
    def total_files(self) -> int:
        return len(self.files)

    def __str__(self) -> str:
        lines = []
        for lhecheck in self.files:
            lines.append(str(lhecheck))
        lines.append("=" * 60)

        lines.append(f"Files processed: {self.total_files}")
        lines.append(f"Total violations: {self.total_violations:,}")
        lines.append("=" * 60)

        return "\n".join(lines)


def get_lhechecksummary(
    filepaths: list[str],
    absolute_threshold: float,
    relative_threshold: float,
    check_momentum: bool = True,
    check_onshell: bool = True,
) -> LHECheckSummary:
    lhechecks = []
    for filepath in filepaths:
        lhecheck = get_lhecheck(
            filepath,
            absolute_threshold,
            relative_threshold,
            check_momentum,
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
  lhecheck file.lhe -a 1e-8                # Check with higher absolute precision
  lhecheck file.lhe -r 1e-8                # Check with higher relative precision
  lhecheck *.lhe -v                        # Check multiple files with verbose output
  lhecheck file.lhe --format=json          # Output results in JSON format
  lhecheck file.lhe --format=yaml          # Output results in YAML format
  lhecheck file.lhe --no-momentum          # Skip momentum conservation checks
  lhecheck file.lhe --no-onshell           # Skip on-shell mass checks
  lhecheck file.lhe -a 1e-10 -r 1e-8 -v    # Custom thresholds with verbose output
        """,
    )

    parser.add_argument("files", nargs="+", help="LHE file(s) to validate")
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

    args = parser.parse_args()

    # Validate threshold arguments
    if args.absolute <= 0:
        print("Error: Absolute threshold must be positive", file=sys.stderr)
        sys.exit(1)
    if args.relative <= 0:
        print("Error: Relative threshold must be positive", file=sys.stderr)
        sys.exit(1)

    # Expand file paths
    file_paths = []
    for pattern in args.files:
        path = Path(pattern)
        if path.exists():
            if path.is_file():
                file_paths.append(str(path))
            else:
                warnings.warn(f"{pattern} is not a file", UserWarning, stacklevel=2)
        else:
            warnings.warn(f"{pattern} not found", UserWarning, stacklevel=2)

    if not file_paths:
        print("Error: No valid files found", file=sys.stderr)
        sys.exit(1)

    lhecheck_summary = get_lhechecksummary(
        file_paths,
        args.absolute,
        args.relative,
        check_momentum=not args.no_momentum,
        check_onshell=not args.no_onshell,
    )
    print_lhecheck_summary(lhecheck_summary, format=args.format)

    # Exit with appropriate code
    sys.exit(0 if lhecheck_summary.total_violations == 0 else 1)


if __name__ == "__main__":
    main()
