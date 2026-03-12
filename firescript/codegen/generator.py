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

        # Ensure outer (main) scope exists for tracking arrays declared at top-level
        self.scope_stack = [[]]

        for child in self.ast.children:
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
        
        # Generate forward declarations for all monomorphized functions
        # This allows them to call each other regardless of definition order
        forward_decls: list[str] = []
        for mono_code in monomorphized_funcs_code:
            # Extract function signature (first line before the opening brace)
            if ' {' in mono_code:
                signature = mono_code.split(' {')[0]
                forward_decls.append(f"{signature};")
        
        # Add the main() function if it was defined
        if main_function_code:
            function_defs.append(main_function_code)

        typedefs_code = ("\n\n".join(typedefs) + "\n\n") if typedefs else ""
        constants_code = ("\n".join(constants) + "\n\n") if constants else ""
        
        # Emit forward declarations for monomorphized functions
        forward_decls_code = ("\n".join(forward_decls) + "\n\n") if forward_decls else ""
        
        # Emit monomorphized functions first, then regular functions
        all_functions = monomorphized_funcs_code + function_defs
        functions_code = ("\n\n".join(all_functions) + "\n\n") if all_functions else ""

        # Only generate wrapper main() if user didn't define one
        if not main_function_code:
            main_code = "int main(void) {\n"
            if main_lines:
                indented_body = "\n".join(
                    "    " + line for line in "\n".join(main_lines).split("\n")
                )
                main_code += f"{indented_body}\n"
            # Add cleanup for owned values declared at top level
            cleanup_lines = self._free_arrays_in_current_scope()
            if cleanup_lines:
                cleanup_code = "\n".join("    " + line for line in cleanup_lines)
                main_code += f"{cleanup_code}\n"
            # Fixed-size arrays on stack, no cleanup needed
            main_code += "    firescript_cleanup();\n"
            main_code += "    return 0;\n"
            main_code += "}\n"
        else:
            main_code = ""

        return header + typedefs_code + constants_code + forward_decls_code + functions_code + main_code

