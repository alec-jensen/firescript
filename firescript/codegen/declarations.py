from enums import NodeTypes
from parser import ASTNode, get_line_and_coumn_from_index, get_line
from utils.type_utils import is_copyable, is_owned, register_class
from typing import Optional
import logging
import os
from .classes import ClassesMixin


class DeclarationsMixin(ClassesMixin):
    def _emit_const_declaration(self, node: ASTNode) -> str:
        """Emit a global constant declaration in C."""
        var_type_fs = node.var_type or "float64"
        var_type_c = self._map_type_to_c(var_type_fs)
        
        # Get initializer value
        init_value = self._visit(node.children[0]) if node.children else "0"
        
        # In C, we use 'const' keyword
        return f"const {var_type_c} {self._mangle_name(node.name)} = {init_value};"

    def _emit_function_definition(self, node: ASTNode) -> str:
        # node.return_type holds the firescript return type (e.g., 'void')
        ret_fs = node.return_type or "void"
        ret_c = self._map_type_to_c(ret_fs)
        
        # Don't mangle the main function name - it needs to be "main" for the entry point
        if node.name == "main":
            mangled_func_name = "main"
        else:
            # Mangle the function name BEFORE pushing new scope so recursive calls can find it
            mangled_func_name = self._mangle_name(node.name)

        # Parameters are all children except the last one, which is the body scope
        params = []
        body_node = None
        
        # Push a new name scope for this function
        self.name_scope_stack.append({})
        
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER:
                base_type = child.var_type or "int32"
                is_array_param = child.is_array
                # For arrays, pass pointer to first element
                ctype = f"{self._map_type_to_c(base_type)}*" if is_array_param else self._map_type_to_c(base_type)
                mangled_param = self._mangle_name(child.name)
                params.append(f"{ctype} {mangled_param}")
                # Array parameters get an implicit companion size parameter
                if is_array_param:
                    params.append(f"int32_t {mangled_param}_len")
            elif child.node_type == NodeTypes.SCOPE:
                body_node = child

        params_sig = ", ".join(params) if params else "void"

        # Save and prepare symbol table for function scope (register params)
        prev_symbols = self.symbol_table.copy()
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER:
                if child.is_array:
                    mangled_param = self._mangle_name(child.name)
                    self.symbol_table[child.name] = (
                        child.var_type or "int32",
                        True,
                        f"{mangled_param}_len",
                    )
                else:
                    self.symbol_table[child.name] = (
                        child.var_type or "int32",
                        False,
                    )

        # Mark we are in a function for return cleanup logic
        prev_in_fn = self._in_function
        self._in_function = True
        # Reset scope stack for the function body (fresh nested scopes inside function)
        prev_scope_stack = self.scope_stack
        self.scope_stack = [[]]
        body_code = self._visit(body_node) if body_node else "{ }"
        
        # Add cleanup code for owned values before function exits
        # Inject cleanup before the closing brace of the function body
        cleanup_lines = self._free_arrays_in_current_scope()
        if cleanup_lines and body_code.startswith("{") and body_code.endswith("}"):
            # Extract the body content (without braces)
            inner = body_code[1:-1].rstrip()
            # Add cleanup before the closing brace
            cleanup_code = "\n".join("    " + line for line in cleanup_lines)
            body_code = "{\n" + inner + "\n" + cleanup_code + "\n}"
        
        # Restore state
        self.scope_stack = prev_scope_stack
        self._in_function = prev_in_fn

        # Restore symbol table after emitting function
        self.symbol_table = prev_symbols

        # Pop the name scope for this function
        self.name_scope_stack.pop()

        return f"{ret_c} {mangled_func_name}({params_sig}) {body_code}"

