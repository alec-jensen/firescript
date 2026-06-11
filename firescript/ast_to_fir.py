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
from typing import Optional

from enums import NodeTypes
from parser import ASTNode

from fir.ir_builder import FIRBuilder
from fir.ir_module import FIRFunction, FIRModule, GlobalConstant, TypeDef
from fir.ir_node import Value
from fir.ir_types import (
    ArrayType,
    FIRType,
    GeneratorType,
    GenericInstanceType,
    SimpleType,
    make_simple,
)

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
}

COMPOUND_OP_MAP = {
    "ADD_ASSIGN": "+",
    "SUBTRACT_ASSIGN": "-",
    "MULTIPLY_ASSIGN": "*",
    "DIVIDE_ASSIGN": "/",
    "MODULO_ASSIGN": "%",
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

    def __init__(self, ast: ASTNode, module_name: str = "firescript"):
        self.ast = ast
        self.module = FIRModule(module_name)

        # Program-wide registries (filled by _collect_program_info)
        self.class_fields: dict[str, list[tuple[str, str]]] = {}
        self.class_categories: dict[str, str] = {}
        self.class_bases: dict[str, Optional[str]] = {}
        self.class_generic_params: dict[str, list[str]] = {}
        self.class_method_names: dict[str, set[str]] = {}
        self.class_method_defs: dict[tuple[str, str], ASTNode] = {}
        self.function_defs: dict[str, ASTNode] = {}
        self.generic_functions: dict[str, list[str]] = {}
        self.generator_defs: dict[str, ASTNode] = {}

        # Per-function conversion state
        self.builder: Optional[FIRBuilder] = None
        self.current_function: Optional[FIRFunction] = None
        # scope stack of name -> (type_str, is_array, array_size)
        self.scopes: list[dict[str, tuple[str, bool, Optional[int]]]] = []
        # (continue_target_block_id, break_target_block_id)
        self.loop_stack: list[tuple[str, str]] = []

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

        if user_main is not None:
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
                for member in child.children:
                    if member.node_type == NodeTypes.CLASS_FIELD:
                        field_type = member.var_type or "int32"
                        if member.is_array:
                            field_type += "[]"
                        fields.append((member.name, field_type))
                    elif member.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
                        methods.add(member.name)
                        self.class_method_defs[(name, member.name)] = member
                self.class_fields[name] = fields
                self.class_method_names[name] = methods
                is_copyable = bool(getattr(child, "is_copyable", False))
                self.class_categories[name] = "copyable" if is_copyable else "owned"
                self.class_bases[name] = getattr(child, "base_class", None)
                self.class_generic_params[name] = list(getattr(child, "type_params", []) or [])
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
            return GenericInstanceType(base, args)

        if type_str in self.class_categories:
            return SimpleType(type_str, category=self.class_categories[type_str], nullable=nullable)
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

    def _push_scope(self) -> None:
        self.scopes.append({})

    def _pop_scope(self) -> None:
        self.scopes.pop()

    def _declare(self, name: str, type_str: str, is_array: bool, size: Optional[int] = None) -> None:
        self.scopes[-1][name] = (type_str, is_array, size)

    def _lookup(self, name: str) -> Optional[tuple[str, bool, Optional[int]]]:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    # ------------------------------------------------------------------
    # Expression typing (reads AST annotations, mirrors codegen lookups)
    # ------------------------------------------------------------------

    def _expr_type(self, node: ASTNode) -> str:
        """Best-effort firescript type string of an expression node."""
        if node.node_type == NodeTypes.LITERAL:
            annotated = getattr(node, "return_type", None)
            if annotated:
                return annotated
            token_type = node.token.type if node.token else None
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
                type_str, is_array, _ = symbol
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
                return method_def.return_type or "void"
            return "void"

        if node.node_type == NodeTypes.TYPE_METHOD_CALL:
            annotated = getattr(node, "return_type", None)
            if annotated:
                return annotated
            class_name = getattr(node, "class_name", "")
            method_def = self._find_method_def(class_name, node.name)
            if method_def is not None:
                return method_def.return_type or "void"
            return "void"

        if node.node_type == NodeTypes.SUPER_CALL:
            return getattr(node, "return_type", None) or "void"

        if node.node_type == NodeTypes.CONSTRUCTOR_CALL:
            return node.name

        if node.node_type == NodeTypes.FIELD_ACCESS:
            annotated = getattr(node, "return_type", None)
            if annotated:
                return annotated
            obj_type = self._expr_type(node.children[0])
            for field_name, field_type in self._all_class_fields(obj_type):
                if field_name == node.name:
                    return field_type
            return "int32"

        return getattr(node, "return_type", None) or "int32"

    def _find_method_def(self, class_name: str, method_name: str) -> Optional[ASTNode]:
        """Find a method definition on a class or any of its base classes."""
        current: Optional[str] = class_name
        seen: set[str] = set()
        while current is not None and current not in seen:
            seen.add(current)
            method = self.class_method_defs.get((current, method_name))
            if method is not None:
                return method
            current = self.class_bases.get(current)
        return None

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

    def _function_params(self, node: ASTNode) -> tuple[list[tuple[str, FIRType]], list[str]]:
        params: list[tuple[str, FIRType]] = []
        modes: list[str] = []
        for child in node.children:
            if child.node_type != NodeTypes.PARAMETER:
                continue
            param_type = self._fir_type(child.var_type, child.is_array)
            params.append((child.name, param_type))
            if getattr(child, "is_borrowed", False):
                if getattr(child, "is_mutable_borrow", False):
                    modes.append("borrow_mut")
                else:
                    modes.append("borrow")
            else:
                modes.append("own")
        return params, modes

    def _register_params_in_scope(self, node: ASTNode) -> None:
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER:
                self._declare(child.name, child.var_type or "int32", child.is_array, None)

    def _convert_function(self, node: ASTNode, fir_name: Optional[str] = None) -> None:
        params, modes = self._function_params(node)
        function = FIRFunction(
            fir_name or node.name,
            params=params,
            return_type=self._fir_type(node.return_type) if node.return_type and node.return_type != "void" else None,
            generic_params=list(getattr(node, "type_params", []) or []),
            param_modes=modes,
        )
        self.module.add_function(function)
        self._convert_body(node, function)

    def _convert_generator(self, node: ASTNode) -> None:
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

    def _convert_method(self, class_name: str, node: ASTNode) -> None:
        params, modes = self._function_params(node)
        is_constructor = bool(getattr(node, "is_constructor", False))
        is_static = bool(getattr(node, "is_static", False))

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
        self._push_scope()
        self._register_params_in_scope(node)

        if is_constructor:
            # 'this' is created by the constructor itself.
            this_type = self._fir_type(class_name)
            this_value = self.builder.allocate(this_type, [])
            self.builder.declare_local("this", this_type, this_value)
            self._declare("this", class_name, False, None)
        elif not is_static:
            if self._lookup("this") is None:
                self._declare("this", class_name, False, None)

        body = node.children[-1] if node.children else None
        if body is not None and body.node_type == NodeTypes.SCOPE:
            self._convert_statements(body.children)

        if not self.builder.current_block.is_terminated():
            if is_constructor:
                this_type = self._fir_type(class_name)
                result = self.builder.load_var("this", this_type)
                self.builder.ret(result)
            else:
                self.builder.ret()

        self._pop_scope()
        self._seal_open_blocks(function)
        self.builder = None
        self.current_function = None

    def _convert_body(self, node: ASTNode, function: FIRFunction) -> None:
        self.current_function = function
        self.builder = FIRBuilder(function)
        self._push_scope()
        self._register_params_in_scope(node)

        body = node.children[-1] if node.children else None
        if body is not None and body.node_type == NodeTypes.SCOPE:
            self._convert_statements(body.children)

        if not self.builder.current_block.is_terminated():
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
        """Terminate any unterminated blocks (unreachable join points)."""
        from fir.ir_node import UnreachableInst

        for block in function.blocks:
            if block.terminator is None:
                block.set_terminator(UnreachableInst())

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
            self.builder.jump(self.loop_stack[-1][1])
            return

        if node_type == NodeTypes.CONTINUE_STATEMENT:
            if not self.loop_stack:
                raise FIRConversionError("continue outside loop", node)
            self.builder.jump(self.loop_stack[-1][0])
            return

        if node_type == NodeTypes.RETURN_STATEMENT:
            if node.children:
                value = self._convert_expression(node.children[0])
                self.builder.ret(value)
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
            var_type = self._fir_type(type_str, True, size)
            init_value = self._convert_expression(init_node) if init_node is not None else None
            if init_value is None:
                # Sized array with no initializer: zero-initialized array literal.
                init_value = self.builder.array_literal([], var_type)
            self.builder.declare_local(node.name, var_type, init_value)
            self._declare(node.name, type_str, True, size)
            return

        var_type = self._fir_type(type_str, nullable=node.is_nullable)
        init_value = self._convert_expression(init_node) if init_node is not None else None
        self.builder.declare_local(node.name, var_type, init_value)
        self._declare(node.name, type_str, False, None)

    def _convert_variable_assignment(self, node: ASTNode) -> None:
        value = self._convert_expression(node.children[0]) if node.children else None
        if value is None:
            raise FIRConversionError("Assignment without value", node)
        if self._lookup(node.name) is None:
            # Implicit declaration (class-typed RHS assignments allow this).
            rhs_type = self._expr_type(node.children[0])
            is_array = rhs_type.endswith("[]")
            base_type = rhs_type[:-2] if is_array else rhs_type
            self.builder.declare_local(node.name, self._fir_type(base_type, is_array), value)
            self._declare(node.name, base_type, is_array, None)
            return
        self.builder.store_var(node.name, value)

    def _convert_assignment(self, node: ASTNode) -> None:
        lhs = node.children[0]
        rhs = node.children[1]
        value = self._convert_expression(rhs)

        if lhs.node_type == NodeTypes.IDENTIFIER:
            self.builder.store_var(lhs.name, value)
            return
        if lhs.node_type == NodeTypes.FIELD_ACCESS:
            obj = self._convert_expression(lhs.children[0])
            self.builder.store_field(obj, lhs.name, value)
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
        var_type = self._fir_type(type_str)
        current = self.builder.load_var(node.name, var_type)
        rhs = self._convert_expression(node.children[0])
        result = self.builder.binary_op(op, current, rhs, var_type)
        self.builder.store_var(node.name, result)

    def _convert_increment(self, node: ASTNode) -> None:
        var_name = node.token.value if node.token else ""
        symbol = self._lookup(var_name)
        type_str = symbol[0] if symbol else "int32"
        var_type = self._fir_type(type_str)
        current = self.builder.load_var(var_name, var_type)
        one = self.builder.int_literal("1", var_type)
        op = "+" if node.name == "++" else "-"
        result = self.builder.binary_op(op, current, one, var_type)
        self.builder.store_var(var_name, result)

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
        self.loop_stack.append((header.id, exit_block.id))
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
        self.loop_stack.append((incr_block.id, exit_block.id))
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
        gen_local = f"__gen_{loop_var}"
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
        self.builder.declare_local(loop_var, self._fir_type(loop_var_type_str), element)
        self._declare(loop_var, loop_var_type_str, False, None)

        self.loop_stack.append((header.id, exit_block.id))
        if body.node_type == NodeTypes.SCOPE:
            self._convert_statements(body.children)
        else:
            self._convert_statement(body)
        self.loop_stack.pop()
        self._pop_scope()
        if not self.builder.current_block.is_terminated():
            self.builder.jump(header.id)

        self.builder.position_at(exit_block)

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

        source = self._convert_expression(collection)
        source_local = f"__str_{loop_var}"
        self.builder.declare_local(source_local, string_type, source)
        index_local = f"__i_{loop_var}"
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
        self.builder.declare_local(loop_var, self._fir_type(loop_var_type_str), element)
        self._declare(loop_var, loop_var_type_str, False, None)

        # The increment happens in a dedicated block so `continue` advances.
        incr_block = self.builder.new_block()
        self.loop_stack.append((incr_block.id, exit_block.id))
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

        source = self._convert_expression(collection)
        source_local = f"__arr_{loop_var}"
        self.builder.declare_local(source_local, array_type, source)
        index_local = f"__i_{loop_var}"
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
        self.builder.declare_local(loop_var, self._fir_type(loop_var_type_str), element)
        self._declare(loop_var, loop_var_type_str, False, None)

        incr_block = self.builder.new_block()
        self.loop_stack.append((incr_block.id, exit_block.id))
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
            return self.builder.load_var(node.name, self._fir_type(base, is_array, size))

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
            cast.instruction.metadata["source_type"] = self._expr_type(node.children[0])
            return cast

        if node_type == NodeTypes.BINARY_EXPRESSION and node.name in ("&&", "||"):
            return self._convert_short_circuit(node)

        if node_type in (
            NodeTypes.BINARY_EXPRESSION,
            NodeTypes.EQUALITY_EXPRESSION,
            NodeTypes.RELATIONAL_EXPRESSION,
        ):
            left = self._convert_expression(node.children[0])
            right = self._convert_expression(node.children[1])
            result_type = self._fir_type(self._expr_type(node))
            op_inst = self.builder.binary_op(node.name, left, right, result_type)
            op_inst.instruction.metadata["operand_type"] = self._expr_type(node.children[0])
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
            return self._convert_function_call(node, as_statement)

        if node_type == NodeTypes.METHOD_CALL:
            return self._convert_method_call(node)

        if node_type == NodeTypes.TYPE_METHOD_CALL:
            class_name = getattr(node, "class_name", "")
            args = [self._convert_expression(arg) for arg in node.children]
            return_type_str = self._expr_type(node)
            return self.builder.call(
                f"{class_name}.{node.name}",
                args,
                ["own"] * len(args),
                self._fir_type(return_type_str) if return_type_str != "void" else None,
            )

        if node_type == NodeTypes.CONSTRUCTOR_CALL:
            args = [self._convert_expression(arg) for arg in node.children]
            class_name = node.name
            if f"{class_name}.{class_name}" in {f.name for f in self.module.functions} or (
                class_name in self.class_method_names
                and class_name in self.class_method_names[class_name]
            ):
                return self.builder.call(
                    f"{class_name}.{class_name}",
                    args,
                    ["own"] * len(args),
                    self._fir_type(class_name),
                )
            # No explicit constructor: positional field initialization.
            return self.builder.allocate(self._fir_type(class_name), args)

        if node_type == NodeTypes.SUPER_CALL:
            return self._convert_super_call(node)

        raise FIRConversionError(f"Unsupported expression node {node_type}", node)

    def _convert_short_circuit(self, node: ASTNode) -> Value:
        """Lower && / || with C-style short-circuit evaluation via a temp local."""
        bool_type = make_simple("bool")
        temp_name = f"__sc_{len(self.current_function.blocks)}_{len(self.builder.current_block.instructions)}"

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

    def _convert_function_call(self, node: ASTNode, as_statement: bool) -> Optional[Value]:
        name = node.name

        if name == "drop":
            target = node.children[0]
            value = self._convert_expression(target)
            self.builder.drop(value)
            if target.node_type == NodeTypes.IDENTIFIER:
                self.current_function.ownership.record_move(target.name)
            return None

        if name in self.class_categories:
            # Positional construction: ClassName(args) maps args to fields.
            args = [self._convert_expression(arg) for arg in node.children]
            return self.builder.allocate(self._fir_type(name), args)

        if name in self.generator_defs:
            gen_def = self.generator_defs[name]
            yield_type_str = getattr(gen_def, "yield_type", gen_def.return_type or "int32")
            gen_type = GeneratorType(self._fir_type(yield_type_str))
            args = [self._convert_expression(arg) for arg in node.children]
            return self.builder.gen_new(name, args, gen_type)

        args = [self._convert_expression(arg) for arg in node.children]
        return_type_str = self._expr_type(node)
        return_type = self._fir_type(return_type_str) if return_type_str != "void" else None

        modes = self._call_arg_modes(name, node)
        call = self.builder.call(name, args, modes, return_type)

        call_inst = call.instruction if call is not None else self.builder.current_block.instructions[-1]
        if name in INTRINSIC_FUNCTIONS:
            call_inst.metadata["intrinsic"] = True
        type_args = list(getattr(node, "type_args", []) or [])
        if not type_args and name in self.generic_functions:
            type_args = self._infer_type_args(name, node)
        if type_args:
            call_inst.metadata["type_args"] = type_args
        return call

    def _call_arg_modes(self, name: str, node: ASTNode) -> list[str]:
        func_def = self.function_defs.get(name)
        if func_def is None:
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
                arg_type = self._expr_type(arg)
                mapping[param_type] = arg_type
        return [mapping[tp] for tp in type_params if tp in mapping] if len(mapping) == len(type_params) else []

    def _convert_method_call(self, node: ASTNode) -> Optional[Value]:
        object_node = node.children[0]
        object_type_str = self._expr_type(object_node)
        method_name = node.name

        if object_type_str.endswith("[]"):
            return self._convert_array_method(node, object_node, object_type_str, method_name)

        if object_type_str == "string":
            if method_name == "length":
                receiver = self._convert_expression(object_node)
                call = self.builder.call("str_length", [receiver], ["borrow"], make_simple("int32"))
                call.instruction.metadata["intrinsic"] = True
                return call

        receiver = self._convert_expression(object_node)
        args = [self._require_value(arg) for arg in node.children[1:]]
        return_type_str = self._expr_type(node)

        modes = ["own"] * len(args)
        method_def = self._find_method_def(object_type_str, method_name)
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

        method_call = self.builder.method_call(
            receiver,
            method_name,
            args,
            modes,
            self._fir_type(return_type_str) if return_type_str != "void" else None,
        )
        if method_call is not None:
            method_call.instruction.metadata["class_name"] = (
                object_type_str if object_type_str in self.class_categories else object_type_str
            )
        return method_call

    def _convert_array_method(
        self, node: ASTNode, object_node: ASTNode, object_type_str: str, method_name: str
    ) -> Value:
        int32 = make_simple("int32")
        size = self._array_size_of(object_node)

        if method_name in ("length", "size"):
            if size is not None:
                return self.builder.int_literal(str(size), int32)
            array = self._convert_expression(object_node)
            call = self.builder.call("array_length", [array], ["borrow"], int32)
            call.instruction.metadata["intrinsic"] = True
            return call

        if method_name in ("index", "count"):
            array = self._convert_expression(object_node)
            needle = self._convert_expression(node.children[1])
            call = self.builder.call(
                f"array_{method_name}", [array, needle], ["borrow", "own"], int32
            )
            call.instruction.metadata["intrinsic"] = True
            if size is not None:
                call.instruction.metadata["array_size"] = size
            call.instruction.metadata["element_type"] = object_type_str[:-2]
            return call

        raise FIRConversionError(f"Unsupported array method '{method_name}'", node)

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
        this_value = self.builder.load_var("this", self._fir_type(this_type_str))
        for field_name, field_type in self._all_class_fields(super_class):
            field_value = self.builder.load_field(base, field_name, self._fir_type(field_type))
            self.builder.store_field(this_value, field_name, field_value)
        release = self.builder.call("free_shallow", [base], ["own"], None)
        last_inst = self.builder.current_block.instructions[-1]
        last_inst.metadata["intrinsic"] = True
        del release
        return None
