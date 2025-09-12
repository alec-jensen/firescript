import logging
import re

class Token:
    type: str
    value: str
    index: int

    def __init__(self, type: str, value: str, index: int) -> None:
        self.type = type
        self.value = value
        self.index = index

    def __str__(self):
        return f"Token('{self.type}', '{self.value}', {self.index})"

class Lexer:
    identifier: str = r"[a-zA-Z_][a-zA-Z0-9_]*"

    keywords: dict[str, str] = {
        "IF": r"if",
        "ELSE": r"else",
        "ELIF": r"elif",
        "WHILE": r"while",
        "FOR": r"for",
        "BREAK": r"break",
        "CONTINUE": r"continue",
        "RETURN": r"return",
        "NULLABLE": r"nullable",
        "GENERATOR": r"generator",
        "CONST": r"const",
        "TERNARY": r"ternary",
    }

    types: dict[str, str] = {
        "INT": r"int",
        "FLOAT": r"float",
        "DOUBLE": r"double",
        "BOOL": r"bool",
        "STRING": r"string",
        "TUPLE": r"tuple",
        "VOID": r"void",
    }

    keywords = keywords | types

    seperators: dict[str, str] = {
        "OPEN_PAREN": r"\(",
        "CLOSE_PAREN": r"\)",
        "OPEN_BRACE": r"\{",
        "CLOSE_BRACE": r"\}",
        "OPEN_BRACKET": r"\[",
        "CLOSE_BRACKET": r"\]",
        "COMMA": r",",
        "SEMICOLON": r";",
        "COLON": r":",
        "DOT": r"\.",
    }

    operators: dict[str, str] = {
        "ADD_ASSIGN": r"\+=",
        "INCREMENT": r"\+\+",
        "ADD": r"\+",
        "SUBTRACT_ASSIGN": r"\-=",
        "DECREMENT": r"\-\-",
        "SUBTRACT": r"\-",
        "MULTIPLY_ASSIGN": r"\*=",
        "MULTIPLY": r"\*",
        "DIVIDE_ASSIGN": r"\/=",
        "DIVIDE": r"\/",
        "MODULO_ASSIGN": r"\%=",
        "MODULO": r"\%",
        "POWER_ASSIGN": r"\*\*=",
        "POWER": r"\*\*",
        "EQUALS": r"\=\=",
        "NOT_EQUALS": r"\!\=",
        "GREATER_THAN_OR_EQUAL": r"\>\=",
        "LESS_THAN_OR_EQUAL": r"\<\=",
        "GREATER_THAN": r"\>",
        "LESS_THAN": r"\<",
        "ASSIGN": r"\=",
        "AND": r"\&\&",
        "OR": r"\|\|",
        "NOT": r"\!",
    }

    literals: dict[str, str] = {
        "BOOLEAN_LITERAL": r"true|false",
        "NULL_LITERAL": r"null",
        "VOID_LITERAL": r"void",
        "FLOAT_LITERAL": r"(-?)[0-9]+\.[0-9]+f",
        "DOUBLE_LITERAL": r"(-?)[0-9]+\.[0-9]+",
        "INTEGER_LITERAL": r"(-?)[0-9]+",
        "STRING_LITERAL": r"(?:[rfb](?!.*[rfb])){0,3}\"(?:\\.|[^\\\"])*\"",
    }

    comments: dict[str, str] = {
        "SINGLE_LINE_COMMENT": r"\/\/.*",
        "MULTI_LINE_COMMENT_START": r"\/\*",
        "MULTI_LINE_COMMENT_END": r"\*\/",
    }

    def __init__(self, file: str) -> None:
        self.file: str = file
        self.all_token_types = self.comments | self.keywords | self.seperators | self.operators | self.literals

    def tokenize(self):
        logging.debug(f"tokenizing file")

        tokens: list[Token] = []
        index = 0

        while index < len(self.file):
            token = Token("", "", index + 1)
            # First, attempt matching any of the specific tokens.
            for token_type, regex in self.all_token_types.items():
                match = re.match(regex, self.file[index:])
                if match:
                    token.type = token_type
                    token.value = match.group()
                    index += len(token.value)
                    break

            # If no specific token matched, fallback to identifier matching or single-character token.
            if not token.type:
                match = re.match(self.identifier, self.file[index:])
                if match:
                    token.type = "IDENTIFIER"
                    token.value = match.group()
                    index += len(token.value)
                else:
                    ch = self.file[index]
                    # Skip whitespace silently (space, tab, newline, carriage return)
                    if ch in (' ', '\t', '\n', '\r'):
                        index += 1
                        continue
                    # Emit UNKNOWN token for any other unexpected single character
                    token.type = "UNKNOWN"
                    token.value = ch
                    index += 1

            tokens.append(token)

        return tokens