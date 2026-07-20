"""AST -> FIR converter.

Converts the semantic-analyzed, preprocessed AST into a FIR module.
Type and ownership conclusions are consumed from AST annotations
(`return_type`, `var_type`, `is_array`, `value_category`, preprocessor-
inserted drop() calls) -- nothing is re-inferred here beyond reading
those annotations.

Naming conventions in the produced module:
- free functions keep their source names
- methods are named "Class.method"; constructors "Class.Class"
- intrinsics (syscall_*, str_*, process_arg*, stdout, conversions) become
  Call instructions with their source names and metadata["intrinsic"]=True
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from enums import NodeTypes
from parser import ASTNode

from fir.ir_builder import FIRBuilder
from fir.ir_module import EnumVariantDef, FIRFunction, FIRModule, GlobalConstant, TypeDef
from fir.ir_node import Value
from fir.ir_types import (
    ArrayType,
    COPYABLE_BUILTINS,
    FIRType,
    GeneratorType,
    GenericInstanceType,
    SimpleType,
    make_simple,
)

# Scalar built-in types a `T?` can meaningfully wrap where "null" needs a
# real, separate representation from the type's own zero value (unlike
# string?/a class?/an array?, where the underlying pointer already has a
# natural null = 0 encoding). See docs/changelog.md's 0.6.0 entry on
# nullable-scalar support and _nullable_scalar_base() below.
NULLABLE_SCALAR_TYPES = COPYABLE_BUILTINS - {"void"}

# Intrinsic call names passed through as FIR Calls with metadata["intrinsic"].
INTRINSIC_FUNCTIONS = frozenset(
    {
        "stdout",
        "process_argc",
        "process_argv_at",
        "str_length",
        "str_char_at",
        "str_index_of",
        "str_slice",
        "syscall_open",
        "syscall_read",
        "syscall_write",
        "syscall_close",
        "syscall_remove",
        "syscall_rename",
        "syscall_move",
        "toInt",
        "toFloat",
        "toDouble",
        "toString",
        "toChar",
        "toBool",
        "int",
        "i32_to_f64",
        "i32_to_f32",
        "f64_to_i32",
        "f32_to_i32",
        "i32_to_str",
        "i64_to_str",
        "f64_to_str",
        "f32_to_str",
        # Low-level runtime primitives (enable_lowlevel_runtime)
        "f64_bits",
        "f128_lo",
        "f128_hi",
        "f128_from_halves",
        "mem_load_u8",
        "mem_store_u8",
        "mem_load_u64",
        "mem_store_u64",
        "mem_copy",
        "str_to_addr",
        "addr_to_str",
        "runtime_state_get",
        "runtime_state_set",
        "win_get_process_heap",
        "win_heap_alloc",
        "win_heap_free",
        "win_get_std_handle",
        "win_write_file",
        "win_read_file",
        "win_create_file_a",
        "win_close_handle",
        "win_delete_file_a",
        "win_move_file_ex_a",
        "win_copy_file_a",
        "win_get_last_error",
        "win_get_command_line_a",
        "win_get_file_size",
        "win_set_file_pointer",
        "win_exit_process",
    }
)

INTRINSIC_RETURN_TYPES: dict[str, str] = {
    "stdout": "void",
    "process_argc": "int32",
    "process_argv_at": "string",
    "str_length": "int32",
    "str_char_at": "string",
    "str_index_of": "int32",
    "str_slice": "string",
    "syscall_open": "SyscallResult",
    "syscall_read": "SyscallResult",
    "syscall_write": "SyscallResult",
    "syscall_close": "SyscallResult",
    "syscall_remove": "SyscallResult",
    "syscall_rename": "SyscallResult",
    "syscall_move": "SyscallResult",
    "toInt": "int32",
    "toFloat": "float32",
    "toDouble": "float64",
    "toString": "string",
    "toChar": "char",
    "toBool": "bool",
    "int": "int32",
    "i32_to_f64": "float64",
    "i32_to_f32": "float32",
    "f64_to_i32": "int32",
    "f32_to_i32": "int32",
    "i32_to_str": "string",
    "i64_to_str": "string",
    "f64_to_str": "string",
    "f32_to_str": "string",
    "f64_bits": "uint64",
    "f128_lo": "uint64",
    "f128_hi": "uint64",
    "f128_from_halves": "float128",
    "mem_load_u8": "uint8",
    "mem_store_u8": "void",
    "mem_load_u64": "uint64",
    "mem_store_u64": "void",
    "mem_copy": "void",
    "str_to_addr": "uint64",
    "addr_to_str": "string",
    "runtime_state_get": "uint64",
    "runtime_state_set": "void",
    "win_get_process_heap": "uint64",
    "win_heap_alloc": "uint64",
    "win_heap_free": "uint32",
    "win_get_std_handle": "uint64",
    "win_write_file": "int32",
    "win_read_file": "int32",
    "win_create_file_a": "uint64",
    "win_close_handle": "int32",
    "win_delete_file_a": "int32",
    "win_move_file_ex_a": "int32",
    "win_copy_file_a": "int32",
    "win_get_last_error": "uint32",
    "win_get_command_line_a": "uint64",
    "win_get_file_size": "uint32",
    "win_set_file_pointer": "uint32",
    "win_exit_process": "void",
}

COMPOUND_OP_MAP = {
    "ADD_ASSIGN": "+",
    "SUBTRACT_ASSIGN": "-",
    "MULTIPLY_ASSIGN": "*",
    "DIVIDE_ASSIGN": "/",
    "MODULO_ASSIGN": "%",
}

# Bare intrinsic calls gated behind a directive: the calling file must
# enable the directive (std modules carry their own; user code without it
# is rejected). The `.length()` method etc. do not route through here.
_LOWLEVEL_RUNTIME_INTRINSICS = frozenset(
    {
        "f64_bits", "f128_lo", "f128_hi", "f128_from_halves",
        "mem_load_u8", "mem_store_u8", "mem_load_u64", "mem_store_u64",
        "mem_copy", "str_to_addr", "addr_to_str", "runtime_state_get", "runtime_state_set",
        "win_get_process_heap", "win_heap_alloc", "win_heap_free", "win_get_std_handle",
        "win_write_file", "win_read_file", "win_create_file_a", "win_close_handle",
        "win_delete_file_a", "win_move_file_ex_a", "win_copy_file_a", "win_get_last_error",
        "win_get_command_line_a", "win_get_file_size", "win_set_file_pointer", "win_exit_process",
        "fs_rt_array_new", "fs_rt_array_copy", "fs_rt_hash",
    }
)

DIRECTIVE_GATED_INTRINSICS: dict[str, str] = {
    "stdout": "enable_lowlevel_stdout",
    "process_argc": "enable_process_args",
    "process_argv_at": "enable_process_args",
    "str_length": "enable_process_args",
    "str_char_at": "enable_process_args",
    "str_index_of": "enable_process_args",
    "str_slice": "enable_process_args",
    "syscall_open": "enable_syscalls",
    "syscall_read": "enable_syscalls",
    "syscall_write": "enable_syscalls",
    "syscall_close": "enable_syscalls",
    "syscall_remove": "enable_syscalls",
    "syscall_rename": "enable_syscalls",
    "syscall_move": "enable_syscalls",
    **{name: "enable_lowlevel_runtime" for name in _LOWLEVEL_RUNTIME_INTRINSICS},
}


class FIRConversionError(Exception):
    """Raised when the converter meets an AST shape it cannot translate."""

    def __init__(self, message: str, node: Optional[ASTNode] = None):
        location = ""
        if node is not None and getattr(node, "token", None) is not None:
            token = node.token
            index = getattr(token, "index", None)
            if index is not None:
                location = f" (source index {index})"
        super().__init__(f"{message}{location}")
        self.node = node


class ASTToFIRConverter:
    """Convert a semantic-analyzed AST into a FIRModule."""

    def __init__(self, ast: ASTNode, module_name: str = "firescript", is_runtime_module: bool = False):
        self.ast = ast
        self.module = FIRModule(module_name)
        # Runtime modules contain only definitions; no synthetic main.
        self.is_runtime_module = is_runtime_module

        # Program-wide registries (filled by _collect_program_info)
        self.class_fields: dict[str, list[tuple[str, str]]] = {}
        # class name -> set of field names that are nullable *scalar*
        # fields (each has a paired "<field>__hasval: bool" companion field
        # -- see _collect_program_info and the "Nullable scalars" section).
        self.nullable_scalar_fields: dict[str, set[str]] = {}
        self.class_categories: dict[str, str] = {}
        self.class_bases: dict[str, Optional[str]] = {}
        self.class_generic_params: dict[str, list[str]] = {}
        self.class_method_names: dict[str, set[str]] = {}
        self.class_method_defs: dict[tuple[str, str], ASTNode] = {}
        # Enum registries: name -> [(variant name, [(field name, FIRType), ...]), ...]
        # in declaration order (tag = index into this list).
        self.enum_variants: dict[str, list[tuple[str, list[tuple[str, FIRType]]]]] = {}
        self.enum_categories: dict[str, str] = {}
        self.function_defs: dict[str, ASTNode] = {}
        self.generic_functions: dict[str, list[str]] = {}
        self.generator_defs: dict[str, ASTNode] = {}

        # Per-function conversion state
        self.builder: Optional[FIRBuilder] = None
        self.current_function: Optional[FIRFunction] = None
        # Declared type of the binding currently being initialized, used to
        # recover generic type args for constructions like `Pair(1, 2)`.
        self._expected_type_str: Optional[str] = None
        # Generic type parameter names in scope for the class/function/method
        # currently being converted (e.g. {"T"} while converting Option<T>'s
        # body) -- a nullable field/param typed with one of these names is
        # treated as nullable-scalar too, since FIR is built once from the
        # generic template before any concrete type is known. See
        # _nullable_scalar_base.
        self._current_generic_params: set[str] = set()
        # Whether the internal __NullableReturn<T> struct (see
        # _resolve_function_return_type) has been registered on
        # self.module yet.
        self._nullable_return_typedef_registered = False
        # id(FUNCTION_CALL node) -> its converted __NullableReturn<T>
        # struct Value, for a nullable-scalar-returning call -- see the
        # "Nullable-scalar return values" section below _call_arg_hasvals.
        self._call_struct_cache: dict[int, Value] = {}
        # scope stack of name -> (type_str, is_array, array_size, unique_name)
        # unique_name disambiguates sibling-scope locals that share a source
        # name, so FIR local names are unique within a function.
        self.scopes: list[dict[str, tuple[str, bool, Optional[int], str]]] = []
        self._used_local_names: set[str] = set()
        self._sc_counter = 0
        self._match_counter = 0
        # (continue_target, break_target, cleanup) -- cleanup is
        # (unique_name, FIRType, source_name) for the current iteration's
        # owned loop-element binding (currently only for-in over a string
        # produces one; see _convert_for_in_string), or None. break/continue
        # jump directly out of the loop body, bypassing the per-iteration
        # drop inserted at the bottom of the body for the normal fallthrough
        # path -- without also dropping it here, taking either exit leaked
        # that iteration's element on exactly the paths that skip the
        # fallthrough (FIRV-O3). `source_name` lets
        # _mark_owned_identifier_moved recognize a bare-identifier move
        # (assignment, explicit drop(), or an own-mode call argument) of
        # this specific loop variable from anywhere else in ast_to_fir.py.
        #
        # The ownership verifier (fir/ownership_verifier.py) recomputes
        # ownership purely from static Drop/Move/StoreVar instructions with
        # no concept of a runtime flag -- a drop gated behind a boolean
        # loaded at runtime looks, to it, like an unconditional drop
        # reachable from every predecessor, so whether to drop the loop
        # variable at any given exit must be a statically fixed decision on
        # every path, not something resolved at runtime. See
        # _convert_for_in_string_body/_convert_for_in_string_if for how the
        # per-iteration cleanup honors that when the loop variable is moved
        # out conditionally partway through the body.
        self.loop_stack: list[tuple[str, str, Optional[tuple[str, FIRType, str]]]] = []
        # Cleared before converting each statement inside a for-in-string
        # loop body, populated by _mark_owned_identifier_moved with the
        # source name of any active loop variable that statement moved --
        # see _convert_for_in_string_body.
        self._loop_move_observations: set[str] = set()

        # Directive gating: file path -> set of enabled directive names.
        # Nodes carry source_file when merged from imports; single-file
        # compiles leave it unset, so both directives and calls share the
        # None ("entry") bucket.
        self.file_directives: dict[Optional[str], set[str]] = {}
        has_imports = any(
            c.node_type == NodeTypes.IMPORT_STATEMENT for c in (ast.children or [])
        )
        for child in ast.children or []:
            if child.node_type == NodeTypes.DIRECTIVE:
                src = self._norm_source(getattr(child, "source_file", None))
                self.file_directives.setdefault(src, set()).add(child.name)
                if not has_imports:
                    # Single-file compile: call nodes are never import-merge
                    # annotated, so they resolve to the None bucket. All
                    # directives belong to this one file.
                    self.file_directives.setdefault(None, set()).add(child.name)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def convert(self) -> FIRModule:
        self._collect_program_info()

        top_level_statements: list[ASTNode] = []
        user_main: Optional[ASTNode] = None

        for child in self.ast.children:
            node_type = child.node_type
            if node_type in (NodeTypes.DIRECTIVE, NodeTypes.IMPORT_STATEMENT):
                continue
            if node_type == NodeTypes.ENUM_DEFINITION:
                self._convert_enum(child)
                continue
            if node_type == NodeTypes.CLASS_DEFINITION:
                self._convert_class(child)
            elif node_type == NodeTypes.FUNCTION_DEFINITION:
                if child.name == "main":
                    user_main = child
                else:
                    self._convert_function(child)
            elif node_type == NodeTypes.GENERATOR_DEFINITION:
                self._convert_generator(child)
            elif node_type == NodeTypes.VARIABLE_DECLARATION and getattr(child, "is_const", False):
                self._convert_const(child)
            else:
                top_level_statements.append(child)

        if self.is_runtime_module:
            if top_level_statements:
                raise FIRConversionError(
                    "Runtime modules must not contain top-level statements"
                )
        elif user_main is not None:
            self._convert_function(user_main)
            if top_level_statements:
                logging.warning(
                    "Top-level statements outside main() are ignored when main() is defined"
                )
        else:
            self._convert_synthetic_main(top_level_statements)

        self.module.validate()
        return self.module

    # ------------------------------------------------------------------
    # Program info collection
    # ------------------------------------------------------------------

    def _collect_program_info(self) -> None:
        for child in self.ast.children:
            if child.node_type == NodeTypes.CLASS_DEFINITION:
                name = child.name
                fields: list[tuple[str, str]] = []
                methods: set[str] = set()
                nullable_scalars: set[str] = set()
                class_type_params = set(getattr(child, "type_params", []) or [])
                for member in child.children:
                    if member.node_type == NodeTypes.CLASS_FIELD:
                        base_field_type = member.var_type or "int32"
                        is_companion_field = (
                            not member.is_array
                            and member.is_nullable
                            and (base_field_type in NULLABLE_SCALAR_TYPES or base_field_type in class_type_params)
                        )
                        field_type = f"{base_field_type}?" if is_companion_field else base_field_type
                        if member.is_array:
                            field_type += "[]"
                        fields.append((member.name, field_type))
                        if is_companion_field:
                            # Companion has-value field for a nullable
                            # *scalar* field (see the "Nullable scalars"
                            # section above _expr_type) -- an ordinary
                            # struct field, so LoadField/StoreField and the
                            # struct-layout builder need no changes at all;
                            # only construction/assignment/comparison sites
                            # (below) need to know it exists. Also fires
                            # when the field's type is the class's own
                            # generic parameter (e.g. `value: T?` in
                            # Option<T>): FIR is built once from the generic
                            # template before any concrete T is known, so a
                            # nullable generic-parameter field must always
                            # get a companion -- it becomes load-bearing
                            # exactly when a caller instantiates T with a
                            # scalar. The stored field type keeps its "?"
                            # suffix (unlike a plain nullable string/class
                            # field, which never carried one) purely so
                            # _expr_type's FIELD_ACCESS branch can tell this
                            # field is nullable-scalar without re-deriving
                            # it from class_type_params at every call site.
                            fields.append((self._hasval_name(member.name), "bool"))
                            nullable_scalars.add(member.name)
                    elif member.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
                        methods.add(member.name)
                        self.class_method_defs[(name, member.name)] = member
                self.nullable_scalar_fields[name] = nullable_scalars
                self.class_fields[name] = fields
                self.class_method_names[name] = methods
                is_copyable = bool(getattr(child, "is_copyable", False))
                self.class_categories[name] = "copyable" if is_copyable else "owned"
                self.class_bases[name] = getattr(child, "base_class", None)
                self.class_generic_params[name] = list(getattr(child, "type_params", []) or [])
            elif child.node_type == NodeTypes.ENUM_DEFINITION:
                name = child.name
                self.enum_variants[name] = [
                    (
                        member.name,
                        [
                            (field_name, self._fir_type(field_type))
                            for field_name, field_type in getattr(member, "payload_fields", []) or []
                        ],
                    )
                    for member in child.children
                    if member.node_type == NodeTypes.ENUM_VARIANT
                ]
                self.enum_categories[name] = "owned"
            elif child.node_type == NodeTypes.FUNCTION_DEFINITION:
                self.function_defs[child.name] = child
                type_params = list(getattr(child, "type_params", []) or [])
                if type_params:
                    self.generic_functions[child.name] = type_params
            elif child.node_type == NodeTypes.GENERATOR_DEFINITION:
                self.generator_defs[child.name] = child

    # ------------------------------------------------------------------
    # Types
    # ------------------------------------------------------------------

    def _fir_type(
        self,
        type_str: Optional[str],
        is_array: bool = False,
        array_size: Optional[int] = None,
        nullable: bool = False,
    ) -> FIRType:
        """Translate a firescript type string into a FIRType."""
        if type_str is None:
            type_str = "int32"
        type_str = type_str.strip()

        if type_str.endswith("?"):
            # The scope table (see _declare/_lookup) has no dedicated slot
            # for nullable-ness, so it's threaded through the type string
            # itself with a trailing "?" -- consistent with SimpleType's
            # own render() convention. Without this, re-deriving a local's
            # type from the scope table at each LoadVar/StoreVar site would
            # silently drop nullable-ness (FIRV-L2).
            nullable = True
            type_str = type_str[:-1].strip()

        if type_str.endswith("[]"):
            return ArrayType(self._fir_type(type_str[:-2]), array_size)
        if is_array:
            return ArrayType(self._fir_type(type_str), array_size)

        if type_str.startswith("generator<") and type_str.endswith(">"):
            return GeneratorType(self._fir_type(type_str[10:-1]))

        if "<" in type_str and type_str.endswith(">"):
            base, args_text = type_str.split("<", 1)
            args_text = args_text[:-1]
            args = [self._fir_type(a) for a in self._split_type_args(args_text)]
            # GenericInstanceType.category previously defaulted unconditionally
            # to "owned" regardless of the underlying class -- a copyable
            # generic class (e.g. `copyable class Pair<T, U>`) was therefore
            # always misclassified as owned, causing the ownership verifier to
            # demand its locals be consumed/dropped (FIRV-O3) even though
            # nothing should ever drop a copyable value.
            category = self.class_categories.get(base, "owned")
            return GenericInstanceType(base, args, category=category)

        if type_str in self.class_categories:
            return SimpleType(type_str, category=self.class_categories[type_str], nullable=nullable)
        if type_str in self.enum_categories:
            return SimpleType(type_str, category=self.enum_categories[type_str], nullable=nullable)
        if type_str == "SyscallResult":
            # Compiler-internal copyable struct backing the syscall_*
            # intrinsics (see flir/lowering.py::ensure_struct's matching
            # special case). Its class definition lives in
            # std/internal/syscalls.fire, merged into class_categories only
            # for the std/internal/ conversion -- every *other* file using
            # SyscallResult must know its category without that merge, or
            # every local of this type looks (wrongly) "owned" (FIRV-O3).
            return SimpleType(type_str, category="copyable", nullable=nullable)
        return make_simple(type_str, nullable=nullable)

    @staticmethod
    def _split_type_args(text: str) -> list[str]:
        args: list[str] = []
        depth = 0
        current = ""
        for ch in text:
            if ch == "<":
                depth += 1
            elif ch == ">":
                depth -= 1
            elif ch == "," and depth == 0:
                args.append(current.strip())
                current = ""
                continue
            current += ch
        if current.strip():
            args.append(current.strip())
        return args

    # ------------------------------------------------------------------
    # Scope helpers
    # ------------------------------------------------------------------

    def _drop_loop_cleanup(self, target_block_id: str) -> None:
        """Drop the current loop's per-iteration owned element (if it has
        one -- see self.loop_stack) and jump to `target_block_id`. Used by
        break/continue and by the normal fallthrough end of a loop body.

        For a for-in-string loop, _convert_for_in_string_body temporarily
        overwrites self.loop_stack[-1]'s cleanup entry with None whenever
        the loop variable has already been moved out earlier on the
        current static path, so a break/continue reached from there (via
        the ordinary BREAK_STATEMENT/CONTINUE_STATEMENT dispatch, which
        calls this method without otherwise knowing about that path's
        ownership state) correctly skips the drop instead of double-
        dropping."""
        cleanup = self.loop_stack[-1][2] if self.loop_stack else None
        if cleanup is not None:
            loop_local, loop_local_type, _source_name = cleanup
            ref = self.builder.load_var(loop_local, loop_local_type)
            self.builder.drop(ref)
        self.builder.jump(target_block_id)

    def _push_scope(self) -> None:
        self.scopes.append({})

    def _pop_scope(self) -> None:
        self.scopes.pop()

    def _declare(self, name: str, type_str: str, is_array: bool, size: Optional[int] = None) -> str:
        unique = name
        counter = 2
        while unique in self._used_local_names:
            unique = f"{name}__{counter}"
            counter += 1
        self._used_local_names.add(unique)
        self.scopes[-1][name] = (type_str, is_array, size, unique)
        return unique

    def _lookup(self, name: str) -> Optional[tuple[str, bool, Optional[int], str]]:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def _local_name(self, name: str) -> str:
        symbol = self._lookup(name)
        return symbol[3] if symbol is not None else name

    # ------------------------------------------------------------------
    # Nullable scalars: T? for a scalar T (int8..uint64, bool, char,
    # float32/64/128) needs a real "has a value" flag alongside the value
    # itself, unlike string?/a class?/an array? (already pointer-shaped, so
    # 0 = null is unambiguous). Locals/fields/parameters get a companion
    # `<name>__hasval: bool` binding, tracked through the same _declare/
    # _lookup scope machinery as the main binding under a derived name --
    # see docs/reference/std/collections.md and docs/changelog.md's 0.6.0
    # entry for the full design and its current coverage.
    # ------------------------------------------------------------------

    def _nullable_scalar_base(self, type_str: Optional[str]) -> Optional[str]:
        """If `type_str` is 'T?' for a scalar T needing a real null/zero
        distinction, return T; else None. A base matching a generic type
        parameter currently in scope (self._current_generic_params) also
        counts: FIR is built once from the generic template, before any
        concrete type is known, so `value: T?` must always get companion
        treatment -- it becomes load-bearing exactly when a caller
        instantiates T with a scalar."""
        if not type_str or not type_str.endswith("?"):
            return None
        base = type_str[:-1].strip()
        if base in NULLABLE_SCALAR_TYPES or base in self._current_generic_params:
            return base
        return None

    @staticmethod
    def _hasval_name(source_name: str) -> str:
        return f"{source_name}__hasval"

    @staticmethod
    def _is_null_literal(node: Optional[ASTNode]) -> bool:
        return (
            node is not None
            and node.node_type == NodeTypes.LITERAL
            and node.token is not None
            and node.token.type == "NULL_LITERAL"
        )

    def _expected_type_if_null(self, node: Optional[ASTNode], expected: Optional[str]) -> Optional[str]:
        """`expected` only matters to _expr_type's NULL_LITERAL branch, so
        only propagate it when `node` is itself a bare null literal --
        setting self._expected_type_str before converting a *compound*
        expression (e.g. a `println(x == null)` call argument, where
        `node` is the whole equality expression, not a null literal) would
        leak into that expression's own nested sub-conversions, resolving
        an unrelated nested null literal to completely the wrong type."""
        return expected if self._is_null_literal(node) else None

    def _nullable_scalar_has_value(self, node: Optional[ASTNode]) -> Value:
        """FIR bool Value: does the nullable-scalar-typed expression `node`
        (or no initializer at all, if None) currently hold a value?
        `null` -> false; a bare identifier of the same nullable-scalar
        shape -> copies that identifier's own companion flag (a plain
        binding-to-binding copy, e.g. `y: int32? = x;`); `obj.field` where
        `obj` is a bare identifier -> copies the field's own companion
        field (e.g. `this.value != null` inside Option.isSome()); anything
        else (a literal, an arithmetic result, a method/constructor call
        result, a field access through a non-identifier receiver such as
        `getObj().field`...) -> true, since firescript's grammar has no
        other way to produce "no value" than writing `null` or copying an
        already-nullable binding/field. A call to a nullable-scalar-
        returning *plain function* is the one call-shaped exception (see
        the "Nullable-scalar return values" section below
        _call_arg_hasvals): it reads the callee's has-value companion out
        of its __NullableReturn<T> result, converting the call at most
        once via self._call_struct_cache so a side-effecting callee isn't
        invoked twice. The non-identifier-receiver
        restriction on field access avoids double-evaluating a
        side-effecting receiver expression (this function and the
        expression's normal conversion are called independently at some
        call sites, e.g. constructor arguments) -- see
        _nullable_scalar_base's docstring for current coverage."""
        bool_type = make_simple("bool")
        if node is None or self._is_null_literal(node):
            return self.builder.bool_literal(False, bool_type)
        if node.node_type == NodeTypes.IDENTIFIER:
            symbol = self._lookup(node.name)
            if symbol is not None and self._nullable_scalar_base(symbol[0]) is not None:
                hv_symbol = self._lookup(self._hasval_name(node.name))
                if hv_symbol is not None:
                    return self.builder.load_var(hv_symbol[3], bool_type)
        if (
            node.node_type == NodeTypes.FIELD_ACCESS
            and node.children[0].node_type == NodeTypes.IDENTIFIER
        ):
            obj_type = self._expr_type(node.children[0])
            base = obj_type.split("<")[0]
            if node.name in self.nullable_scalar_fields.get(base, set()):
                obj = self._convert_expression(node.children[0])
                return self.builder.load_field(obj, self._hasval_name(node.name), bool_type)
        if node.node_type == NodeTypes.FUNCTION_CALL:
            scalar_base = self._nullable_return_scalar_base(node)
            if scalar_base is not None:
                cache_key = id(node)
                struct_value = self._call_struct_cache.get(cache_key)
                if struct_value is None:
                    struct_value = self._convert_function_call(node, False)
                    if struct_value is not None:
                        self._call_struct_cache[cache_key] = struct_value
                if struct_value is not None:
                    return self.builder.load_field(struct_value, "hasval", bool_type)
        return self.builder.bool_literal(True, bool_type)

    def _declare_hasval_companion(self, source_name: str, has_value: Value) -> None:
        unique = self._declare(self._hasval_name(source_name), "bool", False, None)
        self.builder.declare_local(unique, make_simple("bool"), has_value)

    def _store_hasval_companion(self, source_name: str, has_value: Value) -> None:
        hv_symbol = self._lookup(self._hasval_name(source_name))
        if hv_symbol is not None:
            self.builder.store_var(hv_symbol[3], has_value)

    def _call_arg_hasvals(
        self,
        callee_params: list[ASTNode],
        arg_nodes: list[ASTNode],
        callee_generic_params: Optional[set[str]] = None,
    ) -> list[Value]:
        """Has-value companion argument Values (in order) for whichever of
        `callee_params` are nullable-scalar, matching `arg_nodes`
        positionally -- the caller-side counterpart of the implicit
        trailing companion parameters _function_params appends to a
        nullable-scalar-parameter callee's own signature. `callee_params`
        are the callee's *own* (unsubstituted) parameter AST nodes, so
        whether a param needs a companion is judged against the callee's
        *own* generic parameter names (`callee_generic_params`, e.g.
        Option<T>'s {"T"}), not whatever generic params happen to be in
        scope at the call site -- those are unrelated."""
        result: list[Value] = []
        gp = callee_generic_params or set()
        for param, arg_node in zip(callee_params, arg_nodes):
            if getattr(param, "is_array", False) or not getattr(param, "is_nullable", False):
                continue
            base = param.var_type or "int32"
            if base in NULLABLE_SCALAR_TYPES or base in gp:
                result.append(self._nullable_scalar_has_value(arg_node))
        return result

    # ------------------------------------------------------------------
    # Nullable-scalar return values: a plain function declared `-> T?`
    # for a nullable-scalar T is compiled to *actually* return an internal
    # `__NullableReturn<T>` copyable struct { value: T, hasval: bool }
    # instead of a bare T -- reusing the already-tested copyable-struct-
    # by-value construct/return/field-access machinery (the same one
    # CopyableTuple/CopyableOption use) rather than inventing new IR.
    # Callers unwrap it back to (value, hasval) in
    # _convert_function_call_unwrapped / _nullable_scalar_has_value's
    # FUNCTION_CALL branch, which -- critically -- convert the call
    # expression at most once and cache the struct result in
    # self._call_struct_cache, since a caller needing both pieces (e.g.
    # `x: int32? = foo();`, which asks for has-value before the value)
    # must not evaluate a side-effecting call twice.
    #
    # Scope: only plain (free) functions are wrapped/unwrapped this way.
    # A method/constructor/type-method declared `-> T?` parses (the
    # parser accepts nullable return types generally) but is not yet
    # rewritten to this struct-return convention, so comparing such a
    # call's result against `null` does not work correctly yet -- a
    # documented follow-up, not a silent miscompile (nothing produces a
    # __NullableReturn struct for them, so their return type is the
    # ordinary possibly-nullable FIRType exactly as before this feature).
    # ------------------------------------------------------------------

    _NULLABLE_RETURN_STRUCT = "__NullableReturn"

    def _ensure_nullable_return_typedef(self) -> None:
        if self._nullable_return_typedef_registered:
            return
        self._nullable_return_typedef_registered = True
        type_def = TypeDef(
            self._NULLABLE_RETURN_STRUCT,
            category="copyable",
            fields=[("value", make_simple("T")), ("hasval", make_simple("bool"))],
            generic_params=["T"],
        )
        self.module.add_type(type_def)

    def _resolve_function_return_type(self, return_type_str: Optional[str]) -> Optional[FIRType]:
        """FIRType for a plain function's declared return type, wrapping a
        nullable-scalar return in __NullableReturn<T> (see the section
        comment above). Methods/constructors intentionally keep using
        plain self._fir_type(...) -- see the scope note above."""
        if not return_type_str or return_type_str == "void":
            return None
        scalar_base = self._nullable_scalar_base(return_type_str)
        if scalar_base is not None:
            self._ensure_nullable_return_typedef()
            return GenericInstanceType(
                self._NULLABLE_RETURN_STRUCT, [self._fir_type(scalar_base)], category="copyable"
            )
        return self._fir_type(return_type_str)

    def _nullable_return_scalar_base(self, node: ASTNode) -> Optional[str]:
        """If `node` is a FUNCTION_CALL to a plain user function whose
        declared return type is nullable-scalar, return that scalar's
        base type name (unsubstituted, e.g. "T" for a generic function);
        else None. See the section comment above for scope (free
        functions only)."""
        if node.node_type != NodeTypes.FUNCTION_CALL:
            return None
        name = node.name
        base_name = name.split("<")[0] if "<" in name else name
        if base_name in self.class_categories or base_name in self.generator_defs:
            return None
        callee_def = self.function_defs.get(base_name)
        if callee_def is None:
            return None
        gp = set(getattr(callee_def, "type_params", []) or [])
        rt = getattr(callee_def, "return_type", None)
        if not rt or not rt.endswith("?"):
            return None
        base = rt[:-1].strip()
        if base in NULLABLE_SCALAR_TYPES or base in gp:
            return base
        return None

    def _convert_function_call_unwrapped(self, node: ASTNode, as_statement: bool) -> Optional[Value]:
        scalar_base = self._nullable_return_scalar_base(node)
        if scalar_base is None:
            return self._convert_function_call(node, as_statement)
        cache_key = id(node)
        struct_value = self._call_struct_cache.get(cache_key)
        if struct_value is None:
            struct_value = self._convert_function_call(node, as_statement)
            if struct_value is None:
                return None
            self._call_struct_cache[cache_key] = struct_value
        if as_statement:
            return struct_value
        return self.builder.load_field(struct_value, "value", self._fir_type(scalar_base))

    # ------------------------------------------------------------------
    # Expression typing (reads AST annotations, mirrors codegen lookups)
    # ------------------------------------------------------------------

    def _expr_type(self, node: ASTNode) -> str:
        """Best-effort firescript type string of an expression node."""
        if node.node_type == NodeTypes.LITERAL:
            token_type = node.token.type if node.token else None
            if token_type == "NULL_LITERAL":
                # The parser unconditionally stamps return_type = "null" on
                # every null literal at parse time (expressions.py), which
                # is truthy but uninformative -- it must not short-circuit
                # the generic `annotated` check below. Prefer the
                # caller-set expected type (declaration initializers,
                # constructor/call arguments -- see _expected_type_str's
                # other use sites) so `x: int32? = null;`/`Option<int32>
                # (null)` resolve `null`'s FIR type to int32, not the
                # "string" fallback. Without this, the fallback was
                # silently wrong for any nullable *scalar* context (never
                # previously exercised: every prior nullable use was
                # string/a class, where the fallback's guess happened to
                # still be pointer-shaped like the real answer).
                expected = getattr(self, "_expected_type_str", None)
                if expected:
                    return self._strip_nullable_str(expected)
                return "string"
            annotated = getattr(node, "return_type", None)
            if annotated:
                return annotated
            defaults = {
                "INTEGER_LITERAL": "int32",
                "FLOAT_LITERAL": "float32",
                "DOUBLE_LITERAL": "float64",
                "BOOLEAN_LITERAL": "bool",
                "STRING_LITERAL": "string",
                "CHAR_LITERAL": "char",
                "NULL_LITERAL": "null",
            }
            return defaults.get(token_type or "", "int32")

        if node.node_type == NodeTypes.IDENTIFIER:
            symbol = self._lookup(node.name)
            if symbol is not None:
                type_str, is_array = symbol[0], symbol[1]
                return f"{type_str}[]" if is_array else type_str
            base = node.var_type or "int32"
            return f"{base}[]" if node.is_array else base

        if node.node_type == NodeTypes.ARRAY_LITERAL:
            if node.children:
                return f"{self._expr_type(node.children[0])}[]"
            return "int32[]"

        if node.node_type == NodeTypes.ARRAY_ACCESS:
            array_type = self._expr_type(node.children[0])
            return array_type[:-2] if array_type.endswith("[]") else array_type

        if node.node_type == NodeTypes.CAST_EXPRESSION:
            return node.name or node.var_type or "int32"

        if node.node_type in (
            NodeTypes.EQUALITY_EXPRESSION,
            NodeTypes.RELATIONAL_EXPRESSION,
        ):
            return "bool"

        if node.node_type == NodeTypes.BINARY_EXPRESSION:
            if node.name in ("&&", "||"):
                return "bool"
            annotated = getattr(node, "return_type", None)
            if annotated:
                return annotated
            left = self._expr_type(node.children[0])
            right = self._expr_type(node.children[1])
            return right if left in ("null",) else left

        if node.node_type == NodeTypes.UNARY_EXPRESSION:
            if node.name == "!":
                return "bool"
            if node.name in ("++", "--"):
                var_name = node.token.value if node.token else ""
                symbol = self._lookup(var_name)
                return symbol[0] if symbol else "int32"
            return self._expr_type(node.children[0]) if node.children else "int32"

        if node.node_type == NodeTypes.FUNCTION_CALL:
            if node.name in self.class_categories:
                return node.name
            if node.name in self.generator_defs:
                gen = self.generator_defs[node.name]
                yield_type = getattr(gen, "yield_type", gen.return_type or "int32")
                return f"generator<{yield_type}>"
            if node.name in INTRINSIC_RETURN_TYPES:
                return INTRINSIC_RETURN_TYPES[node.name]
            if node.name in self.generic_functions:
                # node.return_type may be a stale, unsubstituted generic
                # placeholder (e.g. "T") for a cross-module generic call
                # whose defining module wasn't merged yet when the call site
                # was first type-checked -- prefer computing the concrete
                # substituted return type from the inferred type args over
                # trusting that annotation.
                type_params = self.generic_functions[node.name]
                type_args = list(getattr(node, "type_args", []) or [])
                if not type_args or any(a in type_params for a in type_args):
                    type_args = self._infer_type_args(node.name, node)
                func_def = self.function_defs.get(node.name)
                if func_def is not None and type_args and len(type_args) == len(type_params):
                    subst = dict(zip(type_params, type_args))
                    ret = func_def.return_type or "void"
                    return subst.get(ret, ret)
            annotated = getattr(node, "return_type", None)
            if annotated:
                return annotated
            func_def = self.function_defs.get(node.name)
            if func_def is not None:
                return func_def.return_type or "void"
            return "void"

        if node.node_type == NodeTypes.METHOD_CALL:
            annotated = getattr(node, "return_type", None)
            if annotated:
                return annotated
            object_type = self._expr_type(node.children[0])
            method_def = self._find_method_def(object_type, node.name)
            if method_def is not None:
                if getattr(method_def, "is_constructor", False):
                    return object_type
                ret = method_def.return_type or "void"
                # As with the FUNCTION_CALL case above: node.return_type may
                # be unset because the call site was type-checked (parser/
                # type_system.py) before the receiver's defining module was
                # merged in (a cross-module generic class, e.g.
                # `vec.get(i)` on an imported `Vec<int32>`), leaving
                # method_def.return_type an unsubstituted generic
                # placeholder like "T" -- substitute it using the receiver's
                # concrete type arguments, the same way FIELD_ACCESS below
                # already does for generic fields.
                base = object_type.split("<")[0]
                if "<" in object_type and object_type.endswith(">"):
                    args = self._split_type_args(object_type.split("<", 1)[1][:-1])
                    subst = dict(zip(self.class_generic_params.get(base, []), args))
                    return subst.get(ret, ret)
                return ret
            return "void"

        if node.node_type == NodeTypes.TYPE_METHOD_CALL:
            class_name = getattr(node, "class_name", "")
            # class_name is "Box" (Box.make(5)) or "Box<int32>"
            # (Box<int32>.make(5), explicit type arguments already
            # resolved by the parser) -- base_name is what class_generic_
            # params/_find_method_def key on either way.
            base_name = class_name.split("<", 1)[0] if "<" in class_name else class_name
            method_def = self._find_method_def(base_name, node.name)
            if method_def is not None and self.class_generic_params.get(base_name):
                # A static method on a generic class template (e.g.
                # `Box.make(5)` for `class Box<T>`): node.return_type (set
                # by parser/type_system.py's TYPE_METHOD_CALL validation)
                # is the *unsubstituted* template return type ("T" or
                # "Box<T>"), same gap the METHOD_CALL branch above already
                # handles for an instance method's return type -- resolve
                # this call's concrete type arguments (explicit from
                # class_name if present, else inferred from argument
                # types) and substitute.
                if "<" in class_name:
                    type_args = self._split_type_args(class_name.split("<", 1)[1][:-1])
                else:
                    type_args = self._infer_class_method_type_args(base_name, method_def, node)
                ret = method_def.return_type or "void"
                if type_args:
                    subst = dict(zip(self.class_generic_params.get(base_name, []), type_args))
                    if ret in subst:
                        return subst[ret]
                    if ret.endswith("[]") and ret[:-2] in subst:
                        return subst[ret[:-2]] + "[]"
                    if "<" in ret and ret.endswith(">"):
                        base, args_text = ret.split("<", 1)
                        inner = [subst.get(a, a) for a in self._split_type_args(args_text[:-1])]
                        return f"{base}<{', '.join(inner)}>"
                return ret
            annotated = getattr(node, "return_type", None)
            if annotated:
                return annotated
            if method_def is not None:
                return method_def.return_type or "void"
            return "void"

        if node.node_type == NodeTypes.SUPER_CALL:
            return getattr(node, "return_type", None) or "void"

        if node.node_type == NodeTypes.CONSTRUCTOR_CALL:
            return node.name

        if node.node_type == NodeTypes.FIELD_ACCESS:
            obj_type = self._expr_type(node.children[0])
            base = obj_type.split("<")[0]
            # The type-checking pass (parser/type_system.py) already stamps
            # a `return_type` on most FIELD_ACCESS nodes, but its own field
            # registries don't carry a "?" suffix for a nullable field --
            # so that annotation alone can't be trusted for nullable-scalar
            # detection (self.nullable_scalar_fields, populated from the
            # same source data this function's fallback below reads, is
            # authoritative and always checked independently).
            is_nullable_scalar_field = node.name in self.nullable_scalar_fields.get(base, set())
            annotated = getattr(node, "return_type", None)
            if annotated:
                result = annotated
            else:
                subst: dict[str, str] = {}
                if "<" in obj_type and obj_type.endswith(">"):
                    args = self._split_type_args(obj_type.split("<", 1)[1][:-1])
                    subst = dict(zip(self.class_generic_params.get(base, []), args))
                result = "int32"
                for field_name, field_type in self._all_class_fields(base):
                    if field_name == node.name:
                        base_ft = field_type[:-1] if field_type.endswith("?") else field_type
                        suffix = "?" if field_type.endswith("?") else ""
                        result = subst.get(base_ft, base_ft) + suffix
                        break
            if is_nullable_scalar_field and not result.endswith("?"):
                result = f"{result}?"
            return result

        if node.node_type == NodeTypes.MATCH_EXPRESSION:
            annotated = getattr(node, "return_type", None)
            if annotated:
                return annotated
            for arm in node.children[1:]:
                body = arm.children[0] if arm.children else None
                if body is not None and body.node_type != NodeTypes.SCOPE:
                    return self._expr_type(body)
            return "void"

        return getattr(node, "return_type", None) or "int32"

    def _find_method_def(self, class_name: str, method_name: str) -> Optional[ASTNode]:
        """Find a method definition on a class or any of its base classes."""
        # class_method_defs is keyed by the bare class name, but callers pass
        # the full declared type including generic args (e.g. "Box<int32>")
        # -- strip them the same way _all_class_fields/FIELD_ACCESS already do.
        current: Optional[str] = class_name.split("<")[0] if class_name else class_name
        seen: set[str] = set()
        while current is not None and current not in seen:
            seen.add(current)
            method = self.class_method_defs.get((current, method_name))
            if method is not None:
                return method
            current = self.class_bases.get(current)
        return None

    def _infer_class_method_type_args(
        self, class_name: str, method_def: ASTNode, call_node: ASTNode
    ) -> list[str]:
        """Infer a generic class's type arguments from a static method
        call's argument types (e.g. `Box.make(5)` for `class Box<T>` with
        `static fn make(v: T) -> Box<T>` infers T=int32), mirroring
        parser/type_system.py's _infer_generic_type_args for a generic
        *function* call -- there's no receiver instance to read concrete
        type arguments from, unlike an ordinary instance method call.
        Returns [] if any type parameter can't be inferred. Only called
        for the inferred-type-arguments call form (`Box.make(...)`) --
        the explicit form (`Box<int32>.make(...)`) carries its type
        arguments directly on class_name instead (see the TYPE_METHOD_CALL
        branches in _expr_type and _convert_expression, which check for
        "<" in class_name before calling this)."""
        type_params = self.class_generic_params.get(class_name, [])
        if not type_params:
            return []
        params = [c for c in method_def.children if c.node_type == NodeTypes.PARAMETER and not getattr(c, "is_receiver", False)]
        type_map: dict[str, str] = {}
        for param, arg_node in zip(params, call_node.children):
            param_type = param.var_type or ""
            if param_type not in type_params:
                continue
            arg_type = self._expr_type(arg_node) or ""
            if getattr(param, "is_array", False) and arg_type.endswith("[]"):
                arg_type = arg_type[:-2]
            if param_type in type_map and type_map[param_type] != arg_type:
                return []
            type_map[param_type] = arg_type
        if any(tp not in type_map for tp in type_params):
            return []
        return [type_map[tp] for tp in type_params]

    def _all_class_fields(self, class_name: str) -> list[tuple[str, str]]:
        """Fields of a class including inherited base-class fields."""
        fields: list[tuple[str, str]] = []
        seen: set[str] = set()
        current: Optional[str] = class_name
        chain: list[str] = []
        while current is not None and current not in seen:
            seen.add(current)
            chain.append(current)
            current = self.class_bases.get(current)
        for cls in reversed(chain):
            for field in self.class_fields.get(cls, []):
                if field[0] not in {f[0] for f in fields}:
                    fields.append(field)
        return fields

    # ------------------------------------------------------------------
    # Top-level constructs
    # ------------------------------------------------------------------

    def _convert_const(self, node: ASTNode) -> None:
        literal_text = self._render_const_initializer(node.children[0]) if node.children else "0"
        const_type = self._fir_type(node.var_type, node.is_array, getattr(node, "array_size", None))
        self.module.add_constant(GlobalConstant(node.name, const_type, literal_text))

    def _render_const_initializer(self, node: ASTNode) -> str:
        if node.node_type == NodeTypes.LITERAL:
            return self._normalize_literal_text(node)
        if node.node_type == NodeTypes.UNARY_EXPRESSION and node.name == "-" and node.children:
            return "-" + self._render_const_initializer(node.children[0])
        raise FIRConversionError(
            f"Unsupported const initializer node {node.node_type}", node
        )

    def _normalize_literal_text(self, node: ASTNode) -> str:
        token = node.token
        text = str(token.value) if token is not None else "0"
        token_type = token.type if token is not None else ""
        if token_type == "INTEGER_LITERAL":
            cleaned = text.replace("_", "")
            for suffix in ("i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"):
                if cleaned.lower().endswith(suffix):
                    return cleaned[: -len(suffix)]
            return cleaned
        if token_type in ("FLOAT_LITERAL", "DOUBLE_LITERAL"):
            cleaned = text.replace("_", "")
            for suffix in ("f128", "f64", "f32", "f"):
                if cleaned.lower().endswith(suffix):
                    return cleaned[: -len(suffix)]
            return cleaned
        return text

    def _convert_class(self, node: ASTNode) -> None:
        type_def = TypeDef(
            node.name,
            category=self.class_categories.get(node.name, "owned"),
            fields=[
                (field_name, self._fir_type(field_type))
                for field_name, field_type in self.class_fields.get(node.name, [])
            ],
            generic_params=self.class_generic_params.get(node.name, []),
            base=self.class_bases.get(node.name),
        )
        self.module.add_type(type_def)

        for member in node.children:
            if member.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
                self._convert_method(node.name, member)

    def _convert_enum(self, node: ASTNode) -> None:
        variants = [
            EnumVariantDef(name, payload) for name, payload in self.enum_variants.get(node.name, [])
        ]
        type_def = TypeDef(
            node.name,
            category=self.enum_categories.get(node.name, "owned"),
            kind="enum",
            variants=variants,
        )
        self.module.add_type(type_def)

    @staticmethod
    def _strip_nullable_str(type_str: str) -> str:
        """Drop a trailing '?' from a type-name string. _expr_type()
        preserves nullable-ness (via the scope table's "?" suffix
        convention, see _fir_type) for callers reconstructing an actual
        FIRType, but a few call sites feed its result into FLIR lowering
        as a bare metadata string used for exact matching (e.g.
        `operand_type`, `source_type`) -- lowering has never cared about
        nullable-ness (it's a FIR/semantic-level distinction only; both
        `string` and `string?` share the same runtime representation), so
        those sites must strip it first.
        """
        return type_str[:-1] if type_str.endswith("?") else type_str

    def _synthesize_zero(self, fir_type: FIRType) -> Optional[Value]:
        """Best-effort zero value for a copyable scalar type.

        Used to keep an implicit/fallthrough Return well-typed (FIRV-T4)
        without changing the runtime value: lowering already zero-fills a
        value-less Return in a non-void function (flir/lowering.py's
        fall-off handling), so emitting the same zero literal here at the
        FIR level is behavior-preserving, just earlier in the pipeline
        (see docs/internal/development/ir_verifier_spec.md section 8.1).
        Returns None for types with no safe zero representation (owned/
        reference types); callers must not synthesize a value-less Return
        for those -- a non-void function that can fall off the end
        without returning an owned value is a real bug the verifier
        should catch, not paper over.
        """
        if not isinstance(fir_type, SimpleType):
            return None
        name = fir_type.name
        if name in ("int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64"):
            return self.builder.int_literal("0", fir_type)
        if name in ("float32", "float64", "float128"):
            return self.builder.float_literal("0", fir_type)
        if name == "bool":
            return self.builder.bool_literal(False, fir_type)
        if name == "char":
            return self.builder.char_literal("\\0", fir_type)
        return None

    def _function_params(self, node: ASTNode) -> tuple[list[tuple[str, FIRType]], list[str]]:
        params: list[tuple[str, FIRType]] = []
        modes: list[str] = []
        # Nullable-scalar parameters (e.g. `value: T?` in Option<T>'s
        # constructor) need a real has-value flag, same as locals/fields --
        # see the "Nullable scalars" section above _expr_type. There is no
        # spare bit in the value's own representation, so the flag is an
        # implicit trailing bool parameter, appended after all declared
        # parameters (in declaration order) so it doesn't disturb existing
        # positional-argument code at any call site that has none.
        hasval_params: list[tuple[str, FIRType]] = []
        hasval_modes: list[str] = []
        bool_type = make_simple("bool")
        for child in node.children:
            if child.node_type != NodeTypes.PARAMETER:
                continue
            is_nullable_scalar_param = (
                not child.is_array
                and getattr(child, "is_nullable", False)
                and self._nullable_scalar_base(f"{child.var_type or 'int32'}?") is not None
            )
            # Only a nullable-*scalar* param's FIRType is marked nullable
            # here (matching the companion has-value param added below for
            # it) -- a nullable string?/class? param keeps its existing
            # plain (non-nullable) FIRType, since those are already
            # unambiguously null-able via the pointer value 0 and marking
            # them nullable here would make FIRV-T6's exact-type-match
            # check reject an ordinary non-null string/class argument at
            # every such call site (a real, pre-existing convention this
            # change must not disturb).
            param_type = self._fir_type(child.var_type, child.is_array, nullable=is_nullable_scalar_param)
            params.append((child.name, param_type))
            if getattr(child, "is_borrowed", False):
                if getattr(child, "is_mutable_borrow", False):
                    modes.append("borrow_mut")
                else:
                    modes.append("borrow")
            else:
                modes.append("own")
            if is_nullable_scalar_param:
                hasval_params.append((self._hasval_name(child.name), bool_type))
                hasval_modes.append("own")
        params.extend(hasval_params)
        modes.extend(hasval_modes)
        return params, modes

    def _register_params_in_scope(self, node: ASTNode, skip_this: bool = False) -> None:
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER:
                if skip_this and child.name == "this":
                    continue
                type_str = child.var_type or "int32"
                # Only a nullable-*scalar* param's scope-table type carries
                # the "?" suffix (matching _function_params -- see its
                # comment). A nullable string?/class? param keeps its plain
                # type here, same as before this feature existed: those
                # are already unambiguously null-able via pointer value 0,
                # and giving them a "?"-suffixed type would make a LoadVar
                # of the param mismatch the (still plain) field/local type
                # it's stored into (FIRV-T7).
                is_nullable_scalar_param = (
                    not child.is_array
                    and getattr(child, "is_nullable", False)
                    and self._nullable_scalar_base(f"{type_str}?") is not None
                )
                if is_nullable_scalar_param:
                    type_str = f"{type_str}?"
                self._declare(child.name, type_str, child.is_array, None)
                if is_nullable_scalar_param:
                    self._declare(self._hasval_name(child.name), "bool", False, None)

    def _convert_function(self, node: ASTNode, fir_name: Optional[str] = None) -> None:
        prev_generic_params = self._current_generic_params
        self._current_generic_params = set(getattr(node, "type_params", []) or [])
        try:
            params, modes = self._function_params(node)
            nullable_scalar_return = self._nullable_scalar_base(node.return_type or "")
            function = FIRFunction(
                fir_name or node.name,
                params=params,
                return_type=self._resolve_function_return_type(node.return_type),
                generic_params=list(getattr(node, "type_params", []) or []),
                param_modes=modes,
            )
            if nullable_scalar_return is not None:
                function.metadata["nullable_scalar_return"] = nullable_scalar_return
            self.module.add_function(function)
            self._convert_body(node, function)
        finally:
            self._current_generic_params = prev_generic_params

    def _convert_generator(self, node: ASTNode) -> None:
        prev_generic_params = self._current_generic_params
        self._current_generic_params = set(getattr(node, "type_params", []) or [])
        try:
            params, modes = self._function_params(node)
            yield_type = getattr(node, "yield_type", node.return_type or "int32")
            function = FIRFunction(
                node.name,
                params=params,
                return_type=GeneratorType(self._fir_type(yield_type)),
                generic_params=list(getattr(node, "type_params", []) or []),
                param_modes=modes,
                is_generator=True,
            )
            function.metadata["yield_type"] = yield_type
            self.module.add_function(function)
            self._convert_body(node, function)
        finally:
            self._current_generic_params = prev_generic_params

    def _convert_method(self, class_name: str, node: ASTNode) -> None:
        prev_generic_params = self._current_generic_params
        self._current_generic_params = set(self.class_generic_params.get(class_name, [])) | set(
            getattr(node, "type_params", []) or []
        )
        try:
            self._convert_method_body(class_name, node)
        finally:
            self._current_generic_params = prev_generic_params

    def _convert_method_body(self, class_name: str, node: ASTNode) -> None:
        is_constructor = bool(getattr(node, "is_constructor", False))
        is_static = bool(getattr(node, "is_static", False))
        params, modes = self._function_params(node)
        if is_constructor:
            # Constructors create 'this' themselves; drop any explicit
            # 'this' parameter the parser kept in the signature.
            filtered = [
                (i, p) for i, p in enumerate(params) if p[0] != "this"
            ]
            params = [p for _, p in filtered]
            modes = [modes[i] for i, _ in filtered]

        return_type_str = node.return_type or "void"
        if is_constructor:
            return_type_str = class_name

        function = FIRFunction(
            f"{class_name}.{node.name}",
            params=params,
            return_type=self._fir_type(return_type_str) if return_type_str != "void" else None,
            generic_params=self.class_generic_params.get(class_name, []),
            param_modes=modes,
        )
        function.metadata["class_name"] = class_name
        function.metadata["is_constructor"] = is_constructor
        function.metadata["is_static"] = is_static
        self.module.add_function(function)

        self.current_function = function
        self.builder = FIRBuilder(function)
        self._used_local_names = set()
        self._push_scope()
        self._register_params_in_scope(node, skip_this=is_constructor)

        if is_constructor:
            # 'this' is created by the constructor itself.
            this_type = self._fir_type(class_name)
            this_value = self.builder.allocate(this_type, [])
            this_local = self._declare("this", class_name, False, None)
            self.builder.declare_local(this_local, this_type, this_value)
        elif not is_static:
            if self._lookup("this") is None:
                self._declare("this", class_name, False, None)

        body = node.children[-1] if node.children else None
        if body is not None and body.node_type == NodeTypes.SCOPE:
            self._convert_statements(body.children)

        if not self.builder.current_block.is_terminated():
            if is_constructor:
                this_type = self._fir_type(class_name)
                result = self.builder.load_var(self._local_name("this"), this_type)
                self.builder.ret(result)
            elif function.return_type is not None:
                self.builder.ret(self._synthesize_zero(function.return_type))
            else:
                self.builder.ret()

        self._pop_scope()
        self._seal_open_blocks(function)
        self.builder = None
        self.current_function = None

    def _convert_body(self, node: ASTNode, function: FIRFunction) -> None:
        self.current_function = function
        self.builder = FIRBuilder(function)
        self._used_local_names = set()
        self._push_scope()
        self._register_params_in_scope(node)

        body = node.children[-1] if node.children else None
        if body is not None and body.node_type == NodeTypes.SCOPE:
            self._convert_statements(body.children)

        if not self.builder.current_block.is_terminated():
            if not function.is_generator and function.return_type is not None:
                self.builder.ret(self._synthesize_zero(function.return_type))
            else:
                self.builder.ret()

        self._pop_scope()
        self._seal_open_blocks(function)
        self.builder = None
        self.current_function = None

    def _convert_synthetic_main(self, statements: list[ASTNode]) -> None:
        function = FIRFunction("main", return_type=None)
        function.metadata["synthetic"] = True
        self.module.add_function(function)

        self.current_function = function
        self.builder = FIRBuilder(function)
        self._used_local_names = set()
        self._push_scope()
        self._convert_statements(statements)
        if not self.builder.current_block.is_terminated():
            self.builder.ret()
        self._pop_scope()
        self._seal_open_blocks(function)
        self.builder = None
        self.current_function = None

    @staticmethod
    def _seal_open_blocks(function: FIRFunction) -> None:
        """Terminate any unterminated blocks, then drop blocks with no
        incoming edge from the entry block.

        An if/else join block (see _convert_if) ends up with zero
        predecessors when every arm already terminates (e.g. `if (c) {
        return a; } else { return b; }`); code positioned there afterward
        (including the function's own implicit trailing return) is
        genuinely unreachable. Pruning it is a pure dead-code removal --
        it cannot change program behavior -- and keeps FIR free of orphan
        blocks (FIRV-S5).
        """
        from fir.ir_node import BranchInst, JumpInst, UnreachableInst

        for block in function.blocks:
            if block.terminator is None:
                block.set_terminator(UnreachableInst())

        if not function.blocks:
            return
        entry_id = function.blocks[0].id
        by_id = {b.id: b for b in function.blocks}
        reachable = {entry_id}
        worklist = [entry_id]
        while worklist:
            block = by_id[worklist.pop()]
            term = block.terminator
            if isinstance(term, BranchInst):
                targets = [term.true_block, term.false_block]
            elif isinstance(term, JumpInst):
                targets = [term.target_block]
            else:
                targets = []
            for target in targets:
                if target in by_id and target not in reachable:
                    reachable.add(target)
                    worklist.append(target)
        function.blocks = [b for b in function.blocks if b.id in reachable]

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def _convert_statements(self, statements: list[ASTNode]) -> None:
        for statement in statements:
            if self.builder.current_block.is_terminated():
                # Code after return/break/continue in the same scope is
                # unreachable; the semantic analyzer warns about it.
                break
            self._convert_statement(statement)

    def _convert_statement(self, node: ASTNode) -> None:
        node_type = node.node_type

        if node_type == NodeTypes.SCOPE:
            # Preprocessor reassignment wrapper: { drop(x); x = RHS; }.
            # RHS may read x, so evaluate RHS first, then drop the old
            # value, then store (the legacy backend freed first, which was
            # a latent use-after-free masked by allocator timing).
            if (
                len(node.children) == 2
                and node.children[0].node_type == NodeTypes.FUNCTION_CALL
                and node.children[0].name == "drop"
                and node.children[1].node_type == NodeTypes.VARIABLE_ASSIGNMENT
                and node.children[0].children
                and node.children[0].children[0].node_type == NodeTypes.IDENTIFIER
                and node.children[0].children[0].name == node.children[1].name
            ):
                assign = node.children[1]
                value = self._require_value(assign.children[0])
                if assign.children[0].node_type == NodeTypes.IDENTIFIER:
                    self._mark_owned_identifier_moved(assign.children[0].name)
                old = self._convert_expression(node.children[0].children[0])
                self.builder.drop(old)
                if self._lookup(assign.name) is None:
                    rhs_type = self._expr_type(assign.children[0])
                    is_array = rhs_type.endswith("[]")
                    base_type = rhs_type[:-2] if is_array else rhs_type
                    unique = self._declare(assign.name, base_type, is_array, None)
                    self.builder.declare_local(unique, self._fir_type(base_type, is_array), value)
                else:
                    self.builder.store_var(self._local_name(assign.name), value)
                return
            self._push_scope()
            self._convert_statements(node.children)
            self._pop_scope()
            return

        if node_type == NodeTypes.VARIABLE_DECLARATION:
            self._convert_variable_declaration(node)
            return

        if node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            self._convert_variable_assignment(node)
            return

        if node_type == NodeTypes.ASSIGNMENT:
            self._convert_assignment(node)
            return

        if node_type == NodeTypes.COMPOUND_ASSIGNMENT:
            self._convert_compound_assignment(node)
            return

        if node_type == NodeTypes.UNARY_EXPRESSION and node.name in ("++", "--"):
            self._convert_increment(node)
            return

        if node_type == NodeTypes.IF_STATEMENT:
            self._convert_if(node)
            return

        if node_type == NodeTypes.WHILE_STATEMENT:
            self._convert_while(node)
            return

        if node_type == NodeTypes.FOR_STATEMENT:
            self._convert_for(node)
            return

        if node_type == NodeTypes.FOR_IN_STATEMENT:
            self._convert_for_in(node)
            return

        if node_type == NodeTypes.BREAK_STATEMENT:
            if not self.loop_stack:
                raise FIRConversionError("break outside loop", node)
            self._drop_loop_cleanup(self.loop_stack[-1][1])
            return

        if node_type == NodeTypes.CONTINUE_STATEMENT:
            if not self.loop_stack:
                raise FIRConversionError("continue outside loop", node)
            self._drop_loop_cleanup(self.loop_stack[-1][0])
            return

        if node_type == NodeTypes.RETURN_STATEMENT:
            func = self.current_function
            # A plain function declared `-> T?` for a nullable-scalar T
            # actually returns __NullableReturn<T> (see
            # _resolve_function_return_type); `return expr;` must build
            # that struct from (expr's value, expr's has-value flag)
            # instead of returning expr's raw value directly.
            nullable_scalar_return_base = (
                func.metadata.get("nullable_scalar_return") if func is not None else None
            )
            is_nullable_scalar_return = nullable_scalar_return_base is not None
            if node.children:
                return_expr = node.children[0]
                has_value = (
                    self._nullable_scalar_has_value(return_expr) if is_nullable_scalar_return else None
                )
                prev_expected = self._expected_type_str
                # So a bare `return null;`'s NullLiteralInst resolves to
                # the function's actual scalar type instead of the
                # context-less "string" fallback (see _expr_type's
                # NULL_LITERAL handling); only set for a direct null
                # literal, not a compound return expression (see
                # _expected_type_if_null).
                self._expected_type_str = (
                    self._expected_type_if_null(return_expr, nullable_scalar_return_base)
                    if is_nullable_scalar_return
                    else None
                )
                value = self._convert_expression(return_expr)
                self._expected_type_str = prev_expected
                # preprocessor.py's RETURN_STATEMENT handler computes the
                # names read (not transferred) by this return expression --
                # e.g. a match/for-in scrutinee, an own-mode `this` read via
                # a field access, a borrowed call argument -- and defers
                # dropping them to here, since it can only insert drops
                # *before* the return statement (which would be a
                # use-after-drop for anything the expression still needs to
                # read). Now that `value` is fully built, it's safe.
                for post_drop_name in getattr(node, "post_return_drop_names", []):
                    symbol = self._lookup(post_drop_name)
                    if symbol is None:
                        continue
                    type_str, is_array, size, unique = symbol
                    drop_type = self._fir_type(type_str, is_array, size)
                    drop_ref = self.builder.load_var(unique, drop_type)
                    self.builder.drop(drop_ref)
                if func is not None and func.return_type is None:
                    # Void function (e.g. script-style top-level `return
                    # N;`): evaluate for side effects, but a void Return
                    # must carry no value (FIRV-T4). Matches existing
                    # lowering behavior, which already discarded the value
                    # here -- see ir_verifier_spec.md section 8.1.
                    self.builder.ret()
                elif is_nullable_scalar_return and has_value is not None and func is not None:
                    wrapped = self.builder.allocate(func.return_type, [value, has_value])
                    self.builder.ret(wrapped)
                else:
                    self.builder.ret(value)
            elif func is not None and func.return_type is not None and not func.is_generator:
                if (
                    is_nullable_scalar_return
                    and isinstance(func.return_type, GenericInstanceType)
                    and func.return_type.type_args
                ):
                    zero = self._synthesize_zero(func.return_type.type_args[0])
                    if zero is not None:
                        false_val = self.builder.bool_literal(False, make_simple("bool"))
                        self.builder.ret(self.builder.allocate(func.return_type, [zero, false_val]))
                    else:
                        self.builder.ret()
                else:
                    self.builder.ret(self._synthesize_zero(func.return_type))
            else:
                self.builder.ret()
            return

        if node_type == NodeTypes.YIELD_STATEMENT:
            value = self._convert_expression(node.children[0])
            self.builder.yield_value(value)
            return

        if node_type in (
            NodeTypes.FUNCTION_CALL,
            NodeTypes.METHOD_CALL,
            NodeTypes.TYPE_METHOD_CALL,
            NodeTypes.CONSTRUCTOR_CALL,
            NodeTypes.SUPER_CALL,
            NodeTypes.MATCH_EXPRESSION,
        ):
            self._convert_expression(node, as_statement=True)
            return

        raise FIRConversionError(f"Unsupported statement node {node_type}", node)

    def _convert_variable_declaration(self, node: ASTNode) -> None:
        type_str = node.var_type or "int32"
        declared_size = getattr(node, "array_size", None)
        init_node = node.children[0] if node.children else None

        if node.is_array:
            size = declared_size
            if init_node is not None and init_node.node_type == NodeTypes.ARRAY_LITERAL:
                element_count = len(init_node.children or [])
                if element_count > 0:
                    size = element_count
                elif size is None:
                    # `int32[] x = [];` declares a zero-length array.
                    size = 0
            var_type = self._fir_type(type_str, True, size)
            if init_node is not None and init_node.node_type == NodeTypes.ARRAY_LITERAL:
                # Build the literal with the declared size so empty literals
                # like `int16[1000] x = [];` allocate the full array.
                elements = [self._require_value(c) for c in (init_node.children or [])]
                init_value = self.builder.array_literal(elements, var_type)
            elif init_node is not None:
                init_value = self._convert_expression(init_node)
            else:
                # Sized array with no initializer: zero-initialized array literal.
                init_value = self.builder.array_literal([], var_type)
            unique = self._declare(node.name, type_str, True, size)
            self.builder.declare_local(unique, var_type, init_value)
            return

        var_type = self._fir_type(type_str, nullable=node.is_nullable)
        is_nullable_scalar = node.is_nullable and self._nullable_scalar_base(f"{type_str}?") is not None
        has_value = self._nullable_scalar_has_value(init_node) if is_nullable_scalar else None
        # Also read by _convert_construction (generic type-arg inference
        # for a constructor-call initializer, e.g. `Pair<int32, string> p
        # = Pair(1, "x");`) -- kept unconditional (not restricted to a
        # direct null-literal init_node like _expected_type_if_null) for
        # that reason. A *nested* null literal several levels down inside
        # a compound init_node (e.g. `x: bool = a == null;`, if the
        # nullable-scalar EQUALITY_EXPRESSION rewrite doesn't apply to
        # `a`'s type) is protected separately, by clearing this before the
        # general binary/equality/relational fallback recurses into its
        # operands -- see that branch in _convert_expression.
        self._expected_type_str = type_str
        init_value = self._convert_expression(init_node) if init_node is not None else None
        self._expected_type_str = None
        # Store nullable-ness in the scope table via the "?" suffix (see
        # _fir_type) so LoadVar/StoreVar sites re-deriving this local's
        # type from its name alone still get it right.
        stored_type_str = f"{type_str}?" if node.is_nullable else type_str
        unique = self._declare(node.name, stored_type_str, False, None)
        self.builder.declare_local(unique, var_type, init_value)
        if is_nullable_scalar and has_value is not None:
            self._declare_hasval_companion(node.name, has_value)

    def _convert_variable_assignment(self, node: ASTNode) -> None:
        rhs = node.children[0] if node.children else None
        existing = self._lookup(node.name)
        is_nullable_scalar = existing is not None and self._nullable_scalar_base(existing[0]) is not None
        has_value = self._nullable_scalar_has_value(rhs) if is_nullable_scalar else None
        value = self._convert_expression(rhs) if rhs is not None else None
        if value is None:
            raise FIRConversionError("Assignment without value", node)
        if rhs is not None and rhs.node_type == NodeTypes.IDENTIFIER:
            self._mark_owned_identifier_moved(rhs.name)
        if existing is None:
            # Implicit declaration (class-typed RHS assignments allow this).
            rhs_type = self._expr_type(node.children[0])
            is_array = rhs_type.endswith("[]")
            base_type = rhs_type[:-2] if is_array else rhs_type
            unique = self._declare(node.name, base_type, is_array, None)
            self.builder.declare_local(unique, self._fir_type(base_type, is_array), value)
            return
        self.builder.store_var(self._local_name(node.name), value)
        if is_nullable_scalar and has_value is not None:
            self._store_hasval_companion(node.name, has_value)

    def _convert_assignment(self, node: ASTNode) -> None:
        lhs = node.children[0]
        rhs = node.children[1]
        lhs_symbol = self._lookup(lhs.name) if lhs.node_type == NodeTypes.IDENTIFIER else None
        is_nullable_scalar = lhs_symbol is not None and self._nullable_scalar_base(lhs_symbol[0]) is not None
        is_nullable_scalar_field = False
        if not is_nullable_scalar and lhs.node_type == NodeTypes.FIELD_ACCESS:
            field_base = self._expr_type(lhs.children[0]).split("<")[0]
            if lhs.name in self.nullable_scalar_fields.get(field_base, set()):
                is_nullable_scalar_field = True
        has_value = (
            self._nullable_scalar_has_value(rhs) if is_nullable_scalar or is_nullable_scalar_field else None
        )
        value = self._convert_expression(rhs)
        if rhs.node_type == NodeTypes.IDENTIFIER:
            self._mark_owned_identifier_moved(rhs.name)

        if lhs.node_type == NodeTypes.IDENTIFIER:
            self.builder.store_var(self._local_name(lhs.name), value)
            if is_nullable_scalar and has_value is not None:
                self._store_hasval_companion(lhs.name, has_value)
            return
        if lhs.node_type == NodeTypes.FIELD_ACCESS:
            obj = self._convert_expression(lhs.children[0])
            self.builder.store_field(obj, lhs.name, value)
            if is_nullable_scalar_field and has_value is not None:
                self.builder.store_field(obj, self._hasval_name(lhs.name), has_value)
            return
        if lhs.node_type == NodeTypes.ARRAY_ACCESS:
            array = self._convert_expression(lhs.children[0])
            index = self._convert_expression(lhs.children[1])
            self.builder.store_array(array, index, value)
            return
        raise FIRConversionError(f"Unsupported assignment target {lhs.node_type}", lhs)

    def _convert_compound_assignment(self, node: ASTNode) -> None:
        op_token = getattr(node.token, "type", None)
        op = COMPOUND_OP_MAP.get(op_token or "", "+")
        symbol = self._lookup(node.name)
        type_str = symbol[0] if symbol else "int32"
        local = self._local_name(node.name)
        var_type = self._fir_type(type_str)
        current = self.builder.load_var(local, var_type)
        rhs = self._convert_expression(node.children[0])
        result = self.builder.binary_op(op, current, rhs, var_type)
        self.builder.store_var(local, result)

    def _convert_increment(self, node: ASTNode) -> None:
        var_name = node.token.value if node.token else ""
        symbol = self._lookup(var_name)
        type_str = symbol[0] if symbol else "int32"
        local = self._local_name(var_name)
        var_type = self._fir_type(type_str)
        current = self.builder.load_var(local, var_type)
        one = self.builder.int_literal("1", var_type)
        op = "+" if node.name == "++" else "-"
        result = self.builder.binary_op(op, current, one, var_type)
        self.builder.store_var(local, result)

    def _convert_if(self, node: ASTNode) -> None:
        join_block = self.builder.new_block()
        self._convert_if_chain(node, join_block.id)
        self.builder.position_at(join_block)

    def _convert_if_chain(self, node: ASTNode, join_id: str) -> None:
        """Convert IF/ELIF/ELSE chains; leaves builder on an arbitrary block."""
        cond = self._convert_expression(node.children[0])
        then_block = self.builder.new_block()
        else_node = node.children[2] if len(node.children) > 2 and node.children[2] else None

        if else_node is not None:
            else_block = self.builder.new_block()
            self.builder.branch(cond, then_block.id, else_block.id)
        else:
            self.builder.branch(cond, then_block.id, join_id)

        self.builder.position_at(then_block)
        self._push_scope()
        then_body = node.children[1]
        if then_body.node_type == NodeTypes.SCOPE:
            self._convert_statements(then_body.children)
        else:
            self._convert_statement(then_body)
        self._pop_scope()
        if not self.builder.current_block.is_terminated():
            self.builder.jump(join_id)

        if else_node is not None:
            self.builder.position_at(else_block)
            if else_node.node_type == NodeTypes.ELIF_STATEMENT:
                self._convert_if_chain(else_node, join_id)
            elif else_node.node_type == NodeTypes.ELSE_STATEMENT:
                self._push_scope()
                else_body = else_node.children[0]
                if else_body.node_type == NodeTypes.SCOPE:
                    self._convert_statements(else_body.children)
                else:
                    self._convert_statement(else_body)
                self._pop_scope()
                if not self.builder.current_block.is_terminated():
                    self.builder.jump(join_id)
            else:
                # Plain else branch stored directly as a scope
                self._push_scope()
                if else_node.node_type == NodeTypes.SCOPE:
                    self._convert_statements(else_node.children)
                else:
                    self._convert_statement(else_node)
                self._pop_scope()
                if not self.builder.current_block.is_terminated():
                    self.builder.jump(join_id)

    def _convert_while(self, node: ASTNode) -> None:
        header = self.builder.new_block()
        body_block = self.builder.new_block()
        exit_block = self.builder.new_block()

        self.builder.jump(header.id)
        self.builder.position_at(header)
        cond = self._convert_expression(node.children[0])
        self.builder.branch(cond, body_block.id, exit_block.id)

        self.builder.position_at(body_block)
        self.loop_stack.append((header.id, exit_block.id, None))
        self._push_scope()
        body = node.children[1]
        if body.node_type == NodeTypes.SCOPE:
            self._convert_statements(body.children)
        else:
            self._convert_statement(body)
        self._pop_scope()
        self.loop_stack.pop()
        if not self.builder.current_block.is_terminated():
            self.builder.jump(header.id)

        self.builder.position_at(exit_block)

    def _convert_for(self, node: ASTNode) -> None:
        init_node, cond_node, incr_node, body_node = node.children[:4]

        self._push_scope()
        if init_node.name != "empty":
            self._convert_statement(init_node)

        header = self.builder.new_block()
        body_block = self.builder.new_block()
        incr_block = self.builder.new_block()
        exit_block = self.builder.new_block()

        self.builder.jump(header.id)
        self.builder.position_at(header)
        if cond_node.name != "empty":
            cond = self._convert_expression(cond_node)
            self.builder.branch(cond, body_block.id, exit_block.id)
        else:
            self.builder.jump(body_block.id)

        self.builder.position_at(body_block)
        self.loop_stack.append((incr_block.id, exit_block.id, None))
        self._push_scope()
        if body_node.node_type == NodeTypes.SCOPE:
            self._convert_statements(body_node.children)
        else:
            self._convert_statement(body_node)
        self._pop_scope()
        self.loop_stack.pop()
        if not self.builder.current_block.is_terminated():
            self.builder.jump(incr_block.id)

        self.builder.position_at(incr_block)
        if incr_node.name != "empty":
            self._convert_statement(incr_node)
        self.builder.jump(header.id)

        self.builder.position_at(exit_block)
        self._pop_scope()

    def _convert_for_in(self, node: ASTNode) -> None:
        var_decl, collection, body = node.children[:3]
        loop_var = var_decl.name
        loop_var_type_str = var_decl.var_type or "int32"

        collection_type = self._expr_type(collection)

        if (
            collection.node_type == NodeTypes.FUNCTION_CALL
            and collection.name in self.generator_defs
        ):
            self._convert_for_in_generator(node, loop_var, loop_var_type_str, collection, body)
            return
        if collection_type == "string":
            self._convert_for_in_string(node, loop_var, loop_var_type_str, collection, body)
            return
        self._convert_for_in_array(node, loop_var, loop_var_type_str, collection, body)

    def _convert_for_in_generator(
        self,
        node: ASTNode,
        loop_var: str,
        loop_var_type_str: str,
        collection: ASTNode,
        body: ASTNode,
    ) -> None:
        gen_def = self.generator_defs[collection.name]
        yield_type_str = getattr(gen_def, "yield_type", gen_def.return_type or "int32")
        elem_type = self._fir_type(yield_type_str)
        gen_type = GeneratorType(elem_type)
        bool_type = make_simple("bool")

        args = [self._convert_expression(arg) for arg in (collection.children or [])]
        gen_value = self.builder.gen_new(collection.name, args, gen_type)
        type_params = list(getattr(gen_def, "type_params", []) or [])
        if type_params and gen_value is not None:
            type_args = self._infer_generator_type_args(gen_def, type_params, collection)
            if type_args:
                gen_value.instruction.metadata["type_args"] = type_args
        gen_local = self._declare(f"__gen_{loop_var}", f"generator<{yield_type_str}>", False, None)
        self.builder.declare_local(gen_local, gen_type, gen_value)

        header = self.builder.new_block()
        body_block = self.builder.new_block()
        exit_block = self.builder.new_block()

        self.builder.jump(header.id)
        self.builder.position_at(header)
        gen_current = self.builder.load_var(gen_local, gen_type)
        has_next = self.builder.gen_next(gen_current, bool_type)
        self.builder.branch(has_next, body_block.id, exit_block.id)

        self.builder.position_at(body_block)
        self._push_scope()
        gen_in_body = self.builder.load_var(gen_local, gen_type)
        element = self.builder.gen_value(gen_in_body, elem_type)
        loop_local = self._declare(loop_var, loop_var_type_str, False, None)
        self.builder.declare_local(loop_local, self._fir_type(loop_var_type_str), element)

        self.loop_stack.append((header.id, exit_block.id, None))
        if body.node_type == NodeTypes.SCOPE:
            self._convert_statements(body.children)
        else:
            self._convert_statement(body)
        self.loop_stack.pop()
        self._pop_scope()
        if not self.builder.current_block.is_terminated():
            # `loop_local` is declared directly here (line ~1454), bypassing
            # the preprocessor's usual owned-local auto-drop insertion --
            # preprocessor.py's FOR_IN_STATEMENT handling explicitly skips
            # the loop variable itself, trusting codegen to manage it (see
            # its comment there). Every existing for-in-over-generator test
            # only yields a Copyable type (int32), so dropping a fresh value
            # each iteration was never needed until a generator yielding an
            # Owned type (e.g. Vec<T>'s `enumerate` yielding Tuple<int32,T>)
            # exposed it as a real gap (FIRV-O3: unconsumed on the loop-back
            # path). Only the normal fallthrough path is handled -- break/
            # continue out of a for-in-over-generator loop with an Owned
            # yield type remains an unhandled case, same as it was before
            # this fix (no existing test exercises it).
            loop_local_fir_type = self._fir_type(loop_var_type_str)
            if loop_local_fir_type.is_owned():
                loop_final = self.builder.load_var(loop_local, loop_local_fir_type)
                self.builder.drop(loop_final)
            self.builder.jump(header.id)

        self.builder.position_at(exit_block)
        # __gen_<var> is always a fresh generator object (the collection
        # expression driving this loop is always a generator-function call,
        # never a bare identifier -- see _convert_for_in's dispatch above),
        # so this loop is its sole owner; preprocessor.py never sees this
        # FIR-synthesized binding, so nothing else drops it (FIRV-O3).
        gen_final = self.builder.load_var(gen_local, gen_type)
        self.builder.drop(gen_final)

    def _mark_owned_identifier_moved(self, name: str) -> None:
        """If `name` (a bare identifier just used as a move source/target --
        a plain assignment RHS, an explicit drop(), or an own-mode call
        argument) is the loop variable of a currently-active for-in-string
        loop, record the move in self._loop_move_observations so
        _convert_for_in_string_body notices its per-iteration cleanup has
        already been handled here and doesn't also drop it at the end of
        the iteration (FIRV-O2) or, on a sibling path that never moved it,
        skip a drop it still needs (FIRV-O3)."""
        for _incr_id, _exit_id, cleanup in self.loop_stack:
            if cleanup is not None and cleanup[2] == name:
                self._loop_move_observations.add(name)
                return

    def _convert_for_in_string_body(
        self,
        stmts: list[ASTNode],
        idx: int,
        var_name: str,
        loop_local: str,
        loop_local_type: FIRType,
        incr_block_id: str,
        consumed: bool = False,
    ) -> None:
        """Convert stmts[idx:] (a for-in-string loop body, or a duplicated
        continuation spliced into one arm of a nested if -- see
        _convert_for_in_string_if), inserting the per-iteration
        `drop(loop_local)` cleanup at every reachable fall-through exit that
        hasn't already consumed the loop variable on that specific static
        path, and tracking that consumption so a break/continue reached
        along the way skips a redundant drop too (see the loop_stack[-1]
        juggling below).

        A single, unconditional drop after the whole body (the previous
        behavior) is wrong whenever the body conditionally moves the loop
        variable elsewhere -- e.g. an accumulator pattern like
        `if (c == last) { count++; } else { last = c; }`: the branch that
        moved it would get double-dropped once the other branch's need for
        a drop was noticed (FIRV-O2), and omitting the drop altogether to
        avoid that would leak it on the branch that never touched it
        (FIRV-O3). A *runtime* flag doesn't work either: the ownership
        verifier recomputes ownership purely from static instructions, so a
        drop gated behind a runtime bool still looks unconditionally
        reachable to it. The only representation the verifier accepts is a
        statically fixed decision on every path -- which means when an
        if/elif/else appears anywhere in the body (not just at the very
        end), both arms need their own, independently-decided copy of
        whatever statements follow it; see _convert_for_in_string_if."""
        n = len(stmts)
        while idx < n:
            if self.builder.current_block.is_terminated():
                return
            stmt = stmts[idx]
            if stmt.node_type == NodeTypes.IF_STATEMENT:
                self._convert_for_in_string_if(
                    stmt, stmts, idx + 1, var_name, loop_local, loop_local_type, incr_block_id, consumed
                )
                return
            # Make break/continue reached *by this exact statement* (not
            # one nested inside further control flow, which manages its own
            # loop_stack entry) see the current consumption state: whatever
            # is live at self.loop_stack[-1] here is this for-in-string
            # loop's own entry (nested loops push/pop their own around
            # their body, restoring this one before returning control here).
            incr_id, exit_id, real_cleanup = self.loop_stack[-1]
            self.loop_stack[-1] = (incr_id, exit_id, None if consumed else real_cleanup)
            self._loop_move_observations.discard(var_name)
            self._convert_statement(stmt)
            if var_name in self._loop_move_observations:
                consumed = True
            self.loop_stack[-1] = (incr_id, exit_id, real_cleanup)
            idx += 1
        if not self.builder.current_block.is_terminated():
            if not consumed:
                ref = self.builder.load_var(loop_local, loop_local_type)
                self.builder.drop(ref)
            self.builder.jump(incr_block_id)

    def _convert_for_in_string_if(
        self,
        node: ASTNode,
        rest_stmts: list[ASTNode],
        rest_idx: int,
        var_name: str,
        loop_local: str,
        loop_local_type: FIRType,
        incr_block_id: str,
        consumed: bool,
    ) -> None:
        """Handle an if/else (or elif chain, via recursion into the else
        branch) inside a for-in-string loop body, converting each arm with
        its own copy of whatever statements follow the if in the enclosing
        statement list. The two arms can leave the loop variable in
        different ownership states (moved on one, untouched on the other),
        and only one static copy of the continuation can be spliced onto a
        given state -- see _convert_for_in_string_body for why that state
        has to be a compile-time decision. Bodies here are small (loop
        iterations), so duplicating the tail is cheap; deeply nested
        chains of such ifs would duplicate more, but that shape doesn't
        arise in practice for a single loop's per-element logic."""
        condition = self._convert_expression(node.children[0])
        then_branch = node.children[1]
        else_branch = node.children[2] if len(node.children) > 2 else None

        then_block = self.builder.new_block()
        else_block = self.builder.new_block()
        self.builder.branch(condition, then_block.id, else_block.id)

        remainder = rest_stmts[rest_idx:]

        self.builder.position_at(then_block)
        self._push_scope()
        then_stmts = list(then_branch.children if then_branch.node_type == NodeTypes.SCOPE else [then_branch])
        self._convert_for_in_string_body(
            then_stmts + remainder, 0, var_name, loop_local, loop_local_type, incr_block_id, consumed
        )
        self._pop_scope()

        self.builder.position_at(else_block)
        self._push_scope()
        if else_branch is not None:
            else_stmts = list(else_branch.children if else_branch.node_type == NodeTypes.SCOPE else [else_branch])
        else:
            else_stmts = []
        self._convert_for_in_string_body(
            else_stmts + remainder, 0, var_name, loop_local, loop_local_type, incr_block_id, consumed
        )
        self._pop_scope()

    def _convert_for_in_string(
        self,
        node: ASTNode,
        loop_var: str,
        loop_var_type_str: str,
        collection: ASTNode,
        body: ASTNode,
    ) -> None:
        int32 = make_simple("int32")
        string_type = make_simple("string")
        bool_type = make_simple("bool")

        if collection.node_type == NodeTypes.IDENTIFIER:
            # Borrow the existing binding directly, same as
            # _convert_for_in_array/_convert_match: `for (c in s) {...}` is
            # borrow-style when `s` is a bare identifier -- the original
            # binding remains the owner, dropped once by the preprocessor's
            # normal scope-exit tracking. Declaring+consuming a second
            # owned local for it here would double-free once the original
            # binding is also dropped (FIRV-O2).
            source_local = self._local_name(collection.name)
        else:
            source = self._convert_expression(collection)
            source_local = self._declare(f"__str_{loop_var}", "string", False, None)
            self.builder.declare_local(source_local, string_type, source)
        index_local = self._declare(f"__i_{loop_var}", "int32", False, None)
        zero = self.builder.int_literal("0", int32)
        self.builder.declare_local(index_local, int32, zero)

        header = self.builder.new_block()
        body_block = self.builder.new_block()
        exit_block = self.builder.new_block()

        self.builder.jump(header.id)
        self.builder.position_at(header)
        index_value = self.builder.load_var(index_local, int32)
        source_value = self.builder.load_var(source_local, string_type)
        length = self.builder.call("str_length", [source_value], ["borrow"], int32)
        length.instruction.metadata["intrinsic"] = True
        cond = self.builder.binary_op("<", index_value, length, bool_type)
        self.builder.branch(cond, body_block.id, exit_block.id)

        self.builder.position_at(body_block)
        self._push_scope()
        index_in_body = self.builder.load_var(index_local, int32)
        source_in_body = self.builder.load_var(source_local, string_type)
        if loop_var_type_str == "string":
            element = self.builder.call(
                "str_char_at", [source_in_body, index_in_body], ["borrow", "own"], string_type
            )
        else:
            element = self.builder.call(
                "str_char_code_at", [source_in_body, index_in_body], ["borrow", "own"], make_simple("char")
            )
        element.instruction.metadata["intrinsic"] = True
        loop_local = self._declare(loop_var, loop_var_type_str, False, None)
        loop_local_type = self._fir_type(loop_var_type_str)
        self.builder.declare_local(loop_local, loop_local_type, element)

        # The increment happens in a dedicated block so `continue` advances.
        incr_block = self.builder.new_block()
        loop_cleanup = (loop_local, loop_local_type, loop_var) if loop_local_type.is_owned() else None
        self.loop_stack.append((incr_block.id, exit_block.id, loop_cleanup))
        if loop_cleanup is not None:
            # loop_local (each iteration's single-character string) is a
            # fresh str_char_at result -- preprocessor.py never sees this
            # FIR-synthesized binding, so nothing else drops it (FIRV-O3).
            # _convert_for_in_string_body inserts that drop at every
            # reachable fall-through exit that hasn't already consumed
            # loop_local itself (e.g. by moving it into an outer variable
            # on just one arm of an if/elif/else in the body, however
            # deeply nested or followed by more code -- see that method's
            # docstring for why a single drop after the whole body can't
            # handle that case). break/continue take care of this same
            # drop on their own exit paths via _drop_loop_cleanup.
            body_stmts = list(body.children) if body.node_type == NodeTypes.SCOPE else [body]
            self._convert_for_in_string_body(body_stmts, 0, loop_var, loop_local, loop_local_type, incr_block.id)
        else:
            if body.node_type == NodeTypes.SCOPE:
                self._convert_statements(body.children)
            else:
                self._convert_statement(body)
            if not self.builder.current_block.is_terminated():
                self.builder.jump(incr_block.id)
        self.loop_stack.pop()
        self._pop_scope()

        self.builder.position_at(incr_block)
        index_for_incr = self.builder.load_var(index_local, int32)
        one = self.builder.int_literal("1", int32)
        next_index = self.builder.binary_op("+", index_for_incr, one, int32)
        self.builder.store_var(index_local, next_index)
        self.builder.jump(header.id)

        self.builder.position_at(exit_block)
        if collection.node_type != NodeTypes.IDENTIFIER:
            # __str_<var> is the sole owner of the string only when it was
            # copied from a fresh temporary (see the borrow-style exemption
            # above); freeing it here mirrors _convert_for_in_array's
            # matching container-level drop.
            src_final = self.builder.load_var(source_local, string_type)
            self.builder.drop(src_final)

    def _convert_for_in_array(
        self,
        node: ASTNode,
        loop_var: str,
        loop_var_type_str: str,
        collection: ASTNode,
        body: ASTNode,
    ) -> None:
        int32 = make_simple("int32")
        bool_type = make_simple("bool")

        collection_type_str = self._expr_type(collection)
        element_type_str = (
            collection_type_str[:-2] if collection_type_str.endswith("[]") else loop_var_type_str
        )
        size = self._array_size_of(collection)
        array_type = self._fir_type(element_type_str, True, size)

        if collection.node_type == NodeTypes.IDENTIFIER:
            # Borrow the existing binding directly: don't declare+consume
            # a second owned local for it. `for (x in numbers) {...}` is
            # borrow-style iteration -- "numbers" remains valid (and is
            # dropped exactly once, by the preprocessor's normal
            # scope-exit tracking) after the loop. Taking ownership here
            # too, as if the array were a fresh temporary, would
            # eventually free the same backing buffer twice (FIRV-O2).
            source_local = self._local_name(collection.name)
        else:
            source = self._convert_expression(collection)
            source_local = self._declare(f"__arr_{loop_var}", element_type_str, True, size)
            self.builder.declare_local(source_local, array_type, source)
        index_local = self._declare(f"__i_{loop_var}", "int32", False, None)
        zero = self.builder.int_literal("0", int32)
        self.builder.declare_local(index_local, int32, zero)

        header = self.builder.new_block()
        body_block = self.builder.new_block()
        exit_block = self.builder.new_block()

        self.builder.jump(header.id)
        self.builder.position_at(header)
        index_value = self.builder.load_var(index_local, int32)
        if size is not None:
            length: Value = self.builder.int_literal(str(size), int32)
        else:
            array_value = self.builder.load_var(source_local, array_type)
            length = self.builder.call("array_length", [array_value], ["borrow"], int32)
            length.instruction.metadata["intrinsic"] = True
        cond = self.builder.binary_op("<", index_value, length, bool_type)
        self.builder.branch(cond, body_block.id, exit_block.id)

        self.builder.position_at(body_block)
        self._push_scope()
        array_in_body = self.builder.load_var(source_local, array_type)
        index_in_body = self.builder.load_var(index_local, int32)
        element = self.builder.index_array(array_in_body, index_in_body, self._fir_type(element_type_str))
        loop_local = self._declare(loop_var, loop_var_type_str, False, None)
        self.builder.declare_local(loop_local, self._fir_type(loop_var_type_str), element)

        incr_block = self.builder.new_block()
        self.loop_stack.append((incr_block.id, exit_block.id, None))
        if body.node_type == NodeTypes.SCOPE:
            self._convert_statements(body.children)
        else:
            self._convert_statement(body)
        self.loop_stack.pop()
        self._pop_scope()
        if not self.builder.current_block.is_terminated():
            self.builder.jump(incr_block.id)

        self.builder.position_at(incr_block)
        index_for_incr = self.builder.load_var(index_local, int32)
        one = self.builder.int_literal("1", int32)
        next_index = self.builder.binary_op("+", index_for_incr, one, int32)
        self.builder.store_var(index_local, next_index)
        self.builder.jump(header.id)

        self.builder.position_at(exit_block)
        if array_type.is_owned() and collection.node_type != NodeTypes.IDENTIFIER:
            # __arr_<var> is the sole owner of the iterated array *only*
            # when `for (x in <expr>)` iterates a fresh temporary (an
            # array literal, a function-call result, ...) with no other
            # owner. When <expr> is a bare identifier naming an existing
            # local/param, that binding remains the owner -- it is (and
            # was already, independent of this fix) dropped by the
            # preprocessor's normal scope-exit tracking; `source` here is
            # just a second reference to the same pointer, and freeing it
            # too would double-free once the original binding is also
            # dropped (FIRV-O2). Freeing __arr_<var> in the temporary case
            # is shallow -- matches flir/lowering.py::lower_drop's
            # existing behavior for array types (backing buffer only) --
            # independent of any separate gap in per-element ownership.
            arr_final = self.builder.load_var(source_local, array_type)
            self.builder.drop(arr_final)

    def _array_size_of(self, node: ASTNode) -> Optional[int]:
        if node.node_type == NodeTypes.ARRAY_LITERAL:
            return len(node.children or [])
        if node.node_type == NodeTypes.IDENTIFIER:
            symbol = self._lookup(node.name)
            if symbol is not None:
                return symbol[2]
        return None

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def _require_value(self, node: ASTNode) -> Value:
        value = self._convert_expression(node)
        if value is None:
            raise FIRConversionError(
                f"Expression {node.node_type} ({node.name}) produces no value but one is required",
                node,
            )
        return value

    def _convert_expression(self, node: ASTNode, as_statement: bool = False) -> Optional[Value]:
        node_type = node.node_type

        if node_type == NodeTypes.LITERAL:
            return self._convert_literal(node)

        if node_type == NodeTypes.IDENTIFIER:
            type_str = self._expr_type(node)
            is_array = type_str.endswith("[]")
            base = type_str[:-2] if is_array else type_str
            symbol = self._lookup(node.name)
            size = symbol[2] if symbol else None
            return self.builder.load_var(self._local_name(node.name), self._fir_type(base, is_array, size))

        if node_type == NodeTypes.ARRAY_LITERAL:
            elements = [self._convert_expression(child) for child in (node.children or [])]
            elem_type_str = self._expr_type(node.children[0]) if node.children else "int32"
            array_type = self._fir_type(elem_type_str, True, len(elements))
            return self.builder.array_literal(elements, array_type)

        if node_type == NodeTypes.ARRAY_ACCESS:
            array = self._convert_expression(node.children[0])
            index = self._convert_expression(node.children[1])
            elem_type = self._fir_type(self._expr_type(node))
            return self.builder.index_array(array, index, elem_type)

        if node_type == NodeTypes.FIELD_ACCESS:
            obj = self._convert_expression(node.children[0])
            field_type = self._fir_type(self._expr_type(node))
            return self.builder.load_field(obj, node.name, field_type)

        if node_type == NodeTypes.CAST_EXPRESSION:
            value = self._convert_expression(node.children[0])
            target = self._fir_type(node.name or node.var_type)
            cast = self.builder.cast(value, target)
            cast.instruction.metadata["source_type"] = self._strip_nullable_str(self._expr_type(node.children[0]))
            return cast

        if node_type == NodeTypes.BINARY_EXPRESSION and node.name in ("&&", "||"):
            return self._convert_short_circuit(node)

        if node_type == NodeTypes.EQUALITY_EXPRESSION:
            null_side, other_side = None, None
            if self._is_null_literal(node.children[0]):
                null_side, other_side = node.children[0], node.children[1]
            elif self._is_null_literal(node.children[1]):
                null_side, other_side = node.children[1], node.children[0]
            if null_side is not None and self._nullable_scalar_base(self._expr_type(other_side)) is not None:
                # `x == null` / `x != null` where x is a nullable *scalar*
                # (int32?, bool?, ...): the value itself has no bit pattern
                # reserved for "no value" (unlike string?/a class?/an
                # array?, where null is unambiguously the pointer value
                # zero), so this compares the companion has-value flag
                # instead of the value -- see _nullable_scalar_has_value.
                has_value = self._nullable_scalar_has_value(other_side)
                bool_type = make_simple("bool")
                if node.name == "==":
                    return self.builder.unary_op("!", has_value, bool_type)
                return has_value

        if node_type in (
            NodeTypes.BINARY_EXPRESSION,
            NodeTypes.EQUALITY_EXPRESSION,
            NodeTypes.RELATIONAL_EXPRESSION,
        ):
            # Each operand's own null-literal resolution (if it is one)
            # must come from its *sibling* operand's type, never from
            # whatever self._expected_type_str an outer caller left set
            # (e.g. a println(...) argument slot, or an enclosing
            # variable's declared type) -- that context describes the
            # whole comparison/binary expression, not either operand
            # individually, and leaking it in resolves an unrelated
            # nested null literal (e.g. `println(x == null)`) to
            # completely the wrong type.
            prev_expected = self._expected_type_str
            self._expected_type_str = (
                self._strip_nullable_str(self._expr_type(node.children[1]))
                if self._is_null_literal(node.children[0])
                else None
            )
            left = self._convert_expression(node.children[0])
            self._expected_type_str = (
                self._strip_nullable_str(self._expr_type(node.children[0]))
                if self._is_null_literal(node.children[1])
                else None
            )
            right = self._convert_expression(node.children[1])
            self._expected_type_str = prev_expected
            result_type = self._fir_type(self._expr_type(node))
            op_inst = self.builder.binary_op(node.name, left, right, result_type)
            op_inst.instruction.metadata["operand_type"] = self._strip_nullable_str(self._expr_type(node.children[0]))
            return op_inst

        if node_type == NodeTypes.UNARY_EXPRESSION:
            if node.name in ("++", "--"):
                # Used as an expression-statement only.
                self._convert_increment(node)
                return None
            operand = self._convert_expression(node.children[0])
            result_type = self._fir_type(self._expr_type(node))
            return self.builder.unary_op(node.name, operand, result_type)

        if node_type == NodeTypes.FUNCTION_CALL:
            return self._convert_function_call_unwrapped(node, as_statement)

        if node_type == NodeTypes.METHOD_CALL:
            return self._convert_method_call(node)

        if node_type == NodeTypes.TYPE_METHOD_CALL:
            class_name = getattr(node, "class_name", "")
            # class_name is "Box" (Box.make(5)) or "Box<int32>"
            # (Box<int32>.make(5)) -- the FIR function is always compiled
            # once under the bare template name (_convert_method_body
            # names it f"{class_name}.{method}" using the class's own
            # declared name, never a composite instantiation), so the call
            # target must use base_name; type_args (explicit from
            # class_name if present, else inferred from argument types)
            # separately tell FLIR lowering's monomorphization dispatch
            # which concrete instantiation to compile/call.
            base_name = class_name.split("<", 1)[0] if "<" in class_name else class_name
            method_def = self._find_method_def(base_name, node.name)
            type_args: list[str] = []
            if method_def is not None and self.class_generic_params.get(base_name):
                if "<" in class_name:
                    type_args = self._split_type_args(class_name.split("<", 1)[1][:-1])
                else:
                    type_args = self._infer_class_method_type_args(base_name, method_def, node)
            args = [self._convert_expression(arg) for arg in node.children]
            return_type_str = self._expr_type(node)
            call = self.builder.call(
                f"{base_name}.{node.name}",
                args,
                ["own"] * len(args),
                self._fir_type(return_type_str) if return_type_str != "void" else None,
            )
            if call is not None and type_args:
                call.instruction.metadata["type_args"] = type_args
            return call

        if node_type == NodeTypes.CONSTRUCTOR_CALL:
            full_name = node.name
            base_name = full_name.split("<")[0] if "<" in full_name else full_name
            return self._convert_construction(node, full_name, base_name)

        if node_type == NodeTypes.SUPER_CALL:
            return self._convert_super_call(node)

        if node_type == NodeTypes.ENUM_VARIANT_CONSTRUCT:
            return self._convert_enum_variant_construct(node)

        if node_type == NodeTypes.MATCH_EXPRESSION:
            return self._convert_match(node, as_statement)

        raise FIRConversionError(f"Unsupported expression node {node_type}", node)

    def _convert_enum_variant_construct(self, node: ASTNode) -> Value:
        """Construct an enum value: EnumName.Variant or EnumName.Variant(args...)."""
        enum_name = getattr(node, "class_name", "")
        variants = self.enum_variants.get(enum_name, [])
        variant_payloads = dict(variants)
        if node.name not in variant_payloads:
            raise FIRConversionError(
                f"Unknown variant '{node.name}' in enum '{enum_name}'", node
            )
        payload_fields = variant_payloads[node.name]
        if len(node.children) != len(payload_fields):
            raise FIRConversionError(
                f"Variant '{enum_name}.{node.name}' expects {len(payload_fields)} argument(s), "
                f"got {len(node.children)}",
                node,
            )
        args = [self._convert_expression(child) for child in node.children]
        enum_type = self._fir_type(enum_name)
        return self.builder.construct_variant(enum_type, node.name, args)

    def _convert_match(self, node: ASTNode, as_statement: bool) -> Optional[Value]:
        """Lower `match` to a chain of tag-compare branches.

        Statement form (as_statement=True) discards each arm's value.
        Expression form requires every arm body to be a plain expression
        (no `{ }` block) and stores each arm's value into a shared temp
        local, loaded once execution reaches the join block.

        Exhaustiveness, duplicate-variant, wildcard-order, and binding
        validity are already enforced by semantic analysis; this pass
        trusts that and focuses purely on control flow.
        """
        scrutinee_node = node.children[0]
        arms = node.children[1:]

        wildcard_arm = next((a for a in arms if getattr(a, "is_wildcard", False)), None)
        non_wildcard_arms = [a for a in arms if not getattr(a, "is_wildcard", False)]
        enum_name = getattr(non_wildcard_arms[0], "enum_name", None) if non_wildcard_arms else None
        variant_fields = dict(self.enum_variants.get(enum_name, [])) if enum_name else {}
        variant_order = [v for v, _ in self.enum_variants.get(enum_name, [])] if enum_name else []

        if not as_statement:
            for arm in arms:
                body = arm.children[0] if arm.children else None
                if body is not None and body.node_type == NodeTypes.SCOPE:
                    raise FIRConversionError(
                        "match used as an expression requires every arm body to be a plain "
                        "expression (no '{ }' block)",
                        arm,
                    )

        # A name keyed on block/instruction counts at generation time is
        # not guaranteed unique across different match expressions in the
        # same function (FIRV-L3); a dedicated monotonic counter is.
        self._match_counter += 1
        marker = str(self._match_counter)
        if scrutinee_node.node_type == NodeTypes.IDENTIFIER:
            # Borrow the existing binding directly, same as
            # _convert_for_in_array: `match e {...}` is borrow-style (e
            # remains valid and is dropped exactly once, by the
            # preprocessor's normal scope-exit tracking, after the
            # match); declaring+consuming a second owned local for it
            # here would double-free once the original binding is also
            # dropped (FIRV-O2).
            scrutinee_temp = self._local_name(scrutinee_node.name)
            scrutinee_type = self._convert_expression(scrutinee_node).result_type
        else:
            scrutinee_value = self._convert_expression(scrutinee_node)
            scrutinee_type = scrutinee_value.result_type
            scrutinee_temp = f"__match_scrutinee_{marker}"
            self._used_local_names.add(scrutinee_temp)
            self.builder.declare_local(scrutinee_temp, scrutinee_type, scrutinee_value)

        result_temp: Optional[str] = None
        result_type: Optional[FIRType] = None
        if not as_statement:
            result_type = self._fir_type(self._expr_type(node))
            result_temp = f"__match_result_{marker}"
            self._used_local_names.add(result_temp)
            self.builder.declare_local(result_temp, result_type)

        join_block = self.builder.new_block()
        int32_type = self._fir_type("int32")
        bool_type = self._fir_type("bool")

        test_block = self.builder.current_block
        for i, arm in enumerate(non_wildcard_arms):
            self.builder.position_at(test_block)
            variant_name = getattr(arm, "variant_name", None)
            tag_index = variant_order.index(variant_name) if variant_name in variant_order else -1
            scrut_ref = self.builder.load_var(scrutinee_temp, scrutinee_type)
            tag_value = self.builder.extract_tag(scrut_ref, int32_type)
            tag_const = self.builder.int_literal(str(tag_index), int32_type)
            is_match = self.builder.binary_op("==", tag_value, tag_const, bool_type)

            arm_block = self.builder.new_block()
            next_block = self.builder.new_block()
            self.builder.branch(is_match, arm_block.id, next_block.id)

            self.builder.position_at(arm_block)
            self._convert_match_arm_body(
                arm, variant_fields, scrutinee_temp, scrutinee_type, result_temp
            )
            if not self.builder.current_block.is_terminated():
                self.builder.jump(join_block.id)

            test_block = next_block

        self.builder.position_at(test_block)
        if wildcard_arm is not None:
            self._convert_match_arm_body(
                wildcard_arm, variant_fields, scrutinee_temp, scrutinee_type, result_temp
            )
            if not self.builder.current_block.is_terminated():
                self.builder.jump(join_block.id)
        else:
            # Exhaustiveness is guaranteed by semantic analysis, so this
            # fallthrough is unreachable at runtime.
            self.builder.unreachable()

        self.builder.position_at(join_block)
        if scrutinee_type.is_owned() and scrutinee_node.node_type != NodeTypes.IDENTIFIER:
            # The scrutinee temp is the sole owner of the matched value
            # (ExtractTag/ExtractPayloadField are non-consuming reads);
            # nothing else drops it, so every arm leaked it (FIRV-O3) --
            # except when scrutinee_node is a bare identifier, in which
            # case the original binding remains the owner (see above).
            scrut_final = self.builder.load_var(scrutinee_temp, scrutinee_type)
            self.builder.drop(scrut_final)
        if result_temp is not None:
            return self.builder.load_var(result_temp, result_type)
        return None

    def _convert_match_arm_body(
        self,
        arm: ASTNode,
        variant_fields: dict[str, list[tuple[str, FIRType]]],
        scrutinee_temp: str,
        scrutinee_type: FIRType,
        result_temp: Optional[str],
    ) -> None:
        self._push_scope()
        variant_name = getattr(arm, "variant_name", None)
        bindings = getattr(arm, "bindings", []) or []
        field_defs = variant_fields.get(variant_name, [])
        field_names = [fname for fname, _ in field_defs]
        field_types = dict(field_defs)
        for field_name, local_name in bindings:
            if field_name not in field_names:
                continue  # already reported by semantic analysis
            field_index = field_names.index(field_name)
            field_type = field_types[field_name]
            scrut_ref = self.builder.load_var(scrutinee_temp, scrutinee_type)
            extracted = self.builder.extract_payload_field(scrut_ref, variant_name, field_index, field_type)
            unique_name = self._declare(local_name, field_type.render(), False)
            self.builder.declare_local(unique_name, field_type, extracted)

        body = arm.children[0] if arm.children else None
        if body is not None:
            if body.node_type == NodeTypes.SCOPE:
                self._convert_statements(body.children)
            else:
                value = self._convert_expression(body)
                if result_temp is not None:
                    self.builder.store_var(result_temp, value)
        self._pop_scope()

    def _convert_short_circuit(self, node: ASTNode) -> Value:
        """Lower && / || with C-style short-circuit evaluation via a temp local."""
        bool_type = make_simple("bool")
        # A name keyed on block/instruction counts at generation time is
        # not guaranteed unique -- two short-circuit expressions converted
        # in different blocks can land on the same (block count,
        # instruction count) pair and collide (FIRV-L3). A dedicated
        # monotonic counter is.
        self._sc_counter += 1
        temp_name = f"__sc_{self._sc_counter}"
        self._used_local_names.add(temp_name)

        left = self._convert_expression(node.children[0])
        self.builder.declare_local(temp_name, bool_type, left)

        rhs_block = self.builder.new_block()
        join_block = self.builder.new_block()
        cond = self.builder.load_var(temp_name, bool_type)
        if node.name == "&&":
            # Evaluate RHS only when LHS is true.
            self.builder.branch(cond, rhs_block.id, join_block.id)
        else:
            # ||: evaluate RHS only when LHS is false.
            self.builder.branch(cond, join_block.id, rhs_block.id)

        self.builder.position_at(rhs_block)
        right = self._convert_expression(node.children[1])
        self.builder.store_var(temp_name, right)
        self.builder.jump(join_block.id)

        self.builder.position_at(join_block)
        return self.builder.load_var(temp_name, bool_type)

    def _convert_literal(self, node: ASTNode) -> Value:
        token_type = node.token.type if node.token else ""
        type_str = self._expr_type(node)

        if token_type == "INTEGER_LITERAL":
            return self.builder.int_literal(self._normalize_literal_text(node), self._fir_type(type_str))
        if token_type in ("FLOAT_LITERAL", "DOUBLE_LITERAL"):
            return self.builder.float_literal(self._normalize_literal_text(node), self._fir_type(type_str))
        if token_type == "BOOLEAN_LITERAL":
            return self.builder.bool_literal(str(node.token.value) == "true", self._fir_type("bool"))
        if token_type == "STRING_LITERAL":
            text = str(node.token.value)
            if text.startswith('"') and text.endswith('"'):
                text = text[1:-1]
            return self.builder.string_literal(text, self._fir_type("string"))
        if token_type == "CHAR_LITERAL":
            text = str(node.token.value)
            if text.startswith("'") and text.endswith("'"):
                text = text[1:-1]
            return self.builder.char_literal(text, self._fir_type("char"))
        if token_type == "NULL_LITERAL":
            null_type = self._fir_type(type_str if type_str != "null" else "string", nullable=True)
            return self.builder.null_literal(null_type)
        raise FIRConversionError(f"Unsupported literal token {token_type}", node)

    @staticmethod
    def _norm_source(source: Optional[str]) -> Optional[str]:
        if not source:
            return None
        try:
            return os.path.normcase(os.path.abspath(source))
        except Exception:
            return source

    def _check_directive(self, node: ASTNode) -> None:
        """Reject directive-gated intrinsics called without the directive
        enabled in the calling file (matches the legacy codegen contract)."""
        required = DIRECTIVE_GATED_INTRINSICS.get(node.name)
        if required is None:
            return
        src = self._norm_source(getattr(node, "source_file", None))
        if required in self.file_directives.get(src, set()):
            return
        raise FIRConversionError(
            f"{node.name}() is not available. Use 'directive {required};' "
            f"in this file to enable it.",
            node,
        )

    def _convert_function_call(self, node: ASTNode, as_statement: bool) -> Optional[Value]:
        name = node.name
        self._check_directive(node)

        if name == "drop":
            target = node.children[0]
            value = self._convert_expression(target)
            self.builder.drop(value)
            if target.node_type == NodeTypes.IDENTIFIER:
                self.current_function.ownership.record_move(target.name)
                self._mark_owned_identifier_moved(target.name)
            return None

        if name == "fs_rt_array_new":
            type_args = list(getattr(node, "type_args", []) or [])
            if len(type_args) != 1:
                raise FIRConversionError(
                    "fs_rt_array_new<T>() requires exactly one type argument", node
                )
            elem_type = self._fir_type(type_args[0])
            array_type = ArrayType(elem_type, size=None)
            count = self._require_value(node.children[0])
            return self.builder.array_alloc(count, array_type)

        if name == "fs_rt_array_copy":
            dst = self._require_value(node.children[0])
            src = self._require_value(node.children[1])
            count = self._require_value(node.children[2])
            self.builder.array_copy(dst, src, count)
            return None

        if name == "fs_rt_hash":
            type_args = list(getattr(node, "type_args", []) or [])
            if len(type_args) != 1:
                raise FIRConversionError(
                    "fs_rt_hash<K>() requires exactly one type argument", node
                )
            key = self._require_value(node.children[0])
            call = self.builder.call(name, [key], ["borrow"], make_simple("uint64"))
            if call is not None:
                call.instruction.metadata["type_args"] = type_args
            return call

        base_name = name.split("<")[0] if "<" in name else name
        if base_name in self.class_categories:
            return self._convert_construction(node, name, base_name)

        if name in self.generator_defs:
            gen_def = self.generator_defs[name]
            yield_type_str = getattr(gen_def, "yield_type", gen_def.return_type or "int32")
            gen_type = GeneratorType(self._fir_type(yield_type_str))
            args = [self._convert_expression(arg) for arg in node.children]
            gen_value = self.builder.gen_new(name, args, gen_type)
            type_params = list(getattr(gen_def, "type_params", []) or [])
            if type_params and gen_value is not None:
                type_args = self._infer_generator_type_args(gen_def, type_params, node)
                if type_args:
                    gen_value.instruction.metadata["type_args"] = type_args
            return gen_value

        type_args = list(getattr(node, "type_args", []) or [])
        if not type_args and name in self.generic_functions:
            type_args = self._infer_type_args(name, node)

        # Determine each positional argument's declared parameter type
        # (substituted for this call's concrete type_args) up front, same
        # rationale as _convert_construction: a bare `null` argument needs
        # it to resolve to the right concrete type, and a nullable-scalar
        # parameter needs a companion has-value argument appended (see
        # _function_params / _call_arg_hasvals).
        callee_def = self.function_defs.get(base_name)
        callee_params: list[ASTNode] = []
        subst: dict[str, str] = {}
        if callee_def is not None:
            callee_params = [c for c in callee_def.children if c.node_type == NodeTypes.PARAMETER]
            callee_generic_params = list(getattr(callee_def, "type_params", []) or [])
            subst = dict(zip(callee_generic_params, type_args)) if type_args else {}

        args: list[Value] = []
        for i, arg_node in enumerate(node.children):
            expected: Optional[str] = None
            if i < len(callee_params):
                p = callee_params[i]
                pt = subst.get(p.var_type or "int32", p.var_type or "int32")
                if getattr(p, "is_nullable", False):
                    pt = f"{pt}?"
                expected = pt
            prev_expected = self._expected_type_str
            self._expected_type_str = self._expected_type_if_null(arg_node, expected)
            args.append(self._require_value(arg_node))
            self._expected_type_str = prev_expected

        hasval_extra = self._call_arg_hasvals(
            callee_params, node.children, set(getattr(callee_def, "type_params", []) or []) if callee_def else set()
        )

        nullable_return_base = self._nullable_return_scalar_base(node)
        if nullable_return_base is not None:
            # The callee actually returns __NullableReturn<T> (see
            # _resolve_function_return_type / _convert_function_call_
            # unwrapped), not the bare nullable-scalar T its source
            # signature declares -- the Call instruction's result type
            # must match the callee's *real* FIR return type exactly
            # (FIRV-T5), substituted for this call's concrete type_args
            # when the callee is itself generic.
            concrete_scalar = subst.get(nullable_return_base, nullable_return_base)
            self._ensure_nullable_return_typedef()
            return_type: Optional[FIRType] = GenericInstanceType(
                self._NULLABLE_RETURN_STRUCT, [self._fir_type(concrete_scalar)], category="copyable"
            )
        else:
            return_type_str = self._expr_type(node)
            return_type = self._fir_type(return_type_str) if return_type_str != "void" else None

        modes = self._call_arg_modes(name, node)
        for arg_node, mode in zip(node.children, modes):
            if mode == "own" and arg_node.node_type == NodeTypes.IDENTIFIER:
                self._mark_owned_identifier_moved(arg_node.name)
        call = self.builder.call(name, args + hasval_extra, modes + ["own"] * len(hasval_extra), return_type)

        call_inst = call.instruction if call is not None else self.builder.current_block.instructions[-1]
        if name in INTRINSIC_FUNCTIONS:
            call_inst.metadata["intrinsic"] = True
        if type_args:
            call_inst.metadata["type_args"] = type_args
        return call

    def _convert_construction(self, node: ASTNode, full_name: str, base_name: str) -> Value:
        """Construct a class instance: explicit constructor call when one
        exists, positional field initialization otherwise. Handles generic
        instances (e.g. `Pair<int32, string>(...)`)."""
        for arg_node in node.children:
            if arg_node.node_type == NodeTypes.IDENTIFIER:
                self._mark_owned_identifier_moved(arg_node.name)

        type_args: list[str] = []
        if "<" in full_name and full_name.endswith(">"):
            type_args = self._split_type_args(full_name.split("<", 1)[1][:-1])
        if not type_args:
            annotated = list(getattr(node, "type_args", []) or [])
            if annotated:
                type_args = annotated
                full_name = f"{base_name}<{', '.join(type_args)}>"
        if not type_args and self.class_generic_params.get(base_name):
            # Fall back to the declared type of the binding being initialized
            # (e.g. `Pair<int32, string> p = Pair(1, "x");`).
            expected = getattr(self, "_expected_type_str", None)
            if expected and expected.split("<")[0] == base_name and "<" in expected:
                full_name = expected
                type_args = self._split_type_args(expected.split("<", 1)[1][:-1])
        result_type = self._fir_type(full_name)

        has_constructor = base_name in self.class_method_names and base_name in self.class_method_names.get(
            base_name, set()
        )

        # Determine each positional constructor argument's declared
        # parameter type (substituted for this instantiation's concrete
        # type_args, e.g. Option<T>'s `value: T?` becomes "int32?" for
        # `Option<int32>(...)`) up front: a bare `null` argument needs it
        # to resolve to the right concrete type (see _expr_type's
        # NULL_LITERAL handling), and a nullable-scalar parameter needs a
        # companion has-value argument appended (see _function_params /
        # _call_arg_hasvals).
        ctor_params: list[ASTNode] = []
        own_generic_params = set(self.class_generic_params.get(base_name, []))
        if has_constructor:
            ctor_def = self.class_method_defs.get((base_name, base_name))
            if ctor_def is not None:
                ctor_params = [
                    c
                    for c in ctor_def.children
                    if c.node_type == NodeTypes.PARAMETER and c.name != "this"
                ]
        subst = dict(zip(self.class_generic_params.get(base_name, []), type_args))

        args: list[Value] = []
        for i, arg_node in enumerate(node.children):
            expected: Optional[str] = None
            if i < len(ctor_params):
                p = ctor_params[i]
                pt = subst.get(p.var_type or "int32", p.var_type or "int32")
                if getattr(p, "is_nullable", False):
                    pt = f"{pt}?"
                expected = pt
            prev_expected = self._expected_type_str
            self._expected_type_str = self._expected_type_if_null(arg_node, expected)
            args.append(self._require_value(arg_node))
            self._expected_type_str = prev_expected

        hasval_extra = self._call_arg_hasvals(ctor_params, node.children, own_generic_params)

        if has_constructor:
            call = self.builder.call(
                f"{base_name}.{base_name}",
                args + hasval_extra,
                ["own"] * (len(args) + len(hasval_extra)),
                result_type,
            )
            if type_args:
                call.instruction.metadata["type_args"] = type_args
            return call
        # No explicit constructor: positional field initialization.
        return self.builder.allocate(result_type, args)

    def _call_arg_modes(self, name: str, node: ASTNode) -> list[str]:
        func_def = self.function_defs.get(name)
        if func_def is None:
            if name in INTRINSIC_FUNCTIONS:
                # Every intrinsic (string/array primitives, numeric
                # conversions, syscalls, low-level mem/win32 primitives)
                # reads its arguments without taking ownership; defaulting
                # to "own" here made every call site look like it consumed
                # its (often borrowed) argument, which FIRV-O7 correctly
                # flags as illegal when the argument is itself a borrow
                # parameter.
                return ["borrow"] * len(node.children)
            return ["own"] * len(node.children)
        modes: list[str] = []
        params = [c for c in func_def.children if c.node_type == NodeTypes.PARAMETER]
        for i, _arg in enumerate(node.children):
            if i < len(params) and getattr(params[i], "is_borrowed", False):
                if getattr(params[i], "is_mutable_borrow", False):
                    modes.append("borrow_mut")
                else:
                    modes.append("borrow")
            else:
                modes.append("own")
        return modes

    def _infer_type_args(self, func_name: str, call_node: ASTNode) -> list[str]:
        type_params = self.generic_functions.get(func_name, [])
        func_def = self.function_defs.get(func_name)
        if not type_params or func_def is None:
            return []
        params = [c for c in func_def.children if c.node_type == NodeTypes.PARAMETER]
        mapping: dict[str, str] = {}
        for param, arg in zip(params, call_node.children):
            param_type = param.var_type or ""
            if param_type in type_params and param_type not in mapping:
                # Nullable-ness doesn't affect runtime representation, so
                # it must not affect a generic instantiation's identity --
                # println<string> and println<string?> are the same
                # monomorphized instance (see _strip_nullable_str).
                arg_type = self._strip_nullable_str(self._expr_type(arg))
                if getattr(param, "is_array", False) and arg_type.endswith("[]"):
                    # `&arr: T[]` binds T to the element type, not the whole
                    # array type -- an `int32[]` argument must infer T=int32,
                    # not T="int32[]".
                    arg_type = arg_type[:-2]
                mapping[param_type] = arg_type
        return [mapping[tp] for tp in type_params if tp in mapping] if len(mapping) == len(type_params) else []

    def _infer_generator_type_args(
        self, gen_def: ASTNode, type_params: list[str], call_node: ASTNode
    ) -> list[str]:
        """Like _infer_type_args, but for a generic generator function call
        (e.g. `enumerate<T>(v)`), and additionally unifies a composite
        generic-class parameter type against the argument's concrete
        instantiation (e.g. param `Vec<T>` vs. argument type `Vec<int32>` ->
        T=int32) -- `_infer_type_args` only matches a bare `T`/`T[]` param,
        which a generator taking a generic-class-typed receiver-like
        parameter (`&v: Vec<T>`) doesn't fit. Generators aren't registered in
        self.function_defs/self.generic_functions (only self.generator_defs),
        so this reads gen_def/type_params directly instead of reusing that
        registry lookup."""
        params = [c for c in gen_def.children if c.node_type == NodeTypes.PARAMETER]
        mapping: dict[str, str] = {}
        for param, arg in zip(params, call_node.children):
            param_type = param.var_type or ""
            arg_type = self._strip_nullable_str(self._expr_type(arg))
            if getattr(param, "is_array", False) and arg_type.endswith("[]"):
                arg_type = arg_type[:-2]
            if param_type in type_params and param_type not in mapping:
                mapping[param_type] = arg_type
            elif (
                "<" in param_type and param_type.endswith(">")
                and "<" in arg_type and arg_type.endswith(">")
            ):
                p_base, p_rest = param_type.split("<", 1)
                a_base, a_rest = arg_type.split("<", 1)
                if p_base == a_base:
                    p_args = self._split_type_args(p_rest[:-1])
                    a_args = self._split_type_args(a_rest[:-1])
                    for pt, at in zip(p_args, a_args):
                        if pt in type_params and pt not in mapping:
                            mapping[pt] = at
        return [mapping[tp] for tp in type_params if tp in mapping] if len(mapping) == len(type_params) else []

    def _convert_method_call(self, node: ASTNode) -> Optional[Value]:
        object_node = node.children[0]
        object_type_str = self._expr_type(object_node)
        method_name = node.name

        if object_type_str.endswith("[]"):
            return self._convert_builtin_method(node, object_node, "array", object_type_str[:-2], method_name)

        if object_type_str == "string":
            return self._convert_builtin_method(node, object_node, "string", None, method_name)

        receiver = self._convert_expression(object_node)
        args = [self._require_value(arg) for arg in node.children[1:]]
        return_type_str = self._expr_type(node)

        modes = ["own"] * len(args)
        method_def = self._find_method_def(object_type_str, method_name)
        hasval_extra: list[Value] = []
        if method_def is not None:
            params = [
                c
                for c in method_def.children
                if c.node_type == NodeTypes.PARAMETER and not getattr(c, "is_receiver", False)
            ]
            modes = []
            for i in range(len(args)):
                if i < len(params) and getattr(params[i], "is_borrowed", False):
                    modes.append(
                        "borrow_mut" if getattr(params[i], "is_mutable_borrow", False) else "borrow"
                    )
                else:
                    modes.append("own")
            receiver_base = object_type_str.split("<")[0] if "<" in object_type_str else object_type_str
            hasval_extra = self._call_arg_hasvals(
                params, node.children[1:], set(self.class_generic_params.get(receiver_base, []))
            )

        method_call = self.builder.method_call(
            receiver,
            method_name,
            args + hasval_extra,
            modes + ["own"] * len(hasval_extra),
            self._fir_type(return_type_str) if return_type_str != "void" else None,
        )
        if method_call is not None:
            method_call.instruction.metadata["class_name"] = (
                object_type_str if object_type_str in self.class_categories else object_type_str
            )
        return method_call

    def _array_length_value(self, object_node: ASTNode, receiver: Optional[Value] = None) -> Value:
        """Resolve an array's length as a FIR value: a compile-time literal
        when the array's size is statically known here (`_array_size_of`),
        else the `array_length` intrinsic call (resolved at FLIR-lowering
        time via the ctx.array_lens mechanism for arrays whose size isn't
        known until then). Pass an already-converted `receiver` when the
        caller also needs the array value for another purpose, so a
        side-effecting `object_node` (e.g. a function call) isn't evaluated
        twice."""
        size = self._array_size_of(object_node)
        if size is not None:
            return self.builder.int_literal(str(size), make_simple("int32"))
        array_val = receiver if receiver is not None else self._convert_expression(object_node)
        call = self.builder.call("array_length", [array_val], ["borrow"], make_simple("int32"))
        call.instruction.metadata["intrinsic"] = True
        return call

    def _convert_builtin_method(
        self, node: ASTNode, object_node: ASTNode, family: str, elem_type: Optional[str], method_name: str
    ) -> Optional[Value]:
        """Convert a dot-method call on a primitive receiver (string/array)
        to a direct FIR call to its @builtin_method-registered backing
        function (firescript/builtin_methods.py) -- a real, non-intrinsic
        function call resolved through the same path as any ordinary
        (possibly generic) function call, since the backing function is
        real firescript source merged into every program from
        std/internal/. Type-checking already validated `method_name`
        against the registry, so a lookup miss here would indicate a
        parser/converter mismatch, not user error.
        """
        from builtin_methods import get_builtin_method_registry

        spec = get_builtin_method_registry().lookup(family, method_name)
        if spec is None:
            raise FIRConversionError(f"Unsupported {family} method '{method_name}'", node)

        if spec.const_fold:
            # .length()/.size(): resolve directly, no call emitted at all --
            # a strict superset of the historical fast path (literal when
            # statically known, the `array_length` intrinsic otherwise),
            # zero call overhead either way.
            return self._array_length_value(object_node)

        receiver = self._convert_expression(object_node)
        user_args = [self._require_value(arg) for arg in node.children[1:]]

        call_args = [receiver]
        modes = [spec.receiver_mode]
        if spec.needs_length:
            call_args.append(self._array_length_value(object_node, receiver))
            modes.append("own")
        call_args.extend(user_args)
        modes.extend(spec.public_param_modes)

        type_args = [elem_type] if (elem_type is not None and spec.type_params) else []
        return_type_str = (
            elem_type if (elem_type is not None and spec.return_type in spec.type_params) else spec.return_type
        )
        return_type = self._fir_type(return_type_str) if return_type_str != "void" else None

        call = self.builder.call(spec.fir_name, call_args, modes, return_type)
        if call is not None and type_args:
            call.instruction.metadata["type_args"] = type_args
        return call

    def _convert_super_call(self, node: ASTNode) -> Optional[Value]:
        super_class = getattr(node, "super_class", None)
        if not super_class:
            raise FIRConversionError("super() call without resolved super class", node)
        args = [self._convert_expression(arg) for arg in (node.children or [])]
        base = self.builder.call(
            f"{super_class}.{super_class}", args, ["own"] * len(args), self._fir_type(super_class)
        )
        # Copy base fields onto this, then release the temporary base object
        # without running its destructor (fields now belong to this).
        this_type_str = self.current_function.metadata.get("class_name", super_class)
        this_value = self.builder.load_var(self._local_name("this"), self._fir_type(this_type_str))
        for field_name, field_type in self._all_class_fields(super_class):
            field_value = self.builder.load_field(base, field_name, self._fir_type(field_type))
            self.builder.store_field(this_value, field_name, field_value)
        release = self.builder.call("free_shallow", [base], ["own"], None)
        last_inst = self.builder.current_block.instructions[-1]
        last_inst.metadata["intrinsic"] = True
        del release
        return None
