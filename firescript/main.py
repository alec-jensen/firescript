import argparse
import logging
import os
import sys
import subprocess

from lexer import Lexer
from parser import Parser
from log_formatter import LogFormatter

parser = argparse.ArgumentParser(description='Firescript compiler')

parser.add_argument('-d', '--debug', action='store_true', help='Debug mode')
parser.add_argument('-o', '--output', help='Output file')
parser.add_argument('-t', '--target', choices=['c', 'web'], help='Target language for compilation. Default is C', default='c')
parser.add_argument('file', help='Input file')

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
# deepcode ignore PT/test: path traversal can be useful
with open(args.file, 'r') as f:
    file = f.read()

lexer = Lexer(file)
tokens = lexer.tokenize()

# some python bs
newline = "\n"
logging.debug(f"tokens:\n{newline.join([str(token) for token in tokens])}")

parser = Parser(tokens, file, os.path.basename(args.file))
ast = parser.parse()
logging.debug(f"ast:\n{ast}")

compiled_location = None

if args.target == 'c':
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

    compile_command = f"gcc {temp_file} -o {temp_file[:-2]}"

    process = subprocess.Popen(compile_command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    output, error = process.communicate()

    if error:
        logging.error(f"Compilation failed:\n{error}")
        sys.exit()

    logging.debug(f"Compilation output:\n{output.decode()}")

    logging.info("Compilation successful!")
    if args.output:
        os.rename(temp_file[:-2], args.output)
        compiled_location = args.output
        logging.info(f"Binary written to {args.output}")
    else:
        compiled_location = "".join(os.path.basename(args.file).split('.')[:-1])
        os.rename(temp_file[:-2], compiled_location)
        logging.info(f"Binary written to {compiled_location}")
else:
    logging.error(f"Unsupported target language: {args.target}")
    sys.exit()
