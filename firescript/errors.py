from __future__ import annotations

from enum import Enum
from typing import Optional


class ErrorCategory(str, Enum):
    PARSER = "parser"
    SEMANTIC = "semantic"
    CODEGEN = "codegen"
    IMPORT = "import"


class CompileTimeError:
    code: str = "FS-COMP-0000"
    category: ErrorCategory = ErrorCategory.PARSER
    message_template: str = "{message}"

    def __init__(
        self,
        *,
        source_file: Optional[str] = None,
        line: int = 0,
        column: int = 0,
        snippet: Optional[str] = None,
        **context: object,
    ):
        self.source_file = source_file
        self.line = line
        self.column = column
        self.snippet = snippet
        self.message = self._render(context)

    def _render(self, context: dict[str, object]) -> str:
        try:
            return self.message_template.format(**context)
        except Exception:
            # Fallback to avoid formatter crashes hiding the actual compiler error.
            return self.message_template

    def to_log_string(self) -> str:
        header = self.message
        if (
            self.source_file
            and self.line > 0
            and self.column >= 0
            and self.snippet is not None
        ):
            return (
                header
                + f"\n> {self.snippet.rstrip()}\n"
                + " " * (self.column + 1)
                + "^"
                + f"\n({self.source_file}:{self.line}:{self.column})"
            )
        return header


class ParserError(CompileTimeError):
    code = "FS-PARSE-0001"
    category = ErrorCategory.PARSER
    message_template = "{message}"


class UnexpectedTokenError(CompileTimeError):
    code = "FS-PARSE-0002"
    category = ErrorCategory.PARSER
    message_template = "Expected {expected} but got {actual}"


class UndefinedIdentifierError(CompileTimeError):
    code = "FS-PARSE-0003"
    category = ErrorCategory.PARSER
    message_template = "Variable '{identifier}' not defined"


class SemanticError(CompileTimeError):
    code = "FS-SEM-0001"
    category = ErrorCategory.SEMANTIC
    message_template = "{message}"


class TypeError(CompileTimeError):
    code = "FS-SEM-0002"
    category = ErrorCategory.SEMANTIC
    message_template = "{detail}"


class CodegenError(CompileTimeError):
    code = "FS-CGEN-0001"
    category = ErrorCategory.CODEGEN
    message_template = "{message}"


class ImportNotFoundError(CompileTimeError):
    code = "FS-IMP-0001"
    category = ErrorCategory.IMPORT
    message_template = "Module not found: {module}"


class CyclicImportError(CompileTimeError):
    code = "FS-IMP-0002"
    category = ErrorCategory.IMPORT
    message_template = "Cyclic import detected: {cycle}"


# Additional Parser Errors for specific syntax issues
class ExpectedTokenError(CompileTimeError):
    code = "FS-PARSE-0010"
    category = ErrorCategory.PARSER
    message_template = "Expected {expected}"


class MissingIdentifierError(CompileTimeError):
    code = "FS-PARSE-0011"
    category = ErrorCategory.PARSER
    message_template = "Expected identifier"


class InvalidExpressionError(CompileTimeError):
    code = "FS-PARSE-0012"
    category = ErrorCategory.PARSER
    message_template = "{detail}"


class InvalidArrayAccessError(CompileTimeError):
    code = "FS-PARSE-0013"
    category = ErrorCategory.PARSER
    message_template = "{detail}"


class InvalidFieldAccessError(CompileTimeError):
    code = "FS-PARSE-0014"
    category = ErrorCategory.PARSER
    message_template = "{detail}"


# Type System Errors
class InvalidTypeError(CompileTimeError):
    code = "FS-SEM-0010"
    category = ErrorCategory.SEMANTIC
    message_template = "{detail}"


class FieldNotFoundError(CompileTimeError):
    code = "FS-SEM-0011"
    category = ErrorCategory.SEMANTIC
    message_template = "Type '{type_name}' has no field '{field_name}'"


class MethodNotFoundError(CompileTimeError):
    code = "FS-SEM-0012"
    category = ErrorCategory.SEMANTIC
    message_template = "Type '{type_name}' has no method '{method_name}'"


class ConstructorNotFoundError(CompileTimeError):
    code = "FS-SEM-0013"
    category = ErrorCategory.SEMANTIC
    message_template = "No constructor defined for type '{type_name}'"


class InvalidOperatorError(CompileTimeError):
    code = "FS-SEM-0014"
    category = ErrorCategory.SEMANTIC
    message_template = "Operator '{operator}' is not valid for type '{type_name}'"


class ControlFlowError(CompileTimeError):
    code = "FS-SEM-0015"
    category = ErrorCategory.SEMANTIC
    message_template = "{statement} statement not within a loop"


class InvalidSuperError(CompileTimeError):
    code = "FS-SEM-0016"
    category = ErrorCategory.SEMANTIC
    message_template = "{detail}"
