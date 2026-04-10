from enums import NodeTypes
from parser import ASTNode, get_line_and_coumn_from_index, get_line
from utils.type_utils import is_copyable, is_owned, register_class
from typing import Optional
import logging
import os
import copy as _copy

from .base import CCodeGeneratorBase


class GenericsMixin(CCodeGeneratorBase):
    def _infer_type_args_from_call(self, func_name: str, call_node: ASTNode) -> Optional[list[str]]:
        """Infer type arguments for a generic function call based on argument types."""
        if func_name not in self.generic_templates:
            return None
        
        template = self.generic_templates[func_name]
        type_params = getattr(template, 'type_params', [])
        if not type_params:
            return []
        
        # Get parameter types from template
        param_types = []
        for child in template.children:
            if child.node_type == NodeTypes.PARAMETER:
                param_types.append(child.var_type or "")
        
        # Get argument types from call
        arg_types = []
        for arg in (call_node.children or []):
            logging.debug(f"Processing arg: {arg.node_type}, name={getattr(arg, 'name', None)}, is_array={getattr(arg, 'is_array', None)}")
            # Try to get the type from the argument node
            arg_type = getattr(arg, 'return_type', None) or getattr(arg, 'var_type', None)
            if not arg_type and arg.node_type in (NodeTypes.EQUALITY_EXPRESSION, NodeTypes.RELATIONAL_EXPRESSION):
                arg_type = "bool"
            if not arg_type:
                try:
                    arg_type = self._type_check_node(arg, self.symbol_table)
                except Exception:
                    arg_type = None
            # Check if it's an array identifier
            if arg.node_type == NodeTypes.IDENTIFIER and getattr(arg, 'is_array', False):
                # It's an array - append []
                arg_type = f"{arg_type}[]"
            
            # Apply type parameter substitution if we're in a monomorphization context
            if arg_type:
                type_map = getattr(self, '_current_type_map', {})
                logging.debug(f"  Trying to substitute arg_type={arg_type}, type_map={type_map}")
                if type_map and arg_type in type_map:
                    original_arg_type = arg_type
                    arg_type = type_map[arg_type]
                    logging.debug(f"  Substituted arg_type from {original_arg_type} to {arg_type}")
            
            if arg_type:
                logging.debug(f"  Got arg_type from node: {arg_type}")
                arg_types.append(arg_type)
            else:
                # For literals, infer from the literal value
                if arg.node_type == NodeTypes.LITERAL:
                    lit_val = str(getattr(arg, 'value', ''))
                    if lit_val.endswith('i8'):
                        arg_types.append('int8')
                    elif lit_val.endswith('i16'):
                        arg_types.append('int16')
                    elif lit_val.endswith('i32') or (lit_val.isdigit() and not any(x in lit_val for x in ['.', 'e', 'E'])):
                        arg_types.append('int32')
                    elif lit_val.endswith('i64'):
                        arg_types.append('int64')
                    elif lit_val.endswith('u8'):
                        arg_types.append('uint8')
                    elif lit_val.endswith('u16'):
                        arg_types.append('uint16')
                    elif lit_val.endswith('u32'):
                        arg_types.append('uint32')
                    elif lit_val.endswith('u64'):
                        arg_types.append('uint64')
                    elif lit_val.endswith('f32'):
                        arg_types.append('float32')
                    elif lit_val.endswith('f64') or any(x in lit_val for x in ['.', 'e', 'E']):
                        arg_types.append('float64')
                    elif lit_val.endswith('f128'):
                        arg_types.append('float128')
                    else:
                        arg_types.append('int32')  # Default
                elif arg.node_type == NodeTypes.IDENTIFIER:
                    # Look up in symbol table
                    sym_info = self.symbol_table.get(arg.name)
                    logging.debug(f"Looking up {arg.name} in symbol table: {sym_info}")
                    if sym_info:
                        # sym_info is (type, is_array, [optional_size])
                        base_type = sym_info[0]
                        is_arr = sym_info[1] if len(sym_info) > 1 else False
                        
                        # Apply type parameter substitution if we're in a monomorphization context
                        type_map = getattr(self, '_current_type_map', {})
                        logging.debug(f"Type map for substitution: {type_map}, base_type: {base_type}")
                        if type_map and base_type in type_map:
                            base_type = type_map[base_type]
                            logging.debug(f"Substituted to: {base_type}")
                        
                        if is_arr:
                            arg_types.append(f"{base_type}[]")
                        else:
                            arg_types.append(base_type)
                    else:
                        return None
                elif arg.node_type == NodeTypes.FIELD_ACCESS:
                    # e.g. t1.first — look up object type then find the field type
                    field_type = getattr(arg, 'return_type', None)
                    if field_type is None:
                        # return_type not set yet; resolve from class_fields
                        obj_node = arg.children[0] if arg.children else None
                        obj_type = None
                        if obj_node and obj_node.node_type == NodeTypes.IDENTIFIER:
                            obj_sym = self.symbol_table.get(obj_node.name)
                            if obj_sym:
                                obj_type = obj_sym[0]
                        elif obj_node is not None:
                            obj_type = getattr(obj_node, 'return_type', None) or getattr(obj_node, 'var_type', None)

                        if obj_type:
                            for fname, ftype in self.class_fields.get(obj_type, []):
                                if fname == arg.name:
                                    field_type = ftype
                                    arg.return_type = ftype  # cache for later
                                    break
                    if field_type:
                        type_map_ctx = getattr(self, '_current_type_map', {})
                        if type_map_ctx and field_type in type_map_ctx:
                            field_type = type_map_ctx[field_type]
                        arg_types.append(field_type)
                    else:
                        return None
                elif arg.node_type == NodeTypes.METHOD_CALL:
                    # Look up return type from registered class methods (handles deferred
                    # generic composite types like Option<string>.isSome())
                    method_ret = getattr(arg, 'return_type', None)
                    if method_ret is None:
                        method_name_lookup = arg.name
                        obj_recv = arg.children[0] if arg.children else None
                        recv_type = None
                        if obj_recv is not None:
                            if obj_recv.node_type == NodeTypes.IDENTIFIER:
                                sym = self.symbol_table.get(obj_recv.name)
                                if sym:
                                    recv_type = sym[0]
                            if recv_type is None:
                                recv_type = getattr(obj_recv, 'return_type', None) or getattr(obj_recv, 'var_type', None)
                        if recv_type:
                            for m in self.class_methods.get(recv_type, []):
                                if m.name == method_name_lookup and not getattr(m, 'is_constructor', False):
                                    method_ret = m.return_type
                                    arg.return_type = method_ret  # cache for later
                                    break
                    if method_ret:
                        type_map_ctx = getattr(self, '_current_type_map', {})
                        if type_map_ctx and method_ret in type_map_ctx:
                            method_ret = type_map_ctx[method_ret]
                        arg_types.append(method_ret)
                    else:
                        return None
                else:
                    return None
        
        # Build type mapping
        type_map: dict[str, str] = {}
        for param_type, arg_type in zip(param_types, arg_types):
            if param_type in type_params:
                if param_type in type_map:
                    if type_map[param_type] != arg_type:
                        # Conflicting inference
                        return None
                else:
                    type_map[param_type] = arg_type
        
        # Return inferred types in parameter order
        inferred = []
        for tp in type_params:
            if tp not in type_map:
                return None
            inferred.append(type_map[tp])
        
        return inferred

    def _collect_generic_instances(self, node: ASTNode):
        """Recursively collect all generic function calls that need monomorphization.
        
        Skip collecting from inside generic function templates during initial pass,
        since type parameters haven't been substituted yet. They'll be collected
        during instantiation when the type_map is active.
        """
        # Skip generic function templates during initial pass (when type_map is not set)
        if node.node_type == NodeTypes.FUNCTION_DEFINITION:
            if hasattr(node, 'type_params') and node.type_params:
                # Only collect from template if we're in an instantiation context (type_map is active)
                if not getattr(self, '_current_type_map', {}):
                    logging.debug(f"Skipping collection from generic template {node.name} (no type_map)")
                    return
        
        if node.node_type == NodeTypes.FUNCTION_CALL:
            func_name = node.name
            logging.debug(f"Function call to '{func_name}', in templates: {func_name in self.generic_templates}, type_args: {getattr(node, 'type_args', None)}")
            if func_name in self.generic_templates:
                # This is a generic function call
                type_args = getattr(node, 'type_args', [])
                
                # If type arguments weren't set during parsing, try to infer them now
                # Always re-infer if we're in a monomorphization context (type_map is set)
                # since the same generic function in different instantiations may have different concrete types
                if not type_args or getattr(self, '_current_type_map', {}):
                    inferred = self._infer_type_args_from_call(func_name, node)
                    logging.debug(f"Inferred type args for {func_name}: {inferred}")
                    if inferred:
                        type_args = inferred
                        logging.debug(f"Using inferred type args for {func_name}: {type_args}")
                
                if type_args:
                    key = (func_name, tuple(type_args))
                    if key not in self.monomorphized_funcs:
                        # Generate mangled name
                        mangled = self._mangle_generic_name(func_name, tuple(type_args))
                        self.monomorphized_funcs[key] = mangled
                        logging.debug(f"Added monomorphized {func_name} with types {type_args} as {mangled}")
        
        # Recurse into children
        for child in (node.children or []):
            if child:
                self._collect_generic_instances(child)

    def _instantiate_generic_function(self, func_name: str, type_args: tuple[str, ...]) -> str:
        """Generate C code for a monomorphized instance of a generic function."""
        template = self.generic_templates[func_name]
        type_params = getattr(template, 'type_params', [])
        
        # Build type substitution map
        type_map = dict(zip(type_params, type_args))
        
        # Substitute types in the function definition
        def substitute_type(t: str) -> str:
            return type_map.get(t, t)
        
        # Get return type and substitute
        ret_type_fs = template.return_type or "void"
        if template.is_array:
            ret_type_fs = ret_type_fs + "[]"
        
        # Substitute type parameters in return type
        for tp, concrete in type_map.items():
            ret_type_fs = ret_type_fs.replace(tp, concrete)
        
        ret_c = self._map_type_to_c(ret_type_fs)
        
        # Get mangled name
        mangled_name = self.monomorphized_funcs[(func_name, type_args)]
        
        # Push a new name scope for this function BEFORE building params
        self.name_scope_stack.append({})
        
        # Build parameters with substituted types
        params = []
        body_node = None
        for child in template.children:
            if child.node_type == NodeTypes.PARAMETER:
                base_type = child.var_type or "int32"
                # Substitute type parameters
                base_type = substitute_type(base_type)
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
        
        # Save and prepare symbol table for function scope
        prev_symbols = self.symbol_table.copy()
        # Store array sizes from call site
        array_size_map = {}
        for child in template.children:
            if child.node_type == NodeTypes.PARAMETER:
                base_type = substitute_type(child.var_type or "int32")
                # Check if the substituted type is an array
                param_is_array = base_type.endswith("[]")
                actual_is_array = child.is_array or param_is_array
                if actual_is_array:
                    elem_type = base_type[:-2] if param_is_array else base_type
                    mangled_param = self._mangle_name(child.name)
                    # Only store _len var name when the param was explicitly declared as T[]
                    # (child.is_array=True). When T itself resolves to an array type, the
                    # monomorphized function has no _len param and _len is unavailable.
                    if child.is_array:
                        self.symbol_table[child.name] = (elem_type, True, f"{mangled_param}_len")
                    else:
                        self.symbol_table[child.name] = (elem_type, True, None)
                else:
                    self.symbol_table[child.name] = (base_type, False)
        
        # Save current type substitution context
        prev_type_map = getattr(self, '_current_type_map', {})
        self._current_type_map = type_map
        
        # Track current function name for error messages
        prev_function_name = getattr(self, '_current_function_name', None)
        self._current_function_name = func_name
        
        # Generate body
        prev_in_fn = self._in_function
        self._in_function = True
        prev_scope_stack = self.scope_stack
        self.scope_stack = [[]]
        
        # Collect generic instances within the body while type_map is active
        # This handles nested generic calls like println(T) inside swap<T>
        if body_node:
            self._collect_generic_instances(body_node)
        
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
        self.symbol_table = prev_symbols
        self._current_type_map = prev_type_map
        
        # Pop the name scope for this function
        self.name_scope_stack.pop()
        
        return f"{ret_c} {mangled_name}({params_sig}) {body_code}"

    def _collect_generic_class_instances(self, node: ASTNode) -> None:
        """Recursively collect all composite generic class type usages for monomorphization.

        Looks for:
        - VARIABLE_DECLARATION with var_type containing '<'
        - CONSTRUCTOR_CALL with name containing '<'
        - FUNCTION_CALL with name matching a generic class template (or containing '<')
        """
        if node.node_type == NodeTypes.VARIABLE_DECLARATION:
            vt = getattr(node, "var_type", None)
            if vt and "<" in vt:
                self._ensure_mono_class(vt)
        elif node.node_type == NodeTypes.CONSTRUCTOR_CALL:
            name = getattr(node, "name", "")
            if name and "<" in name:
                self._ensure_mono_class(name)
        elif node.node_type == NodeTypes.FUNCTION_CALL:
            name = getattr(node, "name", "")
            if name and "<" in name:
                self._ensure_mono_class(name)

        for child in (node.children or []):
            if child:
                self._collect_generic_class_instances(child)

    def _ensure_mono_class(self, composite: str) -> None:
        """Parse composite name and call _register_mono_class if not already done."""
        if composite in self.monomorphized_classes:
            return
        if "<" not in composite:
            return
        bracket = composite.index("<")
        template_name = composite[:bracket]
        if template_name not in self.generic_class_templates:
            return
        args_str = composite[bracket + 1:]
        if args_str.endswith(">"):
            args_str = args_str[:-1]
        type_args = [a.strip() for a in args_str.split(",")]
        self._register_mono_class(composite, template_name, type_args)

    def _register_mono_class(self, composite: str, template_name: str, type_args: list[str]) -> None:
        """Register a monomorphized generic class instance so it gets typedef+method emission."""
        if composite in self.monomorphized_classes:
            return
        self.monomorphized_classes.add(composite)

        template = self.generic_class_templates.get(template_name)
        if template is None:
            return

        type_params = getattr(template, 'type_params', [])
        type_map = dict(zip(type_params, type_args))
        is_copyable_class = getattr(template, 'is_copyable', False)

        def substitute(t: str) -> str:
            if t is None:
                return "int32"
            return type_map.get(t, t)

        c_name = self._mangle_class_composite_name(composite)

        # Register in class_names, class_fields, class_methods
        self.class_names.add(composite)
        register_class(composite, is_copyable_class)

        concrete_fields: list[tuple[str, str]] = []
        for ch in template.children:
            if ch.node_type == NodeTypes.CLASS_FIELD:
                concrete_fields.append((ch.name, substitute(ch.var_type or "int32")))
        self.class_fields[composite] = concrete_fields

        # Build concrete method nodes (deep copy with substituted types)
        concrete_methods: list[ASTNode] = []
        for m in template.children:
            if m.node_type != NodeTypes.CLASS_METHOD_DEFINITION:
                continue
            dm = _copy.deepcopy(m)
            # Substitute type parameters in parameter types and return type
            for ch in dm.children:
                if ch.node_type == NodeTypes.PARAMETER:
                    ch.var_type = substitute(ch.var_type or "int32")
                    # The synthetic 'this' receiver has var_type equal to the template class
                    # name which is not a type parameter itself, so substitute() leaves it
                    # unchanged.  Replace it with the composite name so the emitted C
                    # signature uses the correct monomorphized struct type.
                    if ch.name == "this" and ch.var_type == template_name:
                        ch.var_type = composite
            # Substitute return type (constructors use the template name as return type;
            # replace it with the composite name so codegen emits the right C struct type)
            if dm.return_type:
                rt = substitute(dm.return_type)
                # If the return type is still the template class name, replace with composite
                if rt == template_name:
                    rt = composite
                dm.return_type = rt
            # Tag with the composite class name so _emit_method_definition uses the right C struct name
            setattr(dm, "class_name", composite)
            setattr(dm, "_composite_c_name", c_name)
            concrete_methods.append(dm)
        self.class_methods[composite] = concrete_methods

    def _emit_generic_class_instance(self, composite: str) -> tuple[str, list[str]]:
        """Emit the C typedef struct and method functions for a monomorphized generic class.

        Returns (typedef_str, [method_code, ...]).
        """
        c_name = self._mangle_class_composite_name(composite)
        is_copyable_class = is_copyable(composite, False)

        # Build typedef
        fields = self.class_fields.get(composite, [])
        td_lines = [f"typedef struct {c_name} {{"]
        for fname, ftype in fields:
            ctype = self._map_type_to_c(ftype)
            td_lines.append(f"    {ctype} {fname};")
        td_lines.append(f"}} {c_name};")
        typedef_str = "\n".join(td_lines)

        # Build method functions
        method_codes = []
        for m in self.class_methods.get(composite, []):
            mcode = self._emit_method_definition(composite, m)
            if mcode:
                method_codes.append(mcode)

        return typedef_str, method_codes

