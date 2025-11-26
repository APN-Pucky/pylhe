#!/usr/bin/env python3
"""
CLI tool to validate LHE files and check momentum conservation.

This tool validates that LHE files can be loaded properly and checks
momentum conservation for each event up to a specified precision.
"""

import argparse
import sys
import traceback
import warnings
from pathlib import Path
from typing import Any

import pylhe


def check_momentum_conservation(
    particles: list[pylhe.LHEParticle],
    absolute_threshold: float = 1e-6,
    relative_threshold: float = 1e-6,
) -> tuple[bool, dict[str, Any]]:
    """
    Check momentum conservation for a list of particles.

    Args:
        particles: List of particles in the event
        absolute_threshold: Absolute tolerance for momentum conservation check
        relative_threshold: Relative tolerance for momentum conservation check

    Returns:
        Tuple of (is_conserved, momentum_info) where momentum_info contains
        initial and final momentum sums and differences
    """
    # Separate incoming and outgoing particles
    incoming = [p for p in particles if p.status == -1]
    outgoing = [p for p in particles if p.status == 1]

    # Calculate initial 4-momentum
    initial_px = sum(p.px for p in incoming)
    initial_py = sum(p.py for p in incoming)
    initial_pz = sum(p.pz for p in incoming)
    initial_e = sum(p.e for p in incoming)

    # Calculate final 4-momentum
    final_px = sum(p.px for p in outgoing)
    final_py = sum(p.py for p in outgoing)
    final_pz = sum(p.pz for p in outgoing)
    final_e = sum(p.e for p in outgoing)

    # Calculate differences
    dpx = abs(initial_px - final_px)
    dpy = abs(initial_py - final_py)
    dpz = abs(initial_pz - final_pz)
    de = abs(initial_e - final_e)

    # Calculate relative differences

    pxs = [abs(i.px) for i in [*incoming, *outgoing]] + [
        1e-12
    ]  # Prevent division by zero
    pys = [abs(i.py) for i in [*incoming, *outgoing]] + [
        1e-12
    ]  # Prevent division by zero
    pzs = [abs(i.pz) for i in [*incoming, *outgoing]] + [
        1e-12
    ]  # Prevent division by zero
    es = [abs(i.e) for i in [*incoming, *outgoing]] + [
        1e-12
    ]  # Prevent division by zero

    rdpx = dpx / max(pxs)
    rdpy = dpy / max(pys)
    rdpz = dpz / max(pzs)
    rde = de / max(es)

    # Check conservation using both absolute and relative thresholds
    def check_component(diff: float, rdiff: float) -> bool:
        # Check absolute threshold
        # Check relative threshold (relative to the larger of initial or final)
        return diff < absolute_threshold or rdiff < relative_threshold

    is_conserved = all(
        [
            check_component(dpx, rdpx),
            check_component(dpy, rdpy),
            check_component(dpz, rdpz),
            check_component(de, rde),
        ]
    )

    momentum_info = {
        "initial": {
            "px": initial_px,
            "py": initial_py,
            "pz": initial_pz,
            "e": initial_e,
        },
        "final": {"px": final_px, "py": final_py, "pz": final_pz, "e": final_e},
        "differences": {"dpx": dpx, "dpy": dpy, "dpz": dpz, "de": de},
        "rel_differences": {"rdpx": rdpx, "rdpy": rdpy, "rdpz": rdpz, "rde": rde},
        "incoming_count": len(incoming),
        "outgoing_count": len(outgoing),
    }

    return is_conserved, momentum_info


