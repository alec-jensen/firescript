# firescript/semantic_analyzer.py
"""
Semantic analyzer for ownership, borrowing, and lifetime checking.
Implements the memory management model defined in docs/reference/memory_management.md.
"""
import logging
from typing import Optional, Dict, Set, List, Tuple
from enum import Enum, auto

from enums import NodeTypes
from parser import ASTNode
from errors import CompileTimeError, SemanticError
from utils.type_utils import is_owned
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
    
    def __init__(self, ast: ASTNode, source_file: Optional[str] = None, source_code: Optional[str] = None):
        self.ast = ast
        self.source_file = source_file
        self.source_code = source_code
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

        # Track callable analysis context for validating return semantics.
        # Each frame stores: (return_type, borrowed_parameter_names).
        self.callable_stack: List[Tuple[Optional[str], Set[str]]] = []

    def error(self, text: str, node: Optional[ASTNode] = None) -> None:
        """Record a semantic error with source location, mirroring Parser.error()."""
        if node is None or self.source_code is None:
            err = SemanticError(
                message=text,
                source_file=self.source_file,
            )
            logging.error(err.to_log_string())
            self.errors.append(err)
            return
        try:
            line_num, column_num = get_line_and_coumn_from_index(self.source_code, node.index)
            line_text = get_line(self.source_code, line_num)
            err = SemanticError(
                message=text,
                source_file=self.source_file,
                line=line_num,
                column=column_num,
                snippet=line_text,
            )
            logging.error(err.to_log_string())
            self.errors.append(err)
        except (IndexError, ValueError):
            err = SemanticError(
                message=text,
                source_file=self.source_file,
            )
            logging.error(err.to_log_string())
            self.errors.append(err)
    
    def analyze(self) -> bool:
        """
        Run semantic analysis on the AST.
        Returns True if no errors, False otherwise.
        """
        # First pass: collect function signatures
        self._collect_function_signatures(self.ast)
        
        # Second pass: analyze ownership and borrows
        self._analyze_node(self.ast)
        return len(self.errors) == 0
    
    def _collect_function_signatures(self, node: ASTNode) -> None:
        """First pass: collect all function signatures for parameter checking."""
        if node is None:
            return
            
        if node.node_type == NodeTypes.FUNCTION_DEFINITION:
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
            # Don't recurse into function body - we only need signatures
            return

        if node.node_type == NodeTypes.CLASS_DEFINITION:
            class_name = node.name
            for child in node.children:
                if child.node_type != NodeTypes.CLASS_METHOD_DEFINITION:
                    continue
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
        
        # Recurse for non-function nodes
        if hasattr(node, 'children'):
            for child in node.children:
                self._collect_function_signatures(child)
    
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
            self.error(
                f"Cannot move borrowed value '{binding.name}'; borrowed values cannot transfer ownership",
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
            self.error(
                "Cannot move borrowed value; borrowed values cannot transfer ownership",
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
            self.error(
                f"Use-after-move error: variable '{name}' was moved, cannot use it here",
                use_node,
            )
        elif binding and binding.state == OwnershipState.MAYBE_MOVED:
            self.error(
                f"Use-after-move error: variable '{name}' may have been moved on another control-flow path",
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
            self.error(
                f"Cannot borrow Copyable type '{type_str}'; pass by value instead. "
                f"Borrowing is only allowed for Owned types.",
                node,
            )

    def _analyze_callable_definition(self, node: ASTNode) -> None:
        """Analyze a function-like definition with parameters and body scope."""
        borrowed_params: Set[str] = set()
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER and getattr(child, "is_borrowed", False):
                # Borrowed receiver `this` participates in method borrowing semantics,
                # but should not be treated as an escaping borrowed parameter root for
                # direct return-view checks. Existing class behavior expects returning
                # receiver fields in borrowed methods to remain valid.
                if not bool(getattr(child, "is_receiver", False)) and child.name != "this":
                    borrowed_params.add(child.name)

        self.callable_stack.append((getattr(node, "return_type", None), borrowed_params))
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
            if receiver.node_type == NodeTypes.IDENTIFIER:
                receiver_binding = self._lookup_binding(receiver.name)
                if receiver_binding:
                    method_sig = self.method_signatures.get((receiver_binding.var_type or "", node.name))

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
        
        # Scope: enter/exit scope tracking
        elif node.node_type == NodeTypes.SCOPE:
            self._enter_scope()
            for child in node.children:
                self._analyze_node(child)
                if self._definitely_terminates(child):
                    break
            self._exit_scope()
        
        # Function definition: enter new scope for parameters and body
        elif node.node_type == NodeTypes.FUNCTION_DEFINITION:
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
                _, borrowed_params = self.callable_stack[-1]
                if self._is_direct_borrow_view(ret_expr, borrowed_params) and self._expr_is_owned_value(ret_expr):
                    self.error(
                        "Cannot return borrowed value; borrowed values cannot escape callable scope",
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
        
        # Default: recurse
        else:
            for child in node.children:
                self._analyze_node(child)
    
    def report_errors(self) -> None:
        """Print all collected errors. Errors are already logged by self.error(); this is a no-op."""
        pass
