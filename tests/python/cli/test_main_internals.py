"""Direct in-process unit tests for firescript/main.py: _normalize_cli_path,
setup_logging re-entry, _compile_asm's exception-handling branches,
_compile_runtime_file's parse/semantic error branches, _merge_fir_modules'
type/constant dedup branches, compile_file()'s exception-handling branches
(monkeypatching CompilerPipeline / ASTToFIRConverter / FIRToFLIRLowering
methods to raise), lint_text()'s early-exit branches, and main()'s CLI
error-handling branches (monkeypatching sys.argv / targets.resolve_target /
shutil.move and catching SystemExit).

Everything here runs in-process (not via subprocess), following the pattern
already used elsewhere in tests/python/cli for exception-branch coverage.
"""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

import logging  # noqa: E402
import main as main_mod  # noqa: E402
from main import (  # noqa: E402
    _normalize_cli_path,
    _compile_asm,
    _compile_runtime_file,
    _merge_fir_modules,
    compile_file,
    lint_text,
    setup_logging,
    main as cli_main,
)
from compiler_pipeline import CompilerPipeline  # noqa: E402

SOURCES_DIR = t.sources_dir


# --- _normalize_cli_path -----------------------------------------------------

def test_normalize_cli_path_rejects_empty_string():
    try:
        _normalize_cli_path("")
        t.require(False, "expected ValueError")
    except ValueError as e:
        t.require("non-empty" in str(e), str(e))


def test_normalize_cli_path_rejects_non_string():
    try:
        _normalize_cli_path(None)  # type: ignore[arg-type]
        t.require(False, "expected ValueError")
    except ValueError as e:
        t.require("non-empty" in str(e), str(e))


def test_normalize_cli_path_rejects_nul_byte():
    try:
        _normalize_cli_path("some\x00path.fire")
        t.require(False, "expected ValueError")
    except ValueError as e:
        t.require("NUL" in str(e), str(e))


# --- setup_logging re-entry (handlers.clear() branch) ------------------------

def test_setup_logging_clears_existing_handlers():
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    try:
        setup_logging(debug_mode=False)
        first_handler_count = len(root.handlers)
        t.require_eq(first_handler_count, 1)
        # Calling again must hit `if root_logger.hasHandlers(): clear()`
        # instead of accumulating a second handler.
        setup_logging(debug_mode=True)
        t.require_eq(len(root.handlers), 1)
        t.require_eq(root.level, logging.DEBUG)
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)


def test_setup_logging_json_format():
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    try:
        setup_logging(debug_mode=False, message_format="json")
        t.require_eq(len(root.handlers), 1)
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)


# --- _compile_asm exception branches -----------------------------------------

def _make_trivial_flir_module():
    """Build the smallest possible FLIR module compile_file's normal path
    would produce, so _compile_asm can be called directly."""
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    with open(src, "r") as f:
        content = f.read()
    pipeline = CompilerPipeline(content, "functions.fire", src)
    ast = pipeline.parse()
    if pipeline.has_imports():
        ast = pipeline.resolve_imports()
    ast = pipeline.preprocess()
    pipeline.analyze_semantics()
    from ast_to_fir import ASTToFIRConverter
    from flir import FIRToFLIRLowering

    fir_module = ASTToFIRConverter(ast, module_name="functions").convert()
    flir_module = FIRToFLIRLowering(fir_module, runtime_module=main_mod._runtime_fir_module()).lower()
    return flir_module


def test_compile_asm_codegen_failure_returns_false():
    import codegen.x86_64.flir_to_asm as flir_to_asm_mod

    flir_module = _make_trivial_flir_module()
    orig_generate = flir_to_asm_mod.FLIRToAsmBackend.generate

    def _raise_generate(self):
        raise RuntimeError("injected codegen failure")

    flir_to_asm_mod.FLIRToAsmBackend.generate = _raise_generate
    try:
        with t.tmpdir() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                import time as _time
                result = _compile_asm(flir_module, "functions.fire", None, _time.perf_counter_ns(), _time.perf_counter_ns())
            finally:
                os.chdir(cwd)
        t.require_eq(result, False)
    finally:
        flir_to_asm_mod.FLIRToAsmBackend.generate = orig_generate


