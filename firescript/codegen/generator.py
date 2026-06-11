from enums import NodeTypes
from parser import ASTNode, get_line_and_coumn_from_index, get_line
from utils.type_utils import is_copyable, is_owned, register_class
from typing import Optional
import logging
import os
from .statements import StatementsMixin


class GeneratorMixin(StatementsMixin):
    def generate(self) -> str:
        """Generate C code from the AST"""
        header = "#include <stdio.h>\n#include <stdbool.h>\n#include <stdint.h>\n#include <inttypes.h>\n#include <string.h>\n"
        header += '#include "firescript/runtime/runtime.h"\n'
        header += '#include "firescript/runtime/conversions.h"\n'
        
        # First pass: collect all generic function and class instantiations needed
        for child in self.ast.children:
            self._collect_generic_instances(child)
            self._collect_generic_class_instances(child)
        
        # Emit class typedefs, then constant declarations, then function definitions, then the main body statements
        typedefs: list[str] = []
        constants: list[str] = []
        function_defs: list[str] = []
        monomorphized_funcs_code: list[str] = []  # Keep monomorphized functions separate
        main_lines: list[str] = []
        main_function_code: str | None = None  # Store the main() function separately


        for child in self.ast.children:
            if child.node_type == NodeTypes.GENERATOR_DEFINITION:
                gen_code = self._emit_generator_definition(child)
                if gen_code:
                    typedefs.append(gen_code[0])
                    function_defs.extend(gen_code[1])
                continue
            if child.node_type == NodeTypes.FUNCTION_DEFINITION:
                # Skip generic templates - they'll be instantiated on demand
                if hasattr(child, 'type_params') and child.type_params:
                    continue
                # Check if this is the main() function
                if child.name == "main":
                    main_function_code = self._emit_function_definition(child)
                else:
                    func_code = self._emit_function_definition(child)
                    if func_code:
                        function_defs.append(func_code)
            elif child.node_type == NodeTypes.CLASS_DEFINITION:
                # Skip generic class templates — concrete instances are emitted via monomorphization
                if getattr(child, 'type_params', []):
                    continue
                typedefs.append(self._emit_class_typedef(child))
                # Emit destructor if the class has owned fields
                if self._class_needs_destructor(child.name):
                    dtor = self._emit_destructor(child.name)
                    if dtor:
                        function_defs.append(dtor)
                # Emit method functions for this class
                for m in self.class_methods.get(child.name, []):
                    mcode = self._emit_method_definition(child.name, m)
                    if mcode:
                        function_defs.append(mcode)
            elif child.node_type == NodeTypes.VARIABLE_DECLARATION and getattr(child, 'is_const', False):
                # Emit const declarations as global constants
                const_code = self._emit_const_declaration(child)
                if const_code:
                    constants.append(const_code)
            else:
                stmt_code = self.emit_statement(child)
                if stmt_code:
                    main_lines.append(stmt_code)

        # Emit monomorphized generic class instances BEFORE regular class typedefs
        for composite in list(self.monomorphized_classes):
            td, methods = self._emit_generic_class_instance(composite)
            if td:
                typedefs.insert(0, td)
            for mcode in methods:
                if mcode:
                    function_defs.insert(0, mcode)

        # Emit monomorphized generic function instances BEFORE regular functions
        # Keep instantiating until no new instances are discovered
        instantiated_keys = set()
        iteration = 0
        while True:
            iteration += 1
            logging.debug(f"Monomorphization iteration {iteration}, total instances: {len(self.monomorphized_funcs)}, instantiated: {len(instantiated_keys)}")
            keys_to_instantiate = [k for k in self.monomorphized_funcs.keys() if k not in instantiated_keys]
            logging.debug(f"  Keys to instantiate this iteration: {keys_to_instantiate}")
            if not keys_to_instantiate:
                break
            for key in keys_to_instantiate:
                func_name, type_args = key
                logging.debug(f"  Instantiating {func_name} with {type_args}")
                mono_code = self._instantiate_generic_function(func_name, type_args)
                if mono_code:
                    monomorphized_funcs_code.append(mono_code)
                instantiated_keys.add(key)
        
        # Generate forward declarations for generated functions so calls are
        # order-independent (methods may call helpers emitted later).
        forward_decls: list[str] = []

        def _extract_signature(code: str) -> str | None:
            if ' {' in code:
                return code.split(' {')[0]
            return None
        
        # Add the main() function if it was defined
        if main_function_code:
            function_defs.append(main_function_code)

        typedefs_code = ("\n\n".join(typedefs) + "\n\n") if typedefs else ""
        constants_code = ("\n".join(constants) + "\n\n") if constants else ""
        
        all_functions = monomorphized_funcs_code + function_defs

        seen_decl_sigs: set[str] = set()
        for fn_code in all_functions:
            sig = _extract_signature(fn_code)
            if sig and sig not in seen_decl_sigs:
                forward_decls.append(f"{sig};")
                seen_decl_sigs.add(sig)

        # Emit forward declarations for generated functions
        forward_decls_code = ("\n".join(forward_decls) + "\n\n") if forward_decls else ""

        # Emit monomorphized functions first, then regular functions
        functions_code = ("\n\n".join(all_functions) + "\n\n") if all_functions else ""

        # Only generate wrapper main() if user didn't define one
        if not main_function_code:
            main_code = "int main(int argc, char **argv) {\n"
            main_code += "    firescript_set_process_args(argc, argv);\n"
            if main_lines:
                indented_body = "\n".join(
                    "    " + line for line in "\n".join(main_lines).split("\n")
                )
                main_code += f"{indented_body}\n"
            main_code += "    firescript_cleanup();\n"
            main_code += "    return 0;\n"
            main_code += "}\n"
        else:
            main_code = ""

        return header + typedefs_code + constants_code + forward_decls_code + functions_code + main_code

    # -------------------------------------------------------------------------
    # Generator (language feature) emission
    # -------------------------------------------------------------------------

    def _collect_gen_locals(self, node: ASTNode, locals_out: list) -> None:
        """Recursively collect all VARIABLE_DECLARATION names+types from a body."""
        if node is None:
            return
        if node.node_type == NodeTypes.VARIABLE_DECLARATION:
            locals_out.append((node.name, node.var_type or "int32", node.is_array))
        for child in (node.children or []):
            if child is not None:
                self._collect_gen_locals(child, locals_out)

    def _collect_yield_count(self, node: ASTNode) -> int:
        """Count YIELD_STATEMENT nodes in a subtree."""
        if node is None:
            return 0
        count = 1 if node.node_type == NodeTypes.YIELD_STATEMENT else 0
        for child in (node.children or []):
            if child is not None:
                count += self._collect_yield_count(child)
        return count

    def _emit_gen_body(self, node: ASTNode, yield_counter: list, struct_var: str,
                       c_yield_type: str, gen_locals: set) -> str:
        """Emit a generator body node, replacing yield with state-machine code."""
        if node is None:
            return ""

        if node.node_type == NodeTypes.YIELD_STATEMENT:
            yid = yield_counter[0]
            yield_counter[0] += 1
            val_code = self._emit_gen_expr(node.children[0], struct_var, gen_locals)
            label_name = f"_gen_resume_{struct_var[1:]}_{yid}"  # unique per generator
            return (
                f"*_out = {val_code};\n"
                f"{struct_var}->_state = {yid};\n"
                f"return true;\n"
                f"{label_name}:;"
            )

        if node.node_type == NodeTypes.SCOPE:
            lines = []
            for child in (node.children or []):
                if child is not None:
                    lines.append(self._emit_gen_body(child, yield_counter, struct_var, c_yield_type, gen_locals))
            return "{\n" + "\n".join(lines) + "\n}"

        if node.node_type == NodeTypes.VARIABLE_DECLARATION:
            # Assign into struct field instead of declaring a local
            var_name = node.name
            mangled = self._mangle_name(var_name)
            if node.children:
                rhs = self._emit_gen_expr(node.children[0], struct_var, gen_locals)
                return f"{struct_var}->{mangled} = {rhs};"
            return ""

        if node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            target = node.name
            mangled = self._mangle_name(target)
            if node.node_type == NodeTypes.SCOPE:
                # wrapped drop+assign — emit children
                lines = []
                for child in (node.children or []):
                    if child is not None:
                        lines.append(self._emit_gen_body(child, yield_counter, struct_var, c_yield_type, gen_locals))
                return "\n".join(lines)
            rhs = self._emit_gen_expr(node.children[0], struct_var, gen_locals) if node.children else ""
            if target in gen_locals:
                return f"{struct_var}->{mangled} = {rhs};"
            return f"{mangled} = {rhs};"

        if node.node_type == NodeTypes.WHILE_STATEMENT:
            cond = self._emit_gen_expr(node.children[0], struct_var, gen_locals)
            body = self._emit_gen_body(node.children[1], yield_counter, struct_var, c_yield_type, gen_locals)
            return f"while ({cond})\n{body}"

        if node.node_type == NodeTypes.IF_STATEMENT:
            cond = self._emit_gen_expr(node.children[0], struct_var, gen_locals)
            then_b = self._emit_gen_body(node.children[1], yield_counter, struct_var, c_yield_type, gen_locals)
            result = f"if ({cond})\n{then_b}"
            if len(node.children) > 2:
                else_b = self._emit_gen_body(node.children[2], yield_counter, struct_var, c_yield_type, gen_locals)
                result += f"\nelse\n{else_b}"
            return result

        if node.node_type == NodeTypes.FOR_STATEMENT:
            # C-style for loop — emit init/cond/incr/body using gen context
            init_node, cond_node, incr_node, body_node = node.children[:4]
            init = self._emit_gen_body(init_node, yield_counter, struct_var, c_yield_type, gen_locals).rstrip(";")
            cond = self._emit_gen_expr(cond_node, struct_var, gen_locals)
            incr = self._emit_gen_body(incr_node, yield_counter, struct_var, c_yield_type, gen_locals).rstrip(";")
            body = self._emit_gen_body(body_node, yield_counter, struct_var, c_yield_type, gen_locals)
            return f"for ({init}; {cond}; {incr})\n{body}"

        if node.node_type == NodeTypes.RETURN_STATEMENT:
            # bare return in a generator = exhaustion
            return f"{struct_var}->_state = -1;\nreturn false;"

        if node.node_type == NodeTypes.BREAK_STATEMENT:
            return "break;"

        if node.node_type == NodeTypes.CONTINUE_STATEMENT:
            return "continue;"

        if node.node_type == NodeTypes.COMPOUND_ASSIGNMENT:
            target = node.name  # variable name (same as regular codegen)
            op_type = getattr(node.token, "type", None)
            mangled = self._mangle_name(target)
            rhs = self._emit_gen_expr(node.children[0], struct_var, gen_locals) if node.children else "0"
            op_map = {"ADD_ASSIGN": "+=", "SUBTRACT_ASSIGN": "-=", "MULTIPLY_ASSIGN": "*=",
                      "DIVIDE_ASSIGN": "/=", "MODULO_ASSIGN": "%="}
            c_op = op_map.get(op_type or "", "+=")
            if target in gen_locals:
                return f"{struct_var}->{mangled} {c_op} {rhs};"
            return f"{mangled} {c_op} {rhs};"

        if node.node_type == NodeTypes.UNARY_EXPRESSION:
            target = node.name  # variable name
            mangled = self._mangle_name(target)
            field = f"{struct_var}->{mangled}" if target in gen_locals else mangled
            op = node.token.type if node.token else "++"
            op_str = "++" if op == "INCREMENT" else "--"
            return f"{field}{op_str};"

        # Fallback: emit as expression statement
        code = self._emit_gen_expr(node, struct_var, gen_locals)
        if code:
            return code + ";"
        return ""

    def _emit_gen_expr(self, node: ASTNode, struct_var: str, gen_locals: set) -> str:
        """Emit an expression inside a generator body, redirecting locals to struct fields."""
        if node is None:
            return ""

        if node.node_type == NodeTypes.IDENTIFIER:
            mangled = self._mangle_name(node.name)
            if node.name in gen_locals:
                return f"{struct_var}->{mangled}"
            return mangled

        # For everything else, delegate to regular _visit but patch IDENTIFIER nodes temporarily
        # We use a recursive approach here
        if node.node_type == NodeTypes.LITERAL:
            return self._visit(node)

        if node.node_type == NodeTypes.BINARY_EXPRESSION:
            left = self._emit_gen_expr(node.children[0], struct_var, gen_locals)
            right = self._emit_gen_expr(node.children[1], struct_var, gen_locals)
            return f"({left} {node.name} {right})"

        if node.node_type == NodeTypes.RELATIONAL_EXPRESSION:
            left = self._emit_gen_expr(node.children[0], struct_var, gen_locals)
            right = self._emit_gen_expr(node.children[1], struct_var, gen_locals)
            return f"({left} {node.name} {right})"

        if node.node_type == NodeTypes.EQUALITY_EXPRESSION:
            left = self._emit_gen_expr(node.children[0], struct_var, gen_locals)
            right = self._emit_gen_expr(node.children[1], struct_var, gen_locals)
            return f"({left} {node.name} {right})"

        if node.node_type == NodeTypes.UNARY_EXPRESSION and node.name == "neg":
            operand = self._emit_gen_expr(node.children[0], struct_var, gen_locals)
            return f"(-{operand})"

        if node.node_type == NodeTypes.FUNCTION_CALL:
            args = [self._emit_gen_expr(c, struct_var, gen_locals) for c in node.children]
            mangled = self._mangle_function_name(node.name)
            return f"{mangled}({', '.join(args)})"

        if node.node_type == NodeTypes.CAST_EXPRESSION:
            target_type = node.var_type or "int32"
            c_type = self._map_type_to_c(target_type)
            expr = self._emit_gen_expr(node.children[0], struct_var, gen_locals) if node.children else ""
            return f"(({c_type}){expr})"

        # Fallback: use regular _visit (won't redirect locals but handles exotic cases)
        return self._visit(node)

    def _emit_generator_definition(self, node: ASTNode):
        """
        Emit a generator state-machine struct + new/next functions.
        Returns (typedef_str, [function_str, ...]).
        """
        gen_name = node.name
        yield_type = getattr(node, "yield_type", node.return_type or "int32")
        c_yield_type = self._map_type_to_c(yield_type)

        # Separate params from body (body is last child)
        params = [c for c in node.children[:-1] if c.node_type == NodeTypes.PARAMETER]
        body = node.children[-1]

        # Collect all locals declared in the generator body
        locals_list: list = []
        self._collect_gen_locals(body, locals_list)
        # gen_locals: set of firescript names (un-mangled) — includes params + locals
        param_names = {p.name for p in params}
        gen_locals: set = param_names | {name for name, _, _ in locals_list}

        # Register the generator in name scope so mangling is consistent
        self.name_scope_stack.append({})
        for p in params:
            self._mangle_name(p.name)
        for (lname, _, _) in locals_list:
            self._mangle_name(lname)

        # Count yields to build switch cases
        yield_count = self._collect_yield_count(body)

        # ---- Struct typedef ----
        struct_name = f"_gen_{gen_name}"
        lines = [f"typedef struct {{", f"    int _state;"]
        for p in params:
            c_t = self._map_type_to_c(p.var_type or "int32")
            mangled_p = self._mangle_name(p.name)
            lines.append(f"    {c_t} {mangled_p};")
        for (lname, ltype, lis_array) in locals_list:
            c_t = self._map_type_to_c(ltype + ("[]" if lis_array else ""))
            mangled_l = self._mangle_name(lname)
            lines.append(f"    {c_t} {mangled_l};")
        lines.append(f"}} {struct_name};")
        typedef_str = "\n".join(lines)

        # ---- _new function ----
        param_sig = ", ".join(
            f"{self._map_type_to_c(p.var_type or 'int32')} {self._mangle_name(p.name)}"
            for p in params
        )
        new_lines = [f"{struct_name} {gen_name}_gen_new({param_sig}) {{"]
        new_lines.append(f"    {struct_name} _g;")
        new_lines.append(f"    _g._state = 0;")
        for p in params:
            mangled_p = self._mangle_name(p.name)
            new_lines.append(f"    _g.{mangled_p} = {mangled_p};")
        for (lname, ltype, _) in locals_list:
            mangled_l = self._mangle_name(lname)
            c_t = self._map_type_to_c(ltype)
            new_lines.append(f"    _g.{mangled_l} = ({c_t})0;")
        new_lines.append(f"    return _g;")
        new_lines.append(f"}}")
        new_func = "\n".join(new_lines)

        # ---- _next function ----
        next_lines = [f"bool {gen_name}_gen_next({struct_name}* _gs, {c_yield_type}* _out) {{"]
        # switch for resumption
        next_lines.append(f"    if (_gs->_state == -1) return false;")
        if yield_count > 0:
            next_lines.append(f"    switch (_gs->_state) {{")
            for yid in range(1, yield_count + 1):
                label_name = f"_gen_resume_gs_{yid}"
                next_lines.append(f"        case {yid}: goto {label_name};")
            next_lines.append(f"    }}")
        # emit body
        yield_counter = [1]
        body_code = self._emit_gen_body(body, yield_counter, "_gs", c_yield_type, gen_locals)
        # indent body
        for line in body_code.split("\n"):
            next_lines.append(f"    {line}")
        next_lines.append(f"    _gs->_state = -1;")
        next_lines.append(f"    return false;")
        next_lines.append(f"}}")
        next_func = "\n".join(next_lines)

        self.name_scope_stack.pop()

        # Register the generator type name so for-in can detect it
        self.generator_types[gen_name] = (struct_name, yield_type)

        return (typedef_str, [new_func, next_func])

