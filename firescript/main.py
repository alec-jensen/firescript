import argparse
import logging
import os
import sys
import shutil
import glob
import time

from log_formatter import LogFormatter
from compiler_pipeline import CompilerPipeline
from errors import CompileTimeError
from utils.file_utils import safe_relpath
import targets

FIRESCRIPT_VERSION = "0.5.0"
FIRESCRIPT_RELEASE_DATE = "July 2, 2026"
FIRESCRIPT_RELEASE_NAME = "Kirin"


def _normalize_cli_path(path_value: str) -> str:
    """Normalize a user-provided local path for trusted CLI file operations."""
    if not isinstance(path_value, str) or not path_value:
        raise ValueError("Path must be a non-empty string")
    if "\x00" in path_value:
        raise ValueError("Path contains invalid NUL byte")
    return os.path.abspath(os.path.expanduser(path_value))


def _log_stage_duration(stage_name: str, start_time_ns: int) -> int:
    """Log a debug timing line for a compiler stage and return a new start time."""
    end_time_ns = time.perf_counter_ns()
    logging.debug(f"{stage_name} completed in {(end_time_ns - start_time_ns) / 1_000_000:.2f} ms")
    return end_time_ns


def setup_logging(debug_mode=False, message_format="text"):
    """Configure logging with custom formatter."""
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    console_handler = logging.StreamHandler()
    if message_format == "json":
        from log_formatter import JsonFormatter
        formatter = JsonFormatter()
    else:
        formatter = LogFormatter()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


