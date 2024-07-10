import logging
import re

class Token:
    type: str
    value: str
    index: int

    def __init__(self, type: str = None, value: str = None, index: int = None):
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
    }

    types: dict[str, str] = {
        "INT": r"int",
        "FLOAT": r"float",
        "DOUBLE": r"double",
        "BOOL": r"bool",
        "STRING": r"string",
        "TUPLE": r"tuple",
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
        "ADD": r"\+",
        "ADD_ASSIGN": r"\+=",
        "INCREMENT": r"\+\+",
        "SUBTRACT": r"\-",
        "SUBTRACT_ASSIGN": r"\-=",
        "DECREMENT": r"\-\-",
        "MULTIPLY": r"\*",
        "MULTIPLY_ASSIGN": r"\*=",
        "DIVIDE": r"\/",
        "DIVIDE_ASSIGN": r"\/=",
        "MODULO": r"\%",
        "MODULO_ASSIGN": r"\%=",
        "POWER": r"\*\*",
        "POWER_ASSIGN": r"\*\*=",
        "EQUALS": r"\=\=",
        "ASSIGN": r"\=",
        "NOT_EQUALS": r"\!\=",
        "GREATER_THAN": r"\>",
        "GREATER_THAN_OR_EQUAL": r"\>\=",
        "LESS_THAN": r"\<",
        "LESS_THAN_OR_EQUAL": r"\<\=",
        "AND": r"\&\&",
        "OR": r"\|\|",
        "NOT": r"\!",
    }

    literals: dict[str, str] = {
        "BOOLEAN": r"true|false",
        "NULL": r"null",
        "INTEGER": r"(-?)[0-9]+",
        "DOUBLE": r"(-?)[0-9]+.[0-9]+",
        "FORMATTED_STRING": r"f\".*\"",
        "STRING": r"\".*\"",
        # "TUPLE": r"\((.*?,.*?)\)",
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
            token = Token()
            token.index = index

            for token_type, regex in self.all_token_types.items():
                match = re.match(regex, self.file[index:])
                if match:
                    token.type = token_type
                    token.value = match.group()
                    index += len(token.value)
                    break

            if token.type:
                tokens.append(token)
            else:
                match = re.match(self.identifier, self.file[index:])
                if match:
                    token.type = "IDENTIFIER"
                    token.value = match.group()
                    index += len(token.value)
                    tokens.append(token)
                elif self.file[index] == " " or self.file[index] == "\n":
                    index += 1
                else:
                    logging.error(f"Invalid token: {self.file[index]}")
                    index += 1

        return tokens
