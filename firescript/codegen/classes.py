from enums import NodeTypes
from parser import ASTNode, get_line_and_coumn_from_index, get_line
from utils.type_utils import is_copyable, is_owned, register_class
from typing import Optional
import logging
import os
from .generics import GenericsMixin


class ClassesMixin(GenericsMixin):
    def _emit_class_typedef(self, node: ASTNode) -> str:
        """Emit a C typedef struct for a class definition."""
        c_name = self._get_c_class_name(node.name)
        lines = [f"typedef struct {c_name} {{"]
        for field in node.children:
            if field.node_type == NodeTypes.CLASS_FIELD:
                ctype = self._map_type_to_c(field.var_type or "int32")
                lines.append(f"    {ctype} {field.name};")
        lines.append(f"}} {c_name};")
        return "\n".join(lines)

    def _emit_method_definition(self, class_name: str, node: ASTNode) -> str:
        """Emit a C function for a class method: ClassName_methodName(ClassName this, ...) { ... }.

        Constructors are emitted as: ClassName_ClassName(<args>) { ClassName this = (ClassName){0}; ...; return this; }
        so that `new ClassName(...)` maps cleanly to the generated function.
        """
        ret_fs = node.return_type or "void"
        if ret_fs.endswith("[]"):
            raise NotImplementedError("Array returns are not supported in methods")
        ret_c = self._map_type_to_c(ret_fs)

        is_constructor = bool(getattr(node, "is_constructor", False))

        # Push a new name scope for this method BEFORE building params
        self.name_scope_stack.append({})

        # For constructors: always pre-register 'this' so references in the body aren't mangled.
        if is_constructor:
            self.name_scope_stack[-1]["this"] = "this"

        params = []
        body_node = None
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER:
                base_type = child.var_type or "int32"
                if child.is_array:
                    raise NotImplementedError("Array parameters are not supported in methods")
                ctype = self._map_type_to_c(base_type)
                if is_constructor and child.name == "this":
                    # Skip any explicit 'this' param (already registered above)
                    continue
                params.append(f"{ctype} {self._mangle_name(child.name)}")
            elif child.node_type == NodeTypes.SCOPE:
                body_node = child

        params_sig = ", ".join(params) if params else "void"

        # Prepare symbol table for method scope (register params)
        prev_symbols = self.symbol_table.copy()
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER:
                self.symbol_table[child.name] = (
                    child.var_type or "int32",
                    child.is_array,
                )
        # Register 'this' in the symbol table so that FIELD_ACCESS nodes inside the
        # constructor body can correctly determine ownership (-> vs .) for this class.
        if is_constructor:
            self.symbol_table["this"] = (class_name, False)

        prev_in_fn = self._in_function
        self._in_function = True
        prev_scope_stack = self.scope_stack
        self.scope_stack = [[]]
        body_code = self._visit(body_node) if body_node else "{ }"

        if is_constructor:
            # Check if this is an owned (non-copyable) class
            class_is_owned = is_owned(class_name, False)
            c_class_name = self._get_c_class_name(class_name)

            if class_is_owned:
                # Owned classes: allocate on heap with malloc, return pointer
                init_line = f"    {c_class_name}* this = malloc(sizeof({c_class_name}));"
                zero_init = f"    *this = ({c_class_name}){{0}};"
            else:
                # Copyable classes: stack allocation
                init_line = f"    {c_class_name} this = ({c_class_name}){{0}};"
                zero_init = ""

            def _contains_return(n: ASTNode | None) -> bool:
                if n is None:
                    return False
                if n.node_type == NodeTypes.RETURN_STATEMENT:
                    return True
                for ch in (n.children or []):
                    if ch is not None and _contains_return(ch):
                        return True
                return False

            add_implicit_return = not _contains_return(body_node)

            # body_code is expected to be a '{\n...\n}' block; splice in our lines.
            if body_code.startswith("{\n") and body_code.endswith("\n}"):
                inner = body_code[len("{\n") : -len("\n}")].rstrip("\n")
                lines = ["{", init_line]
                if zero_init:
                    lines.append(zero_init)
                if inner:
                    lines.append(inner)
                # Add cleanup before return
                cleanup_lines = self._free_arrays_in_current_scope()
                if cleanup_lines:
                    lines.extend("    " + line for line in cleanup_lines)
                if add_implicit_return:
                    lines.append("    return this;")
                lines.append("}")
                body_code = "\n".join(lines)
            else:
                # Fallback: wrap the generated body in a new block.
                cleanup_lines = self._free_arrays_in_current_scope()
                cleanup_code = "\n".join("    " + line for line in cleanup_lines) if cleanup_lines else ""
                ret_line = "\n    return this;" if add_implicit_return else ""
                init_lines = f"{init_line}\n{zero_init}\n" if zero_init else f"{init_line}\n"
                body_code = f"{{\n{init_lines}    {body_code}\n{cleanup_code}{ret_line}\n}}"
        else:
            # Regular method - add cleanup before function exits
            cleanup_lines = self._free_arrays_in_current_scope()
            if cleanup_lines and body_code.startswith("{") and body_code.endswith("}"):
                # Extract the body content (without braces)
                inner = body_code[1:-1].rstrip()
                # Add cleanup before the closing brace
                cleanup_code = "\n".join("    " + line for line in cleanup_lines)
                body_code = "{\n" + inner + "\n" + cleanup_code + "\n}"
        
        self.scope_stack = prev_scope_stack
        self._in_function = prev_in_fn
        self.symbol_table = prev_symbols

        # Pop the name scope for this method
        self.name_scope_stack.pop()

        c_class_name = self._get_c_class_name(class_name)
        mname = node.name
        return f"{ret_c} {c_class_name}_{mname}({params_sig}) {body_code}"

