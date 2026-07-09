"""Parallel execution via a process pool (spec sec.3.4 step 5).

Process pool over thread pool: compile+execute kinds are subprocess-heavy,
so processes avoid GIL/lint-lock hazards; python_unit tests run in worker
processes so no shared-state lock is needed (today's error_runner needs a
lint lock; v2 does not).
"""
from __future__ import annotations

import concurrent.futures
import os
import sys
import time

from harness import kinds as kinds_pkg, seeds
from harness.kinds.base import ExecContext
from harness.model import Status, TestCase, TestResult
from harness.workdir import ensure_dir, results_dir_for, work_dir_for


def _execute_one(kind_name: str, case: TestCase, config, master_seed: str, update: bool) -> TestResult:
    if "discovery_error" in case.payload:
        return TestResult(case.id, Status.ERROR, message=case.payload["discovery_error"])

    if case.directives is not None:
        skip_reason = case.directives.value("skip")
        if skip_reason:
            return TestResult(case.id, Status.SKIP, message=skip_reason)

    kind_cls = kinds_pkg.get(kind_name)
    kind = kind_cls()

    cell = case.id.cell
    work_dir = ensure_dir(work_dir_for(case.id.kind, cell, case.id.path, case.id.name))
    results_dir = results_dir_for(case.id.kind, cell, case.id.path, case.id.name)
    per_case_seed = seeds.derive(master_seed, kind_name, case.id.path, case.id.name, cell)
    seed_hex = f"{per_case_seed:016x}"

    ctx = ExecContext(
        work_dir=work_dir,
        results_dir=results_dir,
        seed=seed_hex,
        master_seed=master_seed,
        cell_flags=case.payload.get("cell_flags", []),
        config=config,
        verbose=config.verbose,
    )

    start = time.perf_counter()
    try:
        if update:
            result = kind.update(case, ctx)
        else:
            result = kind.execute(case, ctx)
    except Exception as e:  # noqa: BLE001
        import traceback
        return TestResult(case.id, Status.ERROR, message=str(e), details=traceback.format_exc())
    if result.duration_s == 0.0:
        result.duration_s = time.perf_counter() - start
    return result


class Scheduler:
    def __init__(self, config, master_seed: str, reporter):
        self.config = config
        self.master_seed = master_seed
        self.reporter = reporter

    def run(self, cases: list[TestCase]) -> list[TestResult]:
        results: list[TestResult] = []
        max_workers = max(1, self.config.jobs)

        for case in cases:
            self.reporter.on_case_start(case)

        stop_flag = {"stop": False}

        executor_cls = (
            concurrent.futures.ThreadPoolExecutor
            if max_workers == 1
            else concurrent.futures.ProcessPoolExecutor
        )
        with executor_cls(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_execute_one, case.id.kind, case, self.config, self.master_seed, self.config.update): case
                for case in cases
            }
            try:
                for fut in concurrent.futures.as_completed(futures):
                    case = futures[fut]
                    if stop_flag["stop"]:
                        continue
                    try:
                        result = fut.result()
                    except Exception as e:  # noqa: BLE001
                        import traceback
                        result = TestResult(case.id, Status.ERROR, message=str(e), details=traceback.format_exc())
                    results.append(result)
                    self.reporter.on_case_done(result)
                    if self.config.fail_fast and result.status in (Status.FAIL, Status.ERROR):
                        stop_flag["stop"] = True
                        for f in futures:
                            f.cancel()
            except KeyboardInterrupt:
                print("\nInterrupted -- cancelling pending tests...")
                for f in futures:
                    f.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
                sys.exit(130)

        return results
