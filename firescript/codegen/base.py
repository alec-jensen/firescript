from enums import NodeTypes
from parser import ASTNode, get_line_and_coumn_from_index, get_line
from errors import CompileTimeError, CodegenError
from utils.type_utils import is_copyable, is_owned, register_class
from typing import Optional
import logging
import os
import re

from compiler_types import DirectiveNameSet, FileDirectiveMap, SourceMap, SymbolTable


# A simple type mapping from firescript types to C types.
FIRETYPE_TO_C: dict[str, str] = {
    # integers
    "int8": "int8_t",
    "int16": "int16_t",
    "int32": "int32_t",
    "int64": "int64_t",
    "uint8": "uint8_t",
    "uint16": "uint16_t",
    "uint32": "uint32_t",
    "uint64": "uint64_t",
    # floats (explicit only)
    "float32": "float",
    "float64": "double",
    "float128": "long double",
    # future: "float128": "__float128",
    # others
    "bool": "bool",
    "string": "char*",
}

class CCodeGeneratorBase:
    def __init__(self, ast: ASTNode, source_file: Optional[str] = None):
        self.ast = ast
        self.source_file = source_file
        self.source_code: Optional[str] = None
        self.errors: list[CompileTimeError] = []
        self.symbol_table: SymbolTable = {}
        # Fixed-size array lengths by variable name
        self.array_lengths: dict[str, int] = {}
        self.array_temp_counter = (
            0  # Counter for generating unique array variable names
        )
        # Track owned values (strings, arrays, non-copyable classes) declared per lexical scope
        # to free them at scope exit. Each element is a list of (var_name, var_type) tuples.
        self.scope_stack: list[list[tuple[str, str]]] = [[]]
        # Track whether we're currently visiting inside a function body
        self._in_function: bool = False
        
        # Get the entry file path from the root AST (set during import merge)
        entry_file = getattr(self.ast, "entry_file", None)
        
        # Build per-file directive maps
        # Map: file_path -> set of enabled directive names
        # Normalize paths to ensure consistent lookups regardless of how the file was specified
        self.file_directives: FileDirectiveMap = {}
        for c in (self.ast.children or []):
            if c.node_type == NodeTypes.DIRECTIVE:
                directive_name = getattr(c, "name", "")
                directive_source = getattr(c, "source_file", entry_file or source_file)
                normalized_source = self._normalize_source_path(directive_source)
                if normalized_source is None:
                    continue
                if normalized_source not in self.file_directives:
                    self.file_directives[normalized_source] = set()
                self.file_directives[normalized_source].add(directive_name)
        
        # For backward compatibility, check entry file directives
        entry_source = entry_file if isinstance(entry_file, str) else source_file
        entry_directives = self._directives_for_source(entry_source)
        self.drops_enabled: bool = "enable_drops" in entry_directives
        self.stdout_enabled: bool = "enable_lowlevel_stdout" in entry_directives
        self.syscall_enabled: bool = "enable_syscalls" in entry_directives
        
        # Name mangling support: map original names to mangled names
        self.name_counter = 0
        self.mangled_names: dict[str, str] = {}
        # Stack of name scopes for nested functions/blocks
        self.name_scope_stack: list[dict[str, str]] = [{}]
        # Built-in functions that shouldn't be mangled
        self.builtin_names = {
            "stdout",
            "drop",
            "process_argc",
            "process_argv_at",
            "syscall_open",
            "syscall_read",
            "syscall_write",
            "syscall_close",
        }
        
        # Collect class names and metadata for constructors and methods
        self.class_names: set[str] = set()
        # Maps firescript class name -> mangled C struct name (e.g. "MyClass" -> "MyClass_0")
        self.class_name_map: dict[str, str] = {}
        self.class_fields: dict[str, list[tuple[str, str]]] = {}
        self.class_methods: dict[str, list[ASTNode]] = {}
        for c in (self.ast.children or []):
            if c.node_type == NodeTypes.CLASS_DEFINITION:
                # Skip generic class templates — they'll be instantiated on demand
                if getattr(c, 'type_params', []):
                    continue
                self.class_names.add(c.name)
                # Register mangled C identifier for this class
                mangled_c = f"{c.name}_{self.name_counter}"
                self.name_counter += 1
                self.class_name_map[c.name] = mangled_c
                # Register class with type_utils
                is_copyable_class = getattr(c, "is_copyable", False)
                register_class(c.name, is_copyable_class)
                fields: list[tuple[str, str]] = []
                methods: list[ASTNode] = []
                for ch in c.children:
                    if ch.node_type == NodeTypes.CLASS_FIELD:
                        fields.append((ch.name, ch.var_type or "int32"))
                    elif ch.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
                        methods.append(ch)
                self.class_fields[c.name] = fields
                self.class_methods[c.name] = methods
        
        # Generics support: track monomorphized instances
        # Maps (func_name, tuple of concrete types) -> mangled function name
        self.monomorphized_funcs: dict[tuple[str, tuple[str, ...]], str] = {}
        # Track which generic functions need to be instantiated
        self.generic_templates: dict[str, ASTNode] = {}
        # Generic class templates: template_name -> ASTNode
        self.generic_class_templates: dict[str, ASTNode] = {}
        # Monomorphized generic class instances: composite_name -> True (just tracking what's been emitted)
        self.monomorphized_classes: set[str] = set()
        # Track which user-defined (non-generic) functions have at least one explicit [] array param.
        # Only these functions receive the implicit _len companion parameter, and only calls to
        # them should inject sizes.
        self._explicit_array_param_funcs: set[str] = set()
        # Collect generic function templates, generic class templates, and pre-scan for explicit array-param functions
        for c in (self.ast.children or []):
            if c.node_type == NodeTypes.FUNCTION_DEFINITION:
                if hasattr(c, 'type_params') and c.type_params:
                    self.generic_templates[c.name] = c
                    logging.debug(f"Found generic template: {c.name} with type params {c.type_params}")
                else:
                    # Non-generic: check for explicit [] array parameters
                    for ch in (c.children or []):
                        if ch.node_type == NodeTypes.PARAMETER and ch.is_array:
                            self._explicit_array_param_funcs.add(c.name)
                            break
            elif c.node_type == NodeTypes.CLASS_DEFINITION:
                if getattr(c, 'type_params', []):
                    self.generic_class_templates[c.name] = c
                    logging.debug(f"Found generic class template: {c.name} with type params {c.type_params}")

    def report_error(self, err: CompileTimeError, node: Optional[ASTNode] = None):
        """Report a compilation error object with source location."""
        if node is None:
            if not err.source_file:
                err.source_file = self.source_file
            self.errors.append(err)
            logging.error(err.to_log_string())
            return
        
        # Get source file and source code for this node
        node_source_file = getattr(node, 'source_file', self.source_file)
        source_map: SourceMap = getattr(self.ast, 'source_map', {})
        node_source_code = (
            source_map.get(node_source_file)
            if source_map and isinstance(node_source_file, str)
            else None
        )
        
        # Fall back to main source if not in map
        if node_source_code is None:
            node_source_code = self.source_code
            node_source_file = self.source_file
        
        if node_source_file is None or node_source_code is None:
            if not err.source_file:
                err.source_file = self.source_file
            self.errors.append(err)
            logging.error(err.to_log_string())
            return

        try:
            line_num, column_num = get_line_and_coumn_from_index(node_source_code, node.index)
            line_text = get_line(node_source_code, line_num)
            err.line = line_num
            err.column = column_num
            err.snippet = line_text
            if not err.source_file:
                err.source_file = node_source_file
            self.errors.append(err)
            logging.error(err.to_log_string())
        except (IndexError, ValueError):
            # Node index is out of range - just show the error without source location
            if not err.source_file:
                err.source_file = node_source_file
            self.errors.append(err)
            logging.error(err.to_log_string())

    def error(self, text: str, node: Optional[ASTNode] = None):
        self.report_error(CodegenError(message=text, source_file=self.source_file), node=node)

    def _normalize_source_path(self, source_path: Optional[str]) -> Optional[str]:
        """Normalize a source path for directive/source-map lookups."""
        return os.path.abspath(source_path) if source_path else None

    def _directives_for_source(self, source_path: Optional[str]) -> DirectiveNameSet:
        """Return enabled directives for a given source file."""
        normalized_source = self._normalize_source_path(source_path)
        return self.file_directives.get(normalized_source, set()) if normalized_source else set()

    def _directives_for_node(self, node: ASTNode) -> DirectiveNameSet:
        """Return enabled directives for the file that produced a node."""
        node_source_file = getattr(node, 'source_file', self.source_file)
        return self._directives_for_source(node_source_file)

    def _free_arrays_in_current_scope(self) -> list[str]:
        """Return lines to free owned values declared in the current scope (no pop)."""
        if not self.scope_stack:
            return []
        
        cleanup_lines = []
        # Current scope is the last element in scope_stack
        for var_name, var_type in self.scope_stack[-1]:
            # Generate firescript_free call for each owned value
            cleanup_lines.append(f"firescript_free({var_name});")
        
        return cleanup_lines

    def _free_arrays_in_all_active_scopes(self, exclude_var: Optional[str] = None) -> list[str]:
        """Return lines to free owned values declared in all active scopes (for early returns).
        
        Args:
            exclude_var: Optional mangled variable name to exclude from cleanup (e.g., the returned value)
        """
        if not self.scope_stack:
            return []
        
        cleanup_lines = []
        # Free from innermost to outermost scope (reverse order of allocation)
        for scope in reversed(self.scope_stack):
            for var_name, var_type in reversed(scope):
                # Skip the variable being returned (ownership transfers to caller)
                if exclude_var and var_name == exclude_var:
                    continue
                cleanup_lines.append(f"firescript_free({var_name});")
        
        return cleanup_lines

    def _handle_array_index(self, index_expr):
        """Helper function to properly handle array indices in C"""
        # After removing big number support, just return the expression string
        return str(index_expr)

    def _build_call_args(self, arg_nodes, func_name: Optional[str] = None) -> str:
        """Build a comma-separated argument string, injecting implicit size args for explicit
        array parameters of user-defined functions (those in _explicit_array_param_funcs)."""
        inject_sizes = func_name is not None and func_name in self._explicit_array_param_funcs
        parts = []
        for arg in arg_nodes:
            parts.append(self._visit(arg))
            if inject_sizes:
                # If the argument is an array, pass its size as the implicit companion argument
                is_array_arg = getattr(arg, 'is_array', False)
                if not is_array_arg and arg.node_type == NodeTypes.IDENTIFIER:
                    sym = self.symbol_table.get(arg.name)
                    if sym and len(sym) >= 2 and sym[1]:
                        is_array_arg = True
                if is_array_arg:
                    size_val = None
                    if arg.node_type == NodeTypes.IDENTIFIER:
                        sym_info = self.symbol_table.get(arg.name)
                        if sym_info and len(sym_info) >= 3 and sym_info[2] is not None:
                            size_val = sym_info[2]
                    if size_val is not None:
                        parts.append(str(size_val))
                    else:
                        parts.append("0")
        return ", ".join(parts)

    def _visit(self, node: ASTNode) -> str:
        """Implemented by statement mixins; declared here for static type checking."""
        raise NotImplementedError("_visit must be implemented by codegen mixins")

    def _emit_method_definition(self, class_name: str, node: ASTNode) -> str:
        """Implemented by class mixins; declared here for static type checking."""
        raise NotImplementedError("_emit_method_definition must be implemented by codegen mixins")

    def _mangle_name(self, name: str) -> str:
        """Generate a unique mangled name for a user symbol to avoid C collisions."""
        # Don't mangle built-in functions
        if name in self.builtin_names:
            return name
        
        # Check current scope first, then parent scopes
        for scope in reversed(self.name_scope_stack):
            if name in scope:
                return scope[name]
        
        # Not found in any scope - create new mangled name in current scope
        mangled = f"{name}_{self.name_counter}"
        self.name_counter += 1
        self.name_scope_stack[-1][name] = mangled
        return mangled

    def _get_c_class_name(self, fs_name: str) -> str:
        """Return the C-safe mangled struct name for a firescript class."""
        if "<" in fs_name:
            return self._mangle_class_composite_name(fs_name)
        return self.class_name_map.get(fs_name, fs_name)

    def _mangle_generic_name(self, func_name: str, type_args: tuple[str, ...]) -> str:
        """Generate a mangled name for a monomorphized generic function."""
        # Simple mangling: func_name$type1$type2$...
        # Replace [] with _arr for C-safe names
        safe_types = [t.replace("[]", "_arr") for t in type_args]
        type_suffix = "$".join(safe_types)
        return f"{func_name}${type_suffix}"

    def _map_type_to_c(self, t: str) -> str:
        if t == "void":
            return "void"
        if t.endswith("[]"):
            # Arrays map to pointer to element type
            elem_type = t[:-2]
            return f"{FIRETYPE_TO_C.get(elem_type, elem_type)}*"
        # Handle composite generic class types like "Pair<int32, string>"
        if "<" in t:
            c_name = self._mangle_class_composite_name(t)
            if t in self.class_names and is_owned(t, False):
                return f"{c_name}*"
            return c_name
        # Check if this is a user-defined class
        if t in self.class_names and is_owned(t, False):
            return f"{self._get_c_class_name(t)}*"
        if t in self.class_names:
            return self._get_c_class_name(t)
        return FIRETYPE_TO_C.get(t, t)

    def _normalize_integer_literal(self, s: str) -> str:
        """Convert firescript integer literal (with optional suffix/underscores) to valid C."""
        # strip underscores
        s2 = s.replace("_", "")
        # strip width/unsigned suffixes
        for suf in ("i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"):
            if s2.lower().endswith(suf):
                return s2[: -len(suf)]
        return s2

    def _normalize_float_literal(self, s: str, ftype: str | None) -> str:
        """Convert firescript float literal (with optional suffix/underscores) to valid C.
        ftype can be 'float32' | 'float64' | 'float128' or None if unknown.
        """
        s2 = s.replace("_", "")
        # Remove explicit suffix from literal text if present
        for suf in ("f128", "f64", "f32", "f"):
            if s2.lower().endswith(suf):
                s2 = s2[: -len(suf)]
                break
        # Apply C-specific suffix based on target type
        if ftype == "float32":
            return s2 + "f"
        if ftype == "float128":
            # Map to long double with L suffix
            return s2 + "L"
        # float64 (double) default: no suffix
        return s2

    def _escape_string_literal(self, literal: str) -> str:
        """
        Escape a string literal for C.
        The literal comes from the lexer with quotes included.
        We need to escape ACTUAL special characters (like literal newlines/tabs)
        but preserve escape sequences that are already in the source (like \\n).
        """
        if not literal:
            return '""'
        
        # Remove outer quotes
        if literal.startswith('"') and literal.endswith('"'):
            content = literal[1:-1]
        else:
            content = literal
        
        # Replace actual special characters with their escape sequences
        # Don't touch existing backslash sequences - only literal characters
        result = []
        i = 0
        while i < len(content):
            ch = content[i]
            # If we see a backslash, it's part of an escape sequence - keep as-is
            if ch == '\\':
                result.append(ch)
                i += 1
                # Also keep the next character (part of escape sequence)
                if i < len(content):
                    result.append(content[i])
                    i += 1
            # Escape actual special characters
            elif ch == '\n':
                result.append('\\n')
                i += 1
            elif ch == '\r':
                result.append('\\r')
                i += 1
            elif ch == '\t':
                result.append('\\t')
                i += 1
            elif ch == '\0':
                result.append('\\0')
                i += 1
            elif ch == '"':
                result.append('\\"')
                i += 1
            else:
                result.append(ch)
                i += 1
        
        return f'"{"".join(result)}"'

    def _mangle_class_composite_name(self, composite: str) -> str:
        """Convert 'Pair<int32, string>' into 'Pair_N__int32__string' (base class name mangled)."""
        bracket = composite.index("<")
        base = composite[:bracket]
        rest = composite[bracket:]  # "<int32, string>"
        # Mangle the base class name if registered
        mangled_base = self.class_name_map.get(base, base)
        # Convert type args portion to C-safe suffix
        safe_rest = re.sub(r'[<> ,]+', '__', rest).strip('_')
        return f"{mangled_base}__{safe_rest}"

    def _literal_to_c(self, node: ASTNode) -> str:
        """Turn a LITERAL node into a valid C expression string."""
        tok = node.token
        if tok is None:
            return ""
        t = tok.type
        # Booleans, null, and strings can be used as-is (string includes quotes)
        if t == "BOOLEAN_LITERAL":
            return tok.value
        if t == "NULL_LITERAL":
            return "NULL"
        if t == "STRING_LITERAL":
            # Escape the string literal for C
            return self._escape_string_literal(tok.value)
        # Numbers
        if t == "INTEGER_LITERAL":
            return self._normalize_integer_literal(tok.value)
        if t in ("FLOAT_LITERAL", "DOUBLE_LITERAL"):
            # Choose target float type if known from parser
            ftype = getattr(node, "return_type", None)
            return self._normalize_float_literal(tok.value, ftype)
        return tok.value or ""