def test_compile_asm_assembler_failure_returns_false():
    import backend.x86_64.assembler as assembler_mod

    flir_module = _make_trivial_flir_module()
    orig_assemble = assembler_mod.assemble

    def _raise_assemble(asm_text):
        raise assembler_mod.AssemblerError("injected assembler failure")

    assembler_mod.assemble = _raise_assemble
    main_mod_assemble_backup = None
    try:
        with t.tmpdir() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                import time as _time
                result = _compile_asm(flir_module, "functions.fire", None, _time.perf_counter_ns(), _time.perf_counter_ns())
            finally:
                os.chdir(cwd)
        t.require_eq(result, False)
    finally:
        assembler_mod.assemble = orig_assemble


def test_compile_asm_link_failure_returns_false():
    import backend.windows.pe as pe_mod

    flir_module = _make_trivial_flir_module()
    orig_write_pe = pe_mod.write_pe

    def _raise_write_pe(*args, **kwargs):
        raise RuntimeError("injected link failure")

    pe_mod.write_pe = _raise_write_pe
    try:
        with t.tmpdir() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                import time as _time
                result = _compile_asm(flir_module, "functions.fire", None, _time.perf_counter_ns(), _time.perf_counter_ns())
            finally:
                os.chdir(cwd)
        t.require_eq(result, False)
    finally:
        pe_mod.write_pe = orig_write_pe


def test_compile_asm_emit_obj_unsupported():
    flir_module = _make_trivial_flir_module()
    with t.tmpdir() as tmp:
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            import time as _time
            result = _compile_asm(flir_module, "functions.fire", None, _time.perf_counter_ns(), _time.perf_counter_ns(), emit="obj")
        finally:
            os.chdir(cwd)
    t.require_eq(result, False)


# --- _compile_runtime_file: parse / semantic error branches ------------------

def test_compile_runtime_file_parse_error_raises():
    with t.tmpdir() as tmp:
        bad = os.path.join(tmp, "bad_runtime.fire")
        with open(bad, "w", encoding="utf-8") as f:
            f.write("int32 x = ;\n")
        try:
            _compile_runtime_file(bad)
            t.require(False, "expected RuntimeError")
        except RuntimeError as e:
            t.require("failed to parse" in str(e), str(e))


def test_compile_runtime_file_semantic_error_raises():
    with t.tmpdir() as tmp:
        bad = os.path.join(tmp, "bad_semantic_runtime.fire")
        # Syntactically valid, but a genuine use-after-move semantic error
        # (mirrors tests/sources/invalid/borrow/memory_errors.fire).
        with open(bad, "w", encoding="utf-8") as f:
            f.write(
                "string owned_str = \"hello\";\n"
                "string moved_str = owned_str;\n"
                "int32 len = owned_str.length();\n"
            )
        try:
            _compile_runtime_file(bad)
            t.require(False, "expected RuntimeError")
        except RuntimeError as e:
            t.require("failed semantic analysis" in str(e), str(e))


# --- _merge_fir_modules: type / constant dedup branches ----------------------

def test_merge_fir_modules_adds_new_types_and_constants_skips_dupes():
    from fir import FIRModule, TypeDef
    from fir.ir_module import GlobalConstant
    from fir.ir_types import make_simple

    base = FIRModule("base")
    base.add_type(TypeDef("Existing", "owned", fields=[("x", make_simple("int32"))]))
    base.constants.append(GlobalConstant("EXISTING_C", make_simple("int32"), "1"))

    extra = FIRModule("extra")
    # Duplicate names: must NOT be re-added (exercises the `if not any(...)`
    # False branch for both types and constants).
    extra.add_type(TypeDef("Existing", "owned", fields=[("x", make_simple("int32"))]))
    extra.constants.append(GlobalConstant("EXISTING_C", make_simple("int32"), "1"))
    # New names: must be appended (exercises the True branch).
    extra.add_type(TypeDef("NewType", "owned", fields=[("y", make_simple("int32"))]))
    extra.constants.append(GlobalConstant("NEW_C", make_simple("int32"), "2"))

    merged = _merge_fir_modules(base, extra)

    type_names = [td.name for td in merged.types]
    const_names = [c.name for c in merged.constants]
    t.require_eq(type_names.count("Existing"), 1)
    t.require("NewType" in type_names, type_names)
    t.require_eq(const_names.count("EXISTING_C"), 1)
    t.require("NEW_C" in const_names, const_names)


