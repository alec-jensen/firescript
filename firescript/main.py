import argparse
import logging
import os
import sys
import subprocess
import shutil
import glob
import time

from lexer import Lexer
from parser import Parser
from log_formatter import LogFormatter
from preprocessor import enable_and_insert_drops
from semantic_analyzer import SemanticAnalyzer
from enums import NodeTypes
from imports import ModuleResolver, build_merged_ast
from enums import NodeTypes

FIRESCRIPT_VERSION = "0.4.0"
FIRESCRIPT_RELEASE_DATE = "February 2, 2026"
FIRESCRIPT_RELEASE_NAME = "Phoenix"


def setup_logging(debug_mode=False):
    """Configure logging with custom formatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    console_handler = logging.StreamHandler()
    log_formatter = LogFormatter()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)


def detect_c_compiler():
    """Auto-detect available C compiler."""
    compiler = os.environ.get("CC")
    if not compiler:
        for comp in ["gcc", "clang", "cc"]:
            if shutil.which(comp):
                compiler = comp
                break
    return compiler


def compile_file(file_path, target, cc=None, output=None):
    """Compile a single firescript file"""
    logging.info(f"Starting compilation of {file_path}...")

    start_time = time.perf_counter_ns()

    try:
        # Read source file
        with open(file_path, "r") as f:
            file_content = f.read()
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        return False
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        return False

    # Lexical analysis
    lexer = Lexer(file_content)
    tokens = lexer.tokenize()
    logging.debug(f"tokens:\n{'\n'.join([str(token) for token in tokens])}")

    # Parsing
    # If imports are present, defer some undefined-name checks until after import merge.
    has_import_tokens = any(getattr(t, "type", None) == "IMPORT" for t in tokens)
    parser_instance = Parser(
        tokens,
        file_content,
        os.path.relpath(file_path),
        defer_undefined_identifiers=has_import_tokens,
    )
    ast = parser_instance.parse()
    logging.debug(f"ast:\n{ast}")

    # Resolve imports if present
    has_imports = any(c.node_type == NodeTypes.IMPORT_STATEMENT for c in ast.children)
    if has_imports:
        # Resolve module graph and merge ASTs
        try:
            # Import root defaults to directory containing the entry file
            import_root = os.path.dirname(os.path.abspath(file_path))
            resolver = ModuleResolver(import_root)
            # Prime resolver with already-parsed entry AST to avoid re-parsing errors on undefined imported symbols
            entry_abs = os.path.abspath(file_path)
            dotted = resolver.path_to_dotted(entry_abs)
            from imports import Module  # local import to avoid circular typing
            entry_mod_obj = Module(dotted, entry_abs, ast)
            resolver.modules[dotted] = entry_mod_obj
            # Load dependencies of entry
            for imp in entry_mod_obj.imports:
                if imp.kind != "external":
                    resolver._load_module(imp.module_path, [dotted])
            # Now build full order including entry
            entry_mod, topo = resolver.resolve_for_entry(file_path)
            logging.debug("Import resolution completed successfully.")
            # Build merged AST for single-file codegen
            ast = build_merged_ast(entry_mod, topo)
            logging.debug("Import merge completed successfully.")
        except Exception as e:
            logging.error(f"Import resolution failed: {e}")
            return False

        # If we deferred undefined-identifier checks while parsing (because imports existed),
        # validate them now against the merged symbol table.
        deferred = getattr(parser_instance, "deferred_undefined_identifiers", [])
        if deferred:
            merged_symbols = getattr(ast, "_merged_symbols", {}) or {}
            for name, tok in deferred:
                if name in merged_symbols:
                    continue
                # Also allow class names imported via merge.
                if any(
                    c.node_type == NodeTypes.CLASS_DEFINITION and getattr(c, "name", None) == name
                    for c in (ast.children or [])
                ):
                    continue
                parser_instance.error(f"Variable '{name}' not defined", tok)

        if parser_instance.errors:
            logging.error(f"Parsing failed with {len(parser_instance.errors)} errors")
            return False

    # If there were parser errors and no imports, fail now.
    # If imports were present, some 'undefined symbol' errors may be resolved by the merge above.
    if parser_instance.errors and not has_imports:
        logging.error(f"Parsing failed with {len(parser_instance.errors)} errors")
        return False

    # Preprocess: enable and insert drop() calls if needed (ownership cleanup)
    try:
        ast = enable_and_insert_drops(ast)
        logging.debug("Preprocessing (drop insertion) completed.")
    except Exception as e:
        logging.error(f"Preprocessing failed: {e}")
        return False

    # Semantic analysis: ownership and borrow checking
    try:
        analyzer = SemanticAnalyzer(ast, source_file=file_path)
        if not analyzer.analyze():
            analyzer.report_errors()
            logging.error(f"Semantic analysis failed with {len(analyzer.errors)} errors")
            return False
        logging.debug("Semantic analysis completed.")
    except Exception as e:
        logging.error(f"Semantic analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    logging.debug("Starting code generation...")

    if target == "native":
        from c_code_generator import CCodeGenerator

        # Generate C code
        generator = CCodeGenerator(ast, source_file=file_path)
        generator.source_code = file_content
        output = generator.generate()
        # Safety: wrap any raw free() calls emitted by codegen into firescript_free()
        # This prevents double-free and freeing static literals.
        output = output.replace(" free(", " firescript_free(")
        output = output.replace("\tfree(", "\tfirescript_free(")
        output = output.replace("\nfree(", "\nfirescript_free(")

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

        logging.debug(f"Transpiled code written to {temp_c_file}")
        logging.debug("Starting compilation of transpiled code...")

        # Determine C compiler to use
        compiler = cc or detect_c_compiler()
        if not compiler:
            logging.error("No C compiler found. Install gcc/clang or specify with --cc")
            return False

        logging.debug(f"Using C compiler: {compiler}")

        # Build the transpiled C with runtime
        compile_command = [
            compiler,
            "-O3",
            "-march=native",
            "-mtune=native",
            "-flto",
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
            "firescript/runtime/runtime.c",
            "-Wl,-O2",
            "-Wl,--as-needed",
            "-Wl,--gc-sections",
            "-lgmp",
            "-lmpfr",
            "-o",
            temp_c_file[:-2],
        ]

        try:
            process = subprocess.run(
                compile_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            if process.returncode != 0:
                logging.error(f"C Compilation failed with error:\n{process.stderr}")
                logging.error("This is not an error in your firescript code, but an issue in the compiler.")
                return False

            if process.stdout:
                logging.debug(f"Compilation output:\n{process.stdout}")

        except Exception as e:
            logging.error(f"Failed to execute compiler: {e}")
            return False

        end_time = time.perf_counter_ns()

        logging.info(f"Compilation of {file_path} completed successfully in {(end_time - start_time) / 1_000_000:.2f} ms")

        # Handle output file location
        compiled_binary = os.path.splitext(temp_c_file)[0]
        os.makedirs("build", exist_ok=True)

        # Default output location
        output_path = os.path.join("build", base_name)

        # Windows toolchains typically emit .exe even if -o omits extension
        if os.name == "nt":
            if os.path.exists(compiled_binary + ".exe"):
                compiled_binary = compiled_binary + ".exe"
                output_path = output_path + ".exe"

        try:
            shutil.move(compiled_binary, output_path)
            logging.info(f"Binary written to {output_path}")
            return output_path
        except Exception as e:
            logging.error(f"Failed to move compiled binary: {e}")
            return False
    else:
        logging.error(f"Unsupported target: {target}")
        return False


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
    setup_logging(args.debug)

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
        output_path = compile_file(
            args.file,
            args.target,
            args.cc,
        )

        if not output_path:
            sys.exit(1)

        # Handle output file renaming for single file case
        if output_path and args.output:
            try:
                shutil.move(output_path, args.output)
                logging.info(f"Binary moved to {args.output}")
            except Exception as e:
                logging.error(f"Failed to move binary to {args.output}: {e}")
                sys.exit(1)

    # Compile directory if specified
    if args.dir:
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
            if compile_file(
                file_path,
                args.target,
                args.cc,
            ):
                successful += 1
            else:
                failed += 1

        logging.info(
            f"Directory compilation complete: {successful} successful, {failed} failed"
        )


if __name__ == "__main__":
    main()
