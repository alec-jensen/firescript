"""Shared typing aliases for compiler metadata structures."""

from typing import Any, TypeAlias


DirectiveNameSet: TypeAlias = set[str]
FileDirectiveMap: TypeAlias = dict[str, DirectiveNameSet]
SourceMap: TypeAlias = dict[str, str]
MergedSymbolTableEntry: TypeAlias = tuple[str, bool]
MergedSymbolTable: TypeAlias = dict[str, MergedSymbolTableEntry]
SymbolInfo: TypeAlias = tuple[str, bool] | tuple[str, bool, Any]
SymbolTable: TypeAlias = dict[str, SymbolInfo]