# --- compile_file: exception-handling branches -------------------------------

def _good_source_path():
    return os.path.join(SOURCES_DIR, "functions", "functions.fire")


def test_compile_file_invalid_path_argument_returns_false():
    result = compile_file("bad\x00path.fire", "windows/x86_64")
    t.require_eq(result, False)


def test_compile_file_invalid_output_path_returns_false():
    result = compile_file(_good_source_path(), "windows/x86_64", out_path="bad\x00out.exe", check=True)
    t.require_eq(result, False)


def test_compile_file_default_link_args_none():
    with t.tmpdir() as tmp:
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            # link_args intentionally omitted -> exercises `if link_args is
            # None: link_args = []` inside compile_file.
            result = compile_file(_good_source_path(), "windows/x86_64", check=True)
        finally:
            os.chdir(cwd)
    t.require_eq(result, True)


def test_compile_file_preprocess_exception_returns_false():
    orig = CompilerPipeline.preprocess

    def _raise(self):
        raise RuntimeError("injected preprocess failure")

    CompilerPipeline.preprocess = _raise
    try:
        with t.tmpdir() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                result = compile_file(_good_source_path(), "windows/x86_64", check=True)
            finally:
                os.chdir(cwd)
        t.require_eq(result, False)
    finally:
        CompilerPipeline.preprocess = orig


def test_compile_file_semantic_analysis_exception_returns_false():
    orig = CompilerPipeline.analyze_semantics

    def _raise(self):
        raise RuntimeError("injected semantic analysis failure")

    CompilerPipeline.analyze_semantics = _raise
    try:
        with t.tmpdir() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                result = compile_file(_good_source_path(), "windows/x86_64", check=True)
            finally:
                os.chdir(cwd)
        t.require_eq(result, False)
    finally:
        CompilerPipeline.analyze_semantics = orig


def test_compile_file_emit_deps_write_failure_is_logged_not_fatal():
    with t.tmpdir() as tmp:
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            base_name = os.path.splitext(os.path.basename(_good_source_path()))[0]
            deps_path = os.path.join("build", f"{base_name}.d")
            os.makedirs(deps_path, exist_ok=True)  # a directory where a file is expected
            result = compile_file(_good_source_path(), "windows/x86_64", check=True, emit_deps=True)
        finally:
            os.chdir(cwd)
    # Failure to write deps is only logged, not fatal -- check still succeeds.
    t.require_eq(result, True)


def test_compile_file_emit_ast_write_failure_returns_false():
    with t.tmpdir() as tmp:
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            base_name = os.path.splitext(os.path.basename(_good_source_path()))[0]
            ast_path = os.path.join("build", f"{base_name}.ast")
            os.makedirs(ast_path, exist_ok=True)  # a directory where a file is expected
            result = compile_file(_good_source_path(), "windows/x86_64", emit="ast")
        finally:
            os.chdir(cwd)
    t.require_eq(result, False)


def test_compile_file_emit_ast_success_returns_path():
    with t.tmpdir() as tmp:
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            result = compile_file(_good_source_path(), "windows/x86_64", emit="ast")
        finally:
            os.chdir(cwd)
    t.require(bool(result) and str(result).endswith(".ast"), result)


def test_compile_file_ast_to_fir_exception_returns_false():
    import ast_to_fir as ast_to_fir_mod

    orig = ast_to_fir_mod.ASTToFIRConverter.convert

    def _raise(self):
        raise RuntimeError("injected AST->FIR failure")

    ast_to_fir_mod.ASTToFIRConverter.convert = _raise
    try:
        with t.tmpdir() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                result = compile_file(_good_source_path(), "windows/x86_64")
            finally:
                os.chdir(cwd)
        t.require_eq(result, False)
    finally:
        ast_to_fir_mod.ASTToFIRConverter.convert = orig


