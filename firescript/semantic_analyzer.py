# firescript/semantic_analyzer.py
"""
Semantic analyzer for ownership, borrowing, and lifetime checking.
Implements the memory management model defined in docs/reference/memory_management.md.
"""
import logging
import re
from typing import Optional, Dict, Set, List, Tuple
from enum import Enum, auto

from enums import NodeTypes
from parser import ASTNode
from errors import CompileTimeError, SemanticError, InvalidTypeError, InvalidExpressionError, MissingReturnError
from utils.type_utils import is_owned
from utils.literal_utils import coerce_literal
from utils.file_utils import get_line_and_coumn_from_index, get_line


class OwnershipState(Enum):
    """State of a variable binding in the ownership tracking system."""
    VALID = auto()      # Binding is valid and can be used
    MOVED = auto()      # Ownership was moved; binding is invalid
    MAYBE_MOVED = auto()  # Ownership may have moved on at least one control-flow path
    BORROWED = auto()   # Currently borrowed (for future mut borrow tracking)


class BindingInfo:
    """Information about a variable binding."""
    def __init__(
        self,
        name: str,
        var_type: Optional[str],
        is_array: bool,
        is_borrowed: bool = False,
        state: OwnershipState = OwnershipState.VALID,
        declaration_node: Optional[ASTNode] = None,
    ):
        self.name = name
        self.var_type = var_type
        self.is_array = is_array
        self.is_borrowed = is_borrowed
        self.state = state
        self.declaration_node = declaration_node
        self.last_use_node: Optional[ASTNode] = None
        self.move_node: Optional[ASTNode] = None


class BorrowInfo:
    """Information about a borrowed reference."""
    def __init__(
        self,
        borrowed_name: str,
        borrow_node: ASTNode,
        scope_depth: int,
    ):
        self.borrowed_name = borrowed_name
        self.borrow_node = borrow_node
        self.scope_depth = scope_depth


