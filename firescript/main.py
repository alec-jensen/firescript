import argparse
import logging
import os
import sys
import subprocess
import shutil
import glob
import time

from log_formatter import LogFormatter
from compiler_pipeline import CompilerPipeline
from errors import CompileTimeError

FIRESCRIPT_VERSION = "0.4.0"
FIRESCRIPT_RELEASE_DATE = "February 2, 2026"
FIRESCRIPT_RELEASE_NAME = "Phoenix"


def _normalize_cli_path(path_value: str) -> str:
    """Normalize a user-provided local path for trusted CLI file operations."""
    if not isinstance(path_value, str) or not path_value:
        raise ValueError("Path must be a non-empty string")
    if "\x00" in path_value:
        raise ValueError("Path contains invalid NUL byte")
    return os.path.abspath(os.path.expanduser(path_value))


def _resolve_compiler_executable(compiler: str | None) -> str | None:
    """Resolve compiler to an executable path to avoid command-token injection."""
    if not compiler:
        return None

    candidate = compiler.strip()
    if not candidate or any(ch in candidate for ch in ("\x00", "\n", "\r")):
        return None

    if os.path.isabs(candidate):
        return candidate if os.path.isfile(candidate) and os.access(candidate, os.X_OK) else None

    if os.sep in candidate or (os.altsep and os.altsep in candidate):
        rel_candidate = os.path.abspath(candidate)
        return rel_candidate if os.path.isfile(rel_candidate) and os.access(rel_candidate, os.X_OK) else None

    return shutil.which(candidate)


