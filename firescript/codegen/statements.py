from enums import NodeTypes
from parser import ASTNode, get_line_and_coumn_from_index, get_line
from errors import CodegenError
from utils.type_utils import is_copyable, is_owned, register_class
from typing import Optional
import logging

from .declarations import DeclarationsMixin


class StatementsMixin(DeclarationsMixin):
    def emit_statement(self, node: ASTNode) -> str:
        """
        Generate code for a node that represents a statement.
        Automatically appends a semicolon if one is not already present.
        """
        # (Previously special handling for big number assignments removed)

        code = self._visit(node)
        # Only add semicolon if needed. Special-case return statements whose expression may end with '}'
        if code:
            stripped = code.strip()
            needs_semicolon = True
            if stripped.endswith(";"):
                needs_semicolon = False
            elif stripped.endswith("}"):
                # Do not add semicolons after blocks, but ensure assignment statements
                # that produce compound literals do get a semicolon.
                if node.node_type in (NodeTypes.SCOPE, NodeTypes.IF_STATEMENT, NodeTypes.ELSE_STATEMENT, NodeTypes.ELIF_STATEMENT, NodeTypes.WHILE_STATEMENT, NodeTypes.FOR_STATEMENT, NodeTypes.FOR_IN_STATEMENT):
                    needs_semicolon = False
                elif node.node_type in (NodeTypes.VARIABLE_ASSIGNMENT, NodeTypes.ASSIGNMENT, NodeTypes.RETURN_STATEMENT):
                    needs_semicolon = True
                else:
                    needs_semicolon = True
            elif stripped.startswith("#"):
                needs_semicolon = False
            if needs_semicolon:
                code += ";"
        return code

    def _visit(self, node: ASTNode) -> str:
        if node.node_type == NodeTypes.ROOT:
            lines = []
            for child in node.children:
                # Assume all top-level nodes are statements.
                if child.node_type == NodeTypes.FUNCTION_DEFINITION:
                    # Functions are emitted separately by generate()
                    continue
                stmt_code = self.emit_statement(child)
                if stmt_code:
                    lines.append(stmt_code)
            return "\n".join(lines)
        elif node.node_type == NodeTypes.SCOPE:
            # Enter new scope for tracking owned values
            self.scope_stack.append([])
            lines = []
            for child in node.children:
                # In scopes, each child is a statement.
                stmt_code = self.emit_statement(child)
                if stmt_code:
                    lines.append(stmt_code)
            # Generate cleanup code for owned values in this scope
            cleanup_lines = self._free_arrays_in_current_scope()
            if cleanup_lines:
                lines.extend(cleanup_lines)
            # Pop the scope
            self.scope_stack.pop()
            return "{\n" + "\n".join("    " + line for line in lines) + "\n}"
        elif node.node_type == NodeTypes.ARRAY_LITERAL:
            # Array literals are typically handled in variable declarations for correct element typing.
            # If evaluated as an expression directly, return a placeholder.
            return "/* array literal */"

        elif node.node_type == NodeTypes.VARIABLE_DECLARATION:
            var_type_fs = node.var_type or "int32"
            # Apply type substitution if we're in a generic function
            if hasattr(self, '_current_type_map') and self._current_type_map:
                var_type_fs = self._current_type_map.get(var_type_fs, var_type_fs)
            var_type_c = self._map_type_to_c(var_type_fs)
            self.symbol_table[node.name] = (var_type_fs, node.is_array)

            if node.is_array:
                # Arrays are Owned types - allocate on heap
                init_node = node.children[0] if node.children else None
                elem_c = self._map_type_to_c(var_type_fs)
                mangled_name = self._mangle_name(node.name)
                if init_node and init_node.node_type == NodeTypes.ARRAY_LITERAL:
                    elements = init_node.children or []
                    n = len(elements)
                    # Store array size for length() method
                    self.symbol_table[node.name] = (var_type_fs, node.is_array, n)
                    # Track array for cleanup at scope exit
                    if self.scope_stack:
                        self.scope_stack[-1].append((mangled_name, var_type_fs))
                    # Generate heap allocation for array
                    elem_codes = [self._visit(elem) for elem in elements]
                    lines = []
                    # Allocate array on heap
                    lines.append(f"{elem_c}* {mangled_name} = malloc({n} * sizeof({elem_c}));")
                    # Initialize elements
                    for i, elem_code in enumerate(elem_codes):
                        lines.append(f"{mangled_name}[{i}] = {elem_code};")
                    return "\n".join(lines)
                # Allow initializing from an expression (would need additional handling)
                self.report_error(CodegenError(message="Array initialization from expressions not yet supported for fixed-size arrays"), node)
                return ""
            elif var_type_fs == "string":
                # Strings are Owned (heap-allocated)
                # String literals need to be duplicated to heap
                init_node = node.children[0] if node.children else None
                mangled_name = self._mangle_name(node.name)
                
                # Only track for cleanup if this creates a NEW allocation (not a borrow)
                # Track if: literal, function call, or no initializer (default empty string)
                should_track = (
                    init_node is None or  # Default empty string
                    init_node.node_type == NodeTypes.LITERAL or  # String literal
                    init_node.node_type == NodeTypes.FUNCTION_CALL  # Function returns new string
                )
                if should_track and self.scope_stack:
                    self.scope_stack[-1].append((mangled_name, "string"))
                
                if init_node and init_node.node_type == NodeTypes.LITERAL and init_node.token and init_node.token.type == "STRING_LITERAL":
                    # String literal - use strdup to allocate on heap
                    literal_value = self._escape_string_literal(init_node.token.value)
                    return f"{var_type_c} {mangled_name} = strdup({literal_value});"
                else:
                    # Expression result (already should be heap-allocated)
                    init_value = self._visit(init_node) if init_node else "strdup(\"\")"
                    return f"{var_type_c} {mangled_name} = {init_value};"
            else:
                # Non-array, non-string variable
                mangled_name = self._mangle_name(node.name)
                init_node = node.children[0] if node.children else None
                
                # Track owned (non-copyable) classes for cleanup ONLY if allocated (not borrowed)
                # Track if: 
                # 1. CONSTRUCTOR_CALL (new ClassName(...))
                # 2. FUNCTION_CALL that is a constructor or returns an owned type
                # 3. NOT an identifier (which would be a borrow/copy)
                is_class_type = is_owned(var_type_fs, False)
                should_track = False
                if is_class_type and init_node is not None:
                    if init_node.node_type == NodeTypes.CONSTRUCTOR_CALL:
                        # new ClassName(...) always creates a new allocation
                        should_track = True
                    elif init_node.node_type == NodeTypes.FUNCTION_CALL:
                        # Either constructor or function returning owned type
                        should_track = True
                    # Don't track if it's just copying from another variable (borrow)
                    elif init_node.node_type == NodeTypes.IDENTIFIER:
                        should_track = False
                
                if should_track and self.scope_stack:
                    self.scope_stack[-1].append((mangled_name, var_type_fs))
                
                init_value = self._visit(init_node) if init_node else "0"
                return f"{var_type_c} {mangled_name} = {init_value};"
        elif node.node_type == NodeTypes.ARRAY_ACCESS:
            # Fixed-size array access: arr[idx]
            array_node = node.children[0]
            index_node = node.children[1]
            array_code = self._visit(array_node)
            index_code = self._visit(index_node)
            # Negative indexing support when array length metadata is available.
            # For arrays declared from literals and explicit array params, symbol table
            # stores a third tuple slot with either constant size or <name>_len variable.
            size_expr = None
            if array_node and array_node.node_type == NodeTypes.IDENTIFIER:
                sym = self.symbol_table.get(array_node.name)
                if sym and len(sym) >= 3 and sym[2] is not None:
                    size_expr = str(sym[2])

            if size_expr is not None:
                normalized_index = f"(({index_code}) < 0 ? ({size_expr} + ({index_code})) : ({index_code}))"
                return f"{array_code}[{normalized_index}]"

            # Fallback when length metadata is unavailable.
            return f"{array_code}[{index_code}]"
        elif node.node_type == NodeTypes.LITERAL:
            return self._literal_to_c(node)
        elif node.node_type == NodeTypes.CAST_EXPRESSION:
            expr_node = node.children[0] if node.children else None
            expr_code = self._visit(expr_node) if expr_node is not None else ""
            target_fs = node.name
            
            # Special handling for casting to string
            if target_fs == "string":
                # Check if source is an array
                expr_type = (
                    getattr(expr_node, "return_type", None)
                    or getattr(expr_node, "var_type", None)
                    or (self.symbol_table.get(getattr(expr_node, "name", ""), (None, False))[0]
                       if expr_node and expr_node.node_type == NodeTypes.IDENTIFIER else None)
                )
                is_array = (
                    getattr(expr_node, "is_array", False)
                    or (self.symbol_table.get(getattr(expr_node, "name", ""), (None, False))[1]
                       if expr_node and expr_node.node_type == NodeTypes.IDENTIFIER else False)
                )
                
                # Also check if expr_type ends with [] (for monomorphized type parameters)
                if is_array or (expr_type and isinstance(expr_type, str) and expr_type.endswith("[]")):
                    # Array to string conversion - generate inline code
                    # Get element type and size
                    if expr_type and expr_type.endswith("[]"):
                        elem_type = expr_type[:-2]
                    else:
                        elem_type = expr_type or "int32"
                    
                    # Try to get array size from symbol table
                    array_size = None
                    if expr_node and expr_node.node_type == NodeTypes.IDENTIFIER:
                        sym_info = self.symbol_table.get(expr_node.name)
                        if sym_info and len(sym_info) >= 3:
                            array_size = sym_info[2]
                    
                    if array_size is None:
                        # Can't determine size - this happens with array parameters
                        # For now, just return a simple representation
                        return "strdup(\"[...]\")"
                    
                    # Generate inline array-to-string code
                    temp_var = f"__arr_str_{self.array_temp_counter}"
                    self.array_temp_counter += 1
                    elem_c = self._map_type_to_c(elem_type)
                    
                    # Generate code that builds the string representation
                    # Use format instead of f-strings to handle complex brace escaping
                    code = "({ " + elem_c + "* " + temp_var + "_arr = " + expr_code + "; "
                    code += "size_t " + temp_var + "_size = " + str(array_size) + "; "
                    code += "size_t " + temp_var + "_bufsize = 1024; "
                    code += "char* " + temp_var + " = malloc(" + temp_var + "_bufsize); "
                    code += "size_t " + temp_var + "_len = 0; "
                    code += temp_var + "[" + temp_var + "_len++] = '['; "
                    code += "for (size_t " + temp_var + "_i = 0; " + temp_var + "_i < " + temp_var + "_size; " + temp_var + "_i++) { "
                    code += "if (" + temp_var + "_i > 0) { " + temp_var + "[" + temp_var + "_len++] = ','; " + temp_var + "[" + temp_var + "_len++] = ' '; } "
                    code += "char* " + temp_var + "_elem = firescript_toString(" + temp_var + "_arr[" + temp_var + "_i]); "
                    code += "size_t " + temp_var + "_elem_len = strlen(" + temp_var + "_elem); "
                    code += "while (" + temp_var + "_len + " + temp_var + "_elem_len + 2 >= " + temp_var + "_bufsize) { " + temp_var + "_bufsize *= 2; " + temp_var + " = realloc(" + temp_var + ", " + temp_var + "_bufsize); } "
                    code += "memcpy(" + temp_var + " + " + temp_var + "_len, " + temp_var + "_elem, " + temp_var + "_elem_len); "
                    code += temp_var + "_len += " + temp_var + "_elem_len; "
                    code += "free(" + temp_var + "_elem); "
                    code += "} "
                    code += temp_var + "[" + temp_var + "_len++] = ']'; "
                    code += temp_var + "[" + temp_var + "_len] = '\\0'; "
                    code += temp_var + "; })"
                    return code
                else:
                    # Primitive to string conversion
                    return f"firescript_toString({expr_code})"
            
            target_c = self._map_type_to_c(target_fs)
            return f"(({target_c})({expr_code}))"
        elif node.node_type == NodeTypes.BINARY_EXPRESSION:
            # Generic arithmetic or string concatenation
            left_node, right_node = node.children
            left = self._visit(left_node)
            right = self._visit(right_node)
            op = node.name
            # String concatenation with '+'
            left_t = (
                getattr(left_node, "return_type", None)
                or getattr(left_node, "var_type", None)
                or (self.symbol_table.get(getattr(left_node, "name", ""), (None, False))[0]
                   if left_node.node_type == NodeTypes.IDENTIFIER else None)
            )
            right_t = (
                getattr(right_node, "return_type", None)
                or getattr(right_node, "var_type", None)
                or (self.symbol_table.get(getattr(right_node, "name", ""), (None, False))[0]
                   if right_node.node_type == NodeTypes.IDENTIFIER else None)
            )
            if op == "+" and (left_t == "string" or right_t == "string"):
                lcode = left
                rcode = right
                if left_t != "string":
                    lcode = f"firescript_toString({left})"
                if right_t != "string":
                    rcode = f"firescript_toString({right})"
                return f"firescript_strcat({lcode}, {rcode})"
            # Numeric or generic binary op fallback
            return f"({left} {op} {right})"
        
        elif node.node_type == NodeTypes.UNARY_EXPRESSION:
            op = node.name
            
            # Increment/decrement operators (++/--) have no children
            if op in ("++", "--"):
                var_name = node.token.value if node.token and hasattr(node.token, 'value') else ""
                mangled_var_name = self._mangle_name(var_name)
                return f"{mangled_var_name}{op}"
            
            # Unary +/- operators have a child operand
            if not node.children:
                return ""  # Shouldn't happen, but safety check
                
            operand_node = node.children[0]
            operand = self._visit(operand_node)
            # Unary operators: + is no-op, - negates
            if op == "-":
                return f"(-{operand})"
            elif op == "+":
                return f"(+{operand})"
            else:
                return operand  # Fallback
        
        elif node.node_type == NodeTypes.METHOD_CALL:
            object_node = node.children[0]
            object_code = self._visit(object_node)
            method_name = node.name
            obj_type = (
                getattr(object_node, "return_type", None)
                or (
                    f"{getattr(object_node, 'var_type', None)}[]"
                    if getattr(object_node, "is_array", False) and getattr(object_node, "var_type", None)
                    else getattr(object_node, "var_type", None)
                )
            )
            if isinstance(obj_type, str) and obj_type.endswith("[]"):
                if method_name in ("length", "size"):
                    # For fixed-size arrays, return compile-time size
                    if object_node.node_type == NodeTypes.IDENTIFIER:
                        sym_info = self.symbol_table.get(object_node.name)
                        if sym_info and len(sym_info) >= 3:
                            array_size = sym_info[2]
                            return f"(int32_t){array_size}"
                    self.report_error(CodegenError(message="Cannot determine array size at compile time"), node)
                    return "0"
                if method_name in ("index", "count"):
                    if object_node.node_type == NodeTypes.IDENTIFIER:
                        sym_info = self.symbol_table.get(object_node.name)
                        if sym_info and len(sym_info) >= 3 and len(node.children) >= 2:
                            array_size = sym_info[2]
                            needle_code = self._visit(node.children[1])
                            elem_type = obj_type[:-2]
                            temp_id = self.array_temp_counter
                            self.array_temp_counter += 1
                            if elem_type == "string":
                                pred = f"strcmp({object_code}[__i_{temp_id}], __needle_{temp_id}) == 0"
                            else:
                                pred = f"{object_code}[__i_{temp_id}] == __needle_{temp_id}"
                            if method_name == "index":
                                return (
                                    f"({{ int32_t __result_{temp_id} = -1; "
                                    f"{self._map_type_to_c(elem_type)} __needle_{temp_id} = {needle_code}; "
                                    f"for (int32_t __i_{temp_id} = 0; __i_{temp_id} < (int32_t)({array_size}); __i_{temp_id}++) {{ "
                                    f"if ({pred}) {{ __result_{temp_id} = __i_{temp_id}; break; }} "
                                    f"}} __result_{temp_id}; }})"
                                )
                            return (
                                f"({{ int32_t __count_{temp_id} = 0; "
                                f"{self._map_type_to_c(elem_type)} __needle_{temp_id} = {needle_code}; "
                                f"for (int32_t __i_{temp_id} = 0; __i_{temp_id} < (int32_t)({array_size}); __i_{temp_id}++) {{ "
                                f"if ({pred}) {{ __count_{temp_id}++; }} "
                                f"}} __count_{temp_id}; }})"
                            )
                    self.report_error(CodegenError(message="Cannot determine array size at compile time"), node)
                    return "0"
                # Fixed-size arrays don't support mutation methods
                self.report_error(CodegenError(message=f"Fixed-size arrays don't support method '{method_name}'. Arrays are immutable."), node)
            # Class instance method call -> dispatch to free function Class_method(self, ...)
            # Determine class name from object expression type
            obj_type = (
                getattr(object_node, "var_type", None)
                or getattr(object_node, "return_type", None)
            )
            if obj_type in self.class_names:
                c_obj_type = self._get_c_class_name(obj_type)
                args_code = [self._visit(child) for child in node.children[1:]]
                return f"{c_obj_type}_{method_name}({object_code}{(', ' + ', '.join(args_code)) if args_code else ''})"
            # Fallback (shouldn't happen if type checking is correct)
            args_code = [self._visit(child) for child in node.children[1:]]
            return f"{object_code}.{method_name}({', '.join(args_code)})"
        elif node.node_type == NodeTypes.FIELD_ACCESS:
            # Emit obj.field or obj->field depending on whether obj is a pointer (owned class)
            obj_node = node.children[0] if node.children else None
            obj_code = self._visit(obj_node) if obj_node else ""
            
            # Determine if the object is an owned class (pointer type)
            obj_type = None
            if obj_node and obj_node.node_type == NodeTypes.IDENTIFIER:
                obj_type = self.symbol_table.get(obj_node.name, (None, False))[0]
            elif obj_node:
                obj_type = getattr(obj_node, "return_type", None) or getattr(obj_node, "var_type", None)

            # If the node's return_type was not set during parsing (deferred-import case),
            # resolve it now from class_fields so that callers (like type inference for
            # generic println) can determine the concrete field type.
            if getattr(node, "return_type", None) is None and obj_type:
                fields_for_type = self.class_fields.get(obj_type, [])
                for fname, ftype in fields_for_type:
                    if fname == node.name:
                        node.return_type = ftype
                        break

            # Use -> for owned classes, . for copyable classes and primitives
            if obj_type and obj_type in self.class_names and is_owned(obj_type, False):
                return f"{obj_code}->{node.name}"
            else:
                return f"{obj_code}.{node.name}"
        elif node.node_type == NodeTypes.IDENTIFIER:
            return self._mangle_name(node.name)
        elif node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            # Simple assignment to identifier from expression
            name = node.name
            mangled_name = self._mangle_name(name)
            value_code = self._visit(node.children[0]) if node.children else "0"
            # If variable not yet declared, attempt implicit declaration using RHS type
            if name not in self.symbol_table:
                rhs = node.children[0] if node.children else None
                rhs_type_fs = getattr(rhs, "return_type", None) if rhs is not None else None
                if rhs_type_fs is None and rhs is not None and rhs.node_type == NodeTypes.FUNCTION_CALL and rhs.name in getattr(self, "class_names", set()):
                    rhs_type_fs = rhs.name
                if isinstance(rhs_type_fs, str) and rhs_type_fs.endswith("[]"):
                    elem_fs = rhs_type_fs[:-2]
                    self.symbol_table[name] = (elem_fs, True)
                    self.scope_stack[-1].append((mangled_name, elem_fs))
                    return f"VArray* {mangled_name} = {value_code}"
                # If still unknown, fall back to int32
                fs_type = rhs_type_fs or "int32"
                c_type = self._map_type_to_c(fs_type)
                # Record in symbol table for subsequent uses
                self.symbol_table[name] = (fs_type, False)
                return f"{c_type} {mangled_name} = {value_code}"
            return f"{mangled_name} = {value_code}"
        elif node.node_type == NodeTypes.ASSIGNMENT:
            # General assignment: lhs can be identifier, field access, or array access
            lhs = node.children[0] if node.children else None
            rhs = node.children[1] if node.children and len(node.children) > 1 else None
            lhs_code = self._visit(lhs) if lhs else ""
            rhs_code = self._visit(rhs) if rhs else "0"
            return f"{lhs_code} = {rhs_code}"
        elif node.node_type == NodeTypes.RETURN_STATEMENT:
            # Return with or without expression
            if node.children:
                expr_node = node.children[0]
                expr_code = (
                    self._visit(expr_node)
                    if expr_node is not None
                    else ""
                )
                # For owned values being returned, ownership transfers to caller - don't free them
                # Check if we're returning a simple variable (identifier) - if so, exclude it from cleanup
                exclude_var = None
                if expr_node and expr_node.node_type == NodeTypes.IDENTIFIER:
                    # Returning a variable - exclude it from cleanup (ownership transfers)
                    exclude_var = self._mangle_name(expr_node.name)
                
                # Cleanup other owned values in scope
                cleanup_lines = []
                if self._in_function:
                    cleanup_lines = self._free_arrays_in_all_active_scopes(exclude_var)
                
                if cleanup_lines:
                    cleanup = "\n".join(cleanup_lines)
                    return f"{{\n{cleanup}\nreturn {expr_code};\n}}"
                return f"return {expr_code}"
            # bare return - no value being returned, safe to cleanup all
            cleanup_lines = []
            if self._in_function:
                cleanup_lines = self._free_arrays_in_all_active_scopes()
            if cleanup_lines:
                cleanup = "\n".join(cleanup_lines)
                return f"{{\n{cleanup}\nreturn;\n}}"
            return "return"
        elif node.node_type == NodeTypes.FUNCTION_CALL:
            # Positional constructors for classes (no zero-arg default): map args by field order
            if node.name in getattr(self, "class_names", set()):
                args = [self._visit(arg) for arg in node.children]
                fields = self.class_fields.get(node.name, [])
                inits = []
                for (fname, _ftype), val in zip(fields, args):
                    inits.append(f".{fname} = {val}")
                init_str = ", ".join(inits)
                c_class_name = self._get_c_class_name(node.name)

                # Check if this is an owned (non-copyable) class
                if is_owned(node.name, False):
                    # Owned classes need heap allocation
                    # Generate inline compound statement that allocates and initializes
                    tmp_var = f"__tmp_class_{self.array_temp_counter}"
                    self.array_temp_counter += 1
                    return f"({{ {c_class_name}* {tmp_var} = malloc(sizeof({c_class_name})); *{tmp_var} = ({c_class_name}){{ {init_str} }}; {tmp_var}; }})"
                else:
                    # Copyable classes use stack allocation with compound literal
                    return f"({c_class_name}){{ {init_str} }}"
            if node.name == "stdout":
                # Check if stdout is enabled in the file where this call is made
                node_file_directives = self._directives_for_node(node)
                
                logging.debug(f"stdout() call: file_directives={self.file_directives}, node_directives={node_file_directives}")
                
                if "enable_lowlevel_stdout" not in node_file_directives:
                    self.report_error(
                        CodegenError(
                            message=(
                                "stdout() is not available. Use 'directive enable_lowlevel_stdout;' "
                                "in this file to enable it."
                            )
                        ),
                        node
                    )
                    return ""
                # stdout only accepts strings - no special formatting
                arg = node.children[0]
                arg_code = self._visit(arg)
                return f'printf("%s", {arg_code})'
            elif node.name == "drop":
                # Fixed-size arrays are copyable; drop is a no-op
                return "/* drop noop */"
            elif node.name in ("syscall_open", "syscall_read", "syscall_write", "syscall_close"):
                # Check if syscalls are enabled in the file where this call is made
                node_file_directives = self._directives_for_node(node)
                if "enable_syscalls" not in node_file_directives:
                    self.report_error(
                        CodegenError(
                            message=(
                                f"{node.name}() is not available. Use 'directive enable_syscalls;' "
                                "in this file to enable it."
                            )
                        ),
                        node
                    )
                    return ""
                args = ", ".join(self._visit(arg) for arg in node.children)
                return f"firescript_{node.name}({args})"
            elif node.name == "int":
                # Cast to a native C integer
                arg_code = self._visit(node.children[0])
                return f"firescript_toInt({arg_code})"

            elif node.name == "toInt":
                return f"firescript_toInt({self._visit(node.children[0])})"
            elif node.name == "toFloat":
                return f"firescript_toFloat({self._visit(node.children[0])})"
            elif node.name == "toDouble":
                return f"firescript_toDouble({self._visit(node.children[0])})"
            elif node.name == "toString":
                return f"firescript_toString({self._visit(node.children[0])})"
            elif node.name == "toChar":
                return f"firescript_toChar({self._visit(node.children[0])})"
            elif node.name == "toBool":
                return f"firescript_toBool({self._visit(node.children[0])})"
            # Type conversion functions
            elif node.name == "i32_to_f64":
                arg_code = self._visit(node.children[0])
                return f"((double)({arg_code}))"
            elif node.name == "i32_to_f32":
                arg_code = self._visit(node.children[0])
                return f"((float)({arg_code}))"
            elif node.name == "f64_to_i32":
                arg_code = self._visit(node.children[0])
                return f"((int32_t)({arg_code}))"
            elif node.name == "f32_to_i32":
                arg_code = self._visit(node.children[0])
                return f"((int32_t)({arg_code}))"
            elif node.name == "i32_to_str":
                arg_code = self._visit(node.children[0])
                # Allocate buffer and use sprintf
                return f"firescript_i32_to_str({arg_code})"
            elif node.name == "i64_to_str":
                arg_code = self._visit(node.children[0])
                return f"firescript_i64_to_str({arg_code})"
            elif node.name == "f64_to_str":
                arg_code = self._visit(node.children[0])
                return f"firescript_f64_to_str({arg_code})"
            elif node.name == "f32_to_str":
                arg_code = self._visit(node.children[0])
                return f"firescript_f32_to_str({arg_code})"
            else:
                # Check if this is a generic function call
                func_name = node.name
                type_args = getattr(node, 'type_args', [])
                
                # Re-infer if in monomorphization context, since type parameters may have been substituted
                # OR if type_args not set at all, try to infer them
                if func_name in self.generic_templates:
                    if getattr(self, '_current_type_map', {}) or not type_args:
                        inferred = self._infer_type_args_from_call(func_name, node)
                        if inferred:
                            type_args = inferred
                
                if type_args and func_name in self.generic_templates:
                    # Use the mangled name for generic function
                    key = (func_name, tuple(type_args))
                    if key not in self.monomorphized_funcs:
                        # Late discovery (e.g. FIELD_ACCESS arg type only known after symbol_table
                        # is populated during _visit). Register now so the monomorphization loop
                        # (which runs after all emit_statement calls) will instantiate it.
                        mangled = self._mangle_generic_name(func_name, tuple(type_args))
                        self.monomorphized_funcs[key] = mangled
                    mangled_name = self.monomorphized_funcs[key]
                    args = self._build_call_args(node.children)  # no size injection for generics
                    return f"{mangled_name}({args})"
                
                # Regular function call - inject size args for functions with explicit array params
                args = self._build_call_args(node.children, func_name=node.name)
                return f"{self._mangle_name(node.name)}({args})"
        elif node.node_type == NodeTypes.TYPE_METHOD_CALL:
            # Dispatch to generated constructor/static function: Class_method(args)
            class_name = getattr(node, "class_name", "")
            c_class_name_tmc = self._get_c_class_name(class_name) if class_name else class_name
            args = ", ".join(self._visit(arg) for arg in node.children)
            return f"{c_class_name_tmc}_{node.name}({args})"
        elif node.node_type == NodeTypes.CONSTRUCTOR_CALL:
            # new Class(args) -> call generated function C_Class(args)
            # Constructor is defined as {mangled_class}_{original_class}(...)
            args = [self._visit(arg) for arg in node.children]
            cname = node.name
            c_cname = self._get_c_class_name(cname)
            arglist = ", ".join(args)
            return f"{c_cname}_{cname}({arglist})"
        elif node.node_type == NodeTypes.SUPER_CALL:
            super_class = getattr(node, "super_class", None)
            if not super_class:
                return "/* invalid super call */"
            args_code = [self._visit(arg) for arg in (node.children or [])]

            # `this.super(...)` constructor chaining: call base constructor and copy base fields onto derived `this`
            tmp = f"__super_tmp_{self.array_temp_counter}"
            self.array_temp_counter += 1
            fields = self.class_fields.get(super_class, [])
            c_super_class = self._get_c_class_name(super_class)
            call = f"{c_super_class}_{super_class}({', '.join(args_code)})"
            # Super constructor is defined as {mangled_class}_{original_class}(...)
            lines: list[str] = []
            
            # Check if parent class is owned (returns pointer) or copyable (returns value)
            parent_is_owned = is_owned(super_class, False)
            
            if parent_is_owned:
                # Parent constructor returns a pointer - dereference to copy fields
                lines.append(f"{c_super_class}* {tmp} = {call};")
                for fname, _ftype in fields:
                    # this is also a pointer for owned classes, use ->
                    lines.append(f"this->{fname} = {tmp}->{fname};")
                # Free the temporary parent object after copying fields
                lines.append(f"firescript_free({tmp});")
            else:
                # Parent constructor returns a value - copy directly
                lines.append(f"{c_super_class} {tmp} = {call};")
                for fname, _ftype in fields:
                    # this is a value for copyable classes, use .
                    lines.append(f"this.{fname} = {tmp}.{fname};")
            
            inner = "\n".join("    " + l for l in lines)
            return "{\n" + inner + "\n}"
        elif node.node_type == NodeTypes.IF_STATEMENT:
            # The first child is the condition, the second is the then-branch,
            # and the optional third child is the else-branch.
            condition_code = self._visit(node.children[0])
            then_code = self._visit(node.children[1])
            code = f"if ({condition_code}) {then_code}"
            if len(node.children) > 2 and node.children[2]:
                else_code = self._visit(node.children[2])
                code += f" else {else_code}"
            return code
        elif node.node_type == NodeTypes.ELIF_STATEMENT:
            # The first child is the condition, the second is the then-branch.
            condition_code = self._visit(node.children[0])
            then_code = self._visit(node.children[1])
            code = f"else if ({condition_code}) {then_code}"
            return code
        elif node.node_type == NodeTypes.ELSE_STATEMENT:
            # The only child is the else-branch.
            return f"else {self._visit(node.children[0])}"
        elif node.node_type == NodeTypes.EQUALITY_EXPRESSION:  # ==, !=
            leftNode = node.children[0]
            rightNode = node.children[1]
            left = self._visit(leftNode)
            right = self._visit(rightNode)

            # Get the types properly from symbol table or return_type (Copyable only now)
            left_type = getattr(leftNode, "var_type", None) or (
                self.symbol_table.get(leftNode.name, (None, False))[0]
                if leftNode.node_type == NodeTypes.IDENTIFIER
                else getattr(leftNode, "return_type", None)
            )
            right_type = getattr(rightNode, "var_type", None) or (
                self.symbol_table.get(rightNode.name, (None, False))[0]
                if rightNode.node_type == NodeTypes.IDENTIFIER
                else getattr(rightNode, "return_type", None)
            )

            if left_type in ("int", "float", "double") or right_type in (
                "int",
                "float",
                "double",
            ):
                op = node.name
                return f"({left} {op} {right})"

            # Null pointer comparison - skip strcmp when either side is null
            is_right_null = rightNode.return_type == "null" or (
                rightNode.token and rightNode.token.type == "NULL_LITERAL"
            )
            is_left_null = leftNode.return_type == "null" or (
                leftNode.token and leftNode.token.type == "NULL_LITERAL"
            )
            if is_left_null or is_right_null:
                op = node.name
                node.return_type = "bool"
                return f"({left} {op} {right})"

            # String comparison
            if (
                leftNode.token
                and leftNode.token.type == "STRING_LITERAL"
                or leftNode.return_type == "string"
                or leftNode.var_type == "string"
            ):
                if (
                    rightNode.token
                    and rightNode.token.type == "STRING_LITERAL"
                    or rightNode.return_type == "string"
                    or rightNode.var_type == "string"
                ):
                    node.return_type = "bool"
                    return f"firescript_strcmp({left}, {right})"
                else:
                    self.report_error(CodegenError(message="Cannot compare string with non-string type"), node)
                    return "(0)"
            # Default comparison for Copyables
            op = node.name
            return f"({left} {op} {right})"
        elif node.node_type == NodeTypes.WHILE_STATEMENT:
            condition_code = self._visit(node.children[0])
            body_code = self._visit(node.children[1])
            return f"while ({condition_code}) {body_code}"
        elif node.node_type == NodeTypes.FOR_STATEMENT:
            # C-style for loop: for (init; condition; increment) body
            # children[0] = init, children[1] = condition, children[2] = increment, children[3] = body
            init_node = node.children[0]
            condition_node = node.children[1]
            increment_node = node.children[2]
            body_node = node.children[3]
            
            # Generate code for each part, handling empty placeholders
            init_code = "" if init_node.name == "empty" else self._visit(init_node)
            condition_code = "" if condition_node.name == "empty" else self._visit(condition_node)
            increment_code = "" if increment_node.name == "empty" else self._visit(increment_node)
            body_code = self._visit(body_node)
            
            # Remove trailing semicolons from init and increment since for loop syntax adds them
            if init_code.endswith(";"):
                init_code = init_code[:-1]
            if increment_code.endswith(";"):
                increment_code = increment_code[:-1]
            
            # Remove wrapping parentheses from condition if present (expressions add them)
            if condition_code.startswith("(") and condition_code.endswith(")"):
                condition_code = condition_code[1:-1]
            
            return f"for ({init_code}; {condition_code}; {increment_code}) {body_code}"
        elif node.node_type == NodeTypes.FOR_IN_STATEMENT:
            # For-in loop: for (type item in collection) body
            # children[0] = variable declaration node, children[1] = collection, children[2] = body
            var_decl = node.children[0]
            collection = node.children[1]
            body = node.children[2]
            
            # Extract loop variable name and type from the variable declaration
            # var_decl has var_type attribute and name attribute
            loop_var = var_decl.name
            var_type = var_decl.var_type or "int32"
            
            # Convert firescript type to C type
            c_type = self._map_type_to_c(var_type)
            
            # Generate a unique loop index variable
            loop_idx = f"_i_{loop_var}"
            mangled_loop_var = self._mangle_name(loop_var)
            
            # Add the loop variable to symbol table for the body
            # Save current symbol table state to restore after loop
            old_symbol_entry = self.symbol_table.get(loop_var)
            self.symbol_table[loop_var] = (var_type, False)
            
            # Handle different collection types
            if collection.node_type == NodeTypes.ARRAY_LITERAL:
                # For array literals, we need to create a temporary array
                elements = collection.children or []
                collection_size = len(elements)
                # Generate unique temp array name using counter
                if not hasattr(self, '_temp_array_counter'):
                    self._temp_array_counter = 0
                temp_array_name = f"_temp_array_{self._temp_array_counter}"
                self._temp_array_counter += 1
                
                # Generate code for temporary array
                elem_codes = [self._visit(elem) for elem in elements]
                temp_array_init = []
                temp_array_init.append(f"{c_type} {temp_array_name}[{collection_size}] = {{{', '.join(elem_codes)}}};")
                
                # Generate body code
                body_code = self._visit(body)
                
                # Generate the for-in loop
                result = "\n".join(temp_array_init) + "\n"
                result += f"for (int {loop_idx} = 0; {loop_idx} < {collection_size}; {loop_idx}++) {{\n"
                result += f"{c_type} {mangled_loop_var} = {temp_array_name}[{loop_idx}];\n"
                if body_code.startswith('{') and body_code.endswith('}'):
                    result += body_code.strip()[1:-1]  # Remove outer braces from body
                else:
                    result += body_code
                result += "\n}"
            elif collection.node_type == NodeTypes.IDENTIFIER:
                # It's a variable - check symbol table for size
                collection_code = self._visit(collection)
                collection_name = collection.name
                
                # Check if we have size information in symbol table
                symbol_info = self.symbol_table.get(collection_name)
                if symbol_info and len(symbol_info) >= 3:
                    # Symbol table has (type, is_array, size) for arrays with known size
                    collection_size_expr = str(symbol_info[2])
                else:
                    # Fall back to sizeof (works for stack arrays, not heap arrays)
                    collection_size_expr = f"(sizeof({collection_code}) / sizeof({collection_code}[0]))"
                
                # Generate body code
                body_code = self._visit(body)
                
                # Generate the for-in loop
                result = f"for (int {loop_idx} = 0; {loop_idx} < {collection_size_expr}; {loop_idx}++) {{\n"
                result += f"{c_type} {mangled_loop_var} = {collection_code}[{loop_idx}];\n"
                if body_code.startswith('{') and body_code.endswith('}'):
                    result += body_code.strip()[1:-1]  # Remove outer braces from body
                else:
                    result += body_code
                result += "\n}"
            else:
                # Fallback for other collection types
                collection_code = self._visit(collection)
                collection_size_expr = f"(sizeof(({collection_code})) / sizeof((({collection_code}))[0]))"
                
                # Generate body code
                body_code = self._visit(body)
                
                # Generate the for-in loop
                result = f"for (int {loop_idx} = 0; {loop_idx} < {collection_size_expr}; {loop_idx}++) {{\n"
                result += f"{c_type} {mangled_loop_var} = ({collection_code})[{loop_idx}];\n"
                if body_code.startswith('{') and body_code.endswith('}'):
                    result += body_code.strip()[1:-1]  # Remove outer braces from body
                else:
                    result += body_code
                result += "\n}"
            
            # Restore symbol table
            if old_symbol_entry is not None:
                self.symbol_table[loop_var] = old_symbol_entry
            elif loop_var in self.symbol_table:
                del self.symbol_table[loop_var]
            
            return result
        elif node.node_type == NodeTypes.BREAK_STATEMENT:
            # On break, free arrays declared in current scope so far
            cleanup_lines = self._free_arrays_in_current_scope()
            if cleanup_lines:
                cleanup = "\n".join(cleanup_lines)
                return f"{{\n{cleanup}\nbreak;\n}}"
            return "break"
        elif node.node_type == NodeTypes.CONTINUE_STATEMENT:
            # On continue, free arrays declared in current scope so far
            cleanup_lines = self._free_arrays_in_current_scope()
            if cleanup_lines:
                cleanup = "\n".join(cleanup_lines)
                return f"{{\n{cleanup}\ncontinue;\n}}"
            return "continue"
        elif node.node_type == NodeTypes.RELATIONAL_EXPRESSION:
            leftNode, rightNode = node.children
            left = self._visit(leftNode)
            right = self._visit(rightNode)
            op = node.name
            # Get the types properly from symbol table or return_type
            left_type = (
                getattr(leftNode, "var_type", None)
                or self.symbol_table.get(leftNode.name, (None, False))[0]
                if leftNode.node_type == NodeTypes.IDENTIFIER
                else getattr(leftNode, "return_type", None)
            )
            right_type = (
                getattr(rightNode, "var_type", None)
                or self.symbol_table.get(rightNode.name, (None, False))[0]
                if rightNode.node_type == NodeTypes.IDENTIFIER
                else getattr(rightNode, "return_type", None)
            )

            # Copyable numeric or fallback comparison
            return f"({left} {op} {right})"
        elif node.node_type == NodeTypes.COMPOUND_ASSIGNMENT:
            identifier = node.name
            mangled_identifier = self._mangle_name(identifier)
            op = getattr(node.token, "type", None)
            value = self._visit(node.children[0])
            var_type = self.symbol_table.get(identifier, (None, False))[0]
            # Map firescript compound assignment operators to C operators (Copyable only)
            op_map = {
                "ADD_ASSIGN": "+=",
                "SUBTRACT_ASSIGN": "-=",
                "MULTIPLY_ASSIGN": "*=",
                "DIVIDE_ASSIGN": "/=",
                "MODULO_ASSIGN": "%=",
            }
            c_op = op_map.get(op or "", "+=")  # Default to += if unknown or op is None
            return f"{mangled_identifier} {c_op} {value};"

        elif node.node_type == NodeTypes.UNARY_EXPRESSION:
            if not node.token or not hasattr(node.token, "value"):
                self.report_error(CodegenError(message="Missing token value in unary expression"), node)
                return ""
            identifier = node.token.value
            mangled_identifier = self._mangle_name(identifier)
            op = node.name
            var_type = self.symbol_table.get(identifier, (None, False))[0]
            if op == "++":
                return f"{mangled_identifier}++"
            elif op == "--":
                return f"{mangled_identifier}--"
            else:
                self.report_error(CodegenError(message=f"Unrecognized unary operator '{op}' for {identifier}"), node)
                return ""
        else:
            return ""

