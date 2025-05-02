import argparse
import logging
import os
import sys
import subprocess
import shutil

from lexer import Lexer
from parser import Parser
from log_formatter import LogFormatter

parser = argparse.ArgumentParser(description='firescript compiler')

parser.add_argument('-d', '--debug', action='store_true', help='Debug mode')
parser.add_argument('-o', '--output', help='Output file')
parser.add_argument('-t', '--target', choices=['native', 'web'], help='Target language for compilation. Default is native', default='native')
parser.add_argument('file', help='Input file')
parser.add_argument('--cc', help='C compiler to use (default: auto-detect)', default=None)

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

if not args.file:
    logging.error("No input file specified")
    sys.exit()

logging.info(f"Starting compilation of {args.file}...")
# deepcode ignore PT/test: path traversal can be useful here
with open(args.file, 'r') as f:
    file = f.read()

lexer = Lexer(file)
tokens = lexer.tokenize()

logging.debug(f"tokens:\n{'\n'.join([str(token) for token in tokens])}")

parser = Parser(tokens, file, os.path.relpath(args.file))
ast = parser.parse()
logging.debug(f"ast:\n{ast}")

if parser.errors != []:
    logging.error(f"Compilation failed with {len(parser.errors)} errors:")
    sys.exit()

compiled_location = None

if args.target == 'native':
    from c_code_generator import CCodeGenerator

    generator = CCodeGenerator(ast)
    output = generator.generate()

    # create temp folder if it doesn't exist
    if not os.path.exists('temp'):
        os.makedirs('temp')
    
    temp_file = os.path.join('temp', "".join(os.path.basename(args.file).split('.')[:-1]) + '.c')
    with open(temp_file, 'w') as f:
        f.write(output)
    
    logging.info(f"Transpiled code written to {temp_file}")
    logging.info("Starting compilation of transpiled code...")

    # Determine C compiler to use (using --cc arg, CC env, or auto-detect)
    cc = args.cc or os.environ.get('CC')
    if not cc:
        for comp in ['gcc', 'clang', 'cc']:
            if shutil.which(comp):
                cc = comp
                break
    if not cc:
        logging.error("No C compiler found. Install gcc/clang or specify with --cc")
        sys.exit()
    logging.info(f"Using C compiler: {cc}")

    # Update the compile command to include varray.c and use detected compiler
    compile_command = f"{cc} -O -I . {temp_file} firescript/runtime/runtime.c firescript/runtime/varray.c -o {temp_file[:-2]}"

    process = subprocess.Popen(compile_command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    output, error = process.communicate()

    if error:
        logging.error(f"GCC failed with error:\n{error.decode()}")
        sys.exit()

    logging.debug(f"Compilation output:\n{output.decode()}")

    logging.info("Compilation successful!")
    if args.output:
        os.rename(temp_file[:-2], args.output)
        compiled_location = args.output
        logging.info(f"Binary written to {args.output}")
    else:
        compiled_location = os.path.splitext(os.path.basename(args.file))[0]
        if not os.path.exists('output'):
            os.mkdir('output')
        output_path = os.path.join('output', compiled_location)
        os.rename(temp_file[:-2], output_path)
        logging.info(f"Binary written to {output_path}")
else:
    logging.error(f"Unsupported target: {args.target}")
    sys.exit()
