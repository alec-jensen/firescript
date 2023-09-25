import argparse
import logging

from lexer import Lexer
from log_formatter import LogFormatter

logFormatter = LogFormatter()
rootLogger = logging.getLogger()
rootLogger.setLevel(logging.DEBUG)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)

parser = argparse.ArgumentParser(description='Firescript compiler')

parser.add_argument('-d', '--debug', action='store_true', help='Debug mode')
parser.add_argument('-o', '--output', help='Output file')
parser.add_argument('file', help='Input file')

args = parser.parse_args()

if args.debug:
    print(args)

if args.file:
    logging.info(f"Starting compilation of {args.file}...")
    # deepcode ignore PT/test: path traversal can be useful
    with open(args.file, 'r') as f:
        file = f.read()

    lexer = Lexer()
    tokens = lexer.tokenize(file)

    logging.debug(f"tokens: {', '.join([str(token) for token in tokens])}")
