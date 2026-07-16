"""Direct unit tests for firescript.imports (ModuleResolver, build_merged_ast).

These drive ModuleResolver / Module / build_merged_ast directly with
hand-built files and AST nodes, following the "build IR/AST objects by
hand, drive the pass directly" pattern used elsewhere in this suite (see
e.g. tests/python/fir/test_verifier_types.py). Several branches here are
defensive guards that a real compile through the lexer/parser can't
reach; each such case says so in its docstring/comment.

Known dead code (documented, not re-litigated per-test): the cycle-detection
branch in `ModuleResolver._load_module` (imports.py) can only fire for a
dotted name that is *not yet* in `self.modules` but *is* on the recursion
`load_stack` -- but a real A->B->A import cycle always populates
`self.modules[dotted]` before recursing into B, so `dotted in self.modules`
short-circuits on the way back around and the cycle branch is never reached
through real recursion. We exercise it here only via a direct, artificial
`_load_module` call that fakes up that state.
"""

from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from enums import NodeTypes  # noqa: E402
from parser.ast_node import ASTNode  # noqa: E402
from imports import ImportSpec, Module, ModuleResolver, build_merged_ast  # noqa: E402


def _root(children=None):
    return ASTNode(NodeTypes.ROOT, None, "root", children or [], 0)


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def test_default_import_root_defaults_to_project_root():
    # No import_root given: falls back to the parent of firescript/.
    resolver = ModuleResolver()
    expected = os.path.dirname(os.path.dirname(os.path.abspath(
        os.path.join(REPO_ROOT, "firescript", "imports.py")
    )))
    t.require_eq(os.path.normcase(resolver.import_root), os.path.normcase(expected))


def test_dotted_to_path_stdlib_fallback_when_neither_form_exists():
    resolver = ModuleResolver()
    path = resolver.dotted_to_path("firescript.std.__no_such_module_xyz__")
    # Falls back to the init.fire candidate path (used later for a clearer error).
    t.require(path.endswith(os.path.join("__no_such_module_xyz__", "init.fire")))


def test_path_to_dotted_outside_import_root_uses_basename():
    with t.tmpdir() as root:
        resolver = ModuleResolver(import_root=root)
        with t.tmpdir() as other:
            outside_file = os.path.join(other, "somefile.fire")
            _write(outside_file, "")
            dotted = resolver.path_to_dotted(outside_file)
            t.require_eq(dotted, "somefile")


def test_parse_file_missing_file_raises_file_not_found():
    with t.tmpdir() as root:
        resolver = ModuleResolver(import_root=root)
        try:
            resolver.parse_file(os.path.join(root, "nope.fire"))
            t.require(False, "expected FileNotFoundError")
        except FileNotFoundError:
            pass


def test_parse_file_with_syntax_error_raises_runtime_error():
    with t.tmpdir() as root:
        resolver = ModuleResolver(import_root=root)
        bad_path = os.path.join(root, "bad.fire")
        # Unterminated block / clearly malformed source -> at least one parser error.
        _write(bad_path, "x: int32 = ;")
        try:
            resolver.parse_file(bad_path)
            t.require(False, "expected RuntimeError from parser errors")
        except RuntimeError as e:
            t.require("Parse error" in str(e), str(e))


def test_load_module_external_import_raises():
    # A real "import @someuser/pkg;" is already rejected at *parse* time
    # (parser/declarations.py's _parse_import_declaration calls
    # invalid_expression_error("External packages are not supported", ...)
    # whenever kind == "external"), so parse_file always raises its own
    # "Parse error in ..." RuntimeError before _load_module's own
    # `if imp.kind == "external": raise ...` guard is ever reached --
    # coincidentally with the same message text, which could otherwise
    # mask this from actually exercising imports.py's own check. Inject a
    # hand-built AST to reach the guard directly instead.
    with t.tmpdir() as root:
        resolver = ModuleResolver(import_root=root)
        entry_path = os.path.join(root, "entry.fire")
        _write(entry_path, "")

        import_node = ASTNode(NodeTypes.IMPORT_STATEMENT, None, "import", [], 0)
        import_node.module_path = "@someuser/pkg"
        import_node.kind = "external"
        import_node.alias = None
        import_node.symbols = []
        fake_ast = _root([import_node])
        resolver.parse_file = lambda path: (fake_ast, "")

        try:
            resolver.resolve_for_entry(entry_path)
            t.require(False, "expected RuntimeError for external package import")
        except RuntimeError as e:
            t.require("External packages are not supported" in str(e), str(e))