def _compile_asm(flir_module, file_path, out_path, start_time, stage_start,
                 emit="bin", no_link=False, link_args=None):
    """FLIR -> x86-64 assembly -> machine code -> PE32+ executable.

    Everything is done in-process with the pure-Python assembler and PE
    writer; no external tools are invoked.
    """
    # Only windows/x86_64 is implemented today (see firescript/targets.py);
    # a second supported target would need these picked per-target instead
    # of hardcoded to the x86_64/windows backend.
    from codegen.x86_64.flir_to_asm import FLIRToAsmBackend
    from backend.x86_64.assembler import assemble, AssemblerError
    from backend.windows.pe import write_pe

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    os.makedirs("build/temp", exist_ok=True)
    if emit == "asm":
        # A user-facing deliverable at a stable default path (tests and
        # docs depend on this exact name when -o isn't given).
        asm_path = os.path.join("build", "temp", f"{base_name}.s")
    else:
        # Pure scratch file consumed only by the assembler below and never
        # exposed to the user -- PID-suffixed so concurrent compiler
        # invocations of the same source file (or files sharing a
        # basename) never write it to the same path at once.
        asm_path = os.path.join("build", "temp", f"{base_name}.{os.getpid()}.s")

    try:
        asm_text = FLIRToAsmBackend(flir_module).generate()
    except Exception as e:
        logging.error(f"Code generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    # Locale-default encoding on purpose: source files are read with the
    # locale encoding, so the .s round-trips string literal bytes exactly.
    with open(asm_path, "w", newline="\n") as f:
        f.write(asm_text)
    stage_start = _log_stage_duration("Code generation", stage_start)

    if emit == "asm":
        final_asm = out_path if out_path else asm_path
        if out_path:
            shutil.copy(asm_path, out_path)  # deepcode ignore PathTraversal: user-selected local output path.
        logging.info(f"Assembly written to {final_asm}")
        return final_asm

    if emit == "obj" or no_link:
        logging.error("--emit obj / --no-link is not supported")
        return False

    try:
        obj = assemble(asm_text)
    except AssemblerError as e:
        logging.error(f"Assembly failed: {e}")
        return False
    stage_start = _log_stage_duration("Assemble", stage_start)

    import_dll_map = {
        sym: info[0] for sym, info in getattr(flir_module, "externs", {}).items()
    }
    os.makedirs("build", exist_ok=True)
    final_out = out_path if out_path else os.path.join("build", base_name + ".exe")
    if not final_out.lower().endswith(".exe"):
        final_out += ".exe"
    try:
        write_pe(obj, final_out, import_dll_map=import_dll_map)
    except Exception as e:  # noqa: BLE001
        logging.error(f"Linking (PE write) failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    _log_stage_duration("Link", stage_start)

    end_time = time.perf_counter_ns()
    logging.info(
        f"Compilation of {file_path} completed successfully in {(end_time - start_time) / 1_000_000:.2f} ms"
    )
    logging.info(f"Binary written to {os.path.abspath(final_out)}")
    return final_out


_RUNTIME_FIR_CACHE = None


def _collect_internal_signatures(files: list) -> dict:
    """Lightweight pre-scan of every std/internal/*.fire file's top-level
    declarations, used to seed cross-file symbol visibility for the real
    per-file compile below (_compile_runtime_file). std/internal/ files
    carry no import statements (that pipeline stage is never run for them),
    so without this, a function in one file calling a function defined in
    a sibling file would silently resolve to an unknown return type during
    that file's own (independent) parse -- only the signature is harvested
    here; whether a file's own body type-checks correctly against those
    signatures is decided later, by the real (seeded) parse."""
    from enums import NodeTypes
    from builtin_methods import parse_internal_file_cached

    seed = {
        "user_functions": {},
        "generic_functions": {},
        "generic_constraints": {},
        "user_classes": {},
        "user_types": set(),
    }
    for path in files:
        ast, _ = parse_internal_file_cached(path)
        for child in ast.children:
            if child.node_type in (NodeTypes.FUNCTION_DEFINITION, NodeTypes.GENERATOR_DEFINITION):
                seed["user_functions"][child.name] = child.return_type
                type_params = getattr(child, "type_params", None)
                if type_params:
                    seed["generic_functions"][child.name] = type_params
                    seed["generic_constraints"][child.name] = getattr(child, "type_constraints", None) or {}
            elif child.node_type == NodeTypes.CLASS_DEFINITION:
                fields = {
                    fchild.name: fchild.var_type
                    for fchild in child.children
                    if fchild.node_type == NodeTypes.CLASS_FIELD
                }
                seed["user_classes"][child.name] = fields
                seed["user_types"].add(child.name)
    return seed


def _compile_runtime_file(path: str, seed: dict = None) -> "ASTNode":
    """Parse + preprocess + semantic-analyze a single std/internal/*.fire
    file, returning its processed AST (not yet converted to FIR -- see
    _runtime_fir_module for why that step is deferred and combined across
    files). `seed`, from _collect_internal_signatures, pre-populates this
    file's own parser state with function/class signatures collected from
    every std/internal/*.fire file, so an ordinary call to a sibling
    file's function type-checks correctly during this file's own parse,
    despite there being no import connecting them."""
    from lexer import Lexer
    from parser import Parser

    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    rel = safe_relpath(path)
    tokens = Lexer(source).tokenize()
    parser_instance = Parser(tokens, source, rel, defer_undefined_identifiers=False)
    if seed is not None:
        parser_instance.user_functions.update(seed["user_functions"])
        parser_instance.generic_functions.update(seed["generic_functions"])
        parser_instance.generic_constraints.update(seed["generic_constraints"])
        parser_instance.user_classes.update(seed["user_classes"])
        parser_instance.user_types.update(seed["user_types"])
    ast = parser_instance.parse()
    pipeline = CompilerPipeline(source, rel, path)
    pipeline.parser_instance = parser_instance
    pipeline.ast = ast
    if pipeline.parser_errors:
        raise RuntimeError(
            f"{rel} failed to parse: {len(pipeline.parser_errors)} errors"
        )
    ast = pipeline.preprocess()
    analyzer = pipeline.analyze_semantics()
    if analyzer.errors:
        analyzer.report_errors()
        raise RuntimeError(
            f"{rel} failed semantic analysis: {len(analyzer.errors)} errors"
        )
    return ast


def _runtime_fir_module():
    """Compile every std/internal/*.fire file (the firescript-implemented
    runtime, float128 stubs, and @builtin_method-backed dispatch modules)
    to a single FIR module, cached per process. Lowering routes fs_rt_*
    calls here. New std/internal/ files are picked up automatically -- no
    changes needed here to add one.

    Each file is parsed/preprocessed/semantic-analyzed on its own (for
    accurate per-file error line/column attribution), but FIR conversion
    runs once, over all files' processed ASTs combined into a single root:
    ASTToFIRConverter's own cross-reference bookkeeping (function/class/
    generic definitions, used to resolve e.g. a callee's real &-borrow
    parameter modes) only sees whichever single AST it's given, so
    converting each file separately would silently default any cross-file
    call's argument modes to "own" instead of resolving the callee's real
    signature -- wrongly moving a borrowed argument.
    """
    global _RUNTIME_FIR_CACHE
    if _RUNTIME_FIR_CACHE is None:
        from ast_to_fir import ASTToFIRConverter

        internal_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "std", "internal"
        )
        # sorted() for deterministic compile/merge order (CLAUDE.md
        # determinism rule).
        files = sorted(glob.glob(os.path.join(internal_dir, "*.fire")))
        seed = _collect_internal_signatures(files)
        asts = [_compile_runtime_file(path, seed) for path in files]
        combined_ast = asts[0]
        for extra_ast in asts[1:]:
            for child in extra_ast.children:
                child.parent = combined_ast
                combined_ast.children.append(child)
        converter = ASTToFIRConverter(combined_ast, module_name="fs_runtime", is_runtime_module=True)
        _RUNTIME_FIR_CACHE = converter.convert()
    return _RUNTIME_FIR_CACHE


def compile_file(file_path, target, out_path=None, emit="bin", check=False, emit_deps=False, no_link=False, link_args=None, emit_fir=False, emit_flir=False):
    """Compile a single firescript file for the given `targets.Target`."""
    if link_args is None:
        link_args = []

    logging.info(f"Starting compilation of {file_path}...")

    try:
        file_path = _normalize_cli_path(file_path)
        if out_path:
            out_path = _normalize_cli_path(out_path)
    except ValueError as e:
        logging.error(f"Invalid path argument: {e}")
        return False

    start_time = time.perf_counter_ns()

    try:
        # Read source file
        with open(file_path, "r") as f:  # deepcode ignore PathTraversal: trusted local CLI input path.
            file_content = f.read()
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        return False
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        return False

    stage_start = time.perf_counter_ns()

    pipeline = CompilerPipeline(
        file_content,
        safe_relpath(file_path),
        file_path,
    )
    ast = pipeline.parse()
    tokens = pipeline.tokens
    logging.debug(f"tokens:\n{'\n'.join([str(token) for token in tokens])}")
    logging.debug(f"ast:\n{ast}")
    stage_start = _log_stage_duration("Lex/parse", stage_start)

    # Resolve imports if present
    has_imports = pipeline.has_imports()
    if has_imports:
        try:
            ast = pipeline.resolve_imports()
            logging.debug("Import resolution completed successfully.")
            logging.debug("Import merge completed successfully.")
        except Exception as e:
            logging.error(f"Import resolution failed: {e}")
            return False

        if pipeline.parser_errors:
            logging.error(f"Parsing failed with {len(pipeline.parser_errors)} errors")
            return False
        stage_start = _log_stage_duration("Import resolution", stage_start)

    # If there were parser errors and no imports, fail now.
    # If imports were present, some 'undefined symbol' errors may be resolved by the merge above.
    if pipeline.parser_errors and not has_imports:
        logging.error(f"Parsing failed with {len(pipeline.parser_errors)} errors")
        return False

    # Preprocess: enable and insert drop() calls if needed (ownership cleanup)
    try:
        ast = pipeline.preprocess()
        logging.debug("Preprocessing (drop insertion) completed.")
    except Exception as e:
        logging.error(f"Preprocessing failed: {e}")
        return False
    stage_start = _log_stage_duration("Preprocessing", stage_start)

    # Semantic analysis: ownership and borrow checking
    try:
        analyzer = pipeline.analyze_semantics()
        if analyzer.errors:
            analyzer.report_errors()
            logging.error(f"Semantic analysis failed with {len(analyzer.errors)} errors")
            return False
        logging.debug("Semantic analysis completed.")
    except Exception as e:
        logging.error(f"Semantic analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    stage_start = _log_stage_duration("Semantic analysis", stage_start)

    # Output deps if requested
    if emit_deps:
        if has_imports and getattr(ast, "_resolver", None):
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            os.makedirs("build", exist_ok=True)
            deps_file = os.path.join("build", f"{base_name}.d")
            try:
                with open(deps_file, "w", encoding="utf-8") as f:
                    f.write(f"build/{base_name}.o: {os.path.abspath(file_path)}")
                    for k, m in ast._resolver.modules.items():
                        if m.path != os.path.abspath(file_path):
                            f.write(f" \\\n  {m.path}")
                    f.write("\n")
            except Exception as e:
                logging.error(f"Failed to write dependencies to {deps_file}: {e}")

    # Emit ast if requested
    if emit == "ast":
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        os.makedirs("build", exist_ok=True)
        ast_out = os.path.join("build", f"{base_name}.ast")
        try:
            with open(ast_out, "w", encoding="utf-8") as f:
                f.write(str(ast))
            logging.info(f"AST written to {ast_out}")
            return ast_out
        except Exception as e:
            logging.error(f"Failed to write AST to {ast_out}: {e}")
            return False

    if check:
        logging.info(f"Check completed for {file_path}")
        return True

    if not targets.is_supported(target):
        logging.error(
            f"Unsupported target: {target}. Currently supported: {targets.supported_targets_str()}"
        )
        return False

    # AST -> FIR -> FLIR -> x86-64 assembly.
    from ast_to_fir import ASTToFIRConverter
    from fir import dump_module
    from flir import FIRToFLIRLowering, dump_flir_module

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    try:
        converter = ASTToFIRConverter(ast, module_name=base_name)
        fir_module = converter.convert()
    except Exception as e:
        logging.error(f"AST->FIR conversion failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    stage_start = _log_stage_duration("AST->FIR conversion", stage_start)

    if emit_fir:
        os.makedirs("build", exist_ok=True)
        fir_out = os.path.join("build", f"{base_name}.fir")
        with open(fir_out, "w", encoding="utf-8", newline="\n") as f:
            f.write(dump_module(fir_module))
        logging.info(f"FIR written to {fir_out}")
        if not emit_flir:
            return fir_out

    try:
        flir_module = FIRToFLIRLowering(fir_module, runtime_module=_runtime_fir_module()).lower()
    except Exception as e:
        logging.error(f"FIR->FLIR lowering failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    stage_start = _log_stage_duration("FIR->FLIR lowering", stage_start)

    if emit_flir:
        os.makedirs("build", exist_ok=True)
        flir_out = os.path.join("build", f"{base_name}.flir")
        with open(flir_out, "w", encoding="utf-8", newline="\n") as f:
            f.write(dump_flir_module(flir_module))
        logging.info(f"FLIR written to {flir_out}")
        return flir_out

    return _compile_asm(
        flir_module, file_path, out_path, start_time, stage_start,
        emit=emit, no_link=no_link, link_args=link_args,
    )


def lint_text(source_text: str, file_path: str = "<stdin>"):
    """
    Lint firescript source text without generating any output code.

    Runs the full compiler front-end (lex → parse → import-merge → preprocess →
    semantic-analysis) against the given in-memory text and returns all collected
    diagnostics as a list of CompileTimeError objects. Line and column are
    1-based when available, otherwise 0.

    This function never writes to disk and never writes to logging — errors are
    returned purely as structured data so callers (e.g. the LSP server) can
    display them without polluting stdio.
    """
    import logging as _logging

    errors: list[CompileTimeError] = []

    # Silence the root logger while linting so that error() calls inside the
    # parser / semantic-analyser don't write to stderr and corrupt JSON-RPC I/O.
    root = _logging.getLogger()
    prev_level = root.level
    root.setLevel(_logging.CRITICAL + 1)

    try:
        pipeline = CompilerPipeline(source_text, file_path, file_path)
        ast = pipeline.parse()
        errors.extend(pipeline.parser_errors)

        # Bail early if the AST is too broken to continue.
        if pipeline.parser_errors and not pipeline.has_imports():
            return errors

        if pipeline.has_imports():
            try:
                ast = pipeline.resolve_imports()
            except Exception:
                return errors

            errors = list(pipeline.parser_errors)
            if errors:
                return errors

        try:
            ast = pipeline.preprocess()
        except Exception:
            return errors

        try:
            analyzer = pipeline.analyze_semantics()
            errors.extend(analyzer.errors)
        except Exception:
            pass

    finally:
        root.setLevel(prev_level)

    return errors


def main():
    """Main entry point for the firescript compiler."""
    parser = argparse.ArgumentParser(description="firescript compiler")

    parser.add_argument("-d", "--debug", action="store_true", help="Debug mode")
    parser.add_argument("-o", "--output", help="Output file")
    parser.add_argument(
        "--platform",
        choices=targets.PLATFORM_CHOICES,
        default=None,
        help="Target platform to compile for. Defaults to the host platform.",
    )
    parser.add_argument(
        "--arch",
        choices=targets.ARCH_CHOICES,
        default=None,
        help="Target architecture to compile for. Defaults to the host architecture.",
    )
    parser.add_argument("--message-format", choices=["text", "json"], default="text", help="Format for diagnostic messages")
    parser.add_argument("--emit", choices=["ast", "asm", "obj", "bin"], default="bin", help="Type of output to generate")
    parser.add_argument("--emit-fir", action="store_true", help="Dump FIR (high-level IR) for debugging")
    parser.add_argument("--emit-flir", action="store_true", help="Dump FLIR (lowered IR) for debugging")
    parser.add_argument("--check", action="store_true", help="Run checks only, do not emit code")
    parser.add_argument("--emit-deps", action="store_true", help="Emit dependency information (.d file)")
    parser.add_argument("--no-link", action="store_true", help="Compile only, do not link")
    parser.add_argument("--link-arg", action="append", default=[], help="Additional argument to pass to the linker")

    # Make the file argument optional and add a directory argument
    parser.add_argument("file", nargs="?", help="Input file")
    parser.add_argument("--dir", help="Compile all .fire files in directory")
    parser.add_argument("-v", "--version", action="store_true", help="Show version information and exit")


    args = parser.parse_args()

    if args.version:
        print(f"firescript {FIRESCRIPT_VERSION} - {FIRESCRIPT_RELEASE_NAME}")
        print(f"Released {FIRESCRIPT_RELEASE_DATE}")
        sys.exit(0)

    # Configure logging
    setup_logging(args.debug, args.message_format)

    if args.debug:
        logging.debug(args)

    try:
        resolved_target = targets.resolve_target(args.platform, args.arch)
    except targets.UnknownHostError as e:
        logging.error(
            f"{e}. Pass --platform and --arch explicitly to select a compilation target."
        )
        sys.exit(1)

    # Check that at least one of file or dir is specified
    if not args.file and not args.dir:
        logging.error("No input file or directory specified")
        sys.exit(1)

    # Check for conflicting arguments
    if args.file and args.dir:
        logging.warning("Both file and directory specified, will compile both")

    # Check if output file is specified with directory compilation
    if args.dir and args.output:
        logging.error("Cannot specify output file when compiling a directory")
        sys.exit(1)

    # Compile individual file if specified
    if args.file:
        try:
            args.file = _normalize_cli_path(args.file)
            if args.output:
                args.output = _normalize_cli_path(args.output)
        except ValueError as e:
            logging.error(f"Invalid path argument: {e}")
            sys.exit(1)

        output_path = compile_file(
            args.file,
            resolved_target,
            out_path=args.output,
            emit=args.emit,
            check=args.check,
            emit_deps=args.emit_deps,
            no_link=args.no_link,
            link_args=args.link_arg,
            emit_fir=args.emit_fir,
            emit_flir=args.emit_flir,
        )

        if not output_path:
            sys.exit(1)

        # Handle output file renaming for single file case
        # (if compile_file didn't already write it directly to output_path)
        if output_path and args.output and output_path != args.output:
            try:
                shutil.move(output_path, args.output)  # deepcode ignore PathTraversal: user-selected local output path.
                logging.info(f"Output moved to {args.output}")
            except Exception as e:
                logging.error(f"Failed to move output to {args.output}: {e}")
                sys.exit(1)

    # Compile directory if specified
    if args.dir:
        try:
            args.dir = _normalize_cli_path(args.dir)
        except ValueError as e:
            logging.error(f"Invalid directory argument: {e}")
            sys.exit(1)

        if not os.path.isdir(args.dir):
            logging.error(f"Directory not found: {args.dir}")
            sys.exit(1)

        logging.info(f"Compiling all .fire files in {args.dir}")
        fire_files = glob.glob(os.path.join(args.dir, "*.fire"))

        if not fire_files:
            logging.warning(f"No .fire files found in {args.dir}")

        successful = 0
        failed = 0

        for file_path in fire_files:
            if compile_file(  # deepcode ignore PathTraversal: directory mode compiles user-selected local files.
                file_path,
                resolved_target,
                emit=args.emit,
                check=args.check,
                emit_deps=args.emit_deps,
                no_link=args.no_link,
                link_args=args.link_arg,
                emit_fir=args.emit_fir,
                emit_flir=args.emit_flir,
            ):
                successful += 1
            else:
                failed += 1

        logging.info(
            f"Directory compilation complete: {successful} successful, {failed} failed"
        )


if __name__ == "__main__":
    main()
