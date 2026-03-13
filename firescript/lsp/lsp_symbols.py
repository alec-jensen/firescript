"""Symbol, import, completion, and hover helpers for the firescript LSP."""

import os
from typing import Optional

from lsprotocol.types import CompletionItemKind, Position

from enums import NodeTypes
from imports import ModuleResolver
from firescript.lsp.lsp_utils import (
    cursor_offset,
    find_block_end,
    offset_to_position,
    path_to_uri,
    try_parse,
)
from parser import ASTNode


def walk_scope(
    node: ASTNode,
    source: str,
    cursor_offset_value: int,
    out: list[tuple[str, CompletionItemKind, str]],
    in_scope: bool,
) -> None:
    """Recursively collect symbols visible at cursor_offset_value."""
    for child in (node.children or []):
        if child is None:
            continue

        if child.node_type == NodeTypes.VARIABLE_DECLARATION:
            if in_scope and child.name and child.index <= cursor_offset_value:
                out.append((child.name, CompletionItemKind.Variable, child.var_type or ""))

        elif child.node_type == NodeTypes.FUNCTION_DEFINITION:
            if in_scope and child.name:
                out.append((child.name, CompletionItemKind.Function, child.return_type or child.var_type or ""))
            fn_end = find_block_end(source, child.index)
            cursor_inside = child.index <= cursor_offset_value <= fn_end
            walk_scope(child, source, cursor_offset_value, out, in_scope=cursor_inside)

        elif child.node_type == NodeTypes.CLASS_DEFINITION:
            if in_scope and child.name:
                out.append((child.name, CompletionItemKind.Class, ""))

        elif child.node_type == NodeTypes.PARAMETER:
            if in_scope and child.name:
                out.append((child.name, CompletionItemKind.Variable, child.var_type or ""))

        elif child.node_type == NodeTypes.SCOPE:
            scope_end = find_block_end(source, child.index)
            cursor_inside = child.index <= cursor_offset_value <= scope_end
            walk_scope(child, source, cursor_offset_value, out, in_scope=cursor_inside)

        else:
            walk_scope(child, source, cursor_offset_value, out, in_scope=in_scope)


def collect_import_symbols(
    ast_root: ASTNode,
    file_path: str,
    out: list[tuple[str, CompletionItemKind, str]],
) -> None:
    """Collect completion items for names introduced by import statements."""
    import_root = os.path.dirname(os.path.abspath(file_path)) if file_path else None
    try:
        resolver = ModuleResolver(import_root)
    except Exception:
        return

    for child in (ast_root.children or []):
        if child is None or child.node_type != NodeTypes.IMPORT_STATEMENT:
            continue

        module_path: str = getattr(child, "module_path", "") or ""
        kind: str = getattr(child, "kind", "module") or "module"
        alias: Optional[str] = getattr(child, "alias", None)
        symbols: list[dict] = getattr(child, "symbols", []) or []

        if kind == "external" or not module_path:
            continue

        try:
            if kind == "module":
                name = alias or module_path.rsplit(".", 1)[-1]
                out.append((name, CompletionItemKind.Module, module_path))
                continue

            mod_file = resolver.dotted_to_path(module_path)
            if not os.path.isfile(mod_file):
                continue
            with open(mod_file, "r", encoding="utf-8") as f:
                mod_text = f.read()
            mod_ast = try_parse(mod_text, mod_file)
            if mod_ast is None:
                continue

            exports: dict[str, tuple[CompletionItemKind, str]] = {}
            for node in (mod_ast.children or []):
                if node is None or not node.name:
                    continue
                if node.node_type == NodeTypes.FUNCTION_DEFINITION:
                    exports[node.name] = (CompletionItemKind.Function, node.return_type or node.var_type or "")
                elif node.node_type == NodeTypes.CLASS_DEFINITION:
                    exports[node.name] = (CompletionItemKind.Class, "")
                elif node.node_type == NodeTypes.VARIABLE_DECLARATION:
                    exports[node.name] = (CompletionItemKind.Variable, node.var_type or "")

            if kind == "wildcard":
                for name, (item_kind, detail) in exports.items():
                    out.append((name, item_kind, detail))
            elif kind == "symbols":
                for sym in symbols:
                    sym_name = sym.get("name", "")
                    sym_alias = sym.get("alias") or sym_name
                    if sym_name in exports:
                        item_kind, detail = exports[sym_name]
                        out.append((sym_alias, item_kind, detail))
                    elif sym_name:
                        out.append((sym_alias, CompletionItemKind.Function, ""))
        except Exception:
            pass