def test_load_module_relative_import_raises():
    # A module_path starting with "." can't come from the real parser (a
    # dotted import path is built from IDENTIFIER segments and can't begin
    # with a bare dot), so this guard is defensive/unreachable through
    # normal parsing. Exercise it by injecting a hand-built AST (with an
    # IMPORT_STATEMENT node carrying an artificial module_path) in place
    # of parse_file's real lexer/parser output.
    with t.tmpdir() as root:
        resolver = ModuleResolver(import_root=root)
        entry_path = os.path.join(root, "entry.fire")
        _write(entry_path, "")

        import_node = ASTNode(NodeTypes.IMPORT_STATEMENT, None, "import", [], 0)
        import_node.module_path = ".sibling"
        import_node.kind = "module"
        import_node.alias = None
        import_node.symbols = []
        fake_ast = _root([import_node])
        resolver.parse_file = lambda path: (fake_ast, "")

        try:
            resolver.resolve_for_entry(entry_path)
            t.require(False, "expected RuntimeError for relative import")
        except RuntimeError as e:
            t.require("Relative imports are not supported" in str(e), str(e))


def test_load_module_import_not_found_raises_file_not_found():
    with t.tmpdir() as root:
        resolver = ModuleResolver(import_root=root)
        entry_path = os.path.join(root, "entry.fire")
        _write(entry_path, "import does.not.exist;\n")
        try:
            resolver.resolve_for_entry(entry_path)
            t.require(False, "expected FileNotFoundError")
        except FileNotFoundError as e:
            t.require("Module not found" in str(e), str(e))


def test_cycle_detection_branch_is_unreachable_via_real_recursion_but_direct_call_hits_it():
    # See module docstring: a genuine A->B->A cycle can't reach the
    # `dotted in load_stack` check because `self.modules[dotted]` is set
    # before recursing. We call `_load_module` directly with a load_stack
    # that already contains `dotted` while `self.modules` does not, to
    # exercise the branch as documented dead-but-defensive code.
    with t.tmpdir() as root:
        resolver = ModuleResolver(import_root=root)
        _write(os.path.join(root, "a.fire"), "")
        try:
            resolver._load_module("a", ["a"])
            t.require(False, "expected RuntimeError for cyclic import")
        except RuntimeError as e:
            t.require("Cyclic import detected" in str(e), str(e))


def test_stdlib_sibling_relative_import_resolves_within_package():
    # Mimics the "sibling modules can be imported with short relative
    # paths" stdlib convention (see CLAUDE.md), which no shipped stdlib
    # module currently exercises through @firescript/ imports. We point
    # firescript_root at a temp tree so `_stdlib_package_for`'s non-init.fire
    # branch (parts = dotted.rsplit(".", 1)) and the sibling-candidate
    # resolution in `_load_module` both actually run.
    with t.tmpdir() as root:
        resolver = ModuleResolver(import_root=root)
        resolver.firescript_root = root
        std_dir = os.path.join(root, "std", "pkg")
        _write(os.path.join(std_dir, "leaf.fire"), "export fn leaf_value() -> int32 { return 1; }\n")
        _write(os.path.join(std_dir, "user.fire"), "import leaf.leaf_value;\n")
        entry_path = os.path.join(root, "entry.fire")
        # Trailing ".leaf_value" is parsed as a symbol import, so the
        # module path resolved and loaded is "firescript.std.pkg.user"
        # (matching how the real stdlib always ends an @firescript import
        # in a trailing symbol name -- see std/regex/init.fire).
        _write(entry_path, "import @firescript/std.pkg.user.leaf_value;\n")

        entry_mod, ordered = resolver.resolve_for_entry(entry_path)
        dotted_names = [m.dotted for m in ordered]
        t.require("firescript.std.pkg.leaf" in dotted_names, dotted_names)
        t.require("firescript.std.pkg.user" in dotted_names, dotted_names)


def test_resolve_for_entry_topo_sort_skips_external_kind_modules():
    # `visit()` inside resolve_for_entry has a defensive
    # `if imp.kind == "external": continue` -- but _load_module already
    # raises RuntimeError as soon as it sees an external import (before
    # resolve_for_entry's topo sort ever runs), so this branch can't be
    # reached by loading an entry file normally. We hit it by pre-seeding
    # `resolver.modules` with a fabricated module that has an external
    # import, disjoint from the real entry's dependency graph.
    with t.tmpdir() as root:
        resolver = ModuleResolver(import_root=root)
        entry_path = os.path.join(root, "entry.fire")
        _write(entry_path, "")

        fake_ast = _root()
        fake_mod = Module("fake.module", os.path.join(root, "fake.fire"), fake_ast, "")
        fake_mod.imports = [ImportSpec("someuser/pkg", "external", [], None, (0, 0))]
        resolver.modules["fake.module"] = fake_mod

        entry_mod, ordered = resolver.resolve_for_entry(entry_path)
        t.require(entry_mod.dotted in [m.dotted for m in ordered])
        t.require("fake.module" in [m.dotted for m in ordered])


def test_build_merged_ast_skips_source_read_failure_silently():
    # cache_source_text's disk-read fallback (used when Module.source_text
    # is empty) swallows any exception from open(); construct a Module by
    # hand with an empty source_text and a path that doesn't exist on disk.
    entry_ast = _root()
    entry = Module("entry", "/nonexistent/entry.fire", entry_ast, "")

    dep_ast = _root()
    dep = Module("dep", "/nonexistent/dep.fire", dep_ast, "")

    root = build_merged_ast(entry, [dep, entry])
    t.require(root.node_type == NodeTypes.ROOT)