def test_compile_file_fir_to_flir_exception_returns_false():
    import flir as flir_mod

    orig = flir_mod.FIRToFLIRLowering.lower

    def _raise(self):
        raise RuntimeError("injected FIR->FLIR failure")

    flir_mod.FIRToFLIRLowering.lower = _raise
    try:
        with t.tmpdir() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                result = compile_file(_good_source_path(), "windows/x86_64")
            finally:
                os.chdir(cwd)
        t.require_eq(result, False)
    finally:
        flir_mod.FIRToFLIRLowering.lower = orig


# --- lint_text ----------------------------------------------------------------

def test_lint_text_parser_errors_no_imports_returns_early():
    errors = lint_text("int32 x = ;\n")
    t.require(len(errors) > 0)


def test_lint_text_clean_source_returns_no_errors():
    errors = lint_text("int32 x = 1;\n")
    t.require_eq(errors, [])


def test_lint_text_import_resolution_exception_returns_parser_errors():
    errors = lint_text("import definitely_missing_module_xyz.helper;\nint32 x = helper(1);\n")
    t.require(isinstance(errors, list))


def test_lint_text_preprocess_exception_returns_errors_so_far():
    orig = CompilerPipeline.preprocess

    def _raise(self):
        raise RuntimeError("injected lint preprocess failure")

    CompilerPipeline.preprocess = _raise
    try:
        errors = lint_text("int32 x = 1;\n")
        t.require(isinstance(errors, list))
    finally:
        CompilerPipeline.preprocess = orig


def test_lint_text_semantic_analysis_exception_is_swallowed():
    orig = CompilerPipeline.analyze_semantics

    def _raise(self):
        raise RuntimeError("injected lint semantic failure")

    CompilerPipeline.analyze_semantics = _raise
    try:
        # Must not raise -- the except branch is a bare `pass`.
        errors = lint_text("int32 x = 1;\n")
        t.require(isinstance(errors, list))
    finally:
        CompilerPipeline.analyze_semantics = orig


def test_lint_text_restores_log_level_in_finally():
    root = logging.getLogger()
    saved_level = root.level
    try:
        root.setLevel(logging.INFO)
        lint_text("int32 x = 1;\n")
        t.require_eq(root.level, logging.INFO)
    finally:
        root.setLevel(saved_level)


# --- main(): CLI-level error branches -----------------------------------------

def _run_main_with_argv(argv):
    """Call main.main() with a patched sys.argv, capturing SystemExit."""
    orig_argv = sys.argv
    sys.argv = ["main.py"] + argv
    try:
        try:
            cli_main()
            return 0
        except SystemExit as e:
            return e.code
    finally:
        sys.argv = orig_argv


def test_main_unknown_host_error_exits_1():
    import targets

    orig_resolve = targets.resolve_target

    def _raise(platform, arch):
        raise targets.UnknownHostError("injected unknown host")

    targets.resolve_target = _raise
    try:
        code = _run_main_with_argv([_good_source_path(), "--check"])
        t.require_eq(code, 1)
    finally:
        targets.resolve_target = orig_resolve


def test_main_invalid_file_path_argument_exits_1():
    code = _run_main_with_argv(["bad\x00path.fire"])
    t.require_eq(code, 1)


def test_main_invalid_dir_path_argument_exits_1():
    code = _run_main_with_argv(["--dir", "bad\x00dir"])
    t.require_eq(code, 1)


def test_main_output_move_failure_exits_1():
    import shutil as shutil_mod

    orig_move = shutil_mod.move

    def _raise(src, dst):
        raise OSError("injected move failure")

    shutil_mod.move = _raise
    try:
        with t.tmpdir() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                # --emit-fir always writes to build/<name>.fir regardless of
                # -o, so output_path != args.output here -- the only way to
                # actually reach main()'s shutil.move rename branch (a plain
                # -o binary compile writes directly to args.output already).
                out_path = os.path.join(tmp, "custom_output.fir")
                code = _run_main_with_argv([_good_source_path(), "--emit-fir", "-o", out_path])
            finally:
                os.chdir(cwd)
        t.require_eq(code, 1)
    finally:
        shutil_mod.move = orig_move


def test_main_dir_with_no_fire_files_warns_but_succeeds():
    with t.tmpdir() as tmp:
        code = _run_main_with_argv(["--dir", tmp])
    t.require(code is None or code == 0)