def build_symbol_map(node: ASTNode, out: dict[str, ASTNode]) -> None:
    """Populate out with name -> ASTNode bindings; first definition wins."""
    for child in (node.children or []):
        if child is None:
            continue
        if child.node_type in (
            NodeTypes.VARIABLE_DECLARATION,
            NodeTypes.FUNCTION_DEFINITION,
            NodeTypes.CLASS_DEFINITION,
            NodeTypes.PARAMETER,
        ) and child.name:
            if child.name not in out:
                out[child.name] = child
        build_symbol_map(child, out)


def format_hover(node: ASTNode) -> str:
    """Return a Markdown code-fenced hover string for a symbol node."""
    if node.node_type == NodeTypes.FUNCTION_DEFINITION:
        params = [
            c for c in (node.children or [])
            if c is not None and c.node_type == NodeTypes.PARAMETER
        ]
        param_strs = []
        for p in params:
            t = p.var_type or "?"
            arr = "[]" if getattr(p, "is_array", False) else ""
            ref = "&" if getattr(p, "is_ref", False) else ""
            param_strs.append(f"{ref}{t}{arr} {p.name}")
        ret = node.var_type or node.return_type or "void"
        arr = "[]" if getattr(node, "is_array", False) else ""
        return f"```firescript\n{ret}{arr} {node.name}({', '.join(param_strs)})\n```"
    if node.node_type == NodeTypes.CLASS_DEFINITION:
        return f"```firescript\nclass {node.name}\n```"
    if node.node_type in (NodeTypes.VARIABLE_DECLARATION, NodeTypes.PARAMETER):
        mods = ""
        if getattr(node, "is_const", False):
            mods += "const "
        if getattr(node, "is_nullable", False):
            mods += "nullable "
        t = node.var_type or "?"
        arr = "[]" if getattr(node, "is_array", False) else ""
        decl = f"{mods}{t}{arr} {node.name}"
        if getattr(node, "is_const", False):
            value_node = next(
                (c for c in (node.children or [])
                 if c is not None and c.node_type not in (NodeTypes.PARAMETER,) and getattr(c, "token", None) is not None),
                None,
            )
            if value_node is not None:
                decl += f" = {value_node.token.value}"
        return f"```firescript\n{decl}\n```"
    return ""


def find_field_access_at_offset(node: ASTNode, cursor_off: int) -> Optional[ASTNode]:
    """Return the field-access node whose field-name token covers cursor_off."""
    if node.node_type == NodeTypes.FIELD_ACCESS:
        tok = node.token
        if tok is not None:
            start = tok.index
            end = start + len(node.name)
            if start <= cursor_off <= end:
                return node
    for child in (node.children or []):
        if child is None:
            continue
        result = find_field_access_at_offset(child, cursor_off)
        if result is not None:
            return result
    return None


def find_method_call_at_offset(node: ASTNode, cursor_off: int) -> Optional[ASTNode]:
    """Return the method-call node whose method-name token covers cursor_off."""
    if node.node_type == NodeTypes.METHOD_CALL:
        tok = node.token
        if tok is not None:
            start = tok.index
            end = start + len(node.name)
            if start <= cursor_off <= end:
                return node
    for child in (node.children or []):
        if child is None:
            continue
        result = find_method_call_at_offset(child, cursor_off)
        if result is not None:
            return result
    return None


