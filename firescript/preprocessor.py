import logging
from collections import defaultdict
from typing import List, Tuple, Dict, Optional

from enums import NodeTypes
from parser import ASTNode
from utils.type_utils import is_owned as _is_owned_registered


DROP_DIRECTIVE_NAME = "enable_drops"

# Call-site signature types
# Maps function/constructor/method name to list of is_borrowed per parameter (excluding receiver)
_SigMap = Dict[str, List[bool]]


def _collect_signatures(ast: ASTNode) -> Tuple[_SigMap, _SigMap, Dict[str, _SigMap], Dict[str, Dict[str, Optional[str]]]]:
    """Walk the AST and return (func_sigs, ctor_sigs, method_sigs, method_return_types).

    func_sigs:   {func_name: [is_borrowed, ...]}
    ctor_sigs:   {class_name: [is_borrowed, ...]}  (constructor params, excl. receiver)
    method_sigs: {class_name: {method_name: [is_borrowed, ...]}}  (excl. receiver)
    method_return_types: {class_name: {method_name: return_type}}
    """
    func_sigs: _SigMap = {}
    ctor_sigs: _SigMap = {}
    method_sigs: Dict[str, _SigMap] = {}
    method_return_types: Dict[str, Dict[str, Optional[str]]] = {}

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
            method_return_types.setdefault(node.name, {})
            for child in node.children:
                if child.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
                    flags = _param_flags(child.children)
                    if getattr(child, "is_constructor", False):
                        ctor_sigs[node.name] = flags
                    else:
                        method_sigs[node.name][child.name] = flags
                        method_return_types[node.name][child.name] = child.return_type
        for c in (node.children or []):
            if c is not None:
                walk(c)

    walk(ast)
    return func_sigs, ctor_sigs, method_sigs, method_return_types


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


def _definitely_terminates(node: Optional[ASTNode]) -> bool:
    """Return True if this node definitely exits current control flow
    (return/break/continue on every path). Mirrors
    semantic_analyzer.py::SemanticAnalyzer._definitely_terminates -- kept as
    a separate, structural-only copy here since this module has no access
    to that analyzer's per-binding state, just the raw AST."""
    if node is None:
        return False
    if node.node_type in (NodeTypes.RETURN_STATEMENT, NodeTypes.BREAK_STATEMENT, NodeTypes.CONTINUE_STATEMENT):
        return True
    if node.node_type == NodeTypes.SCOPE:
        return any(_definitely_terminates(c) for c in node.children)
    if node.node_type == NodeTypes.IF_STATEMENT:
        if len(node.children) < 2:
            return False
        then_branch = node.children[1]
        else_branch = node.children[2] if len(node.children) > 2 else None
        if else_branch is None:
            return False
        return _definitely_terminates(then_branch) and _definitely_terminates(else_branch)
    return False