# NOTE on dead code: `append_export`'s own `if not name: return` guard
# (imports.py ~line 250-252) turns out to be unreachable through
# `build_merged_ast`, given the invariants of its only two call sites:
#   - the primary call site looks the node up via
#     `top_level_by_name.get(symbol_name)`, and `top_level_by_name` is
#     only ever populated for children whose `getattr(child, "name", None)`
#     is truthy (`if child_name: top_level_by_name[child_name] = child`) --
#     so any node reachable that way already has a truthy `.name`.
#   - the fallback call site (entry/import name-conflict resolution) only
#     calls `append_export(c, ...)` for a `c` whose name is already a key
#     in `seen`, which likewise requires a truthy name.
# There is no way to make append_export receive a node with a falsy name
# without patching the closures directly, so this is left undriven and
# documented here rather than forced with an artificial code path.


def test_append_symbol_with_deps_skips_node_already_emitted():
    # `if symbol_name in emitted_for_module: return` -- reached when the
    # same top-level symbol is both directly exported *and* a transitive
    # dependency of another export.
    call_b = ASTNode(NodeTypes.FUNCTION_CALL, None, "b", [], 0)
    fn_a = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, "a", [call_b], 0)
    fn_b = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, "b", [], 0)

    dep_ast = _root([fn_a, fn_b])
    dep = Module("dep", "/nonexistent/dep.fire", dep_ast, "unused")
    # Both "a" and "b" are exported directly, and "a" also calls "b".
    dep.exports = {"a": fn_a, "b": fn_b}

    entry_ast = _root()
    entry = Module("entry", "/nonexistent/entry.fire", entry_ast, "unused")

    root = build_merged_ast(entry, [dep, entry])
    names = sorted(getattr(c, "name", None) for c in root.children)
    t.require_eq(names, ["a", "b"])


def test_append_export_skips_duplicate_symbol_name_across_modules():
    fn_a = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, "shared", [], 0)
    fn_b = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, "shared", [], 0)

    mod_a_ast = _root([fn_a])
    mod_a = Module("mod_a", "/nonexistent/mod_a.fire", mod_a_ast, "unused")
    mod_a.exports = {"shared": fn_a}

    mod_b_ast = _root([fn_b])
    mod_b = Module("mod_b", "/nonexistent/mod_b.fire", mod_b_ast, "unused")
    mod_b.exports = {"shared": fn_b}

    entry_ast = _root()
    entry = Module("entry", "/nonexistent/entry.fire", entry_ast, "unused")

    root = build_merged_ast(entry, [mod_a, mod_b, entry])
    # Only the first module's definition of "shared" should survive.
    shared_nodes = [c for c in root.children if getattr(c, "name", None) == "shared"]
    t.require(len(shared_nodes) == 1, shared_nodes)
    t.require(shared_nodes[0] is fn_a)


def test_append_symbol_with_deps_node_none_when_export_missing_from_top_level():
    # append_symbol_with_deps is first invoked directly from mod.exports
    # (not gated on membership in top_level_by_name, unlike its recursive
    # dependency-following calls). Craft a Module whose exports dict
    # references a name that never appears in mod.ast.children, so the
    # `top_level_by_name.get(...)` lookup misses and the function returns
    # early via the `node is None` guard.
    dep_ast = _root()  # no children at all
    dep = Module("dep", "/nonexistent/dep.fire", dep_ast, "unused")
    phantom = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, "phantom", [], 0)
    dep.exports = {"phantom": phantom}

    entry_ast = _root()
    entry = Module("entry", "/nonexistent/entry.fire", entry_ast, "unused")

    root = build_merged_ast(entry, [dep, entry])
    t.require(len(root.children) == 0, "export missing from top_level_by_name must be skipped")


def test_mutual_recursion_hits_resolving_guard():
    # Two exported functions that call each other. `collect_called_function_names`
    # + `append_symbol_with_deps` walk the call graph to order dependencies
    # before the caller; mutual recursion means the second function is
    # already `resolving` by the time it's revisited, exercising the
    # `if symbol_name in resolving_for_module: return` guard.
    call_b = ASTNode(NodeTypes.FUNCTION_CALL, None, "b", [], 0)
    fn_a = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, "a", [call_b], 0)
    call_a = ASTNode(NodeTypes.FUNCTION_CALL, None, "a", [], 0)
    fn_b = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, "b", [call_a], 0)

    dep_ast = _root([fn_a, fn_b])
    dep = Module("dep", "/nonexistent/dep.fire", dep_ast, "unused")
    dep.exports = {"a": fn_a, "b": fn_b}

    entry_ast = _root()
    entry = Module("entry", "/nonexistent/entry.fire", entry_ast, "unused")

    root = build_merged_ast(entry, [dep, entry])
    names = sorted(getattr(c, "name", None) for c in root.children)
    t.require_eq(names, ["a", "b"])