def resolve_imported_symbol(
    ast_root: ASTNode,
    word: str,
    file_path: str,
) -> Optional[tuple[str, str, ASTNode]]:
    """Resolve an imported name to its definition."""
    import_root = os.path.dirname(os.path.abspath(file_path)) if file_path else None
    try:
        resolver = ModuleResolver(import_root)
    except Exception:
        return None

    for child in (ast_root.children or []):
        if child is None or child.node_type != NodeTypes.IMPORT_STATEMENT:
            continue

        module_path: str = getattr(child, "module_path", "") or ""
        kind: str = getattr(child, "kind", "module") or "module"
        symbols: list[dict] = getattr(child, "symbols", []) or []

        if kind == "external" or not module_path:
            continue

        if kind == "module":
            last_seg = module_path.rsplit(".", 1)[-1]
            parent_path = module_path.rsplit(".", 1)[0] if "." in module_path else ""
            if last_seg != word or not parent_path:
                continue
            try:
                mod_file = resolver.dotted_to_path(parent_path)
                if not os.path.isfile(mod_file):
                    continue
                with open(mod_file, "r", encoding="utf-8") as f:
                    mod_text = f.read()
                mod_ast = try_parse(mod_text, mod_file)
                if mod_ast is None:
                    continue
                msym: dict[str, ASTNode] = {}
                build_symbol_map(mod_ast, msym)
                def_node = msym.get(word)
                if def_node is not None:
                    return (mod_file, mod_text, def_node)
            except Exception:
                pass
            continue

        target_name: Optional[str] = None
        if kind == "wildcard":
            target_name = word
        elif kind == "symbols":
            for sym in symbols:
                alias = sym.get("alias") or sym.get("name", "")
                if alias == word:
                    target_name = sym.get("name", "")
                    break

        if not target_name:
            continue

        try:
            mod_file = resolver.dotted_to_path(module_path)
            if not os.path.isfile(mod_file):
                continue
            with open(mod_file, "r", encoding="utf-8") as f:
                mod_text = f.read()
            mod_ast = try_parse(mod_text, mod_file)
            if mod_ast is None:
                continue
            sym_map: dict[str, ASTNode] = {}
            build_symbol_map(mod_ast, sym_map)
            def_node = sym_map.get(target_name)
            if def_node is None:
                continue
            return (mod_file, mod_text, def_node)
        except Exception:
            pass

    return None


def find_import_definition(
    ast_root: ASTNode,
    word: str,
    file_path: str,
) -> Optional[tuple[str, Position]]:
    """Return (file_uri, Position) of the definition of word in an imported module."""
    result = resolve_imported_symbol(ast_root, word, file_path)
    if result is None:
        return None
    mod_file, mod_text, def_node = result
    def_pos = offset_to_position(mod_text, def_node.index)
    return (path_to_uri(mod_file), def_pos)


def find_class_node(ast: ASTNode, class_name: str, file_path: str) -> Optional[ASTNode]:
    """Find the class definition node for class_name."""
    for child in (ast.children or []):
        if child is None:
            continue
        if child.node_type == NodeTypes.CLASS_DEFINITION and getattr(child, "name", None) == class_name:
            return child

    result = resolve_imported_symbol(ast, class_name, file_path)
    if result is not None:
        _mod_file, _mod_text, def_node = result
        if def_node.node_type == NodeTypes.CLASS_DEFINITION:
            return def_node

    import_root = os.path.dirname(os.path.abspath(file_path)) if file_path else None
    try:
        resolver = ModuleResolver(import_root)
    except Exception:
        return None

    for child in (ast.children or []):
        if child is None or child.node_type != NodeTypes.IMPORT_STATEMENT:
            continue
        if getattr(child, "kind", "") != "module":
            continue
        module_path: str = getattr(child, "module_path", "") or ""
        if not module_path:
            continue
        last_component = module_path.rsplit(".", 1)[-1]
        if last_component != class_name:
            continue
        try:
            mod_file = resolver.dotted_to_path(module_path)
            if not os.path.isfile(mod_file):
                continue
            with open(mod_file, "r", encoding="utf-8") as f:
                mod_text = f.read()
            mod_ast = try_parse(mod_text, mod_file)
            if mod_ast is None:
                continue
            for mchild in (mod_ast.children or []):
                if (
                    mchild is not None
                    and mchild.node_type == NodeTypes.CLASS_DEFINITION
                    and mchild.name == class_name
                ):
                    return mchild
        except Exception:
            pass

    return None


