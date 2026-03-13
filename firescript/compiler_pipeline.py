"""Compiler pipeline helpers for frontend and semantic stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from enums import NodeTypes
from frontend_pipeline import tokenize_and_parse, resolve_imports_and_deferred_identifiers
from parser import Parser, ASTNode
from preprocessor import enable_and_insert_drops
from semantic_analyzer import SemanticAnalyzer


@dataclass
class CompilerPipeline:
    source_text: str
    source_name: str
    source_path: str
    parser_instance: Optional[Parser] = None
    ast: Optional[ASTNode] = None
    analyzer: Optional[SemanticAnalyzer] = None

    def parse(self) -> ASTNode:
        """Run lexer and parser, storing parser state and AST."""
        self.parser_instance, self.ast, _ = tokenize_and_parse(self.source_text, self.source_name)
        return self.ast

    @property
    def tokens(self):
        return self.parser_instance.tokens if self.parser_instance is not None else []

    @property
    def parser_errors(self):
        return self.parser_instance.errors if self.parser_instance is not None else []

    def has_imports(self) -> bool:
        """Return whether the current AST contains import statements."""
        return bool(
            self.ast is not None
            and any(c.node_type == NodeTypes.IMPORT_STATEMENT for c in self.ast.children)
        )

    def resolve_imports(self) -> ASTNode:
        """Resolve import graph and deferred identifiers into a merged AST."""
        if self.ast is None or self.parser_instance is None:
            raise RuntimeError("parse() must be called before resolve_imports()")
        self.ast = resolve_imports_and_deferred_identifiers(
            self.ast,
            self.parser_instance,
            self.source_path,
        )
        return self.ast

    def preprocess(self) -> ASTNode:
        """Run preprocessor passes on the current AST."""
        if self.ast is None:
            raise RuntimeError("parse() must be called before preprocess()")
        self.ast = enable_and_insert_drops(self.ast)
        return self.ast

    def analyze_semantics(self) -> SemanticAnalyzer:
        """Run semantic analysis on the current AST."""
        if self.ast is None:
            raise RuntimeError("parse() must be called before analyze_semantics()")
        self.analyzer = SemanticAnalyzer(
            self.ast,
            source_file=self.source_path,
            source_code=self.source_text,
        )
        self.analyzer.analyze()
        return self.analyzer