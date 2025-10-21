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
        "INT8": r"int8",
        "INT16": r"int16",
        "INT32": r"int32",
        "INT64": r"int64",
        "UINT8": r"uint8",
        "UINT16": r"uint16",
        "UINT32": r"uint32",
        "UINT64": r"uint64",
        "FLOAT32": r"float32",
        "FLOAT64": r"float64",
        "FLOAT128": r"float128",
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

    # Literal patterns
    # Notes:
    # - Support underscores in numeric literals (e.g., 1_000, 0xFF_FF)
    # - Support bases for integers: 0b, 0o, 0x (with underscores)
    # - Support integer suffixes: i8|i16|i32|i64|u8|u16|u32|u64
    # - Support float forms with decimal and/or exponent, with suffixes: f|f32|f64|f128
    #   (legacy 'f' is treated as float32 downstream)
    # - Keep token categories aligned with parser expectations. The parser will further
    #   interpret suffixes to determine precise types.
    float_core = r"(?:[0-9](?:_?[0-9])*\.(?:[0-9](?:_?[0-9])*)?(?:[eE][+\-]?(?:[0-9](?:_?[0-9])*))?|[0-9](?:_?[0-9])*(?:[eE][+\-]?(?:[0-9](?:_?[0-9])*)))"
    int_core = r"(?:0[bB](?:_?[01])+|0[oO](?:_?[0-7])+|0[xX](?:_?[0-9a-fA-F])+|[0-9](?:_?[0-9])*)"

    literals: dict[str, str] = {
        "BOOLEAN_LITERAL": r"true|false",
        "NULL_LITERAL": r"null",
        "VOID_LITERAL": r"void",
    # Float literal with explicit suffix (f, f32, f64, f128) - longest first to avoid premature 'f' match
    "FLOAT_LITERAL": rf"-?{float_core}(?:f128|f64|f32|f)",
        # Float literal without suffix
        "DOUBLE_LITERAL": rf"-?{float_core}",
        # Integer literal (bases with underscores) with optional width/unsigned suffix
        "INTEGER_LITERAL": rf"-?{int_core}(?:i8|i16|i32|i64|u8|u16|u32|u64)?",
        "STRING_LITERAL": r"(?:[rfb](?!.*[rfb])){0,3}\"(?:\\.|[^\\\"])*\"",
    }

    comments: dict[str, str] = {
        "SINGLE_LINE_COMMENT": r"\/\/.*",
        "MULTI_LINE_COMMENT_START": r"\/\*",
        "MULTI_LINE_COMMENT_END": r"\*\/",
    }

    def __init__(self, file: str) -> None:
        self.file: str = file
        self.all_token_types = (
            self.comments
            | self.keywords
            | self.seperators
            | self.operators
            | self.literals
        )

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
                    if ch in (" ", "\t", "\n", "\r"):
                        index += 1
                        continue
                    # Emit UNKNOWN token for any other unexpected single character
                    token.type = "UNKNOWN"
                    token.value = ch
                    index += 1

            tokens.append(token)

        return tokens
