import logging
from collections import defaultdict
from typing import List, Tuple, Dict, Optional

from enums import NodeTypes
from parser import ASTNode
from utils.type_utils import is_owned


DROP_DIRECTIVE_NAME = "enable_drops"

# Call-site signature types
# Maps function/constructor/method name to list of is_borrowed per parameter (excluding receiver)
_SigMap = Dict[str, List[bool]]


def _collect_signatures(ast: ASTNode) -> Tuple[_SigMap, _SigMap, Dict[str, _SigMap]]:
    """Walk the AST and return (func_sigs, ctor_sigs, method_sigs).

    func_sigs:   {func_name: [is_borrowed, ...]}
    ctor_sigs:   {class_name: [is_borrowed, ...]}  (constructor params, excl. receiver)
    method_sigs: {class_name: {method_name: [is_borrowed, ...]}}  (excl. receiver)
    """
    func_sigs: _SigMap = {}
    ctor_sigs: _SigMap = {}
    method_sigs: Dict[str, _SigMap] = {}

    def _param_flags(children) -> List[bool]:
        return [
            getattr(c, "is_borrowed", False)
            for c in children
            if c.node_type == NodeTypes.PARAMETER and not getattr(c, "is_receiver", False)
        ]

    def walk(node: ASTNode) -> None:
        if node.node_type == NodeTypes.FUNCTION_DEFINITION:
            func_sigs[node.name] = _param_flags(node.children)
        elif node.node_type == NodeTypes.CLASS_DEFINITION:
            method_sigs.setdefault(node.name, {})
            for child in node.children:
                if child.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
                    flags = _param_flags(child.children)
                    if getattr(child, "is_constructor", False):
                        ctor_sigs[node.name] = flags
                    else:
                        method_sigs[node.name][child.name] = flags
        for c in (node.children or []):
            if c is not None:
                walk(c)

    walk(ast)
    return func_sigs, ctor_sigs, method_sigs


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


def _mentions_var(node: Optional[ASTNode], var_name: str) -> bool:
    """Return True if the subtree contains an identifier reference to var_name."""
    if node is None:
        return False
    if node.node_type == NodeTypes.IDENTIFIER and node.name == var_name:
        return True
    for child in node.children:
        if child is not None and _mentions_var(child, var_name):
            return True
    return False


def _is_drop_call(node: ASTNode, var_name: Optional[str] = None) -> bool:
    """Return True if node is a drop() call, optionally for a specific variable."""
    if node.node_type != NodeTypes.FUNCTION_CALL or node.name != "drop":
        return False
    if var_name is None:
        return True
    return bool(node.children and node.children[0].name == var_name)


def _reorganize_drops(children: List[ASTNode]) -> List[ASTNode]:
    """Move drop() calls inserted at scope exit to just after the last use of each variable.

    Drops that have no use in the scope (e.g. variable declared but never referenced) are
    kept at the end of the scope — conservative placement is always correct.
    """
    # Separate drops from regular statements (preserve order of drops)
    drop_map: Dict[str, ASTNode] = {}   # var_name -> drop node (last wins if duplicated)
    stmts: List[ASTNode] = []
    for child in children:
        if _is_drop_call(child):
            var_name = child.children[0].name
            drop_map[var_name] = child
        else:
            stmts.append(child)

    if not drop_map:
        return children  # nothing to reorganize

    # For each drop variable find the last stmt index that transitively mentions it
    placement: Dict[str, int] = {}  # var_name -> stmt index, or -1 if never mentioned
    for var_name in drop_map:
        last_idx = -1
        for i, stmt in enumerate(stmts):
            if _mentions_var(stmt, var_name):
                last_idx = i
        placement[var_name] = last_idx

    # Group drops by insertion point
    drops_after: Dict[int, List[ASTNode]] = defaultdict(list)
    end_drops: List[ASTNode] = []
    for var_name, idx in placement.items():
        if idx == -1:
            end_drops.append(drop_map[var_name])
        else:
            drops_after[idx].append(drop_map[var_name])

    # Reconstruct: for each stmt, append it then any drops whose last use was here
    result: List[ASTNode] = []
    for i, stmt in enumerate(stmts):
        result.append(stmt)
        result.extend(drops_after.get(i, []))
    result.extend(end_drops)
    return result


