import argparse
import logging
import os
import sys
import subprocess
import shutil
import glob

from lexer import Lexer
from parser import Parser
from log_formatter import LogFormatter

parser = argparse.ArgumentParser(description='firescript compiler')

parser.add_argument('-d', '--debug', action='store_true', help='Debug mode')
parser.add_argument('-o', '--output', help='Output file')
parser.add_argument('-t', '--target', choices=['native', 'web'], help='Target language for compilation. Default is native', default='native')
parser.add_argument('--cc', help='C compiler to use (default: auto-detect)', default=None)
# Make the file argument optional and add a directory argument
parser.add_argument('file', nargs='?', help='Input file')
parser.add_argument('--dir', help='Compile all .fire files in directory')

args = parser.parse_args()

rootLogger = logging.getLogger()
rootLogger.setLevel(logging.INFO)

if args.debug:
    rootLogger.setLevel(logging.DEBUG)

consoleHandler = logging.StreamHandler()
logFormatter = LogFormatter()
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)

if args.debug:
    logging.debug(args)

# Check that at least one of file or dir is specified
if not args.file and not args.dir:
    logging.error("No input file or directory specified")
    sys.exit()

# Check for conflicting arguments
if args.file and args.dir:
    logging.warning("Both file and directory specified, will compile both")

# Check if output file is specified with directory compilation
if args.dir and args.output:
    logging.error("Cannot specify output file when compiling a directory")
    sys.exit()

def compile_file(file_path, target, cc=None):
    """Compile a single firescript file"""
    logging.info(f"Starting compilation of {file_path}...")
    # deepcode ignore PT/test: path traversal can be useful here
    with open(file_path, 'r') as f:
        file_content = f.read()

    lexer = Lexer(file_content)
    tokens = lexer.tokenize()

    logging.debug(f"tokens:\n{'\n'.join([str(token) for token in tokens])}")

    parser_instance = Parser(tokens, file_content, os.path.relpath(file_path))
    ast = parser_instance.parse()
    logging.debug(f"ast:\n{ast}")

    if parser_instance.errors != []:
        logging.error(f"Parsing failed with {len(parser_instance.errors)} errors")
        return False

    logging.debug("Starting code generation...")

    if target == 'native':
        from c_code_generator import CCodeGenerator

        generator = CCodeGenerator(ast)
        output = generator.generate()

        # create temp folder if it doesn't exist
        if not os.path.exists('build/temp'):
            os.makedirs('build/temp')
        
        temp_file = os.path.join('build/temp', "".join(os.path.basename(file_path).split('.')[:-1]) + '.c')
        with open(temp_file, 'w') as f:
            f.write(output)
        
        logging.debug(f"Transpiled code written to {temp_file}")
        logging.debug("Starting compilation of transpiled code...")

        # Determine C compiler to use (using --cc arg, CC env, or auto-detect)
        compiler = cc or os.environ.get('CC')
        if not compiler:
            for comp in ['gcc', 'clang', 'cc']:
                if shutil.which(comp):
                    compiler = comp
                    break
        if not compiler:
            logging.error("No C compiler found. Install gcc/clang or specify with --cc")
            return False
        logging.debug(f"Using C compiler: {compiler}")

        # Update the compile command to include varray.c and use detected compiler
        compile_command = f"{compiler} -O -I . {temp_file} firescript/runtime/runtime.c firescript/runtime/varray.c -lgmp -o {temp_file[:-2]}"

        process = subprocess.Popen(compile_command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        output, error = process.communicate()

        if error:
            logging.error(f"Compilation failed with error:\n{error.decode()}")
            return False

        logging.debug(f"Compilation output:\n{output.decode()}")

        logging.info("Compilation successful!")
        
        # Handle output file location
        compiled_location = os.path.splitext(os.path.basename(file_path))[0]
        if not os.path.exists('build'):
            os.mkdir('build')
        output_path = os.path.join('build', compiled_location)
        os.rename(temp_file[:-2], output_path)
        logging.info(f"Binary written to {output_path}")
        return output_path
    else:
        logging.error(f"Unsupported target: {target}")
        return False

# Compile individual file if specified
if args.file:
    output_path = compile_file(args.file, args.target, args.cc)
    
    # Handle output file renaming for single file case
    if output_path and args.output:
        os.rename(output_path, args.output)
        logging.info(f"Binary moved to {args.output}")

# Compile directory if specified
if args.dir:
    if not os.path.isdir(args.dir):
        logging.error(f"Directory not found: {args.dir}")
        sys.exit()
    
    logging.info(f"Compiling all .fire files in {args.dir}")
    fire_files = glob.glob(os.path.join(args.dir, "*.fire"))
    
    if not fire_files:
        logging.warning(f"No .fire files found in {args.dir}")
    
    successful = 0
    failed = 0
    
    for file_path in fire_files:
        if compile_file(file_path, args.target, args.cc):
            successful += 1
        else:
            failed += 1
    
    logging.info(f"Directory compilation complete: {successful} successful, {failed} failed")