class SemanticAnalyzer:
    """
    Performs semantic analysis for ownership and borrowing.
    
    Responsibilities:
    - Track ownership state of all bindings
    - Detect use-after-move errors
    - Validate borrow rules (Owned types only, no escaping)
    - Mark last uses for drop insertion optimization
    - Validate parameter passing semantics (owned vs borrowed)
    """
    
    def __init__(
        self,
        ast: ASTNode,
        source_file: Optional[str] = None,
        source_code: Optional[str] = None,
        check_references: bool = False,
    ):
        self.ast = ast
        self.source_file = source_file
        self.source_code = source_code
        # When the entry file has imports, the parser could not resolve
        # callees/base classes/imported members while parsing it (they only
        # exist after import merging), so those checks happen here instead,
        # against the merged AST. Off for standalone files (std/internal)
        # whose cross-file callees are not visible in their own AST.
        self.check_references = check_references

        # Definitions found in the (merged) AST, for call/inheritance checks.
        self.function_defs: Dict[str, ASTNode] = {}
        self.class_defs: Dict[str, ASTNode] = {}
        self.method_defs: Dict[Tuple[str, str], ASTNode] = {}
        self.errors: List[CompileTimeError] = []
        
        # Stack of scopes; each scope maps variable name -> BindingInfo
        self.scope_stack: List[Dict[str, BindingInfo]] = [{}]
        
        # Track active borrows per scope
        self.active_borrows: List[BorrowInfo] = []
        
        # Track which nodes represent moves (for diagnostics)
        self.move_nodes: Set[ASTNode] = set()
        
        # Track last uses for drop insertion
        self.last_uses: Dict[str, ASTNode] = {}

        # Track if we're currently in a move context (to skip use-after-move check on RHS)
        self._in_move_rhs: bool = False

        # Track function signatures: func_name -> list of (param_name, param_type, is_array, is_borrowed)
        self.function_signatures: Dict[str, List[Tuple[str, str, bool, bool]]] = {}

        # Track class method signatures: (class_name, method_name) ->
        # list of (param_name, param_type, is_array, is_borrowed), excluding receiver.
        self.method_signatures: Dict[Tuple[str, str], List[Tuple[str, str, bool, bool]]] = {}

        # Track enum variants: enum_name -> {variant_name -> [(field_name, field_type), ...]}
        # (declaration order preserved; empty list means a tag-only variant).
        self.enum_variants: Dict[str, Dict[str, List[Tuple[str, str]]]] = {}

        # Track callable analysis context for validating return semantics.
        # Each frame stores: (return_type, borrowed_parameter_names, receiver_is_mutable).
        # receiver_is_mutable is False for &this (read-only), True for &mut this or no receiver.
        self.callable_stack: List[Tuple[Optional[str], Set[str], bool]] = []
        # Parallel to callable_stack: the borrowed parameters declared `&mut`
        # (a plain `&` parameter is a read-only view).
        self._mutable_borrow_stack: List[Set[str]] = []

    def report_error(self, err: CompileTimeError, node: Optional[ASTNode] = None) -> None:
        """Record a semantic error object with source location, mirroring Parser.report_error()."""
        if node is None or self.source_code is None:
            if not err.source_file:
                err.source_file = self.source_file
            logging.error(err)
            self.errors.append(err)
            return
        try:
            line_num, column_num = get_line_and_coumn_from_index(self.source_code, node.index)
            line_text = get_line(self.source_code, line_num)
            err.line = line_num
            err.column = column_num
            err.snippet = line_text
            if not err.source_file:
                err.source_file = self.source_file
            logging.error(err)
            self.errors.append(err)
        except (IndexError, ValueError):
            if not err.source_file:
                err.source_file = self.source_file
            logging.error(err)
            self.errors.append(err)

    def error(self, text: str, node: Optional[ASTNode] = None) -> None:
        self.report_error(SemanticError(message=text, source_file=self.source_file), node=node)
    
    def analyze(self) -> bool:
        """
        Run semantic analysis on the AST.
        Returns True if no errors, False otherwise.
        """
        # First pass: collect function signatures
        self._collect_function_signatures(self.ast)
        if self.check_references:
            self._check_class_hierarchy()

        # Second pass: analyze ownership and borrows
        self._analyze_node(self.ast)
        return len(self.errors) == 0
    
    def _collect_function_signatures(self, node: ASTNode) -> None:
        """First pass: collect all function signatures for parameter checking."""
        if node is None:
            return
            
        if node.node_type in (NodeTypes.FUNCTION_DEFINITION, NodeTypes.GENERATOR_DEFINITION):
            func_name = node.name
            params = []
            for child in node.children:
                if child.node_type == NodeTypes.PARAMETER:
                    param_name = child.name
                    param_type = child.var_type or "int32"
                    is_array = child.is_array
                    is_borrowed = getattr(child, "is_borrowed", False)
                    params.append((param_name, param_type, is_array, is_borrowed))
            self.function_signatures[func_name] = params
            self.function_defs[func_name] = node
            # Don't recurse into function body - we only need signatures
            return

        if node.node_type == NodeTypes.CLASS_DEFINITION:
            class_name = node.name
            self.class_defs[class_name] = node
            for child in node.children:
                if child.node_type != NodeTypes.CLASS_METHOD_DEFINITION:
                    continue
                self.method_defs[(class_name, child.name)] = child
                method_params = []
                receiver_consumed = False
                for mchild in child.children:
                    if mchild.node_type != NodeTypes.PARAMETER:
                        continue
                    is_receiver = bool(getattr(mchild, "is_receiver", False)) or mchild.name == "this"
                    if is_receiver and not receiver_consumed:
                        receiver_consumed = True
                        continue
                    param_name = mchild.name
                    param_type = mchild.var_type or "int32"
                    is_array = mchild.is_array
                    is_borrowed = getattr(mchild, "is_borrowed", False)
                    method_params.append((param_name, param_type, is_array, is_borrowed))
                self.method_signatures[(class_name, child.name)] = method_params

            # Don't recurse into method bodies during signature collection.
            return

        if node.node_type == NodeTypes.ENUM_DEFINITION:
            self.enum_variants[node.name] = {
                member.name: list(getattr(member, "payload_fields", []) or [])
                for member in node.children
                if member.node_type == NodeTypes.ENUM_VARIANT
            }
            return

        # Recurse for non-function nodes
        if hasattr(node, 'children'):
            for child in node.children:
                self._collect_function_signatures(child)
    
    # -- type-level checks on the merged AST ----------------------------------

    def _invalid_type(self, message: str, node: Optional[ASTNode]) -> None:
        self.report_error(InvalidTypeError(detail=message, source_file=self.source_file), node)

    def _type_of(self, node: Optional[ASTNode]) -> Optional[str]:
        """Best-effort type string of an expression (None when unknown)."""
        if node is None:
            return None
        if node.node_type == NodeTypes.IDENTIFIER:
            binding = self._lookup_binding(node.name)
            if binding is not None and binding.var_type:
                return f"{binding.var_type}[]" if binding.is_array else binding.var_type
            return None
        rt = getattr(node, "return_type", None)
        return rt if isinstance(rt, str) and rt else None

    @staticmethod
    def _split_type_args(type_str: str) -> Tuple[str, List[str]]:
        """'Pair<int32, Box<string>>' -> ('Pair', ['int32', 'Box<string>'])."""
        if "<" not in type_str or not type_str.endswith(">"):
            return type_str, []
        base, rest = type_str.split("<", 1)
        inner = rest[:-1]
        args: List[str] = []
        depth = 0
        cur = ""
        for ch in inner:
            if ch == "<":
                depth += 1
            elif ch == ">":
                depth -= 1
            if ch == "," and depth == 0:
                args.append(cur.strip())
                cur = ""
            else:
                cur += ch
        if cur.strip():
            args.append(cur.strip())
        return base, args

    def _is_subclass(self, actual: str, expected: str) -> bool:
        seen: Set[str] = set()
        cur = actual
        while cur and cur not in seen:
            seen.add(cur)
            cdef = self.class_defs.get(cur)
            cur = getattr(cdef, "base_class", None) if cdef is not None else None
            if cur == expected:
                return True
        return False

    def _argument_problem(
        self, expected: str, expected_nullable: bool, arg: ASTNode, actual: Optional[str],
        null_is_error: bool,
    ) -> Tuple[str, str]:
        """("ok"|"mismatch"|"null"|"range", detail) for passing `arg` to a
        parameter of type `expected`. Unknown types are accepted."""
        if actual is None:
            return "ok", ""
        if actual == "null":
            return ("null", "") if (null_is_error and not expected_nullable) else ("ok", "")
        applied, err = coerce_literal(arg, expected)
        if applied:
            return ("range", err) if err else ("ok", "")
        norm = lambda t: t.replace(" ", "")
        a = norm(actual[:-1] if actual.endswith("?") else actual)
        e = norm(expected[:-1] if expected.endswith("?") else expected)
        if a == e or self._is_subclass(a, e):
            return "ok", ""
        return "mismatch", ""

    def _check_call_arguments(
        self,
        call: ASTNode,
        args: List[ASTNode],
        params: List[ASTNode],
        subst: Dict[str, str],
        what: str,
        null_is_error: bool,
        check_types: bool = True,
    ) -> None:
        """Argument count and type checks for a call whose callee was only
        resolvable after import merging."""
        if len(args) != len(params):
            self._invalid_type(
                f"{what[0].upper()}{what[1:]} expected {len(params)} argument(s), got {len(args)}", call
            )
            return
        if not check_types:
            return
        for i, (param, arg) in enumerate(zip(params, args)):
            base = param.var_type or ""
            # Substitute type parameters word by word ("Pair<K, V>" -> "Pair<int32, string>").
            expected = re.sub(r"\w+", lambda m: subst.get(m.group(0), m.group(0)), base)
            if param.is_array:
                expected += "[]"
            actual = self._type_of(arg)
            if actual is not None and subst and any(
                tp in re.findall(r"\w+", actual) for tp in subst
            ):
                continue
            kind, detail = self._argument_problem(
                expected, bool(param.is_nullable), arg, actual, null_is_error
            )
            if kind == "mismatch":
                self._invalid_type(f"Argument {i + 1} for {what} expected type {expected}, got {actual}", arg)
            elif kind == "null":
                self._invalid_type(
                    f"Argument {i + 1} for {what} cannot be null: parameter type {expected} is not nullable", arg
                )
            elif kind == "range":
                self._invalid_type(detail, arg)

    def _is_known_callee(self, name: str) -> bool:
        from parser.base import ParserBase
        from ast_to_fir import INTRINSIC_RETURN_TYPES, DIRECTIVE_GATED_INTRINSICS

        return (
            name in self.class_defs
            or name in ParserBase.builtin_functions
            or name in INTRINSIC_RETURN_TYPES
            or name in DIRECTIVE_GATED_INTRINSICS
            or "<" in name
        )

    def _check_function_call(self, node: ASTNode) -> None:
        """A free-function call in a file whose imports were resolved after
        parsing: the callee must exist, be a function, and receive
        arguments matching its signature."""
        name = node.name
        fdef = self.function_defs.get(name)
        if fdef is None:
            if not self.check_references or self._is_known_callee(name):
                return
            if self._lookup_binding(name) is not None:
                self._invalid_type(f"'{name}' is a variable, not a function; it cannot be called", node)
            else:
                self.report_error(
                    InvalidExpressionError(detail=f"Function '{name}' is not defined", source_file=self.source_file),
                    node,
                )
            return
        if getattr(node, "_signature_checked", False) or not self.check_references:
            return
        params = [c for c in fdef.children if c.node_type == NodeTypes.PARAMETER]
        subst: Dict[str, str] = {}
        check_types = True
        if fdef.type_params:
            if node.type_args and len(node.type_args) == len(fdef.type_params):
                subst = dict(zip(fdef.type_params, node.type_args))
            else:
                check_types = False  # type arguments are inferred later; count only
        self._check_call_arguments(
            node, node.children, params, subst, f"function '{name}'", True, check_types
        )

    def _check_method_call(self, node: ASTNode, receiver_type: Optional[str]) -> None:
        """Argument checks for an instance-method call on a class that was
        only resolvable after import merging (e.g. an imported generic class
        such as `ArrayList<int32>`)."""
        if not self.check_references or getattr(node, "_signature_checked", False) or not receiver_type:
            return
        base, targs = self._split_type_args(receiver_type[:-1] if receiver_type.endswith("?") else receiver_type)
        cdef = self.class_defs.get(base)
        mdef = self.method_defs.get((base, node.name))
        if cdef is None or mdef is None or bool(getattr(mdef, "is_static", False)):
            return
        class_params = list(getattr(cdef, "type_params", []) or [])
        if class_params and len(targs) != len(class_params):
            return
        params = [
            c for c in mdef.children
            if c.node_type == NodeTypes.PARAMETER
            and not (bool(getattr(c, "is_receiver", False)) or c.name == "this")
        ]
        if getattr(mdef, "type_params", None):
            return  # method-level generics are resolved at monomorphization
        self._check_call_arguments(
            node, node.children[1:], params, dict(zip(class_params, targs)),
            f"method '{node.name}'", False,
        )

    def _check_class_hierarchy(self) -> None:
        """Unknown base classes and inheritance cycles, across the merged AST."""
        for name, cdef in self.class_defs.items():
            base = getattr(cdef, "base_class", None)
            if not base or base == name:
                continue
            base_name = base.split("<", 1)[0]
            if base_name not in self.class_defs:
                self._invalid_type(f"Unknown base class '{base}' for class '{name}'", cdef)
                continue
            seen = {name}
            cur: Optional[str] = base_name
            while cur:
                if cur in seen:
                    if cur == name:
                        self._invalid_type(
                            f"Cyclic inheritance: class '{name}' (indirectly) inherits from itself", cdef
                        )
                    break
                seen.add(cur)
                nxt = self.class_defs.get(cur)
                cur_base = getattr(nxt, "base_class", None) if nxt is not None else None
                cur = cur_base.split("<", 1)[0] if cur_base else None

    def _current_scope(self) -> Dict[str, BindingInfo]:
        """Get the current (innermost) scope."""
        return self.scope_stack[-1]
    
    def _enter_scope(self) -> None:
        """Enter a new lexical scope."""
        self.scope_stack.append({})
    
    def _exit_scope(self) -> None:
        """Exit the current scope."""
        if len(self.scope_stack) > 1:
            scope_depth = len(self.scope_stack)
            # Remove borrows that are going out of scope
            self.active_borrows = [
                b for b in self.active_borrows if b.scope_depth < scope_depth
            ]
            self.scope_stack.pop()
    
    def _lookup_binding(self, name: str) -> Optional[BindingInfo]:
        """Look up a binding in the scope stack (inner to outer)."""
        for scope in reversed(self.scope_stack):
            if name in scope:
                return scope[name]
        return None
    
    def _register_binding(
        self,
        name: str,
        var_type: Optional[str],
        is_array: bool,
        node: ASTNode,
        is_borrowed: bool = False,
    ) -> None:
        """Register a new binding in the current scope."""
        self._current_scope()[name] = BindingInfo(
            name, var_type, is_array, is_borrowed, OwnershipState.VALID, node
        )

    def _is_illegal_borrow_move(self, binding: BindingInfo, use_node: ASTNode) -> bool:
        """Return True if this binding cannot be moved because it is borrowed."""
        if binding.is_borrowed and is_owned(binding.var_type, binding.is_array):
            self.report_error(
                SemanticError(message=f"Cannot move borrowed value '{binding.name}'; borrowed values cannot transfer ownership"),
                use_node,
            )
            return True
        return False

    def _is_direct_borrow_view(self, node: Optional[ASTNode], borrowed_params: Set[str]) -> bool:
        """Return True when expression is a direct borrowed view rooted at a borrowed parameter.

        This includes:
        - borrowed identifier: s
        - field projection of borrowed value: s.field
        - array projection of borrowed value: s[i]
        """
        if node is None:
            return False

        if node.node_type == NodeTypes.IDENTIFIER:
            return node.name in borrowed_params

        if node.node_type == NodeTypes.FIELD_ACCESS and node.children:
            return self._is_direct_borrow_view(node.children[0], borrowed_params)

        if node.node_type == NodeTypes.ARRAY_ACCESS and node.children:
            return self._is_direct_borrow_view(node.children[0], borrowed_params)

        return False

    def _is_read_only_borrowed_param(self, name: str) -> bool:
        """True if `name` is a plain `&` (non-`&mut`) borrowed parameter of
        the callable being analyzed (docs/reference/memory_management.md,
        section 4: a borrow is a read-only view)."""
        if not self.callable_stack or not self._mutable_borrow_stack:
            return False
        binding = self._lookup_binding(name)
        return (
            name in self._current_borrowed_params()
            and name not in self._mutable_borrow_stack[-1]
            and binding is not None
            and binding.is_borrowed
        )

    def _check_borrow_write(self, node: ASTNode) -> None:
        """`lhs = rhs` where lhs is a field/element: it must not write
        through a read-only borrowed parameter, and the stored value must
        not be a borrowed view (a borrow cannot be retained in a field)."""
        if len(node.children) != 2:
            return
        lhs, rhs = node.children
        root = lhs
        while root is not None and root.node_type in (NodeTypes.FIELD_ACCESS, NodeTypes.ARRAY_ACCESS) and root.children:
            root = root.children[0]
        if (
            root is not None
            and root is not lhs
            and root.node_type == NodeTypes.IDENTIFIER
            and self._is_read_only_borrowed_param(root.name)
        ):
            self.report_error(
                SemanticError(
                    message=(
                        f"Cannot mutate through borrowed parameter '{root.name}'; a '&' borrow is "
                        f"read-only (declare it '&mut' to allow mutation)"
                    )
                ),
                node,
            )
        if lhs.node_type == NodeTypes.FIELD_ACCESS and self._expr_is_owned_value(rhs):
            borrowed_params = self._current_borrowed_params()
            is_borrow = False
            if rhs.node_type == NodeTypes.IDENTIFIER:
                binding = self._lookup_binding(rhs.name)
                is_borrow = bool(binding and binding.is_borrowed)
            else:
                is_borrow = self._is_direct_borrow_view(rhs, borrowed_params)
            if is_borrow:
                self.report_error(
                    SemanticError(
                        message="Cannot store a borrowed value in a field; borrowed values cannot outlive the borrow"
                    ),
                    rhs,
                )

    def _check_mutating_call_on_borrow(self, node: ASTNode, receiver: ASTNode, receiver_type: Optional[str]) -> None:
        """Calling a `&mut this` method needs a mutable receiver: reject it on
        a read-only `&` parameter or from inside a `&this` method."""
        if receiver.node_type != NodeTypes.IDENTIFIER or not receiver_type or not self.callable_stack:
            return
        base = self._split_type_args(receiver_type)[0]
        mdef = self.method_defs.get((base, node.name))
        if mdef is None or bool(getattr(mdef, "is_static", False)):
            return
        callee_receiver = next(
            (p for p in mdef.children if p.node_type == NodeTypes.PARAMETER
             and (bool(getattr(p, "is_receiver", False)) or p.name == "this")),
            None,
        )
        if callee_receiver is None or not bool(getattr(callee_receiver, "is_mutable_borrow", False)):
            return
        if receiver.name == "this":
            read_only = not self.callable_stack[-1][2]
        else:
            read_only = self._is_read_only_borrowed_param(receiver.name)
        if read_only:
            self.report_error(
                SemanticError(
                    message=(
                        f"Cannot call '&mut this' method '{node.name}' on read-only borrowed "
                        f"receiver '{receiver.name}'"
                    )
                ),
                node,
            )

    def _current_borrowed_params(self) -> Set[str]:
        """Get borrowed parameter names for the currently analyzed callable."""
        if not self.callable_stack:
            return set()
        return self.callable_stack[-1][1]

    def _is_illegal_borrow_view_move(self, expr: Optional[ASTNode], use_node: ASTNode) -> bool:
        """Return True when an expression tries to move from a borrowed view."""
        borrowed_params = self._current_borrowed_params()
        if not borrowed_params:
            return False

        if self._is_direct_borrow_view(expr, borrowed_params) and self._expr_is_owned_value(expr):
            self.report_error(
                SemanticError(message="Cannot move borrowed value; borrowed values cannot transfer ownership"),
                use_node,
            )
            return True

        return False

    def _expr_is_owned_value(self, node: Optional[ASTNode]) -> bool:
        """Best-effort check for whether an expression denotes an Owned value."""
        if node is None:
            return False

        if node.node_type == NodeTypes.IDENTIFIER:
            binding = self._lookup_binding(node.name)
            if binding:
                return is_owned(binding.var_type, binding.is_array)

        expr_type = getattr(node, "return_type", None)
        if isinstance(expr_type, str) and expr_type:
            if expr_type.endswith("[]"):
                return is_owned(expr_type[:-2], True)
            return is_owned(expr_type, False)

        return False

    def _builtin_method_sig(self, family: str, method_name: str) -> Optional[List[Tuple[str, str, bool, bool]]]:
        """Look up a @builtin_method's public (non-receiver, non-length)
        parameter signature, shaped to match method_signatures'
        (param_name, param_type, is_array, is_borrowed) convention -- so a
        real call like `.count(needle)` gets real ownership/move checking
        on `needle` instead of the historical silent skip for unregistered
        callees."""
        from builtin_methods import get_builtin_method_registry

        spec = get_builtin_method_registry().lookup(family, method_name)
        if spec is None:
            return None
        return [
            ("", ptype, ptype.endswith("[]"), pmode in ("borrow", "borrow_mut"))
            for ptype, pmode in zip(spec.public_param_types, spec.public_param_modes)
        ]

    def _analyze_call_args_with_signature(
        self,
        args: List[ASTNode],
        sig: Optional[List[Tuple[str, str, bool, bool]]],
        call_node: ASTNode,
    ) -> None:
        """Analyze call arguments and apply move semantics from a callable signature.

        Signature tuple shape: (param_name, param_type, is_array, is_borrowed).
        """
        for i, arg in enumerate(args):
            self._analyze_node(arg)

            if sig is None or i >= len(sig):
                continue

            _, _, _, param_is_borrowed = sig[i]
            if not param_is_borrowed:
                if arg.node_type == NodeTypes.IDENTIFIER:
                    arg_binding = self._lookup_binding(arg.name)
                    if arg_binding and is_owned(arg_binding.var_type, arg_binding.is_array):
                        if not self._is_illegal_borrow_move(arg_binding, arg):
                            self._mark_moved(arg.name, call_node)
                else:
                    self._is_illegal_borrow_view_move(arg, arg)
    
    def _mark_moved(self, name: str, move_node: ASTNode) -> None:
        """Mark a binding as moved (invalidated)."""
        binding = self._lookup_binding(name)
        if binding:
            binding.state = OwnershipState.MOVED
            binding.move_node = move_node
            self.move_nodes.add(move_node)
    
    def _check_use_after_move(self, name: str, use_node: ASTNode) -> None:
        """Check if a use occurs after ownership was moved."""
        binding = self._lookup_binding(name)
        if binding and binding.state == OwnershipState.MOVED:
            logging.debug(f"Use-after-move detected: {name} in node type {use_node.node_type}")
            self.report_error(
                SemanticError(message=f"Use-after-move error: variable '{name}' was moved, cannot use it here"),
                use_node,
            )
        elif binding and binding.state == OwnershipState.MAYBE_MOVED:
            self.report_error(
                SemanticError(message=f"Use-after-move error: variable '{name}' may have been moved on another control-flow path"),
                use_node,
            )

    def _snapshot_binding_states(self) -> Dict[BindingInfo, OwnershipState]:
        """Capture ownership states for all currently visible bindings."""
        snap: Dict[BindingInfo, OwnershipState] = {}
        for scope in self.scope_stack:
            for binding in scope.values():
                snap[binding] = binding.state
        return snap

    def _restore_binding_states(self, snapshot: Dict[BindingInfo, OwnershipState]) -> None:
        """Restore ownership states for bindings present in a snapshot."""
        for binding, state in snapshot.items():
            binding.state = state

    def _merge_state_pair(self, a: OwnershipState, b: OwnershipState) -> OwnershipState:
        """Merge ownership states from two control-flow paths."""
        if a == b:
            return a
        movedish = {OwnershipState.MOVED, OwnershipState.MAYBE_MOVED}
        if a in movedish and b in movedish:
            # If both paths move (or maybe move), treat as moved after join.
            return OwnershipState.MOVED
        if a in movedish or b in movedish:
            return OwnershipState.MAYBE_MOVED
        if OwnershipState.BORROWED in (a, b):
            return OwnershipState.BORROWED
        return OwnershipState.VALID

    def _definitely_terminates(self, node: Optional[ASTNode]) -> bool:
        """Return True if this node definitely exits current control flow."""
        if node is None:
            return False

        if node.node_type in (NodeTypes.RETURN_STATEMENT, NodeTypes.BREAK_STATEMENT, NodeTypes.CONTINUE_STATEMENT):
            return True

        if node.node_type == NodeTypes.SCOPE:
            for child in node.children:
                if self._definitely_terminates(child):
                    return True
            return False

        if node.node_type == NodeTypes.IF_STATEMENT:
            if len(node.children) < 2:
                return False
            then_branch = node.children[1]
            else_branch = node.children[2] if len(node.children) > 2 else None
            if else_branch is None:
                return False
            return self._definitely_terminates(then_branch) and self._definitely_terminates(else_branch)

        return False

    def _contains_loop_break(self, node: Optional[ASTNode]) -> bool:
        """True if a `break` that targets the loop whose body is `node`
        appears in it (breaks inside nested loops belong to those loops)."""
        if node is None:
            return False
        if node.node_type == NodeTypes.BREAK_STATEMENT:
            return True
        if node.node_type in (NodeTypes.WHILE_STATEMENT, NodeTypes.FOR_STATEMENT, NodeTypes.FOR_IN_STATEMENT):
            return False
        return any(self._contains_loop_break(c) for c in node.children if c is not None)

    @staticmethod
    def _is_true_literal(node: Optional[ASTNode]) -> bool:
        return (
            node is not None
            and node.node_type == NodeTypes.LITERAL
            and getattr(node, "return_type", None) == "bool"
            and node.name == "true"
        )

    def _always_returns(self, node: Optional[ASTNode]) -> bool:
        """Conservative all-paths-return analysis: True only if control can
        never fall off the end of `node` (every path returns, or the end is
        unreachable because of an infinite loop)."""
        if node is None:
            return False
        nt = node.node_type
        if nt == NodeTypes.RETURN_STATEMENT:
            return True
        if nt == NodeTypes.SCOPE:
            return any(self._always_returns(c) for c in node.children)
        if nt == NodeTypes.IF_STATEMENT:
            if len(node.children) < 3:
                return False
            return self._always_returns(node.children[1]) and self._always_returns(node.children[2])
        if nt == NodeTypes.WHILE_STATEMENT and len(node.children) >= 2:
            return self._is_true_literal(node.children[0]) and not self._contains_loop_break(node.children[1])
        if nt == NodeTypes.FOR_STATEMENT and len(node.children) >= 4:
            cond = node.children[1]
            no_cond = cond is None or (cond.node_type == NodeTypes.LITERAL and cond.name == "empty")
            return (no_cond or self._is_true_literal(cond)) and not self._contains_loop_break(node.children[3])
        if nt == NodeTypes.MATCH_EXPRESSION:
            arms = node.children[1:]
            return bool(arms) and all(
                a.children and self._always_returns(a.children[0]) for a in arms
            )
        return False

    def _check_missing_return(self, node: ASTNode) -> None:
        """A non-void function/method must return on every control-flow path
        (constructors and generators are exempt)."""
        if node.node_type == NodeTypes.GENERATOR_DEFINITION or getattr(node, "is_constructor", False):
            return
        ret = getattr(node, "return_type", None)
        if ret is None or ret == "void" or ret.startswith("generator<"):
            return
        body = next((c for c in node.children if c.node_type == NodeTypes.SCOPE), None)
        if body is None or self._always_returns(body):
            return
        kind = "Method" if node.node_type == NodeTypes.CLASS_METHOD_DEFINITION else "Function"
        self.report_error(
            MissingReturnError(kind=kind, name=node.name, return_type=ret),
            node,
        )

    # Types a match scrutinee can definitely never have as an enum.
    _NON_ENUM_TYPES = frozenset(
        {
            "int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64",
            "float32", "float64", "float128", "bool", "char", "string", "void",
        }
    )

    def _always_exits_loop(self, node: Optional[ASTNode]) -> bool:
        """True if every path through `node` leaves the enclosing loop for
        good (`break` or `return`), so nothing moved in it is seen again."""
        if node is None:
            return False
        if node.node_type in (NodeTypes.BREAK_STATEMENT, NodeTypes.RETURN_STATEMENT):
            return True
        if node.node_type == NodeTypes.SCOPE:
            return any(self._always_exits_loop(c) for c in node.children)
        if node.node_type == NodeTypes.IF_STATEMENT and len(node.children) > 2:
            return self._always_exits_loop(node.children[1]) and self._always_exits_loop(node.children[2])
        return False

    def _check_loop_carried_moves(
        self,
        before: Dict[BindingInfo, OwnershipState],
        after: Dict[BindingInfo, OwnershipState],
        body: Optional[ASTNode],
        fresh_each_iteration: Optional[ASTNode] = None,
    ) -> None:
        """A variable declared outside a loop that the loop body moves is
        moved again (use-after-move) on the next iteration, unless the body
        always leaves the loop right after. A for-in loop variable
        (`fresh_each_iteration`, its declaration) is a new value every
        iteration and may be moved freely."""
        if self._always_exits_loop(body):
            return
        for binding, state_before in before.items():
            if state_before != OwnershipState.VALID:
                continue
            if fresh_each_iteration is not None and binding.declaration_node is fresh_each_iteration:
                continue
            if after.get(binding) in (OwnershipState.MOVED, OwnershipState.MAYBE_MOVED) and binding.move_node is not None:
                self.report_error(
                    SemanticError(
                        message=(
                            f"Use-after-move error: variable '{binding.name}' is moved inside a loop "
                            f"and would be used again on the next iteration"
                        )
                    ),
                    binding.move_node,
                )

    def _validate_match_arms(self, match_node: ASTNode, arms: List[ASTNode]) -> None:
        """Check exhaustiveness, duplicate variants, wildcard placement, and
        binding arity for a match expression's arms."""
        if not arms:
            self.report_error(
                SemanticError(message="'match' must have at least one arm"), match_node
            )
            return

        seen_variants: Set[str] = set()
        wildcard_seen = False
        enum_name: Optional[str] = None

        # The scrutinee must be a value of an enum type, and every pattern
        # must name that same enum.
        scrutinee = match_node.children[0] if match_node.children else None
        scrutinee_type = self._type_of(scrutinee)
        scrutinee_enum: Optional[str] = None
        wrong_enum_arm = False
        if scrutinee_type is not None:
            base_t = scrutinee_type[:-1] if scrutinee_type.endswith("?") else scrutinee_type
            if base_t in self.enum_variants:
                scrutinee_enum = base_t
                enum_name = base_t
            elif base_t.endswith("[]") or base_t in self._NON_ENUM_TYPES or base_t in self.class_defs:
                self._invalid_type(
                    f"Cannot match on a value of type {scrutinee_type}: 'match' requires an enum value",
                    scrutinee,
                )
                return

        for arm in arms:
            is_wildcard = bool(getattr(arm, "is_wildcard", False))

            if wildcard_seen:
                self.report_error(
                    SemanticError(message="Unreachable match arm: a wildcard '_' arm must be last"),
                    arm,
                )

            if is_wildcard:
                wildcard_seen = True
                continue

            arm_enum_name = getattr(arm, "enum_name", None)
            variant_name = getattr(arm, "variant_name", None)

            if enum_name is None:
                enum_name = arm_enum_name
            elif arm_enum_name and arm_enum_name != enum_name:
                if scrutinee_enum is not None:
                    message = (
                        f"Match arm pattern '{arm_enum_name}.{variant_name}' does not match "
                        f"the scrutinee's enum type '{scrutinee_enum}'"
                    )
                else:
                    message = (
                        f"Match arm pattern '{arm_enum_name}.{variant_name}' does not match "
                        f"enum type '{enum_name}' used by earlier arms"
                    )
                self.report_error(SemanticError(message=message), arm)
                wrong_enum_arm = True

            if arm_enum_name not in self.enum_variants:
                self.report_error(
                    SemanticError(message=f"Unknown enum type '{arm_enum_name}' in match pattern"),
                    arm,
                )
                continue

            variant_payloads = self.enum_variants[arm_enum_name]
            if variant_name not in variant_payloads:
                self.report_error(
                    SemanticError(message=f"Unknown variant '{variant_name}' in enum '{arm_enum_name}'"),
                    arm,
                )
                continue

            if variant_name in seen_variants:
                self.report_error(
                    SemanticError(
                        message=f"Duplicate match arm for variant '{arm_enum_name}.{variant_name}'"
                    ),
                    arm,
                )
            seen_variants.add(variant_name)

            bindings = getattr(arm, "bindings", []) or []
            field_names = {fname for fname, _ in variant_payloads[variant_name]}
            seen_fields: Set[str] = set()
            for field_name, _local_name in bindings:
                if field_name not in field_names:
                    self.report_error(
                        SemanticError(
                            message=(
                                f"Variant '{arm_enum_name}.{variant_name}' has no payload field "
                                f"'{field_name}'"
                            )
                        ),
                        arm,
                    )
                    continue
                if field_name in seen_fields:
                    self.report_error(
                        SemanticError(
                            message=(
                                f"Field '{field_name}' is bound more than once in this match pattern"
                            )
                        ),
                        arm,
                    )
                seen_fields.add(field_name)

        if (
            enum_name is not None
            and enum_name in self.enum_variants
            and not wildcard_seen
            and not wrong_enum_arm
        ):
            missing = set(self.enum_variants[enum_name].keys()) - seen_variants
            if missing:
                missing_list = ", ".join(sorted(missing))
                self.report_error(
                    SemanticError(
                        message=(
                            f"Non-exhaustive match on enum '{enum_name}': missing variant(s) "
                            f"{missing_list} (add arms for them or a trailing '_' wildcard)"
                        )
                    ),
                    match_node,
                )

    def _register_match_arm_bindings(self, arm: ASTNode) -> None:
        """Register a match arm's payload bindings as borrowed values scoped
        to the arm body. Bindings resolve by declared field name (optionally
        renamed via `field: local`) and are read-only borrows by default
        (like `&this`); explicit move-out-of-payload syntax is a planned
        follow-up."""
        bindings = getattr(arm, "bindings", []) or []
        if not bindings:
            return
        enum_name = getattr(arm, "enum_name", None)
        variant_name = getattr(arm, "variant_name", None)
        payload_fields = dict(self.enum_variants.get(enum_name or "", {}).get(variant_name or "", []))
        for field_name, local_name in bindings:
            bind_type = payload_fields.get(field_name)
            self._register_binding(local_name, bind_type, False, arm, is_borrowed=True)

    def _validate_borrow(
        self,
        var_type: Optional[str],
        is_array: bool,
        node: ASTNode,
    ) -> None:
        """Validate that borrowing is only used on Owned types.
        
        Exception: Generic type parameters (single capital letter like T, U, etc.)
        are allowed to be borrowed - Copyable values will be implicitly copied
        while Owned values will be borrowed.
        """
        # Allow borrowing of generic type parameters (T, U, etc.)
        if var_type and len(var_type) == 1 and var_type.isupper():
            return  # Generic type parameter - skip validation
            
        if not is_owned(var_type, is_array):
            type_str = f"{var_type}[]" if is_array else var_type
            self.report_error(
                SemanticError(
                    message=(
                        f"Cannot borrow Copyable type '{type_str}'; pass by value instead. "
                        f"Borrowing is only allowed for Owned types."
                    )
                ),
                node,
            )

    def _analyze_callable_definition(self, node: ASTNode) -> None:
        """Analyze a function-like definition with parameters and body scope."""
        borrowed_params: Set[str] = set()
        mutable_borrowed: Set[str] = set()
        receiver_is_mutable = True  # default: no receiver means no mutation restriction
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER and getattr(child, "is_borrowed", False):
                if bool(getattr(child, "is_receiver", False)) or child.name == "this":
                    # Determine receiver mutability: &mut this → mutable, &this → read-only
                    receiver_is_mutable = bool(getattr(child, "is_mutable_borrow", False))
                else:
                    borrowed_params.add(child.name)
                    if getattr(child, "is_mutable_borrow", False):
                        mutable_borrowed.add(child.name)

        self._mutable_borrow_stack.append(mutable_borrowed)
        self.callable_stack.append((getattr(node, "return_type", None), borrowed_params, receiver_is_mutable))
        self._enter_scope()
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER:
                is_borrowed = getattr(child, "is_borrowed", False)
                if is_borrowed:
                    self._validate_borrow(child.var_type, child.is_array, child)
                self._register_binding(
                    child.name,
                    child.var_type,
                    child.is_array,
                    child,
                    is_borrowed=is_borrowed,
                )
            elif child.node_type == NodeTypes.SCOPE:
                self._analyze_node(child)
        self._exit_scope()
        self.callable_stack.pop()
        self._mutable_borrow_stack.pop()
        self._check_missing_return(node)

    def _analyze_node(self, node: ASTNode) -> None:
        """Recursively analyze a node and its children."""
        if node is None:
            return
        
        # Variable declaration: register binding and check for moves in initializer
        if node.node_type == NodeTypes.VARIABLE_DECLARATION:
            # Check if RHS is a move (identifier of Owned type) BEFORE analyzing children
            # Copyable types are copied, not moved
            will_move = False
            if len(node.children) > 0:
                init_expr = node.children[0]
                if init_expr.node_type == NodeTypes.IDENTIFIER:
                    # Check if we're moving an Owned value (not Copyable)
                    source_binding = self._lookup_binding(init_expr.name)
                    if source_binding:
                        is_owned_value = is_owned(source_binding.var_type, source_binding.is_array)
                        if is_owned_value:
                            if self._is_illegal_borrow_move(source_binding, init_expr):
                                will_move = False
                            else:
                                will_move = True
                else:
                    self._is_illegal_borrow_view_move(init_expr, init_expr)
            
            # Analyze initializer (but mark that we're in a move context if needed)
            if will_move:
                self._in_move_rhs = True
            for child in node.children:
                self._analyze_node(child)
            if will_move:
                self._in_move_rhs = False
                # Now mark the source as moved AFTER analyzing
                init_expr = node.children[0]
                if init_expr.node_type == NodeTypes.IDENTIFIER:
                    self._mark_moved(init_expr.name, node)
            
            # Register the new binding
            self._register_binding(node.name, node.var_type, node.is_array, node)
        
        # Variable assignment: check for Owned type reassignment (drop old value)
        elif node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            # Check if target is valid (not moved)
            self._check_use_after_move(node.name, node)
            if self._is_read_only_borrowed_param(node.name):
                self.report_error(
                    SemanticError(
                        message=(
                            f"Cannot assign to borrowed parameter '{node.name}'; "
                            f"a borrow is a read-only view of the caller's value"
                        )
                    ),
                    node,
                )
            
            # Analyze RHS first
            for child in node.children:
                self._analyze_node(child)
            
            # Check if RHS is a move (identifier of Owned type)
            if len(node.children) > 0:
                rhs_expr = node.children[0]
                if rhs_expr.node_type == NodeTypes.IDENTIFIER:
                    # Check if we're moving an Owned value
                    source_binding = self._lookup_binding(rhs_expr.name)
                    if source_binding and is_owned(source_binding.var_type, source_binding.is_array):
                        if not self._is_illegal_borrow_move(source_binding, rhs_expr):
                            # This is a move - mark the source as moved
                            self._mark_moved(rhs_expr.name, node)
                else:
                    self._is_illegal_borrow_view_move(rhs_expr, rhs_expr)
            
            # Get target binding to check if we're dropping an Owned value
            binding = self._lookup_binding(node.name)
            if binding and is_owned(binding.var_type, binding.is_array):
                # Old value is being dropped (in practice, preprocessor will insert drop)
                pass
        
        # Identifier use: check for use-after-move unless we're in a move RHS context
        elif node.node_type == NodeTypes.IDENTIFIER:
            if not self._in_move_rhs:
                self._check_use_after_move(node.name, node)
            # Track as potential last use (will be refined by control flow analysis)
            binding = self._lookup_binding(node.name)
            if binding:
                binding.last_use_node = node
        
        # Function call: check parameter passing semantics
        elif node.node_type == NodeTypes.FUNCTION_CALL:
            # Special case: drop() calls are auto-inserted by preprocessor
            # We'll filter out invalid drops later, so don't check use-after-move here
            if node.name == "drop":
                # Skip analysis of drop() arguments to avoid false positives
                pass
            else:
                self._check_function_call(node)
                # Get function signature if available
                func_sig = self.function_signatures.get(node.name)

                # Constructor calls via Type(args) route through FUNCTION_CALL in the AST.
                if func_sig is None:
                    func_sig = self.method_signatures.get((node.name, node.name))

                self._analyze_call_args_with_signature(node.children, func_sig, node)

        # Method call: check parameter passing semantics for class methods
        elif node.node_type == NodeTypes.METHOD_CALL:
            if not node.children:
                return

            receiver = node.children[0]
            self._analyze_node(receiver)

            method_sig = None
            receiver_type: Optional[str] = None
            receiver_is_array = False
            if receiver.node_type == NodeTypes.IDENTIFIER:
                receiver_binding = self._lookup_binding(receiver.name)
                if receiver_binding:
                    receiver_type = receiver_binding.var_type
                    receiver_is_array = receiver_binding.is_array
            else:
                # A non-identifier receiver (e.g. a field access like
                # this.sink.take(...)) has no binding to look up -- fall
                # back to the type parser/type_system.py already resolved
                # onto the node, same as _expr_is_owned_value. Without
                # this, method_sig stayed None for any such receiver, so
                # _analyze_call_args_with_signature silently skipped move-
                # marking its "own"-mode arguments -- the semantic
                # analyzer's conclusions (which drop-insertion trusts)
                # never recorded the move, so an already-moved argument
                # got a second, erroneous auto-drop at scope end (FIRV-O2).
                expr_type = getattr(receiver, "return_type", None)
                if isinstance(expr_type, str) and expr_type:
                    if expr_type.endswith("[]"):
                        receiver_type = expr_type[:-2]
                        receiver_is_array = True
                    else:
                        receiver_type = expr_type

            if receiver_type is not None and not receiver_is_array:
                self._check_method_call(node, receiver_type)
                self._check_mutating_call_on_borrow(node, receiver, receiver_type)

            if receiver_type is not None:
                # Array/string dot-methods are @builtin_method-registered
                # (see builtin_methods.py), not user class methods -- and
                # must be checked ahead of the class-method lookup below,
                # since `method_signatures` keys on var_type alone and
                # doesn't distinguish e.g. a plain `string` from a
                # `string[]` (both would key on "string").
                if receiver_is_array:
                    method_sig = self._builtin_method_sig("array", node.name)
                elif receiver_type == "string":
                    method_sig = self._builtin_method_sig("string", node.name)
                else:
                    method_sig = self.method_signatures.get((receiver_type, node.name))

            args = node.children[1:]
            self._analyze_call_args_with_signature(args, method_sig, node)

        # Type-level method call (constructor/static-like): Type.method(args)
        elif node.node_type == NodeTypes.TYPE_METHOD_CALL:
            class_name = getattr(node, "class_name", None)
            method_name = node.name
            sig = None
            if class_name:
                sig = self.method_signatures.get((class_name, method_name))
            self._analyze_call_args_with_signature(node.children, sig, node)

        # Java-like constructor call: new Type(args)
        elif node.node_type == NodeTypes.CONSTRUCTOR_CALL:
            class_name = node.name
            sig = self.method_signatures.get((class_name, class_name))
            self._analyze_call_args_with_signature(node.children, sig, node)

        # Enum variant construction: EnumName.Variant(args). Payload fields
        # are always owned by value (no borrow syntax for them), so every
        # argument is unconditionally moved into the payload.
        elif node.node_type == NodeTypes.ENUM_VARIANT_CONSTRUCT:
            sig = [("", "", False, False) for _ in node.children]
            self._analyze_call_args_with_signature(node.children, sig, node)

        # Scope: enter/exit scope tracking
        elif node.node_type == NodeTypes.SCOPE:
            self._enter_scope()
            for child in node.children:
                self._analyze_node(child)
                if self._definitely_terminates(child):
                    break
            self._exit_scope()
        
        # Function definition: enter new scope for parameters and body
        elif node.node_type in (NodeTypes.FUNCTION_DEFINITION, NodeTypes.GENERATOR_DEFINITION):
            self._analyze_callable_definition(node)
        
        # Class definition: register class, analyze methods
        elif node.node_type == NodeTypes.CLASS_DEFINITION:
            # Class name is already registered by parser in user_classes
            # Analyze methods
            for child in node.children:
                if child.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
                    self._analyze_node(child)
        
        # Class method: similar to function
        elif node.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
            self._analyze_callable_definition(node)
        
        # Return statement: check that returned Owned values transfer ownership
        elif node.node_type == NodeTypes.RETURN_STATEMENT:
            for child in node.children:
                self._analyze_node(child)
            if self.callable_stack and node.children:
                ret_expr = node.children[0]
                _, borrowed_params, _ = self.callable_stack[-1]
                if self._is_direct_borrow_view(ret_expr, borrowed_params) and self._expr_is_owned_value(ret_expr):
                    self.report_error(
                        SemanticError(message="Cannot return borrowed value; borrowed values cannot escape callable scope"),
                        ret_expr,
                    )
        
        # If-statement: merge ownership states from then/else paths
        elif node.node_type == NodeTypes.IF_STATEMENT:
            if not node.children:
                return

            condition = node.children[0]
            then_branch = node.children[1] if len(node.children) > 1 else None
            else_branch = node.children[2] if len(node.children) > 2 else None

            # Condition executes before branching.
            if condition is not None:
                self._analyze_node(condition)

            base_snapshot = self._snapshot_binding_states()

            # Analyze then path.
            if then_branch is not None:
                self._analyze_node(then_branch)
            then_snapshot = self._snapshot_binding_states()
            then_terminates = self._definitely_terminates(then_branch)

            # Analyze else path from the same base state.
            self._restore_binding_states(base_snapshot)
            if else_branch is not None:
                self._analyze_node(else_branch)
            else_snapshot = self._snapshot_binding_states()
            else_terminates = self._definitely_terminates(else_branch)

            # If there's no else, false-path is the original base state.
            if else_branch is None:
                else_snapshot = base_snapshot
                else_terminates = False

            # Merge states back into live bindings after the if statement.
            # If one branch definitely terminates, only the non-terminating path
            # contributes to post-if state.
            if then_terminates and else_terminates:
                merged_sources = [base_snapshot]
            elif then_terminates:
                merged_sources = [else_snapshot]
            elif else_terminates:
                merged_sources = [then_snapshot]
            else:
                merged_sources = [then_snapshot, else_snapshot]

            all_bindings = set(base_snapshot.keys())
            for src in merged_sources:
                all_bindings |= set(src.keys())

            for binding in all_bindings:
                merged_state = None
                for src in merged_sources:
                    src_state = src.get(binding, base_snapshot.get(binding, binding.state))
                    merged_state = src_state if merged_state is None else self._merge_state_pair(merged_state, src_state)
                if merged_state is not None:
                    binding.state = merged_state

        # Match expression: validate patterns (exhaustiveness, duplicates,
        # wildcard order, binding arity), register payload bindings as
        # scoped borrows, and merge ownership states across arms (an N-way
        # generalization of the if/else merge above).
        elif node.node_type == NodeTypes.MATCH_EXPRESSION:
            if not node.children:
                return

            scrutinee = node.children[0]
            arms = node.children[1:]

            self._analyze_node(scrutinee)
            self._validate_match_arms(node, arms)

            base_snapshot = self._snapshot_binding_states()
            arm_results: List[Tuple[Dict[BindingInfo, OwnershipState], bool]] = []

            for arm in arms:
                self._restore_binding_states(base_snapshot)
                self._enter_scope()
                self._register_match_arm_bindings(arm)
                body = arm.children[0] if arm.children else None
                if body is not None:
                    self._analyze_node(body)
                terminates = self._definitely_terminates(body)
                self._exit_scope()
                arm_results.append((self._snapshot_binding_states(), terminates))

            non_terminating = [snap for snap, terminates in arm_results if not terminates]
            merged_sources = non_terminating if non_terminating else [base_snapshot]

            all_bindings = set(base_snapshot.keys())
            for src in merged_sources:
                all_bindings |= set(src.keys())

            for binding in all_bindings:
                merged_state = None
                for src in merged_sources:
                    src_state = src.get(binding, base_snapshot.get(binding, binding.state))
                    merged_state = src_state if merged_state is None else self._merge_state_pair(merged_state, src_state)
                if merged_state is not None:
                    binding.state = merged_state

        # While loop: body may execute zero or more times, so merge one-iteration
        # path with skip-loop path.
        elif node.node_type == NodeTypes.WHILE_STATEMENT:
            if not node.children:
                return

            condition = node.children[0] if len(node.children) > 0 else None
            body = node.children[1] if len(node.children) > 1 else None

            # Condition is evaluated at least once for entering the loop.
            if condition is not None:
                self._analyze_node(condition)

            base_snapshot = self._snapshot_binding_states()

            # One potential iteration path.
            if body is not None:
                self._analyze_node(body)
            iter_snapshot = self._snapshot_binding_states()
            self._check_loop_carried_moves(base_snapshot, iter_snapshot, body)

            # Restore and merge with the skip-loop path (base state).
            self._restore_binding_states(base_snapshot)
            all_bindings = set(base_snapshot.keys()) | set(iter_snapshot.keys())
            for binding in all_bindings:
                base_state = base_snapshot.get(binding, binding.state)
                iter_state = iter_snapshot.get(binding, base_state)
                binding.state = self._merge_state_pair(iter_state, base_state)

        # C-style for loop: init executes once; body/increment may execute zero or
        # more times, so merge one-iteration path with skip-loop path.
        elif node.node_type == NodeTypes.FOR_STATEMENT:
            init = node.children[0] if len(node.children) > 0 else None
            condition = node.children[1] if len(node.children) > 1 else None
            increment = node.children[2] if len(node.children) > 2 else None
            body = node.children[3] if len(node.children) > 3 else None

            if init is not None:
                self._analyze_node(init)
            if condition is not None:
                self._analyze_node(condition)

            base_snapshot = self._snapshot_binding_states()

            if body is not None:
                self._analyze_node(body)
            if increment is not None:
                self._analyze_node(increment)
            iter_snapshot = self._snapshot_binding_states()
            self._check_loop_carried_moves(base_snapshot, iter_snapshot, body)

            self._restore_binding_states(base_snapshot)
            all_bindings = set(base_snapshot.keys()) | set(iter_snapshot.keys())
            for binding in all_bindings:
                base_state = base_snapshot.get(binding, binding.state)
                iter_state = iter_snapshot.get(binding, base_state)
                binding.state = self._merge_state_pair(iter_state, base_state)

        # For-in loop: collection expression is evaluated once; body may execute
        # zero or more times, so merge one-iteration path with skip-loop path.
        elif node.node_type == NodeTypes.FOR_IN_STATEMENT:
            loop_var_decl = node.children[0] if len(node.children) > 0 else None
            collection = node.children[1] if len(node.children) > 1 else None
            body = node.children[2] if len(node.children) > 2 else None

            if loop_var_decl is not None:
                self._analyze_node(loop_var_decl)
            if collection is not None:
                self._analyze_node(collection)

            base_snapshot = self._snapshot_binding_states()

            if body is not None:
                self._analyze_node(body)
            iter_snapshot = self._snapshot_binding_states()
            self._check_loop_carried_moves(base_snapshot, iter_snapshot, body, loop_var_decl)

            self._restore_binding_states(base_snapshot)
            all_bindings = set(base_snapshot.keys()) | set(iter_snapshot.keys())
            for binding in all_bindings:
                base_state = base_snapshot.get(binding, binding.state)
                iter_state = iter_snapshot.get(binding, base_state)
                binding.state = self._merge_state_pair(iter_state, base_state)

        # Other control flow nodes: recurse conservatively
        elif node.node_type in (NodeTypes.ELIF_STATEMENT, NodeTypes.ELSE_STATEMENT):
            for child in node.children:
                self._analyze_node(child)

        # Field assignment: enforce that &this receivers cannot mutate fields
        elif node.node_type == NodeTypes.ASSIGNMENT:
            lhs = node.children[0] if node.children else None
            self._check_borrow_write(node)
            if lhs and lhs.node_type == NodeTypes.FIELD_ACCESS and lhs.children:
                root = lhs.children[0]
                if root.node_type == NodeTypes.IDENTIFIER and root.name == "this":
                    if self.callable_stack:
                        _, _, receiver_is_mutable = self.callable_stack[-1]
                        if not receiver_is_mutable:
                            self.report_error(
                                SemanticError(
                                    message=(
                                        "Cannot mutate field through a read-only receiver '&this'; "
                                        "declare the receiver as '&mut this' to allow mutation"
                                    )
                                ),
                                node,
                            )
            for child in node.children:
                self._analyze_node(child)

        # Default: recurse
        else:
            for child in node.children:
                self._analyze_node(child)
    
    def report_errors(self) -> None:
        """Print all collected errors. Errors are already logged by self.error(); this is a no-op."""
        pass