def hover_field_access(
    fa_node: ASTNode,
    ast: ASTNode,
    sym_map: dict,
    file_path: str,
) -> Optional[str]:
    """Return a hover string for a field-access node with concrete generic types resolved."""
    obj_node = fa_node.children[0] if fa_node.children else None
    if obj_node is None:
        return None

    obj_type: Optional[str] = None
    if obj_node.node_type == NodeTypes.IDENTIFIER:
        var_decl = sym_map.get(obj_node.name)
        if var_decl is not None:
            obj_type = getattr(var_decl, "var_type", None)
    if obj_type is None:
        return None

    field_name: str = fa_node.name

    if "<" in obj_type:
        bracket = obj_type.index("<")
        template_name = obj_type[:bracket]
        args_raw = obj_type[bracket + 1:]
        if args_raw.endswith(">"):
            args_raw = args_raw[:-1]
        type_args = [a.strip() for a in args_raw.split(",")]
    else:
        template_name = obj_type
        type_args = []

    class_node = find_class_node(ast, template_name, file_path)
    if class_node is None:
        return None

    type_params: list = getattr(class_node, "type_params", []) or []
    type_map = dict(zip(type_params, type_args))

    for ch in (class_node.children or []):
        if ch is None:
            continue
        if ch.node_type == NodeTypes.CLASS_FIELD and ch.name == field_name:
            raw_type: str = ch.var_type or "?"
            concrete_type = type_map.get(raw_type, raw_type)
            return f"```firescript\n{concrete_type} {field_name}\n```"

    return None


def hover_method_call(
    mc_node: ASTNode,
    ast: ASTNode,
    sym_map: dict,
    file_path: str,
) -> Optional[str]:
    """Return a hover string for a method call, showing the concrete method signature."""
    obj_node = mc_node.children[0] if mc_node.children else None
    if obj_node is None:
        return None

    obj_type: Optional[str] = None
    if obj_node.node_type == NodeTypes.IDENTIFIER:
        var_decl = sym_map.get(obj_node.name)
        if var_decl is not None:
            obj_type = getattr(var_decl, "var_type", None)
    if obj_type is None:
        return None

    method_name: str = mc_node.name

    if "<" in obj_type:
        bracket = obj_type.index("<")
        template_name = obj_type[:bracket]
        args_raw = obj_type[bracket + 1:]
        if args_raw.endswith(">"):
            args_raw = args_raw[:-1]
        type_args = [a.strip() for a in args_raw.split(",")]
    else:
        template_name = obj_type
        type_args = []

    class_node = find_class_node(ast, template_name, file_path)
    if class_node is None:
        return None

    type_params: list = getattr(class_node, "type_params", []) or []
    type_map = dict(zip(type_params, type_args))

    for ch in (class_node.children or []):
        if ch is None:
            continue
        if ch.node_type == NodeTypes.CLASS_METHOD_DEFINITION and ch.name == method_name:
            if getattr(ch, "is_constructor", False):
                continue
            params = [
                c for c in (ch.children or [])
                if c is not None and c.node_type == NodeTypes.PARAMETER and c.name != "this"
            ]
            param_strs = []
            for p in params:
                t = type_map.get(p.var_type or "?", p.var_type or "?")
                arr = "[]" if getattr(p, "is_array", False) else ""
                param_strs.append(f"{t}{arr} {p.name}")
            ret = ch.return_type or "void"
            ret = type_map.get(ret, ret)
            return f"```firescript\n{ret} {method_name}({', '.join(param_strs)})\n```"

    return None