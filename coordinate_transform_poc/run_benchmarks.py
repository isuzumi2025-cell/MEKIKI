#!/usr/bin/env python3
"""
CLI runner — executes the full benchmark suite and writes the report
to stdout and optionally to a file.

Usage:
    python -m coordinate_transform_poc.run_benchmarks [--output report.txt]
"""

from __future__ import annotations

import argparse
import sys
import time

from .accuracy_benchmark import run_full_benchmark
from .boundary_tests import format_boundary_report, run_boundary_tests


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run MEKIKI coordinate-transform POC benchmarks"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Write the report to this file (in addition to stdout).",
    )
    parser.add_argument(
        "--n-accuracy",
        type=int,
        default=100_000,
        help="Number of points for accuracy tests (default: 100 000).",
    )
    parser.add_argument(
        "--n-throughput-scalar",
        type=int,
        default=10_000,
        help="Number of points for scalar throughput (default: 10 000).",
    )
    parser.add_argument(
        "--n-throughput-batch",
        type=int,
        default=1_000_000,
        help="Number of points for batch throughput (default: 1 000 000).",
    )
    args = parser.parse_args()

    t_start = time.perf_counter()

    # ── Part 1: Accuracy + Throughput + Precision ──
    print("Running accuracy / throughput / precision benchmarks …", file=sys.stderr)
    report = run_full_benchmark(
        n_accuracy=args.n_accuracy,
        n_throughput_scalar=args.n_throughput_scalar,
        n_throughput_batch=args.n_throughput_batch,
    )
    report_text = report.print_report()

    # ── Part 2: Boundary / worst-case tests ──
    print("Running boundary / worst-case tests …", file=sys.stderr)
    boundary_results = run_boundary_tests()
    boundary_text = format_boundary_report(boundary_results)

    elapsed = time.perf_counter() - t_start

    full_report = (
        report_text
        + "\n\n"
        + boundary_text
        + f"\n\nTotal benchmark time: {elapsed:.2f} s\n"
    )

    print(full_report)

    if args.output:
        with open(args.output, "w") as fh:
            fh.write(full_report)
        print(f"\nReport written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