def _reorganize_drops(statements: List[ASTNode], trailing_drops: List[ASTNode]) -> List[ASTNode]:
    """Move each auto-inserted, scope-exit `trailing_drops` entry to just
    after the last use of its variable within `statements`.

    Only ever repositions drops the preprocessor itself appended for
    scope-exit -- never a drop() call already present in `statements`
    (including a user-written one), which stays exactly where it is.
    `statements` may itself already contain drop() calls (explicit
    user-written ones, or ones nested inside processed sub-statements);
    treating those as further reorganization candidates based on a "last
    mention" heuristic could relocate a live, user-placed drop past a
    later return/break/continue in the same statement list, turning it
    into dead code that never runs (an under-drop, FIRV-O3) -- exactly
    what happened here before this function stopped conflating the two.

    Drops with no use in the scope (e.g. variable declared but never
    referenced) are kept at the end of the scope — conservative placement
    is always correct there.
    """
    if not trailing_drops:
        return statements

    drop_map: Dict[str, ASTNode] = {}   # var_name -> drop node (last wins if duplicated)
    for drop_node in trailing_drops:
        drop_map[drop_node.children[0].name] = drop_node
    stmts = statements

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
    func_sigs, ctor_sigs, method_sigs, method_return_types = _collect_signatures(ast)

    # Generic class templates (e.g. `class Option<T?>`) are deliberately never
    # registered with utils.type_utils.register_class (see
    # parser/declarations.py's _parse_class_definition: the bare template
    # name must not resolve as a standalone concrete type during parsing).
    # That means the module-level is_owned() can never see them, so an
    # own-mode `this`/param/local of a generic-class type was silently never
    # tracked for auto-drop at all (ast_to_fir.py's own class_categories --
    # built straight from each CLASS_DEFINITION node's is_copyable flag,
    # generic or not -- disagreed, which is why the ownership verifier
    # (which trusts ast_to_fir.py's categorization) correctly flagged these
    # as leaked). Build a local name->is_copyable map from the same
    # CLASS_DEFINITION nodes ast_to_fir.py's _collect_program_info reads, and
    # shadow is_owned with a wrapper that consults it first.
    _generic_class_copyable: Dict[str, bool] = {
        child.name: bool(getattr(child, "is_copyable", False))
        for child in ast.children
        if child.node_type == NodeTypes.CLASS_DEFINITION and getattr(child, "type_params", None)
    }

    def is_owned(base_type: Optional[str], is_array: bool) -> bool:
        base_name = base_type.split("<", 1)[0] if base_type else base_type
        if base_name in _generic_class_copyable:
            return True if is_array else not _generic_class_copyable[base_name]
        return _is_owned_registered(base_type, is_array)

    # Each scope (for Owned locals): list of (name, var_type, is_array)
    scope_stack: List[List[Tuple[str, Optional[str], bool]]] = [[]]
    # Variable maps for lookup: stack of dicts name -> (var_type, is_array, origin)
    # origin in {"local", "param", "global"}
    var_maps: List[Dict[str, Tuple[Optional[str], bool, str]]] = [dict()]
    # Stack of scope depths at loop body entry — used by break/continue to know
    # how many frames to drain.
    loop_boundaries: List[int] = []

    def _collect_identifier_names(node: Optional[ASTNode]) -> set[str]:
        """Collect identifier names referenced anywhere in an expression
        subtree, for the "don't drop what this return expression still
        reads" purpose (see the RETURN_STATEMENT handler). Deliberately
        broad/conservative: the drops this exemption set protects run
        *before* the return statement, so *any* identifier the expression
        still reads -- transferred or merely borrowed (e.g. a match
        scrutinee, or a borrowed call argument) -- must not be dropped
        first, or the read is a use-after-drop. A precise, transfer-only
        exemption was tried and reverted (see ir_verifier_spec.md section
        8 items 12-13): it's wrong for this specific purpose and trades a
        real bug (use-after-drop) for a narrower one (an under-dropped
        leak, FIRV-O3) it was trying to fix.
        """
        if node is None:
            return set()
        names: set[str] = set()
        if node.node_type == NodeTypes.IDENTIFIER and node.name:
            names.add(node.name)
        for child in node.children:
            if child is not None:
                names.update(_collect_identifier_names(child))
        return names

    def _return_transferred_identifiers(expr: Optional[ASTNode]) -> set[str]:
        """Names within a return expression that are actually
        ownership-transferred: the bare returned identifier, or an
        identifier passed to a non-borrowed function/constructor
        parameter. An identifier passed only to *borrowed* parameters
        (including every intrinsic -- unknown to func_sigs/ctor_sigs,
        since intrinsics all borrow their arguments) is not transferred.
        """
        if expr is None:
            return set()
        if expr.node_type == NodeTypes.IDENTIFIER:
            return {expr.name} if expr.name else set()

        transferred: set[str] = set()

        def walk(node: Optional[ASTNode]) -> None:
            if node is None:
                return
            if node.node_type == NodeTypes.FUNCTION_CALL:
                # Bare `ClassName(args)` construction parses as a
                # FUNCTION_CALL (not a distinct CONSTRUCTOR_CALL node) --
                # check ctor_sigs first so a constructor's own borrow
                # flags are consulted instead of silently missing (falling
                # through to the "unknown callee" default).
                flags = ctor_sigs.get(node.name) if node.name in ctor_sigs else func_sigs.get(node.name)
                for i, arg in enumerate(node.children):
                    borrowed = flags[i] if flags is not None and i < len(flags) else True
                    if arg is not None and arg.node_type == NodeTypes.IDENTIFIER and not borrowed:
                        transferred.add(arg.name)
                    walk(arg)
                return
            if node.node_type == NodeTypes.CONSTRUCTOR_CALL:
                flags = ctor_sigs.get(node.name)
                for i, arg in enumerate(node.children):
                    borrowed = flags[i] if flags is not None and i < len(flags) else True
                    if arg is not None and arg.node_type == NodeTypes.IDENTIFIER and not borrowed:
                        transferred.add(arg.name)
                    walk(arg)
                return
            if node.node_type == NodeTypes.METHOD_CALL:
                receiver = node.children[0] if node.children else None
                args = node.children[1:]
                class_name: Optional[str] = None
                if receiver is not None and receiver.node_type == NodeTypes.CONSTRUCTOR_CALL:
                    class_name = receiver.name
                elif (
                    receiver is not None
                    and receiver.node_type == NodeTypes.FUNCTION_CALL
                    and receiver.name in ctor_sigs
                ):
                    # Bare `ClassName(args)` construction parses as
                    # FUNCTION_CALL (see the FUNCTION_CALL branch above).
                    class_name = receiver.name
                elif receiver is not None and receiver.node_type == NodeTypes.IDENTIFIER:
                    for frame in reversed(var_maps):
                        if receiver.name in frame:
                            class_name = frame[receiver.name][0]
                            break
                flags = method_sigs.get(class_name or "", {}).get(node.name) if class_name else None
                for i, arg in enumerate(args):
                    # Unresolved receiver class or method: conservatively
                    # treat as transferred (matches the prior, blanket-
                    # exempt behavior for this one case).
                    borrowed = flags[i] if flags is not None and i < len(flags) else False
                    if arg is not None and arg.node_type == NodeTypes.IDENTIFIER and not borrowed:
                        transferred.add(arg.name)
                    walk(arg)
                walk(receiver)
                return
            for c in node.children or []:
                walk(c)

        walk(expr)
        return transferred

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
        remove it from scope_stack (ownership transferred to callee) -- including when the
        argument is itself an own-mode parameter of the enclosing function/method, which is
        now scope-tracked too (see the FUNCTION_DEFINITION handler above)."""
        if is_borrowed_flags is None:
            return
        for i, arg in enumerate(args):
            borrowed = is_borrowed_flags[i] if i < len(is_borrowed_flags) else False
            if not borrowed and arg is not None and arg.node_type == NodeTypes.IDENTIFIER:
                # Check if this identifier is an owned variable in our scope
                for frame in reversed(var_maps):
                    if arg.name in frame:
                        vt, ia, origin = frame[arg.name]
                        if is_owned(vt, ia):
                            _remove_from_scope_stack(arg.name)
                        break

    def _move_source_identifier(rhs: Optional[ASTNode]) -> None:
        """If `rhs` is a bare identifier naming an owned local, it is being moved
        (e.g. `Point p2 = p1;` or `p2 = p1;`); remove it from the scope_stack so it
        is not dropped — ownership has transferred to the destination."""
        if rhs is None or rhs.node_type != NodeTypes.IDENTIFIER:
            return
        for frame in reversed(var_maps):
            if rhs.name in frame:
                vt, ia, origin = frame[rhs.name]
                if is_owned(vt, ia):
                    _remove_from_scope_stack(rhs.name)
                return

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
            # A bare-identifier initializer of an owned local is a move.
            _move_source_identifier(node.children[0] if node.children else None)
            return node

        # General assignment (field/array/identifier target, e.g.
        # `this.field = param;` in a constructor): a bare-identifier RHS
        # naming an owned param/local is a move into the target, same as
        # VARIABLE_ASSIGNMENT's RHS below -- just with no "drop the old
        # value" step, since the target isn't a tracked local's own scope
        # entry. Without this, a constructor moving an owned parameter
        # into `this.field` never removed that parameter from scope
        # tracking, so it looked doubly-consumed once params started
        # being auto-dropped at scope exit (FIRV-O2).
        if node.node_type == NodeTypes.ASSIGNMENT:
            new_children = []
            for c in node.children:
                new_children.append(process_node(c) if c is not None else None)
            node.children = new_children
            rhs = node.children[1] if len(node.children) > 1 else None
            if rhs is not None and rhs.node_type == NodeTypes.IDENTIFIER:
                for frame in reversed(var_maps):
                    if rhs.name in frame:
                        vt, ia, origin = frame[rhs.name]
                        if is_owned(vt, ia):
                            _remove_from_scope_stack(rhs.name)
                        break
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
            # A bare-identifier RHS that names an owned local is a move.
            _move_source_identifier(node.children[0] if node.children else None)
            if sym is not None:
                vt, ia, origin = sym
                if is_owned(vt, ia):
                    wrap = ASTNode(NodeTypes.SCOPE, node.token, "scope", [], node.index)
                    wrap.children.append(_make_drop_call(target, vt, ia))
                    wrap.children.append(node)
                    return wrap
            elif var_maps and target not in var_maps[-1]:
                # No prior declaration anywhere in scope: this
                # `target = expr;` is itself the (type-inferred) implicit
                # declaration -- e.g. script-style top-level `v1 =
                # Vec2(3, 4);` with no type annotation. Register it the
                # same way an explicit VARIABLE_DECLARATION would so it
                # gets auto-dropped, but only when the RHS's class is
                # staticly known here (a bare constructor call) -- general
                # RHS type inference isn't available before semantic
                # analysis runs. Without this, an owned value bound only
                # through this implicit-declaration form was never tracked
                # at all and always leaked (FIRV-O3).
                rhs = node.children[0] if node.children else None
                inferred_class: Optional[str] = None
                if rhs is not None and rhs.node_type == NodeTypes.CONSTRUCTOR_CALL:
                    inferred_class = rhs.name
                elif rhs is not None and rhs.node_type == NodeTypes.FUNCTION_CALL and rhs.name in ctor_sigs:
                    inferred_class = rhs.name
                elif rhs is not None and rhs.node_type == NodeTypes.METHOD_CALL and rhs.children:
                    receiver = rhs.children[0]
                    receiver_class: Optional[str] = None
                    if receiver.node_type == NodeTypes.CONSTRUCTOR_CALL:
                        receiver_class = receiver.name
                    elif receiver.node_type == NodeTypes.FUNCTION_CALL and receiver.name in ctor_sigs:
                        receiver_class = receiver.name
                    elif receiver.node_type == NodeTypes.IDENTIFIER:
                        for frame in reversed(var_maps):
                            if receiver.name in frame:
                                receiver_class = frame[receiver.name][0]
                                break
                    if receiver_class is not None:
                        inferred_class = method_return_types.get(receiver_class, {}).get(rhs.name)
                if inferred_class is not None and is_owned(inferred_class, False):
                    var_maps[-1][target] = (inferred_class, False, "local")
                    scope_stack[-1].append((target, inferred_class, False))
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
            is_constructor = bool(getattr(node, "is_constructor", False))
            for c in node.children[:-1]:
                if c.node_type == NodeTypes.PARAMETER:
                    var_maps[-1][c.name] = (c.var_type, c.is_array, "param")
                    new_kids.append(c)
                    # An own-mode (non-borrowed) Owned parameter is the
                    # callee's responsibility to drop, exactly like a
                    # local -- register it the same way so the normal
                    # scope-exit/return/break/continue drop machinery
                    # covers it too. Without this, a function that never
                    # explicitly consumes its own owned parameter silently
                    # leaked it (FIRV-O3).
                    #
                    # A constructor's `this` receiver is exempt even when
                    # written `owned this`: ast_to_fir.py's _convert_method
                    # drops it from the actual FIR signature and always
                    # allocates its own fresh `this`, which it implicitly
                    # returns at the end of the constructor. Registering it
                    # here would insert a drop for a value that synthesized
                    # return is about to read again -- a use-after-drop.
                    is_ctor_this_receiver = (
                        is_constructor
                        and getattr(c, "is_receiver", False)
                        and c.name == "this"
                    )
                    if (
                        not is_ctor_this_receiver
                        and not getattr(c, "is_borrowed", False)
                        and is_owned(c.var_type, c.is_array)
                    ):
                        scope_stack[-1].append((c.name, c.var_type, c.is_array))
            body = node.children[-1] if node.children else None
            if body is not None:
                processed_body = process_node(body)
                # Whatever remains in the params frame after processing
                # the body is what no return/break/continue path already
                # dropped -- i.e. control can fall off the end of the
                # function while still owning that parameter. Append
                # trailing drops the same way a SCOPE appends its own
                # (see the SCOPE handler above); an already-terminating
                # body (every path returns) leaves this frame empty, so
                # this is a no-op in that case.
                for nm, vt, ia in scope_stack[-1]:
                    processed_body.children.append(_make_drop_call(nm, vt, ia))
                new_kids.append(processed_body)
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
            # Auto-append drops at scope exit for all owned locals in this frame
            trailing_drops = [_make_drop_call(nm, vt, ia) for nm, vt, ia in scope_stack[-1]]
            # Move those trailing drops to just after the last use of each variable
            node.children = _reorganize_drops(new_children, trailing_drops)
            scope_stack.pop()
            var_maps.pop()
            return node

        # Return: drop all owned vars in all active scopes, skipping vars
        # referenced anywhere in the return expression. The drops this
        # inserts run *before* the return statement, so any identifier the
        # return expression still needs to read -- transferred or merely
        # borrowed -- must not be dropped first (that would be a
        # use-after-drop, a real bug, not just an imprecise leak). This is
        # deliberately the conservative superset _return_transferred_
        # identifiers computes (which is precise about *transfer* but
        # wrong for this "don't drop what's still read" purpose); the
        # cost is under-dropping (FIRV-O3 leaks) in the narrower case
        # `_return_transferred_identifiers` was built to fix (a var
        # referenced only as a borrowed sub-argument, e.g. `return
        # fs_rt_str_dup(view);`), which is fixed at specific call sites
        # (see std/internal/io.fire's fs_rt_argv_at) instead.
        if node.node_type == NodeTypes.RETURN_STATEMENT:
            wrap = ASTNode(NodeTypes.SCOPE, node.token, "scope", [], node.index)
            expr = node.children[0] if node.children else None
            used_in_return = _collect_identifier_names(expr) if expr is not None else set()
            transferred = _return_transferred_identifiers(expr) if expr is not None else set()
            # Names read within the return expression but not actually
            # transferred out (e.g. a match/for-in scrutinee, a borrowed
            # call argument, an own-mode `this` receiver read via a field
            # access) are exempted from the *pre*-drop above -- correctly,
            # since dropping them before the expression evaluates would be
            # a use-after-drop -- but nothing else ever drops them either,
            # which leaks them (FIRV-O3). ast_to_fir.py's RETURN_STATEMENT
            # conversion inserts a Drop for each of these *after* it
            # finishes building the return value but *before* emitting the
            # Return, which is the one ordering that is safe for both
            # concerns at once.
            post_drop_names = sorted(
                nm
                for frame in scope_stack
                for nm, vt, ia in frame
                if nm in used_in_return and nm not in transferred
            )
            if post_drop_names:
                setattr(node, "post_return_drop_names", post_drop_names)
            for frame in scope_stack:
                for nm, vt, ia in frame:
                    if nm not in used_in_return:
                        wrap.children.append(_make_drop_call(nm, vt, ia))
            wrap.children.append(node)
            # NOTE: do NOT clear the scope_stack frames here (see the
            # identical note on Break/Continue below). scope_stack frames
            # for outer scopes are shared, mutable list objects visible to
            # every sibling branch (e.g. both arms of an if/elif/else, or
            # code after the if entirely) -- clearing them here previously
            # made every *later* return/scope-exit in the function believe
            # already-handled-on-this-one-path variables needed no drop at
            # all, silently leaking them on every other path (FIRV-O3).
            # A return is terminal, so no other statement in *this* block
            # follows it; any apparent "extra" drop this leaves for a
            # provably-unreachable join point downstream (e.g. both arms
            # of an if/else already returned) lands in a block
            # ast_to_fir.py's _seal_open_blocks prunes as unreachable.
            return wrap

        # If/elif/else: process the condition against the real (shared) scope
        # -- it always evaluates -- then fork scope_stack per arm so a move
        # inside only one branch doesn't corrupt tracking for its sibling or
        # for code after the whole statement. `_move_source_identifier`/
        # `_apply_move_semantics` record a move by removing the moved name
        # from whichever frame it's declared in; since frames are the same
        # shared, mutable list objects visible to every arm, processing arms
        # sequentially against one shared scope_stack made a move real on
        # only one path look like it happened on every path -- either
        # leaking an outer variable neither arm actually consumed on the
        # untaken path (FIRV-O3) or, once the reconciliation below started
        # correctly noticing the variable is still needed on the other arm,
        # double-dropping it there instead (FIRV-O2), because a single
        # trailing drop placed after the whole if/else runs on *every* path
        # reaching the join, including the one that already moved it.
        # A terminating arm (return/break/continue on every path) is a dead
        # end for anything past the if -- it already drained its own
        # scope_stack contents via the Return/Break/Continue handling above,
        # so it's excluded from reconciliation entirely, matching
        # semantic_analyzer.py's analogous if/else ownership merge.
        if node.node_type == NodeTypes.IF_STATEMENT:
            if not node.children:
                return node
            condition = process_node(node.children[0])
            then_branch = node.children[1] if len(node.children) > 1 else None
            else_branch = node.children[2] if len(node.children) > 2 else None

            baseline = [list(frame) for frame in scope_stack]

            def _run_arm(branch: Optional[ASTNode]):
                if branch is None:
                    return None, baseline, False
                scope_stack.clear()
                scope_stack.extend([list(frame) for frame in baseline])
                processed = process_node(branch)
                frames = [list(frame) for frame in scope_stack]
                return processed, frames, _definitely_terminates(branch)

            processed_then, then_frames, then_terminates = _run_arm(then_branch)
            processed_else, else_frames, else_terminates = _run_arm(else_branch)
            then_live = not then_terminates
            else_live = not else_terminates

            merged = [list(frame) for frame in baseline]
            for i in range(len(baseline)):
                for nm, vt, ia in baseline[i]:
                    then_has = any(n2 == nm for n2, _, _ in then_frames[i])
                    else_has = any(n2 == nm for n2, _, _ in else_frames[i])
                    then_moved_live = then_live and not then_has
                    else_moved_live = else_live and not else_has
                    if not (then_moved_live or else_moved_live):
                        continue  # untouched on every live path -- keep tracking as-is
                    if then_moved_live and else_moved_live:
                        # Consumed on every live path -- fully handled already.
                        merged[i] = [t for t in merged[i] if t[0] != nm]
                        continue
                    # Mixed: consumed on one live path, not the other. Insert
                    # an explicit drop directly at the tail of whichever live
                    # arm(s) still hold it -- a shared trailing drop after
                    # the whole if-statement can't be correct for only one
                    # of two diverging paths.
                    if then_live and then_has:
                        processed_then.children.append(_make_drop_call(nm, vt, ia))
                    if else_live and else_has:
                        if processed_else is None:
                            # No else branch: synthesize an empty one so the
                            # drop still runs on the (implicit) false path.
                            processed_else = ASTNode(NodeTypes.SCOPE, node.token, "scope", [], node.index)
                        processed_else.children.append(_make_drop_call(nm, vt, ia))
                    merged[i] = [t for t in merged[i] if t[0] != nm]

            scope_stack.clear()
            scope_stack.extend(merged)

            new_children = [condition]
            if processed_then is not None:
                new_children.append(processed_then)
            if processed_else is not None:
                new_children.append(processed_else)
            node.children = new_children
            return node

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

        # Explicit user-written drop(x): consumes x here, same as any other
        # move, so it must stop being tracked for automatic scope-exit
        # dropping. Previously masked by scope_stack being one shared,
        # unforked list across if/else arms -- a sibling branch's unrelated
        # move of the same name coincidentally cleared tracking before this
        # ever mattered. Forking scope_stack per arm (see the IF_STATEMENT
        # handler above) exposed this as a real gap: an explicit drop(x) in
        # one arm was invisible to tracking, so the other arm still
        # "having" x looked like a genuine mixed-consumption case, and the
        # reconciliation logic inserted a second, redundant drop right next
        # to the user's own explicit one (FIRV-O2, double-drop).
        if node.node_type == NodeTypes.FUNCTION_CALL and node.name == "drop":
            new_children = [process_node(c) if c is not None else None for c in node.children]
            node.children = new_children
            target = new_children[0] if new_children else None
            if target is not None and target.node_type == NodeTypes.IDENTIFIER:
                for frame in reversed(var_maps):
                    if target.name in frame:
                        vt, ia, origin = frame[target.name]
                        if is_owned(vt, ia):
                            _remove_from_scope_stack(target.name)
                        break
            return node

        # Call sites: apply move semantics to arguments of owned types
        if node.node_type == NodeTypes.FUNCTION_CALL:
            # A bare `ClassName(args)` may be parsed as a function call; fall back
            # to the constructor signature so owned arguments are still moved.
            flags = func_sigs.get(node.name)
            if flags is None:
                flags = ctor_sigs.get(node.name)
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

        # this.super(args): ast_to_fir.py::_convert_super_call always passes
        # every argument "own" (base = self.builder.call(f"{super_class}.
        # {super_class}", args, ["own"] * len(args), ...)) regardless of
        # the base constructor's own borrow flags, so every argument is
        # unconditionally moved -- same as enum variant construction.
        # Without this, an owned argument threaded through a super() call
        # (common in constructor chains: B.B calling this.super(id)) was
        # never removed from scope tracking, so it looked doubly consumed
        # once params started being auto-dropped at scope exit (FIRV-O2).
        if node.node_type == NodeTypes.SUPER_CALL:
            new_children = [process_node(c) if c is not None else None for c in node.children]
            node.children = new_children
            _apply_move_semantics(new_children, [False] * len(new_children))
            return node

        # Enum variant construction (EnumName.Variant(args)): payload fields
        # are always owned by value (no borrow syntax for them), so every
        # argument is unconditionally moved into the payload.
        if node.node_type == NodeTypes.ENUM_VARIANT_CONSTRUCT:
            new_children = [process_node(c) if c is not None else None for c in node.children]
            node.children = new_children
            _apply_move_semantics(new_children, [False] * len(new_children))
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
    trailing_drops = [_make_drop_call(nm, vt, ia) for nm, vt, ia in scope_stack[-1]]
    # Apply last-use optimization to top-level scope as well
    ast.children = _reorganize_drops(new_root_children, trailing_drops)

    return ast
