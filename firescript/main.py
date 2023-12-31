import argparse
import logging
import os

from lexer import Lexer
from parser import Parser
from log_formatter import LogFormatter

parser = argparse.ArgumentParser(description='Firescript compiler')

parser.add_argument('-d', '--debug', action='store_true', help='Debug mode')
parser.add_argument('-o', '--output', help='Output file')
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

if args.file:
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