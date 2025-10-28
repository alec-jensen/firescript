import logging
from typing import List, Tuple, Dict, Optional

from enums import NodeTypes
from parser import ASTNode
from utils.type_utils import is_owned


DROP_DIRECTIVE_NAME = "enable_drops"


def _make_identifier(name: str, var_type: str | None, is_array: bool) -> ASTNode:
    return ASTNode(
        NodeTypes.IDENTIFIER,
        None,
        name,
        [],
        0,
        var_type,
        False,
        False,
        var_type,
        is_array,
        is_array,
    )


def _make_drop_call(name: str, var_type: str | None, is_array: bool) -> ASTNode:
    ident = _make_identifier(name, var_type, is_array)
    call = ASTNode(NodeTypes.FUNCTION_CALL, None, "drop", [ident], 0)
    return call


def _collect_directive(ast: ASTNode) -> bool:
    for child in ast.children:
        if child.node_type == NodeTypes.DIRECTIVE and child.name == DROP_DIRECTIVE_NAME:
            return True
    return False


def _ensure_drop_directive(ast: ASTNode):
    if not _collect_directive(ast):
        ast.children.insert(0, ASTNode(NodeTypes.DIRECTIVE, None, DROP_DIRECTIVE_NAME, [], 0))


def enable_and_insert_drops(ast: ASTNode) -> ASTNode:
    """
    Enable drop insertion via a directive and transform the AST by inserting
    explicit drop() calls at scope exits and before early exits (return/break/continue)
    for Owned variables (currently: arrays).
    """
    _ensure_drop_directive(ast)

    # Each scope (for Owned locals): list of (name, var_type, is_array)
    scope_stack: List[List[Tuple[str, Optional[str], bool]]] = [[]]
    # Variable maps for lookup: stack of dicts name -> (var_type, is_array, origin)
    # origin in {"local", "param", "global"}
    var_maps: List[Dict[str, Tuple[Optional[str], bool, str]]] = [dict()]

    def process_node(node: ASTNode) -> ASTNode:
        # Variable declaration: track owned locals by name
        if node.node_type == NodeTypes.VARIABLE_DECLARATION:
            if is_owned(node.var_type, node.is_array):
                scope_stack[-1].append((node.name, node.var_type, node.is_array))
            # Register in current var map as local
            if var_maps:
                var_maps[-1][node.name] = (node.var_type, node.is_array, "local")
            # Also recursively process initializer if present
            new_children = []
            for c in node.children:
                new_children.append(process_node(c) if c is not None else None)
            node.children = new_children
            return node

        # Variable assignment: drop old value if assigning to an Owned local (not a param)
        if node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            target = node.name
            # Lookup symbol from inner to outer var maps
            sym: Optional[Tuple[Optional[str], bool, str]] = None
            for frame in reversed(var_maps):
                if target in frame:
                    sym = frame[target]
                    break
            # Process RHS first
            new_children = []
            for c in node.children:
                new_children.append(process_node(c) if c is not None else None)
            node.children = new_children
            if sym is not None:
                vt, ia, origin = sym
                if origin != "param" and is_owned(vt, ia):
                    # Wrap: drop(target); target = expr
                    wrap = ASTNode(NodeTypes.SCOPE, node.token, "scope", [], node.index)
                    wrap.children.append(_make_drop_call(target, vt, ia))
                    wrap.children.append(node)
                    return wrap
            return node

        # Function definition: process body (body is a SCOPE node)
        if node.node_type == NodeTypes.FUNCTION_DEFINITION:
            new_kids = []
            # Begin a new var map frame for params and function-local declarations
            var_maps.append(dict())
            # Register parameters into current frame (mark as params)
            for c in node.children[:-1]:
                if c.node_type == NodeTypes.PARAMETER:
                    var_maps[-1][c.name] = (c.var_type, c.is_array, "param")
                    new_kids.append(c)
            # Process body
            body = node.children[-1] if node.children else None
            if body is not None:
                new_kids.append(process_node(body))
            node.children = new_kids
            # Pop var map frame
            var_maps.pop()
            return node

        # Scope: push new frame, process children, then append drops for this frame
        if node.node_type == NodeTypes.SCOPE:
            scope_stack.append([])
            var_maps.append(dict())
            new_children = []
            for c in node.children:
                new_children.append(process_node(c))
            # Append drops for this scope
            drops: List[ASTNode] = []
            for nm, vt, ia in scope_stack[-1]:
                drops.append(_make_drop_call(nm, vt, ia))
            new_children.extend(drops)
            node.children = new_children
            scope_stack.pop()
            var_maps.pop()
            return node

        # Return: wrap with a scope that does drops for all active frames, then return
        if node.node_type == NodeTypes.RETURN_STATEMENT:
            wrap = ASTNode(NodeTypes.SCOPE, node.token, "scope", [], node.index)
            # drain all frames outer-to-inner
            for frame in scope_stack:
                for nm, vt, ia in frame:
                    wrap.children.append(_make_drop_call(nm, vt, ia))
            wrap.children.append(node)
            return wrap

        # Break/Continue: drop current scope owned vars before control transfer
        if node.node_type in (NodeTypes.BREAK_STATEMENT, NodeTypes.CONTINUE_STATEMENT):
            wrap = ASTNode(NodeTypes.SCOPE, node.token, "scope", [], node.index)
            if scope_stack:
                for nm, vt, ia in scope_stack[-1]:
                    wrap.children.append(_make_drop_call(nm, vt, ia))
            wrap.children.append(node)
            return wrap

        # Other nodes: recurse into children
        new_children = []
        for c in node.children:
            new_children.append(process_node(c) if c is not None else None)
        node.children = new_children
        return node

    # Treat root like a scope for top-level declarations
    scope_stack = [[]]
    var_maps = [dict()]
    new_root_children = []
    for child in ast.children:
        new_root_children.append(process_node(child))
    # Append drops for top-level scope at end of program
    for nm, vt, ia in scope_stack[-1]:
        new_root_children.append(_make_drop_call(nm, vt, ia))
    ast.children = new_root_children

    return ast