def validate_lhe_file(
    filepath: str,
    absolute_threshold: float = 1e-6,
    relative_threshold: float = 1e-6,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Validate an LHE file and check momentum conservation.

    Args:
        filepath: Path to the LHE file
        absolute_threshold: Absolute tolerance for momentum conservation check
        relative_threshold: Relative tolerance for momentum conservation check
        verbose: Whether to print detailed information

    Returns:
        Dictionary with validation results
    """
    results = {
        "file": filepath,
        "valid": False,
        "loadable": False,
        "event_count": 0,
        "momentum_violations": 0,
        "max_absolute_violation": 0.0,
        "max_relative_violation": 0.0,
        "errors": [],
    }

    try:
        # Try to load the LHE file
        if verbose:
            print(f"Loading {filepath}...")

        lhefile = pylhe.LHEFile.fromfile(filepath)
        results["loadable"] = True

        if verbose:
            print("✓ File loaded successfully")

        # Check momentum conservation for each event
        event_count = 0
        momentum_violations = 0
        max_absolute_violation = 0.0
        max_relative_violation = 0.0

        for event in lhefile.events:
            event_count += 1

            is_conserved, momentum_info = check_momentum_conservation(
                event.particles, absolute_threshold, relative_threshold
            )

            if not is_conserved:
                momentum_violations += 1
                # Track maximum absolute violation
                max_abs_diff = max(
                    momentum_info["differences"]["dpx"],
                    momentum_info["differences"]["dpy"],
                    momentum_info["differences"]["dpz"],
                    momentum_info["differences"]["de"],
                )
                max_absolute_violation = max(max_absolute_violation, max_abs_diff)

                max_rel_diff = max(
                    momentum_info["rel_differences"]["rdpx"],
                    momentum_info["rel_differences"]["rdpy"],
                    momentum_info["rel_differences"]["rdpz"],
                    momentum_info["rel_differences"]["rde"],
                )

                max_relative_violation = max(max_relative_violation, max_rel_diff)

                if verbose:
                    print(f"✗ Event {event_count}: Momentum not conserved")
                    print(
                        f"  {'Component':<10} {'Initial':<12} {'Final':<12} {'Abs Diff':<12} {'Rel Diff':<12}"
                    )
                    print(
                        f"  {'-' * 10:<10} {'-' * 12:<12} {'-' * 12:<12} {'-' * 12:<12} {'-' * 12:<12}"
                    )

                    initial = momentum_info["initial"]
                    final = momentum_info["final"]
                    diffs = momentum_info["differences"]
                    rel_diffs = momentum_info["rel_differences"]

                    components = [
                        ("px", "px", "dpx", "rdpx"),
                        ("py", "py", "dpy", "rdpy"),
                        ("pz", "pz", "dpz", "rdpz"),
                        ("e", "E", "de", "rde"),
                    ]

                    for comp_key, comp_name, diff_key, rel_diff_key in components:
                        print(
                            f"  {comp_name:<10} {initial[comp_key]:<12.4e} {final[comp_key]:<12.4e} {diffs[diff_key]:<12.4e} {rel_diffs[rel_diff_key]:<12.4e}"
                        )

        results.update(
            {
                "valid": momentum_violations == 0,
                "event_count": event_count,
                "momentum_violations": momentum_violations,
                "max_absolute_violation": max_absolute_violation,
                "max_relative_violation": max_relative_violation,
            }
        )

        if verbose:
            print(f"\nSummary for {filepath}:")
            print(f"  Total events: {event_count:,}")
            print(f"  Momentum violations: {momentum_violations:,}")
            if momentum_violations > 0:
                print(f"  Maximum absolute violation: {max_absolute_violation:.2e}")
                print(f"  Maximum relative violation: {max_relative_violation:.2e}")
                print(f"  Absolute threshold: {absolute_threshold:.2e}")
                print(f"  Relative threshold: {relative_threshold:.2e}")

    except Exception as e:
        results["errors"] = str(e)
        if verbose:
            # show traceback in verbose mode
            print(f"✗ Error loading {filepath}: {e}")
            print(traceback.format_exc())

    return results


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

    # Validate all files
    all_valid = True
    total_events = 0
    total_violations = 0

    for filepath in file_paths:
        results = validate_lhe_file(
            filepath, args.absolute, args.relative, args.verbose
        )

        if not results["loadable"]:
            print(f"✗ {filepath}: Cannot load file")
            print(f"  Error: {results['errors']}")
            all_valid = False
            continue

        if not results["valid"]:
            print(
                f"✗ {filepath}: {results['momentum_violations']}/{results['event_count']} events violate momentum conservation"
            )
            print(
                f"  Maximum absolute violation: {results['max_absolute_violation']:.2e}"
            )
            print(
                f"  Maximum relative violation: {results['max_relative_violation']:.2e}"
            )
            print(
                f"  Thresholds: absolute={args.absolute:.2e}, relative={args.relative:.2e}"
            )
            all_valid = False
        else:
            print(
                f"✓ {filepath}: All {results['event_count']:,} events pass validation"
            )

        total_events += results["event_count"]
        total_violations += results["momentum_violations"]

        if args.verbose and len(file_paths) > 1:
            print()  # Add spacing between files in verbose mode

    # Print summary for multiple files
    if len(file_paths) > 1:
        print("\nOverall Summary:")
        print(f"  Files processed: {len(file_paths)}")
        print(f"  Total events: {total_events:,}")
        print(f"  Total violations: {total_violations:,}")
        print(
            f"  Thresholds: absolute={args.absolute:.2e}, relative={args.relative:.2e}"
        )

    # Exit with appropriate code
    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
