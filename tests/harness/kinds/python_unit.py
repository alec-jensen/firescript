"""`python` kind: tests/python/**/test_*.py, run in worker processes
(spec sec.4.4)."""
from __future__ import annotations

import glob
import importlib.util
import os
import sys
import time
import traceback

from harness.config import PYTHON_TESTS_DIR, REPO_ROOT
from harness.directives import DirectiveError, parse_python_directives
from harness.kinds.base import ExecContext, Kind
from harness.model import Status, TestCase, TestId, TestResult
from harness.pyunit import SubtestFailure, TestFailure


def _repo_relative(path: str) -> str:
    return os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")


def _module_name_for(path: str) -> str:
    rel = os.path.relpath(path, REPO_ROOT).replace(os.sep, ".")
    return "tests_python_" + rel[:-3].replace(".", "_")


def _load_module(path: str):
    name = _module_name_for(path)
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PythonUnitKind(Kind):
    name = "python"

    def discover(self, config) -> list[TestCase]:
        cases: list[TestCase] = []
        pattern = os.path.join(PYTHON_TESTS_DIR, "**", "test_*.py")
        for path in sorted(glob.glob(pattern, recursive=True)):
            rel = _repo_relative(path)
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            try:
                module_directives = parse_python_directives(text)
            except DirectiveError as e:
                cases.append(
                    TestCase(
                        id=TestId(kind="python", path=rel, name="<module>"),
                        payload={"discovery_error": str(e)},
                    )
                )
                continue

            try:
                module = _load_module(path)
            except Exception as e:  # noqa: BLE001
                cases.append(
                    TestCase(
                        id=TestId(kind="python", path=rel, name="<import>"),
                        payload={"discovery_error": f"failed to import: {e}"},
                    )
                )
                continue

            for attr_name in dir(module):
                if not attr_name.startswith("test_"):
                    continue
                fn = getattr(module, attr_name)
                if not callable(fn):
                    continue
                param_values = getattr(fn, "_pyunit_params", None)
                if param_values is None:
                    cases.append(
                        TestCase(
                            id=TestId(kind="python", path=rel, name=attr_name),
                            directives=module_directives,
                            payload={"module_path": path, "func_name": attr_name},
                        )
                    )
                else:
                    for value in param_values:
                        cases.append(
                            TestCase(
                                id=TestId(kind="python", path=rel, name=f"{attr_name}[{value}]"),
                                directives=module_directives,
                                payload={"module_path": path, "func_name": attr_name, "param": value},
                            )
                        )
        return cases

    def execute(self, case: TestCase, ctx: ExecContext) -> TestResult:
        start = time.perf_counter()
        try:
            module = _load_module(case.payload["module_path"])
            fn = getattr(module, case.payload["func_name"])
            if "param" in case.payload:
                fn(case.payload["param"])
            else:
                fn()
        except (TestFailure, SubtestFailure, AssertionError) as e:
            return TestResult(
                case.id, Status.FAIL, message=str(e),
                details=traceback.format_exc(), duration_s=time.perf_counter() - start,
            )
        except Exception as e:  # noqa: BLE001
            return TestResult(
                case.id, Status.ERROR, message=str(e),
                details=traceback.format_exc(), duration_s=time.perf_counter() - start,
            )
        return TestResult(case.id, Status.PASS, duration_s=time.perf_counter() - start)
