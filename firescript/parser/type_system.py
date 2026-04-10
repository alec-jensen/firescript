import logging
from typing import Optional

from utils.type_utils import is_owned, is_copyable
from enums import NodeTypes
from .ast_node import ASTNode
from .statements import StatementsMixin


class TypeSystemMixin(StatementsMixin):
    def _annotate_value_category(self, node: ASTNode, var_type: Optional[str], is_array: bool):
        """Annotate node.value_category based on ownership/copyability of var_type."""
        try:
            node.value_category = (
                "Owned" if is_owned(var_type, is_array) else (
                    "Copyable" if is_copyable(var_type, is_array) else None
                )
            )
        except Exception:
            pass

    def resolve_variable_types(self, node: ASTNode, current_scope=None):
        """
        Recursively traverse the AST to annotate Identifier nodes with the variable type,
        enforce no shadowing and undefined variable usage.
        """
        if current_scope is None:
            current_scope = {}

        # New scope node: copy parent scope
        if node.node_type == NodeTypes.SCOPE:
            new_scope = current_scope.copy()
            for child in node.children:
                self.resolve_variable_types(child, new_scope)
            return

        # For loops: create new scope for init variables
        if node.node_type in (NodeTypes.FOR_STATEMENT, NodeTypes.FOR_IN_STATEMENT):
            new_scope = current_scope.copy()
            # Process all children (init, condition, increment, body) in the new scope
            for child in node.children:
                self.resolve_variable_types(child, new_scope)
            return

        # Function definition: parameters introduce a new scope level
        if node.node_type == NodeTypes.FUNCTION_DEFINITION:
            # Children layout: [params..., body_scope]
            new_scope = current_scope.copy()
            # Register parameters (prevent shadowing outer vars)
            for child in node.children[
                :-1
            ]:  # all except last which should be body scope
                if child.node_type == NodeTypes.PARAMETER:
                    # PARAMETER nodes store type in var_type field (5th arg when constructed)
                    param_type = child.var_type
                    param_name = child.name
                    is_array = child.is_array
                    if param_name in new_scope:
                        self.invalid_type_error(
                            f"Parameter '{param_name}' already declared in an outer scope; shadowing not allowed",
                            child.token,
                        )
                    new_scope[param_name] = (param_type, is_array)
                    self._annotate_value_category(child, param_type, is_array)
            # Traverse body with parameter scope
            body = node.children[-1] if node.children else None
            if body:
                self.resolve_variable_types(body, new_scope)
            return

        # Class method definition: similar to function but includes receiver parameter
        if node.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
            new_scope = current_scope.copy()
            for child in node.children[:-1]:  # params (including receiver)
                if child.node_type == NodeTypes.PARAMETER:
                    param_type = child.var_type
                    param_name = child.name
                    is_array = child.is_array
                    if param_name in new_scope:
                        self.invalid_type_error(
                            f"Parameter '{param_name}' already declared in an outer scope; shadowing not allowed",
                            child.token,
                        )
                    new_scope[param_name] = (param_type, is_array)
                    self._annotate_value_category(child, param_type, is_array)
            # Inject implicit alias 'this' to the class type for method/constructor bodies,
            # so 'this.x' resolves even if receiver param was named differently or synthetic.
            cls_name = getattr(node, "class_name", None)
            if cls_name and "this" not in new_scope and not bool(getattr(node, "is_static", False)):
                new_scope["this"] = (cls_name, False)
            body = node.children[-1] if node.children else None
            if body:
                self.resolve_variable_types(body, new_scope)
            return

        # Variable declaration: enforce no shadowing
        if node.node_type == NodeTypes.VARIABLE_DECLARATION:
            if node.name in current_scope:
                self.invalid_type_error(
                    f"Variable '{node.name}' already declared in an outer scope; shadowing not allowed",
                    node.token,
                )
            current_scope[node.name] = (node.var_type, node.is_array)
            self._annotate_value_category(node, node.var_type, node.is_array)
            # Resolve initializer expression
            for child in node.children:
                self.resolve_variable_types(child, current_scope)
            return

        # Variable assignment: allow implicit declaration for class-typed RHS
        if node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            # Resolve RHS first to allow identifiers inside it to be typed
            for child in node.children:
                self.resolve_variable_types(child, current_scope)
            if node.name not in current_scope:
                inferred_type = None
                rhs = node.children[0] if node.children else None
                if rhs is not None:
                    # Constructor-style call: ClassName(...)
                    if rhs.node_type == NodeTypes.FUNCTION_CALL and rhs.name in self.user_types:
                        inferred_type = rhs.name
                    # Instance method call: obj.method(...)
                    elif rhs.node_type == NodeTypes.METHOD_CALL and rhs.children:
                        obj = rhs.children[0]
                        obj_type = getattr(obj, "var_type", None)
                        if obj_type is None and isinstance(obj, ASTNode) and obj.node_type == NodeTypes.IDENTIFIER:
                            obj_type = current_scope.get(obj.name, (None, False))[0]
                        if obj_type and (obj_type in self.user_methods) and (rhs.name in self.user_methods[obj_type]):
                            inferred_type = self.user_methods[obj_type][rhs.name].get("return")
                current_scope[node.name] = (inferred_type, False)
            return

        # Identifier usage: ensure variable defined
        if node.node_type == NodeTypes.IDENTIFIER:
            if node.name not in current_scope:
                if self.defer_undefined_identifiers:
                    self.deferred_undefined_identifiers.append((node.name, node.token))
                else:
                    self.undefined_identifier_error(node.name, node.token)
            else:
                node.var_type, node.is_array = current_scope[node.name]
                self._annotate_value_category(node, node.var_type, node.is_array)
            return

        # Recurse into children for all other nodes
        for child in node.children:
            self.resolve_variable_types(child, current_scope)

    def type_check(self):
        """Initiates the type checking process on the AST."""
        logging.debug("Starting type checking...")
        symbol_table = (
            {}
        )  # Build initial symbol table if needed, or rely on resolved types
        self._type_check_node(self.ast, symbol_table)
        logging.debug("Type checking finished.")

    def _get_node_type(self, node: ASTNode, symbol_table: dict) -> Optional[str]:
        """Helper to get the full type string (e.g., 'int', 'string[]')."""
        base_type = None
        is_array = False

        if node.node_type == NodeTypes.LITERAL:
            # Ensure token exists before accessing its type
            if node.token:
                # Prefer an explicitly annotated return_type from parse_primary
                if getattr(node, 'return_type', None):
                    base_type = node.return_type
                else:
                    # Fallback defaults consistent with new numeric model
                    if node.token.type == "INTEGER_LITERAL":
                        base_type = "int32"
                    elif node.token.type == "FLOAT_LITERAL":
                        base_type = "float32"
                    elif node.token.type == "DOUBLE_LITERAL":
                        base_type = "float64"
                    elif node.token.type == "BOOLEAN_LITERAL":
                        base_type = "bool"
                    elif node.token.type == "STRING_LITERAL":
                        base_type = "string"
                    elif node.token.type == "NULL_LITERAL":
                        base_type = "null"  # Special case for null
            is_array = False
        elif node.node_type == NodeTypes.IDENTIFIER:
            # Types should be resolved by resolve_variable_types
            base_type = node.var_type
            is_array = node.is_array
        elif node.node_type == NodeTypes.ARRAY_LITERAL:
            # Determine type from elements, assume consistent type for now
            if not node.children:
                # Cannot determine type of empty array literal yet
                # self.invalid_type_error("Cannot determine type of empty array literal", node.token)
                return None  # Or a special "empty_array" type?
            # Check the type of the first element to infer array type
            first_elem_type_node = node.children[0]
            # Ensure the first element node itself has a token before checking type
            if first_elem_type_node:
                first_elem_type = self._type_check_node(
                    first_elem_type_node, symbol_table
                )
                if first_elem_type is None:
                    return None  # Error in element
                if first_elem_type.endswith("[]"):
                    self.invalid_type_error(
                        "Array literals cannot directly contain arrays", node.token
                    )
                    return None
                base_type = first_elem_type
                is_array = True
            else:
                # Handle case where first element node is somehow None (shouldn't happen in valid AST)
                return None

        elif node.node_type == NodeTypes.FUNCTION_CALL:
            # Return type is pre-defined for built-ins
            base_type = node.return_type  # May include '[]' if function returns array
            # Check if base_type is not None before checking endswith and slicing
            if base_type:
                is_array = base_type.endswith("[]")
                if is_array:
                    base_type = base_type[:-2]
            else:
                is_array = False  # Cannot be an array if base_type is None
        elif node.node_type == NodeTypes.METHOD_CALL:
            # Return type determined during method call check
            base_type = node.return_type
            # Check if base_type is not None before checking endswith and slicing
            if base_type:
                is_array = base_type.endswith("[]")
                if is_array:
                    base_type = base_type[:-2]
            else:
                is_array = False
        elif node.node_type == NodeTypes.SUPER_CALL:
            base_type = node.return_type
            if base_type:
                is_array = base_type.endswith("[]")
                if is_array:
                    base_type = base_type[:-2]
            else:
                is_array = False
        elif node.node_type == NodeTypes.ARRAY_ACCESS:
            # Type is the element type of the array
            array_expr_node = node.children[0]
            # Ensure the array expression node exists
            if array_expr_node:
                array_type = self._type_check_node(array_expr_node, symbol_table)
                if array_type and array_type.endswith("[]"):
                    base_type = array_type[:-2]
                    is_array = False
                else:
                    # Error handled in _type_check_node or array_type is None
                    return None
            else:
                # Handle case where array expression node is None
                return None
        elif node.node_type in (
            NodeTypes.BINARY_EXPRESSION,
            NodeTypes.EQUALITY_EXPRESSION,
            NodeTypes.RELATIONAL_EXPRESSION,
        ):
            # Type determined during expression check
            base_type = node.return_type
            is_array = False  # These expressions don't return arrays directly

        if base_type is None:
            # If after all checks, base_type is still None, return None
            # This can happen for nodes that don't evaluate to a value (like ROOT, SCOPE)
            # or if an error occurred determining the type.
            return None

        return f"{base_type}[]" if is_array else base_type

    def _infer_generic_type_args(self, func_name: str, arg_types: list[str]) -> Optional[list[str]]:
        """Infer type arguments for a generic function call based on argument types.
        Returns a list of concrete types for each type parameter, or None if inference fails.
        """
        if func_name not in self.generic_functions:
            return None
        
        type_params = self.generic_functions[func_name]
        if not type_params:
            return []
        
        # Get the function definition to examine parameter types
        func_def = None
        for child in self.ast.children:
            if child.node_type == NodeTypes.FUNCTION_DEFINITION and child.name == func_name:
                func_def = child
                break
        
        if not func_def:
            return None
        
        # Extract parameter types from function definition
        param_types = []
        for child in func_def.children:
            if child.node_type == NodeTypes.PARAMETER:
                param_types.append(child.var_type or "")
        
        # Build a mapping from type parameters to inferred concrete types
        type_map: dict[str, str] = {}
        
        for param_type, arg_type in zip(param_types, arg_types):
            if param_type in type_params:
                # Direct type parameter match
                if param_type in type_map:
                    if type_map[param_type] != arg_type:
                        # Conflicting inference
                        return None
                else:
                    type_map[param_type] = arg_type
        
        # Check if all type parameters were inferred
        inferred_types = []
        for tp in type_params:
            if tp not in type_map:
                # Could not infer this type parameter
                return None
            inferred_types.append(type_map[tp])
        
        return inferred_types

    def _type_check_node(self, node: ASTNode, symbol_table: dict) -> Optional[str]:
        """Recursively checks types in the AST node and returns the node's expression type."""
        node_type_str = None  # The type of the expression this node represents

        # Special handling for generic function definitions: set type parameter context
        if node.node_type == NodeTypes.FUNCTION_DEFINITION and hasattr(node, 'type_params') and node.type_params:
            prev_type_params = self._current_type_params
            self._current_type_params = node.type_params.copy()
            child_types = [
                self._type_check_node(child, symbol_table) for child in node.children
            ]
            self._current_type_params = prev_type_params
        else:
            # First, recursively check children to determine their types
            child_types = [
                self._type_check_node(child, symbol_table) for child in node.children
            ]

        # --- Type Checking Logic based on Node Type ---
        if node.node_type == NodeTypes.ROOT or node.node_type == NodeTypes.SCOPE:
            # Scopes don't have a type themselves, just check children
            pass  # Children already checked

        elif node.node_type == NodeTypes.VARIABLE_DECLARATION:
            declared_type = f"{node.var_type}[]" if node.is_array else node.var_type
            initializer_type = child_types[0] if child_types else None

            if initializer_type:
                # Special case: initializing with null
                if initializer_type == "null":
                    if not node.is_nullable:
                        self.invalid_type_error(
                            f"Cannot initialize non-nullable variable '{node.name}' with null",
                            node.token,
                        )
                # General case: types must match
                elif declared_type != initializer_type:
                    # Strict: no implicit coercions between numeric families
                    self.type_error(
                        f"Type mismatch for variable '{node.name}'. Expected {declared_type}, got {initializer_type}",
                        node.token,
                    )
            # Add variable to symbol table for current scope (if not already done by resolve)
            symbol_table[node.name] = (node.var_type, node.is_array, node.is_nullable)

        elif node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            var_info = symbol_table.get(node.name)
            assigned_type = child_types[0] if child_types else None
            if not var_info:
                # Implicit declaration on first assignment: register with inferred type
                if assigned_type is not None:
                    # assigned_type may be 'Type[]'; identify array-ness
                    is_arr = assigned_type.endswith("[]")
                    base_t = assigned_type[:-2] if is_arr else assigned_type
                    symbol_table[node.name] = (base_t, is_arr, False)
                else:
                    self.undefined_identifier_error(node.name, node.token)
                    return None
            else:
                var_type, is_array = var_info[0], var_info[1]
                is_nullable = var_info[2] if len(var_info) > 2 else False
                expected_type = f"{var_type}[]" if is_array else var_type
                if assigned_type:
                    if assigned_type == "null":
                        if not is_nullable:
                            self.invalid_type_error(
                                f"Cannot assign null to non-nullable variable '{node.name}'",
                                node.token,
                            )
                    elif expected_type != assigned_type:
                        # TODO: Implement type coercion rules
                        self.type_error(
                            f"Type mismatch assigning to variable '{node.name}'. Expected {expected_type}, got {assigned_type}",
                            node.token,
                        )

        elif node.node_type == NodeTypes.BINARY_EXPRESSION:
            left_type = child_types[0]
            right_type = child_types[1]
            op = node.name

            if left_type is None or right_type is None:
                return None

            integer_types = self.INTEGER_TYPES
            float_types = {"float", "double", "float32", "float64", "float128"}
            
            # Check if a type is a type parameter (in current generic function scope)
            is_left_type_param = left_type in self._current_type_params
            is_right_type_param = right_type in self._current_type_params

            node_type_str: Optional[str] = None

            # String concatenation stays allowed for string + string
            if op == "+":
                # Allow string concatenation with any type (converted in codegen)
                if left_type == "string" or right_type == "string":
                    node_type_str = "string"
                elif left_type == right_type and left_type in integer_types:
                    node_type_str = left_type
                elif left_type == right_type and left_type in float_types:
                    node_type_str = left_type
                # Allow if both are the same type parameter (assumed to be numeric via constraints)
                elif left_type == right_type and is_left_type_param:
                    node_type_str = left_type
                else:
                    self.invalid_type_error(
                        f"Operator '{op}' not supported between types {left_type} and {right_type}",
                        node.token,
                    )
            elif op in ("-", "*", "/", "**"):
                if left_type == right_type and left_type in integer_types:
                    node_type_str = left_type
                elif left_type == right_type and left_type in float_types:
                    node_type_str = left_type
                # Allow if both are the same type parameter (assumed to be numeric via constraints)
                elif left_type == right_type and is_left_type_param:
                    node_type_str = left_type
                else:
                    self.invalid_type_error(
                        f"Operator '{op}' not supported between types {left_type} and {right_type}",
                        node.token,
                    )
            elif op in ("&&", "||"):
                if left_type == "bool" and right_type == "bool":
                    node_type_str = "bool"
                else:
                    self.invalid_type_error(
                        f"Operator '{op}' requires bool operands, got {left_type} and {right_type}",
                        node.token,
                    )
            elif op == "%":
                if left_type == right_type and left_type in integer_types:
                    node_type_str = left_type
                # Allow if both are the same type parameter (assumed to be numeric via constraints)
                elif left_type == right_type and is_left_type_param:
                    node_type_str = left_type
                else:
                    self.invalid_type_error(
                        f"Operator '{op}' requires integer operands of the same type, got {left_type} and {right_type}",
                        node.token,
                    )
            else:
                self.invalid_type_error(f"Unsupported binary operator '{op}'", node.token)

            node.return_type = node_type_str

        elif node.node_type == NodeTypes.UNARY_EXPRESSION:
            op = node.name
            
            # Increment/decrement operators (++/--) have no children - they operate on the identifier stored in node.token
            if op in ("++", "--"):
                # The variable being incremented/decremented is in node.token
                var_name = node.token.value if node.token and hasattr(node.token, 'value') else None
                if var_name:
                    var_info = symbol_table.get(var_name)
                    if var_info:
                        var_type, is_array = var_info[0], var_info[1]
                        # Increment/decrement only work on integer types
                        if var_type in self.INTEGER_TYPES:
                            node_type_str = var_type
                        else:
                            self.type_error(f"Operator '{op}' requires an integer variable, got {var_type}", node.token)
                    else:
                        self.undefined_identifier_error(var_name, node.token)
                return node_type_str
            
            # Unary +/- operators have a child operand
            if not child_types:
                self.invalid_type_error(f"Unary operator '{op}' missing operand", node.token)
                return None
                
            operand_type = child_types[0]

            if operand_type is None:
                return None

            integer_types = self.INTEGER_TYPES
            float_types = {"float", "double", "float32", "float64", "float128"}
            
            # Unary + and - work on numeric types and type parameters
            if op in ("+", "-"):
                is_numeric = operand_type in integer_types or operand_type in float_types
                is_type_param = operand_type in self._current_type_params
                
                if is_numeric or is_type_param:
                    node_type_str = operand_type  # Same type as operand
                else:
                    self.invalid_type_error(
                        f"Unary operator '{op}' requires numeric operand, got {operand_type}",
                        node.token,
                    )
                    node_type_str = None
            elif op == "!":
                if operand_type == "bool":
                    node_type_str = "bool"
                else:
                    self.invalid_type_error(
                        f"Unary operator '{op}' requires bool operand, got {operand_type}",
                        node.token,
                    )
                    node_type_str = None
            else:
                self.invalid_type_error(f"Unsupported unary operator '{op}'", node.token)
                node_type_str = None

            node.return_type = node_type_str

        elif node.node_type == NodeTypes.EQUALITY_EXPRESSION:  # ==, !=
            left_type = child_types[0]
            right_type = child_types[1]
            op = node.name

            if left_type is None or right_type is None:
                return None

            # Allow comparison between same-type numerics, string==string, bool==bool, or with null
            integer_types = self.INTEGER_TYPES
            float_types = {"float32", "float64", "float128"}
            if (
                (left_type == right_type and (left_type in integer_types or left_type in float_types))
                or (left_type == right_type and left_type in {"string", "bool"})
                or (left_type == "null" or right_type == "null")
            ):
                node_type_str = "bool"
            else:
                self.invalid_type_error(
                    f"Cannot compare types {left_type} and {right_type} with '{op}'",
                    node.token,
                )

            node.return_type = node_type_str

        elif node.node_type == NodeTypes.RELATIONAL_EXPRESSION:  # >, <, >=, <=
            left_type = child_types[0]
            right_type = child_types[1]
            op = node.name

            if left_type is None or right_type is None:
                return None

            integer_types = self.INTEGER_TYPES
            float_types = {"float32", "float64", "float128"}
            
            # Allow comparisons if both types are the same, and either:
            # 1. They are known numeric types, OR
            # 2. They are type parameters (assumed to be constrained to numeric types)
            is_numeric = left_type in integer_types or left_type in float_types
            is_type_param = left_type in self._current_type_params
            
            if left_type == right_type and (is_numeric or is_type_param):
                node_type_str = "bool"
            else:
                self.invalid_type_error(
                    f"Operator '{op}' requires same-type numeric operands, got {left_type} and {right_type}",
                    node.token,
                )

            node.return_type = node_type_str

        elif node.node_type == NodeTypes.CAST_EXPRESSION:
            expr_type = child_types[0] if child_types else None
            target_type = getattr(node, "name", None)

            if expr_type is None or target_type is None:
                return None

            # Allow casting arrays to string
            if isinstance(expr_type, str) and expr_type.endswith("[]"):
                if target_type == "string":
                    # Array to string is allowed
                    node_type_str = "string"
                    node.return_type = "string"
                else:
                    self.invalid_type_error(
                        f"Cannot cast array type {expr_type} to {target_type}",
                        node.token,
                    )
                    return None
            elif isinstance(target_type, str) and target_type.endswith("[]"):
                self.invalid_type_error(
                    f"Cannot cast to array type {target_type}",
                    node.token,
                )
                return None

            integer_types = self.INTEGER_TYPES
            float_types = {"float32", "float64", "float128"}
            
            # Allow casting to string from any type
            if target_type == "string":
                node_type_str = "string"
                node.return_type = "string"
            elif target_type not in integer_types and target_type not in float_types:
                self.invalid_type_error(
                    f"Cannot cast to unknown or non-numeric type {target_type}",
                    node.token,
                )
                return None
            elif expr_type not in integer_types and expr_type not in float_types and expr_type != "bool" and expr_type != "string":
                self.invalid_type_error(
                    f"Cannot cast non-numeric type {expr_type} to {target_type}",
                    node.token,
                )
                return None
            else:
                node_type_str = target_type
                node.return_type = target_type

        elif node.node_type == NodeTypes.FUNCTION_CALL:
            # Basic check for built-ins
            func_name = node.name
            
            # Check if this is a generic function call
            if func_name in self.generic_functions:
                # Check if type arguments are explicitly provided
                if hasattr(node, 'type_args') and node.type_args:
                    # Explicit type arguments provided
                    type_params = self.generic_functions[func_name]
                    if len(node.type_args) != len(type_params):
                        self.invalid_type_error(
                            f"Generic function '{func_name}' expects {len(type_params)} type arguments, got {len(node.type_args)}",
                            node.token,
                        )
                else:
                    # Infer type arguments from call arguments
                    inferred = self._infer_generic_type_args(func_name, [t for t in child_types if t is not None])
                    if inferred is None:
                        self.invalid_type_error(
                            f"Could not infer type arguments for generic function '{func_name}'",
                            node.token,
                        )
                        node.type_args = []
                    else:
                        node.type_args = inferred
                
                # Validate type constraints if we have type arguments
                if hasattr(node, 'type_args') and node.type_args:
                    constraints = self.generic_constraints.get(func_name, {})
                    type_params = self.generic_functions[func_name]
                    for tp, concrete_type in zip(type_params, node.type_args):
                        if tp in constraints:
                            constraint = constraints[tp]
                            # Parse constraint (simple version: just check if type is in union)
                            allowed_types = [t.strip() for t in constraint.split("|")]
                            if concrete_type not in allowed_types and constraint not in ["Numeric", "Comparable", "SignedInt", "UnsignedInt", "Float", "Integer"]:
                                self.invalid_type_error(
                                    f"Type '{concrete_type}' does not satisfy constraint '{constraint}' for type parameter '{tp}'",
                                    node.token,
                                )
                    
                    # Set return type by substituting type parameters
                    generic_return_type = self.user_functions.get(func_name)
                    if generic_return_type:
                        # Create type substitution map
                        type_subst = dict(zip(type_params, node.type_args))
                        # Substitute return type if it's a type parameter
                        if generic_return_type in type_subst:
                            node.return_type = type_subst[generic_return_type]
                            node_type_str = node.return_type
                        else:
                            node.return_type = generic_return_type
                            node_type_str = generic_return_type
            
            expected_arg_count = -1  # Use -1 for variable args like print
            expected_arg_types = []  # Define expected types for builtins

            if func_name == "print":
                expected_arg_count = 1  # Simplified: assumes 1 arg for now
                # Allow printing any basic type
            elif func_name in ("toInt", "toBool", "toString", "toChar"):
                expected_arg_count = 1
                # Allow conversion from reasonable types (simplified check)
            elif func_name == "typeof":
                expected_arg_count = 1

            if expected_arg_count != -1 and len(child_types) != expected_arg_count:
                self.invalid_type_error(
                    f"Function '{func_name}' expected {expected_arg_count} arguments, got {len(child_types)}",
                    node.token,
                )
            elif expected_arg_types:
                for i, arg_type in enumerate(child_types):
                    if (
                        i < len(expected_arg_types)
                        and expected_arg_types[i] != "T"
                        and arg_type != expected_arg_types[i]
                    ):
                        # TODO: Add coercion checks for conversions
                        self.invalid_type_error(
                            f"Argument {i+1} for function '{func_name}' expected type {expected_arg_types[i]}, got {arg_type}",
                            node.children[i].token,
                        )

            # Return type is already set in the node for builtins during parsing
            # Constructors: calling a class name acts as a constructor with positional args matching field order
            if func_name in self.user_types:
                # Validate against class fields order
                fields_map = self.user_classes.get(func_name, {})
                field_order = list(fields_map.items())  # [(name, type), ...] insertion order preserved
                if len(child_types) != len(field_order):
                    self.invalid_type_error(
                        f"Constructor '{func_name}' expected {len(field_order)} args, got {len(child_types)}",
                        node.token,
                    )
                else:
                    for i, (arg_t, (_, exp_t)) in enumerate(zip(child_types, field_order)):
                        if arg_t != exp_t:
                            self.invalid_type_error(
                                f"Constructor '{func_name}' arg {i+1} expected {exp_t}, got {arg_t}",
                                node.children[i].token if i < len(node.children) else node.token,
                            )
                node_type_str = func_name
                node.return_type = func_name
            else:
                # For non-generic functions, use the stored return type
                if func_name not in self.generic_functions and not hasattr(node, 'return_type'):
                    node.return_type = self.user_functions.get(func_name)
                node_type_str = node.return_type

        elif node.node_type == NodeTypes.METHOD_CALL:
            object_type = child_types[0]
            method_name = node.name
            arg_types = child_types[1:]

            if object_type is None:
                return None  # Error in object expression

            node.return_type = None  # Reset before check

            if isinstance(object_type, str) and object_type.endswith("[]"):  # It's an array method
                elem_type = object_type[:-2]
                if method_name == "append":
                    if len(arg_types) == 1:
                        if arg_types[0] == elem_type:
                            node.return_type = object_type  # append returns the array itself (or void?) - let's say array type for chaining
                        else:
                            self.invalid_type_error(
                                f"Method 'append' for {object_type} expected element type {elem_type}, got {arg_types[0]}",
                                node.children[1].token,
                            )
                    else:
                        self.invalid_type_error(
                            f"Method 'append' expected 1 argument, got {len(arg_types)}",
                            node.token,
                        )
                elif method_name == "insert":
                    if len(arg_types) == 2:
                        if arg_types[0] in self.INTEGER_TYPES:
                            if arg_types[1] == elem_type:
                                node.return_type = object_type
                            else:
                                self.invalid_type_error(
                                    f"Method 'insert' for {object_type} expected element type {elem_type}, got {arg_types[1]}",
                                    node.children[2].token,
                                )
                        else:
                            self.invalid_type_error(
                                f"Method 'insert' expected integer index as first argument, got {arg_types[0]}",
                                node.children[1].token,
                            )
                    else:
                        self.invalid_type_error(
                            f"Method 'insert' expected 2 arguments (index, element), got {len(arg_types)}",
                            node.token,
                        )
                elif method_name == "pop":
                    if len(arg_types) == 0:  # Pop last
                        node.return_type = elem_type
                    elif len(arg_types) == 1:  # Pop at index
                        if arg_types[0] in self.INTEGER_TYPES:
                            node.return_type = elem_type
                        else:
                            self.invalid_type_error(
                                f"Method 'pop' expected integer index, got {arg_types[0]}",
                                node.children[1].token,
                            )
                    else:
                        self.invalid_type_error(
                            f"Method 'pop' expected 0 or 1 argument, got {len(arg_types)}",
                            node.token,
                        )
                elif method_name == "clear":
                    if len(arg_types) == 0:
                        node.return_type = (
                            "void"  # Or None? Let's use void consistently
                        )
                    else:
                        self.invalid_type_error(
                            f"Method 'clear' expected 0 arguments, got {len(arg_types)}",
                            node.token,
                        )
                elif method_name in ("length", "size"):
                    if len(arg_types) == 0:
                        node.return_type = "int32"
                    else:
                        self.invalid_type_error(
                            f"Method '{method_name}' expected 0 arguments, got {len(arg_types)}",
                            node.token,
                        )
                elif method_name in ("index", "count"):
                    if len(arg_types) == 1:
                        if arg_types[0] == elem_type:
                            node.return_type = "int32"
                        else:
                            self.invalid_type_error(
                                f"Method '{method_name}' for {object_type} expected element type {elem_type}, got {arg_types[0]}",
                                node.children[1].token,
                            )
                    else:
                        self.invalid_type_error(
                            f"Method '{method_name}' expected 1 argument, got {len(arg_types)}",
                            node.token,
                        )
                else:
                    self.invalid_type_error(
                        f"Unknown method '{method_name}' for array type {object_type}",
                        node.token,
                    )
            else:
                # Class instance methods
                if object_type in self.user_methods and method_name in self.user_methods[object_type]:
                    sig = self.user_methods[object_type][method_name]
                    if bool(sig.get("is_static", False)):
                        self.invalid_type_error(
                            f"Static method '{method_name}' must be called on type '{object_type}', not an instance",
                            node.token,
                        )
                        return None
                    expected_params = sig.get("params", [])
                    if len(arg_types) != len(expected_params):
                        self.invalid_type_error(
                            f"Method '{method_name}' for '{object_type}' expected {len(expected_params)} args, got {len(arg_types)}",
                            node.token,
                        )
                    else:
                        for i, (arg_t, exp_t) in enumerate(zip(arg_types, expected_params)):
                            if arg_t != exp_t:
                                self.invalid_type_error(
                                    f"Argument {i+1} for method '{method_name}' expected type {exp_t}, got {arg_t}",
                                    node.children[i+1].token if len(node.children) > i+1 else node.token,
                                )
                    node.return_type = sig.get("return")
                else:
                    # When imports are pending, defer method lookup for unresolved
                    # imported types (including composite generic types like
                    # Option<string>) until after import resolution/merge.
                    if (
                        self.defer_undefined_identifiers
                        and object_type
                        and (
                            "<" in object_type
                            or object_type not in self.user_methods
                        )
                    ):
                        pass  # Will be resolved after import merge
                    else:
                        self.invalid_type_error(
                            f"Methods not supported for type {object_type}",
                            node.children[0].token,
                        )

        elif node.node_type == NodeTypes.SUPER_CALL:
            enclosing_class = getattr(node, "enclosing_class", None)
            super_class = getattr(node, "super_class", None)
            in_ctor = bool(getattr(node, "in_constructor", False))

            if not enclosing_class:
                self.invalid_type_error("'super' can only be used inside a class method", node.token)
                return None
            if not super_class:
                self.invalid_type_error(f"Class '{enclosing_class}' has no base class; cannot use 'super'", node.token)
                return None

            if not in_ctor:
                self.invalid_type_error("'this.super(...)' is only valid inside a constructor", node.token)
                return None

            # Validate constructor exists on base
            if super_class not in self.user_methods or super_class not in self.user_methods[super_class]:
                self.invalid_type_error(f"No constructor defined for base type '{super_class}'", node.token)
                return None
            sig = self.user_methods[super_class][super_class]
            expected_params = sig.get("params", [])
            if len(child_types) != len(expected_params):
                self.invalid_type_error(
                    f"Super constructor '{super_class}' expected {len(expected_params)} args, got {len(child_types)}",
                    node.token,
                )
            else:
                for i, (arg_t, exp_t) in enumerate(zip(child_types, expected_params)):
                    if arg_t != exp_t:
                        self.invalid_type_error(
                            f"Super constructor '{super_class}' arg {i+1} expected {exp_t}, got {arg_t}",
                            node.children[i].token if i < len(node.children) else node.token,
                        )

            node.return_type = "void"
            node_type_str = "void"
        elif node.node_type == NodeTypes.TYPE_METHOD_CALL:
            class_name = getattr(node, "class_name", None)
            method_name = node.name
            if not class_name or class_name not in self.user_methods or method_name not in self.user_methods[class_name]:
                self.invalid_type_error(f"Unknown constructor or static method '{method_name}' for type '{class_name}'", node.token)
                return None
            sig = self.user_methods[class_name][method_name]
            is_static = bool(sig.get("is_static", False))
            is_constructor = sig.get("return") == class_name
            if not is_static and not is_constructor:
                self.invalid_type_error(f"'{method_name}' is neither a static method nor a constructor for type '{class_name}'", node.token)
                return None
            # Validate args
            expected_params = sig.get("params", [])
            if len(child_types) != len(expected_params):
                self.invalid_type_error(
                    f"Call '{class_name}.{method_name}' expected {len(expected_params)} args, got {len(child_types)}",
                    node.token,
                )
            else:
                for i, (arg_t, exp_t) in enumerate(zip(child_types, expected_params)):
                    if arg_t != exp_t:
                        self.invalid_type_error(
                            f"Call '{class_name}.{method_name}' arg {i+1} expected {exp_t}, got {arg_t}",
                            node.children[i].token if i < len(node.children) else node.token,
                        )
            if is_static:
                node.return_type = sig.get("return")
                node_type_str = sig.get("return")
            else:
                node.return_type = class_name
                node_type_str = class_name

            node_type_str = node.return_type
        elif node.node_type == NodeTypes.CONSTRUCTOR_CALL:
            class_name = node.name
            # Look up a constructor method whose name equals the class name
            if class_name not in self.user_methods or class_name not in self.user_methods[class_name]:
                self.invalid_type_error(f"No constructor defined for type '{class_name}'", node.token)
                return None
            sig = self.user_methods[class_name][class_name]
            expected_params = sig.get("params", [])
            if len(child_types) != len(expected_params):
                self.invalid_type_error(
                    f"Constructor '{class_name}' expected {len(expected_params)} args, got {len(child_types)}",
                    node.token,
                )
            else:
                for i, (arg_t, exp_t) in enumerate(zip(child_types, expected_params)):
                    if arg_t != exp_t:
                        self.invalid_type_error(
                            f"Constructor '{class_name}' arg {i+1} expected {exp_t}, got {arg_t}",
                            node.children[i].token if i < len(node.children) else node.token,
                        )
            node.return_type = class_name
            node_type_str = class_name

        elif node.node_type == NodeTypes.FIELD_ACCESS:
            # Field access: left child is the object expression
            obj_type = child_types[0]
            field_name = node.name
            if obj_type is None:
                return None
            # Only support user-defined classes for now
            if obj_type in self.user_classes:
                fields = self.user_classes[obj_type]
                if field_name in fields:
                    node.return_type = fields[field_name]
                    node_type_str = fields[field_name]
                else:
                    self.invalid_type_error(f"Type '{obj_type}' has no field '{field_name}'", node.token)
                    node_type_str = None
            elif obj_type in self.generic_class_templates:
                # Inside a generic class template body: look up field from template nodes
                template_fields: dict[str, str] = {}
                for ch in (self._class_field_nodes.get(obj_type) or []):
                    if ch.node_type == NodeTypes.CLASS_FIELD:
                        template_fields[ch.name] = ch.var_type or "int32"
                if field_name in template_fields:
                    node.return_type = template_fields[field_name]
                    node_type_str = template_fields[field_name]
                else:
                    self.invalid_type_error(f"Type '{obj_type}' has no field '{field_name}'", node.token)
                    node_type_str = None
            else:
                # In deferred-import mode a composite generic type like "Tuple<int32, string>"
                # may not be registered until imports are fully merged.  Suppress the error so
                # parsing can complete; the real check happens after merging.
                if self.defer_undefined_identifiers and obj_type and "<" in obj_type:
                    node_type_str = None
                else:
                    self.invalid_type_error(f"Field access on non-class type '{obj_type}'", node.token)
                    node_type_str = None

        elif node.node_type == NodeTypes.ARRAY_ACCESS:
            array_type = child_types[0]
            index_type = child_types[1]

            if array_type is None or index_type is None:
                return None

            if not array_type.endswith("[]"):
                self.invalid_type_error(
                    f"Cannot apply index operator [] to non-array type {array_type}",
                    node.children[0].token,
                )
            elif index_type not in self.INTEGER_TYPES:
                self.invalid_type_error(
                    f"Array index must be an integer type, got {index_type}",
                    node.children[1].token,
                )
            else:
                node_type_str = array_type[:-2]  # The element type

            node.return_type = node_type_str

        elif (
            node.node_type == NodeTypes.IF_STATEMENT
            or node.node_type == NodeTypes.WHILE_STATEMENT
        ):
            condition_type = child_types[0]
            if condition_type is None:
                return None
            if condition_type != "bool":
                self.invalid_type_error(
                    f"Condition for '{node.name}' statement must be a boolean, got {condition_type}",
                    node.children[0].token,
                )
            # Body/branches are checked recursively, statement itself has no type

        elif (
            node.node_type == NodeTypes.BREAK_STATEMENT
            or node.node_type == NodeTypes.CONTINUE_STATEMENT
        ):
            # Validate placement: must be inside a loop (while for now)
            cur = node.parent
            in_loop = False
            while cur is not None:
                if cur.node_type == NodeTypes.WHILE_STATEMENT or cur.node_type == NodeTypes.FOR_STATEMENT or cur.node_type == NodeTypes.FOR_IN_STATEMENT:
                    in_loop = True
                    break
                cur = cur.parent
            if not in_loop:
                self.invalid_type_error(f"'{node.name}' statement not within a loop", node.token)

        # --- Determine node's type string based on checks ---
        # If node_type_str wasn't set explicitly, try getting it generally
        if node_type_str is None:
            node_type_str = self._get_node_type(node, symbol_table)

        return node_type_str