def _homebrew_prefix(formula_name):
    """Return the Homebrew prefix for a formula, or None if unavailable."""
    brew = shutil.which("brew")
    if not brew:
        return None

    try:
        process = subprocess.run(
            [brew, "--prefix", formula_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except Exception:
        return None

    if process.returncode != 0:
        return None

    prefix = process.stdout.strip()
    return prefix or None


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


def detect_c_compiler():
    """Auto-detect available C compiler."""
    compiler = _resolve_compiler_executable(os.environ.get("CC"))
    if not compiler:
        for comp in ["gcc", "clang", "cc"]:
            resolved = _resolve_compiler_executable(comp)
            if resolved:
                compiler = resolved
                break
    return compiler


def compile_file(file_path, target, cc=None, out_path=None, emit="bin", check=False, emit_deps=False, no_link=False, link_args=None):
    """Compile a single firescript file"""
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
        os.path.relpath(file_path),
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

    logging.debug("Starting code generation...")

    if target == "native":
        from codegen import CCodeGenerator

        # Generate C code
        generator = CCodeGenerator(ast, source_file=file_path)
        generator.source_code = file_content
        output = generator.generate()
        if generator.errors:
            logging.error(f"Code generation failed with {len(generator.errors)} errors")
            return False
        # Safety: wrap any raw free() calls emitted by codegen into firescript_free()
        # This prevents double-free and freeing static literals.
        output = output.replace(" free(", " firescript_free(")
        output = output.replace("\tfree(", "\tfirescript_free(")
        output = output.replace("\nfree(", "\nfirescript_free(")
        stage_start = _log_stage_duration("Code generation", stage_start)

        # Create temp folder if it doesn't exist
        os.makedirs("build/temp", exist_ok=True)

        # Determine output file path
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        temp_c_file = os.path.join("build/temp", f"{base_name}.c")

        # Write generated C code to file
        try:
            with open(temp_c_file, "w") as f:
                f.write(output)
        except Exception as e:
            logging.error(f"Failed to write C code to {temp_c_file}: {e}")
            return False
        stage_start = _log_stage_duration("Write transpiled C", stage_start)

        logging.debug(f"Transpiled code written to {temp_c_file}")

        if emit == "c":
            out_c = out_path if out_path else temp_c_file
            if out_path:
                shutil.copy(temp_c_file, out_path)  # deepcode ignore PathTraversal: user-selected local output path.
            logging.info(f"C source written to {out_c}")
            return out_c

        logging.debug("Starting compilation of transpiled code...")

        # Determine C compiler to use
        compiler = _resolve_compiler_executable(cc) if cc else detect_c_compiler()
        if not compiler:
            logging.error("No C compiler found. Install gcc/clang or specify with --cc")
            return False

        logging.debug(f"Using C compiler: {compiler}")

        is_macos = sys.platform == "darwin"

        include_dirs = []
        library_dirs = []
        if is_macos:
            for formula_name in ("gmp", "mpfr"):
                prefix = _homebrew_prefix(formula_name)
                if not prefix:
                    continue

                include_dir = os.path.join(prefix, "include")
                library_dir = os.path.join(prefix, "lib")

                if os.path.isdir(include_dir) and include_dir not in include_dirs:
                    include_dirs.append(include_dir)
                if os.path.isdir(library_dir) and library_dir not in library_dirs:
                    library_dirs.append(library_dir)

        # Build the transpiled C with runtime
        # Note: -flto (Link Time Optimization) doesn't work with clang on Windows MinGW
        # because clang produces LLVM bitcode files that the MinGW linker can't handle
        use_lto = not (os.name == "nt" and "clang" in compiler)
        
        compile_command = [compiler, "-O3"]  # deepcode ignore CommandInjection: compiler executable is validated and shell is disabled.

        # macOS GCC/Clang both behave more reliably without native march/tune flags.
        if not is_macos:
            compile_command.extend([
                "-march=native",
                "-mtune=native",
            ])

        for include_dir in include_dirs:
            compile_command.append(f"-I{include_dir}")
        
        if use_lto:
            compile_command.append("-flto")
        
        compile_command.extend([
            "-fomit-frame-pointer",
            "-fno-plt",
            "-fstrict-aliasing",
            "-fno-stack-protector",
            "-foptimize-sibling-calls",
            "-ffunction-sections",
            "-fdata-sections",
            "-DNDEBUG",
            "-I",
            ".",
            temp_c_file,
        ])
        
        out_obj = ""
        if emit == "obj" or no_link:
            out_obj = out_path if out_path else temp_c_file[:-2] + ".o"
            compile_command.extend(["-c", "-o", out_obj])
        else:
            linker_flags = []
            for library_dir in library_dirs:
                linker_flags.append(f"-L{library_dir}")
            if not is_macos:
                linker_flags.extend([
                    "-Wl,-O2",
                    "-Wl,--as-needed",
                    "-Wl,--gc-sections",
                ])
            compile_command.extend([
                "firescript/runtime/runtime.c",
                "-lgmp",
                "-lmpfr",
            ])
            compile_command.extend(linker_flags)
            for la in link_args:
                compile_command.append(la)
            
            compile_command.extend([
                "-o",
                temp_c_file[:-2],
            ])

        try:
            process = subprocess.run(
                compile_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )  # deepcode ignore CommandInjection: argument list invocation with shell=False.

            if process.returncode != 0:
                logging.error(f"C Compilation failed with error:\n{process.stderr}")
                logging.error("This is not an error in your firescript code, but an issue in the compiler.")
                return False

            if process.stdout:
                logging.debug(f"Compilation output:\n{process.stdout}")

        except Exception as e:
            logging.error(f"Failed to execute compiler: {e}")
            return False
        stage_start = _log_stage_duration("C compilation", stage_start)

        end_time = time.perf_counter_ns()

        logging.info(f"Compilation of {file_path} completed successfully in {(end_time - start_time) / 1_000_000:.2f} ms")
        
        if emit == "obj" or no_link:
            logging.info(f"Object file written to {out_obj}")
            return out_obj

        # Handle output file location
        compiled_binary = os.path.splitext(temp_c_file)[0]
        os.makedirs("build", exist_ok=True)

        # Default output location
        final_out_path = out_path if out_path else os.path.join("build", base_name)

        # Windows toolchains typically emit .exe even if -o omits extension
        if os.name == "nt":
            if os.path.exists(compiled_binary + ".exe"):
                compiled_binary = compiled_binary + ".exe"
                if not out_path or not final_out_path.endswith(".exe"):
                    final_out_path = final_out_path + ".exe"

        try:
            shutil.move(compiled_binary, final_out_path)  # deepcode ignore PathTraversal: user-selected local output path.
            logging.info(f"Binary written to {final_out_path}")
            return final_out_path
        except Exception as e:
            logging.error(f"Failed to move compiled binary: {e}")
            return False
    else:
        logging.error(f"Unsupported target: {target}")
        return False


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
        "-t",
        "--target",
        choices=["native", "web"],
        help="Target language for compilation. Default is native",
        default="native",
    )
    parser.add_argument(
        "--cc", help="C compiler to use (default: auto-detect)", default=None
    )
    parser.add_argument("--message-format", choices=["text", "json"], default="text", help="Format for diagnostic messages")
    parser.add_argument("--emit", choices=["ast", "c", "obj", "bin"], default="bin", help="Type of output to generate")
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
            args.target,
            args.cc,
            out_path=args.output,
            emit=args.emit,
            check=args.check,
            emit_deps=args.emit_deps,
            no_link=args.no_link,
            link_args=args.link_arg,
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
                args.target,
                args.cc,
                emit=args.emit,
                check=args.check,
                emit_deps=args.emit_deps,
                no_link=args.no_link,
                link_args=args.link_arg,
            ):
                successful += 1
            else:
                failed += 1

        logging.info(
            f"Directory compilation complete: {successful} successful, {failed} failed"
        )


if __name__ == "__main__":
    main()
