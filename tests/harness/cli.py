"""Argument parsing, profiles, and top-level orchestration (spec sec.6)."""
from __future__ import annotations

import argparse
import sys
import time

from harness import coverage_glue, discovery, seeds
from harness.config import PROFILES, RunConfig
from harness.model import Status
from harness.report import ConsoleReporter, JsonReporter, TeeReporter, colorize
from harness.scheduler import Scheduler
from harness.workdir import wipe_trees


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="tests/run.py",
        description="firescript unified test runner",
    )
    ap.add_argument("selectors", nargs="*", help="path / category / kind:X / name:glob selectors")
    ap.add_argument("--update", action="store_true", help="bless mode: rewrite in-file expectations / snapshots")
    ap.add_argument("--jobs", type=int, default=None, help="parallelism (default: cpu count)")
    ap.add_argument("--fail-fast", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--timeout", type=float, default=None)
    ap.add_argument("--compile-timeout", type=float, default=None)
    ap.add_argument("--matrix", default=None, help="quick|full|sample=K")
    ap.add_argument("--determinism", default=None, help="off|sample|all")
    ap.add_argument("--seed", default=None, help="fix the master seed (hex)")
    coverage_group = ap.add_mutually_exclusive_group()
    coverage_group.add_argument("--coverage", dest="coverage", action="store_true", default=None)
    coverage_group.add_argument("--no-coverage", dest="coverage", action="store_false")
    ap.add_argument("--coverage-fail-under", type=float, default=None)
    ap.add_argument("--uncovered", action="store_true")
    ap.add_argument("--json", dest="json_path", default=None)
    ap.add_argument("--keep-artifacts", action="store_true")
    ap.add_argument("--profile", choices=list(PROFILES.keys()), default="local")
    ap.add_argument("--list", dest="list_only", action="store_true")
    return ap


def config_from_args(args: argparse.Namespace) -> RunConfig:
    config = RunConfig(
        selectors=args.selectors,
        update=args.update,
        fail_fast=args.fail_fast,
        verbose=args.verbose,
        seed=seeds.parse_master_seed(args.seed) if args.seed else None,
        coverage=args.coverage,
        coverage_fail_under=args.coverage_fail_under,
        uncovered=args.uncovered,
        json_path=args.json_path,
        keep_artifacts=args.keep_artifacts,
        list_only=args.list_only,
        profile=args.profile,
    )
    if args.jobs is not None:
        config.jobs = args.jobs
    if args.timeout is not None:
        config.timeout = args.timeout
    if args.compile_timeout is not None:
        config.compile_timeout = args.compile_timeout

    config._matrix_is_default = args.matrix is None
    config._determinism_is_default = args.determinism is None
    config.apply_profile()
    if args.matrix is not None:
        config.matrix = args.matrix
    if args.determinism is not None:
        config.determinism = args.determinism

    if config.update:
        config.matrix = "quick"  # --update never runs non-default cells (spec sec.6.3)

    return config


def main(argv: list[str] | None = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    config = config_from_args(args)

    master_seed = config.seed or seeds.new_master_seed()
    config.seed = master_seed
    seed_line = f"Seed: {seeds.format_seed(master_seed)}"
    print(seed_line)

    wipe_trees(config.keep_artifacts or config.list_only)

    cases = discovery.discover_cases(config)
    cases = discovery.apply_selectors(cases, config.selectors)

    if config.list_only:
        for case in cases:
            print(case.id)
        return 0

    use_coverage = config.coverage
    if use_coverage is None:
        use_coverage = coverage_glue.available() and not config.selectors
    cov = coverage_glue.start() if use_coverage else None

    console = ConsoleReporter(verbose=config.verbose)
    json_reporter = JsonReporter() if config.json_path else None
    reporter = TeeReporter(console, json_reporter) if json_reporter else console

    scheduler = Scheduler(config, master_seed, reporter)
    started = time.time()
    results = scheduler.run(cases)

    coverage_pct = None

    def _coverage_report():
        nonlocal coverage_pct
        coverage_pct = coverage_glue.finish(cov, config.uncovered, config.coverage_fail_under)

    console.summarize(results, seed_line, coverage_report_fn=_coverage_report if use_coverage else None)
    if not use_coverage:
        print(colorize("\n(coverage disabled for this run)", "90"))

    if json_reporter is not None:
        json_reporter.write(
            config.json_path, seed=seeds.format_seed(master_seed), profile=config.profile,
            matrix=config.matrix, started=started, coverage_pct=coverage_pct,
        )

    failed = any(r.status in (Status.FAIL, Status.ERROR) for r in results)
    if config.coverage_fail_under is not None and coverage_pct is not None and coverage_pct < config.coverage_fail_under:
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
