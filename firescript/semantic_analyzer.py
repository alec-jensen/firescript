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
from utils.type_utils import is_owned, is_copyable, is_user_class


class OwnershipState(Enum):
    """State of a variable binding in the ownership tracking system."""
    VALID = auto()      # Binding is valid and can be used
    MOVED = auto()      # Ownership was moved; binding is invalid
    BORROWED = auto()   # Currently borrowed (for future mut borrow tracking)


class BindingInfo:
    """Information about a variable binding."""
    def __init__(
        self,
        name: str,
        var_type: Optional[str],
        is_array: bool,
        state: OwnershipState = OwnershipState.VALID,
        declaration_node: Optional[ASTNode] = None,
    ):
        self.name = name
        self.var_type = var_type
        self.is_array = is_array
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
    
    def __init__(self, ast: ASTNode, source_file: Optional[str] = None):
        self.ast = ast
        self.source_file = source_file
        self.errors: List[str] = []
        
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
    ) -> None:
        """Register a new binding in the current scope."""
        self._current_scope()[name] = BindingInfo(
            name, var_type, is_array, OwnershipState.VALID, node
        )
    
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
            import logging
            logging.debug(f"Use-after-move detected: {name} in node type {use_node.node_type}")
            self.errors.append(
                f"Use-after-move error: variable '{name}' was moved, cannot use it here"
            )
    
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
            self.errors.append(
                f"Cannot borrow Copyable type '{type_str}'; pass by value instead. "
                f"Borrowing is only allowed for Owned types. Location: {node}"
            )
    
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
                            will_move = True
            
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
                        # This is a move - mark the source as moved
                        self._mark_moved(rhs_expr.name, node)
            
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
                
                if func_sig:
                    # Check each argument against its parameter
                    args = node.children
                    for i, arg in enumerate(args):
                        if i >= len(func_sig):
                            # More args than params - parser should have caught this
                            continue
                        
                        param_name, param_type, param_is_array, param_is_borrowed = func_sig[i]
                        
                        # Analyze the argument expression
                        self._analyze_node(arg)
                        
                        # If parameter is not borrowed and argument is an identifier of Owned type, it's a move
                        if not param_is_borrowed and arg.node_type == NodeTypes.IDENTIFIER:
                            arg_binding = self._lookup_binding(arg.name)
                            if arg_binding and is_owned(arg_binding.var_type, arg_binding.is_array):
                                # This is a move - mark the argument as moved
                                self._mark_moved(arg.name, node)
                else:
                    # Built-in function or method - just analyze arguments
                    for child in node.children:
                        self._analyze_node(child)
        
        # Scope: enter/exit scope tracking
        elif node.node_type == NodeTypes.SCOPE:
            self._enter_scope()
            for child in node.children:
                self._analyze_node(child)
            self._exit_scope()
        
        # Function definition: enter new scope for parameters and body
        elif node.node_type == NodeTypes.FUNCTION_DEFINITION:
            self._enter_scope()
            # Register parameters as bindings
            for child in node.children:
                if child.node_type == NodeTypes.PARAMETER:
                    is_borrowed = getattr(child, "is_borrowed", False)
                    if is_borrowed:
                        # Validate that borrowed parameters are Owned types
                        self._validate_borrow(child.var_type, child.is_array, child)
                    self._register_binding(child.name, child.var_type, child.is_array, child)
                elif child.node_type == NodeTypes.SCOPE:
                    # Function body
                    self._analyze_node(child)
            self._exit_scope()
        
        # Class definition: register class, analyze methods
        elif node.node_type == NodeTypes.CLASS_DEFINITION:
            is_copyable_class = getattr(node, "is_copyable", False)
            # Class name is already registered by parser in user_classes
            # Analyze methods
            for child in node.children:
                if child.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
                    self._analyze_node(child)
        
        # Class method: similar to function
        elif node.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
            self._enter_scope()
            for child in node.children:
                if child.node_type == NodeTypes.PARAMETER:
                    is_borrowed = getattr(child, "is_borrowed", False)
                    if is_borrowed:
                        self._validate_borrow(child.var_type, child.is_array, child)
                    self._register_binding(child.name, child.var_type, child.is_array, child)
                elif child.node_type == NodeTypes.SCOPE:
                    self._analyze_node(child)
            self._exit_scope()
        
        # Return statement: check that returned Owned values transfer ownership
        elif node.node_type == NodeTypes.RETURN_STATEMENT:
            for child in node.children:
                self._analyze_node(child)
            # TODO: Validate that borrowed returns don't escape
        
        # Control flow: analyze branches
        elif node.node_type in (NodeTypes.IF_STATEMENT, NodeTypes.ELIF_STATEMENT, NodeTypes.ELSE_STATEMENT, NodeTypes.WHILE_STATEMENT, NodeTypes.FOR_STATEMENT, NodeTypes.FOR_IN_STATEMENT):
            for child in node.children:
                self._analyze_node(child)
        
        # Default: recurse
        else:
            for child in node.children:
                self._analyze_node(child)
    
    def report_errors(self) -> None:
        """Print all collected errors."""
        for error in self.errors:
            logging.error(error)