def enable_and_insert_drops(ast: ASTNode) -> ASTNode:
    """
    Enable drop insertion via a directive and transform the AST by inserting
    explicit drop() calls at scope exits and before early exits (return/break/continue)
    for Owned variables, then move each drop to just after the variable's last use.
    """
    _ensure_drop_directive(ast)

    # Collect function/constructor/method signatures for move tracking
    func_sigs, ctor_sigs, method_sigs = _collect_signatures(ast)

    # Each scope (for Owned locals): list of (name, var_type, is_array)
    scope_stack: List[List[Tuple[str, Optional[str], bool]]] = [[]]
    # Variable maps for lookup: stack of dicts name -> (var_type, is_array, origin)
    # origin in {"local", "param", "global"}
    var_maps: List[Dict[str, Tuple[Optional[str], bool, str]]] = [dict()]
    # Stack of scope depths at loop body entry — used by break/continue to know
    # how many frames to drain.
    loop_boundaries: List[int] = []

    def _collect_identifier_names(node: Optional[ASTNode]) -> set[str]:
        """Collect identifier names referenced by an expression subtree."""
        if node is None:
            return set()
        names: set[str] = set()
        if node.node_type == NodeTypes.IDENTIFIER and node.name:
            names.add(node.name)
        for child in node.children:
            if child is not None:
                names.update(_collect_identifier_names(child))
        return names

    def _drops_for_frames(frames: List[List[Tuple[str, Optional[str], bool]]]) -> List[ASTNode]:
        """Generate drop calls for the given scope frames (innermost first)."""
        drops: List[ASTNode] = []
        for frame in reversed(frames):
            for nm, vt, ia in frame:
                drops.append(_make_drop_call(nm, vt, ia))
        return drops

    def _remove_from_scope_stack(name: str) -> None:
        """Remove a variable from the scope_stack (it was moved, so no drop needed)."""
        for frame in reversed(scope_stack):
            for i, (nm, vt, ia) in enumerate(frame):
                if nm == name:
                    frame.pop(i)
                    return

    def _apply_move_semantics(args: List[ASTNode], is_borrowed_flags: Optional[List[bool]]) -> None:
        """For each argument that is an owned-type identifier passed to a non-borrowed param,
        remove it from scope_stack (ownership transferred to callee)."""
        if is_borrowed_flags is None:
            return
        for i, arg in enumerate(args):
            borrowed = is_borrowed_flags[i] if i < len(is_borrowed_flags) else False
            if not borrowed and arg is not None and arg.node_type == NodeTypes.IDENTIFIER:
                # Check if this identifier is an owned variable in our scope
                for frame in reversed(var_maps):
                    if arg.name in frame:
                        vt, ia, origin = frame[arg.name]
                        if origin != "param" and is_owned(vt, ia):
                            _remove_from_scope_stack(arg.name)
                        break

    def process_node(node: ASTNode) -> ASTNode:
        # Variable declaration: track owned locals by name
        if node.node_type == NodeTypes.VARIABLE_DECLARATION:
            if is_owned(node.var_type, node.is_array):
                scope_stack[-1].append((node.name, node.var_type, node.is_array))
            if var_maps:
                var_maps[-1][node.name] = (node.var_type, node.is_array, "local")
            new_children = []
            for c in node.children:
                new_children.append(process_node(c) if c is not None else None)
            node.children = new_children
            return node

        # Variable assignment: drop old value if assigning to an Owned local
        if node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            target = node.name
            sym: Optional[Tuple[Optional[str], bool, str]] = None
            for frame in reversed(var_maps):
                if target in frame:
                    sym = frame[target]
                    break
            new_children = []
            for c in node.children:
                new_children.append(process_node(c) if c is not None else None)
            node.children = new_children
            if sym is not None:
                vt, ia, origin = sym
                if origin != "param" and is_owned(vt, ia):
                    wrap = ASTNode(NodeTypes.SCOPE, node.token, "scope", [], node.index)
                    wrap.children.append(_make_drop_call(target, vt, ia))
                    wrap.children.append(node)
                    return wrap
            return node

        # Function/method definition: process body
        if node.node_type in (NodeTypes.FUNCTION_DEFINITION, NodeTypes.CLASS_METHOD_DEFINITION, NodeTypes.GENERATOR_DEFINITION):
            new_kids = []
            var_maps.append(dict())
            # Isolate scope_stack so returns inside the function don't drain outer scopes
            saved_scope_stack = scope_stack.copy()
            saved_loop_boundaries = loop_boundaries.copy()
            scope_stack.clear()
            loop_boundaries.clear()
            scope_stack.append([])
            for c in node.children[:-1]:
                if c.node_type == NodeTypes.PARAMETER:
                    var_maps[-1][c.name] = (c.var_type, c.is_array, "param")
                    new_kids.append(c)
            body = node.children[-1] if node.children else None
            if body is not None:
                new_kids.append(process_node(body))
            node.children = new_kids
            scope_stack.clear()
            scope_stack.extend(saved_scope_stack)
            loop_boundaries.clear()
            loop_boundaries.extend(saved_loop_boundaries)
            var_maps.pop()
            return node

        # Scope: push new frame, process children, append drops, run last-use optimization
        if node.node_type == NodeTypes.SCOPE:
            scope_stack.append([])
            var_maps.append(dict())
            new_children = []
            for c in node.children:
                new_children.append(process_node(c))
            # Append drops at scope exit for all owned locals in this frame
            for nm, vt, ia in scope_stack[-1]:
                new_children.append(_make_drop_call(nm, vt, ia))
            # Move drops to last use of each variable
            node.children = _reorganize_drops(new_children)
            scope_stack.pop()
            var_maps.pop()
            return node

        # Return: drop all owned vars in all active scopes, skipping vars used in return expr
        if node.node_type == NodeTypes.RETURN_STATEMENT:
            wrap = ASTNode(NodeTypes.SCOPE, node.token, "scope", [], node.index)
            used_in_return = _collect_identifier_names(node.children[0]) if node.children else set()
            for frame in scope_stack:
                for nm, vt, ia in frame:
                    if nm not in used_in_return:
                        wrap.children.append(_make_drop_call(nm, vt, ia))
            wrap.children.append(node)
            # Clear all frames so parent scopes don't emit double-drops for these vars
            for frame in scope_stack:
                frame.clear()
            return wrap

        # Break/Continue: drop all owned vars in scopes between here and the loop boundary
        if node.node_type in (NodeTypes.BREAK_STATEMENT, NodeTypes.CONTINUE_STATEMENT):
            wrap = ASTNode(NodeTypes.SCOPE, node.token, "scope", [], node.index)
            if loop_boundaries:
                boundary = loop_boundaries[-1]
                # Drain all frames from innermost back to (and including) the loop body frame
                frames_to_drain = scope_stack[boundary:]
                wrap.children.extend(_drops_for_frames(frames_to_drain))
            elif scope_stack:
                # Fallback: no recorded loop boundary — drain innermost scope only
                for nm, vt, ia in scope_stack[-1]:
                    wrap.children.append(_make_drop_call(nm, vt, ia))
            wrap.children.append(node)
            # NOTE: do NOT clear the scope_stack frames here. Break/continue only
            # exits one iteration/the loop — other iterations (or the fallthrough path
            # for break) still need the scope-exit drops. The registry-based
            # firescript_free is safe against double-free (registry_remove is a no-op
            # for already-freed pointers), so any redundant scope-exit drop is harmless.
            return wrap

        # Loop statements: record loop boundary before processing body
        if node.node_type in (NodeTypes.WHILE_STATEMENT, NodeTypes.FOR_STATEMENT, NodeTypes.FOR_IN_STATEMENT):
            loop_boundaries.append(len(scope_stack))
            new_children = []
            for idx, c in enumerate(node.children):
                if c is None:
                    new_children.append(None)
                elif node.node_type == NodeTypes.FOR_IN_STATEMENT and idx == 0:
                    # The loop variable declaration: don't track in scope_stack.
                    # Codegen manages it (stack-allocated per iteration).
                    new_children.append(c)
                else:
                    new_children.append(process_node(c))
            node.children = new_children
            loop_boundaries.pop()
            return node

        # Call sites: apply move semantics to arguments of owned types
        if node.node_type == NodeTypes.FUNCTION_CALL:
            flags = func_sigs.get(node.name)
            new_children = [process_node(c) if c is not None else None for c in node.children]
            node.children = new_children
            _apply_move_semantics(new_children, flags)
            return node

        if node.node_type == NodeTypes.CONSTRUCTOR_CALL:
            flags = ctor_sigs.get(node.name)
            new_children = [process_node(c) if c is not None else None for c in node.children]
            node.children = new_children
            _apply_move_semantics(new_children, flags)
            return node

        if node.node_type == NodeTypes.METHOD_CALL:
            new_children = [process_node(c) if c is not None else None for c in node.children]
            node.children = new_children
            # Resolve receiver type to look up method signature
            receiver = new_children[0] if new_children else None
            receiver_type = None
            if receiver is not None and receiver.node_type == NodeTypes.IDENTIFIER:
                for frame in reversed(var_maps):
                    if receiver.name in frame:
                        vt, _ia, _origin = frame[receiver.name]
                        receiver_type = vt
                        break
            if receiver_type and receiver_type in method_sigs:
                flags = method_sigs[receiver_type].get(node.name)
                if flags:
                    _apply_move_semantics(new_children[1:], flags)
            return node

        if node.node_type == NodeTypes.TYPE_METHOD_CALL:
            new_children = [process_node(c) if c is not None else None for c in node.children]
            node.children = new_children
            class_name = getattr(node, "class_name", None)
            if class_name and class_name in method_sigs:
                flags = method_sigs[class_name].get(node.name)
                if flags:
                    _apply_move_semantics(new_children, flags)
            return node

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
    # Drop top-level owned vars at end of program
    for nm, vt, ia in scope_stack[-1]:
        new_root_children.append(_make_drop_call(nm, vt, ia))
    # Apply last-use optimization to top-level scope as well
    ast.children = _reorganize_drops(new_root_children)

    return ast
