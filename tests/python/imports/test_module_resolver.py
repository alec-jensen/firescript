"""Direct unit tests for firescript/imports.py's ModuleResolver and
build_merged_ast: stdlib package derivation, cycle detection, and
build_merged_ast's entry-vs-import / import-vs-import conflict recording."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from enums import NodeTypes  # noqa: E402
from parser.ast_node import ASTNode  # noqa: E402
from imports import ModuleResolver, Module, build_merged_ast  # noqa: E402


def _root(children=None) -> ASTNode:
    return ASTNode(NodeTypes.ROOT, None, "root", children or [], 0)


def _func_def(name: str) -> ASTNode:
    body = ASTNode(NodeTypes.SCOPE, None, "scope", [], 0)
    node = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, name, [body], 0, return_type="void")
    return node


# --- _stdlib_package_for: non-init.fire module strips last component -------

def test_stdlib_package_for_regular_file_strips_last_component():
    resolver = ModuleResolver()
    # firescript/std/cli/args.fire is a regular (non-init.fire) stdlib
    # module, so its package prefix is the parent "firescript.std.cli".
    pkg = resolver._stdlib_package_for("firescript.std.cli.args")
    t.require_eq(pkg, "firescript.std.cli")


def test_stdlib_package_for_non_stdlib_returns_none():
    resolver = ModuleResolver()
    t.require(resolver._stdlib_package_for("some.user.module") is None)


# --- _load_module: cycle rejection -----------------------------------------
# parse_file is monkeypatched to return hand-built ASTs so we can drive
# _load_module's DFS without needing real files on disk.

def _with_fake_modules(fake_asts: dict, fake_imports: dict):
    """Monkeypatch parse_file and iter_imports-derived Module.imports for a
    resolver so _load_module's DFS walks a hand-built dependency graph
    instead of touching disk. Returns (resolver, restore_fn)."""
    resolver = ModuleResolver()

    def fake_isfile(path):
        return True

    def fake_parse_file(self, file_path):
        dotted = self._dotted_for_path.get(file_path)
        return fake_asts[dotted], ""

    orig_isfile = os.path.isfile
    orig_parse_file = ModuleResolver.parse_file
    orig_dotted_to_path = ModuleResolver.dotted_to_path
    orig_post_init = Module.__post_init__

    resolver._dotted_for_path = {}

    def fake_dotted_to_path(self, dotted):
        p = f"<fake>/{dotted}.fire"
        self._dotted_for_path[p] = dotted
        return p

    def fake_post_init(self):
        self.imports = list(fake_imports.get(self.dotted, []))

    os.path.isfile = fake_isfile
    ModuleResolver.parse_file = fake_parse_file
    ModuleResolver.dotted_to_path = fake_dotted_to_path
    Module.__post_init__ = fake_post_init

    def restore():
        os.path.isfile = orig_isfile
        ModuleResolver.parse_file = orig_parse_file
        ModuleResolver.dotted_to_path = orig_dotted_to_path
        Module.__post_init__ = orig_post_init

    return resolver, restore


def test_load_module_cyclic_import_raises_runtime_error():
    """A real A -> B -> A cycle (not an artificial load_stack) is detected:
    the in-progress (load_stack) check runs before the already-loaded
    shortcut, and the reported cycle names the modules involved."""
    with t.tmpdir() as root:
        for name, dep in (("a", "b"), ("b", "a")):
            with open(os.path.join(root, name + ".fire"), "w", encoding="utf-8") as f:
                f.write(f"import {dep}.x;\nexport fn x() -> int32 {{ return 1; }}\n")
        resolver = ModuleResolver(import_root=root)
        try:
            resolver.resolve_for_entry(os.path.join(root, "a.fire"))
            t.require(False, "expected a cyclic import error")
        except RuntimeError as e:
            t.require("Cyclic import detected: a -> b -> a" in str(e), str(e))
            t.require_eq(e.error.code, "FS-IMP-0002")


def test_load_module_diamond_import_is_not_a_cycle():
    with t.tmpdir() as root:
        files = {
            "a": "import b.x;\nimport c.x;\n",
            "b": "import d.x;\nexport fn x() -> int32 { return 1; }\n",
            "c": "import d.x;\nexport fn x() -> int32 { return 1; }\n",
            "d": "export fn x() -> int32 { return 1; }\n",
        }
        for name, text in files.items():
            with open(os.path.join(root, name + ".fire"), "w", encoding="utf-8") as f:
                f.write(text)
        resolver = ModuleResolver(import_root=root)
        _, ordered = resolver.resolve_for_entry(os.path.join(root, "a.fire"))
        t.require_eq(sorted(m.dotted for m in ordered), ["a", "b", "c", "d"])


# --- build_merged_ast: entry-conflict paths ---

def test_build_merged_ast_entry_symbol_replaces_imported_one():
    fn_imported = _func_def("greet")
    dep = Module("dep", "<dep>", _root([fn_imported]))
    dep.exports = {"greet": fn_imported}

    fn_entry = _func_def("greet")
    entry_ast = _root([fn_entry])
    entry = Module("entry", "<entry>", entry_ast)

    root = build_merged_ast(entry, [dep, entry])
    greet_nodes = [c for c in root.children if getattr(c, "name", None) == "greet"]
    t.require_eq(len(greet_nodes), 1)
    t.require(greet_nodes[0] is fn_entry, "entry definition must replace the imported one")
    # ...and the replacement is recorded so the frontend can report it when
    # the entry explicitly imported the name.
    t.require_eq(root._import_conflicts, [{"symbol": "greet", "first": "dep", "second": "entry", "entry": True}])


def test_build_merged_ast_entry_conflict_value_error_fallback_is_exercised():
    """If root.children.index(prev) raises ValueError (e.g. the previously
    -seen node isn't actually present in root.children), build_merged_ast
    must not crash: it falls back to calling append_export(c, entry.path)
    instead of replacing in place. append_export's own duplicate-name
    guard then sees 'greet' already in `seen` and drops the entry's
    definition too (only logging the conflict) -- so the net, observable
    effect of this fallback is that the *imported* definition survives
    and the entry's own definition is silently dropped. This looks like
    an edge-case bug (the entry's own definition should arguably win) but
    is exercised here purely to cover the ValueError branch, not to
    assert it is correct."""
    fn_imported = _func_def("greet")
    dep = Module("dep", "<dep>", _root([fn_imported]))
    dep.exports = {"greet": fn_imported}

    fn_entry = _func_def("greet")
    entry_ast = _root([fn_entry])
    entry = Module("entry", "<entry>", entry_ast)

    # Force root.children.index(prev) to raise ValueError by making the
    # ROOT node's children list a subclass whose .index always fails --
    # intercepted via ASTNode.__init__ so it applies only to the ROOT node
    # build_merged_ast constructs internally.
    class _NeverFound(list):
        def index(self, *a, **kw):
            raise ValueError("not present")

    orig_init = ASTNode.__init__

    def patched_init(self, node_type, token, name, children, index, *a, **kw):
        orig_init(self, node_type, token, name, children, index, *a, **kw)
        if node_type == NodeTypes.ROOT:
            self.children = _NeverFound(self.children)

    ASTNode.__init__ = patched_init
    try:
        root = build_merged_ast(entry, [dep, entry])
    finally:
        ASTNode.__init__ = orig_init

    greet_nodes = [c for c in root.children if getattr(c, "name", None) == "greet"]
    t.require_eq(len(greet_nodes), 1)
    t.require(greet_nodes[0] is fn_imported, "fallback append_export drops the entry def (dup-name guard)")
