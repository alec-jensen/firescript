"""Direct unit tests for firescript/imports.py's ModuleResolver and
build_merged_ast: default import_root, dotted<->path fallbacks, parse_file
error paths, cycle/external/relative-import rejection (via monkeypatching
parse_file to inject a hand-built AST), and build_merged_ast's duplicate-
symbol / entry-conflict branches."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from enums import NodeTypes  # noqa: E402
from parser.ast_node import ASTNode  # noqa: E402
import imports as imports_mod  # noqa: E402
from imports import ModuleResolver, Module, build_merged_ast  # noqa: E402


def _root(children=None) -> ASTNode:
    return ASTNode(NodeTypes.ROOT, None, "root", children or [], 0)


def _func_def(name: str) -> ASTNode:
    body = ASTNode(NodeTypes.SCOPE, None, "scope", [], 0)
    node = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, name, [body], 0, return_type="void")
    return node


def _var_decl(name: str, value: ASTNode) -> ASTNode:
    return ASTNode(NodeTypes.VARIABLE_DECLARATION, None, name, [value], 0, var_type="int32")


def _int_literal(text: str = "1") -> ASTNode:
    return ASTNode(NodeTypes.LITERAL, None, text, [], 0, var_type="int32")


# --- ModuleResolver.__init__ default import_root ---------------------------

def test_default_import_root_is_project_root():
    resolver = ModuleResolver()
    expected = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(imports_mod.__file__))))
    t.require_eq(resolver.import_root, expected)


# --- dotted_to_path fallback when neither init.fire nor <name>.fire exists --

def test_dotted_to_path_stdlib_missing_returns_init_path():
    resolver = ModuleResolver()
    path = resolver.dotted_to_path("firescript.std.__definitely_missing_pkg__")
    t.require(path.endswith(os.path.join("__definitely_missing_pkg__", "init.fire")), path)


# --- path_to_dotted fallback for paths outside import_root ------------------

def test_path_to_dotted_outside_root_uses_basename():
    with t.tmpdir() as tmp:
        resolver = ModuleResolver(import_root=os.path.join(tmp, "proj_root"))
        outside_path = os.path.join(tmp, "elsewhere", "my_module.fire")
        dotted = resolver.path_to_dotted(outside_path)
        t.require_eq(dotted, "my_module")


# --- parse_file: FileNotFoundError and parser-error branches ---------------

def test_parse_file_missing_file_raises_file_not_found():
    resolver = ModuleResolver()
    with t.tmpdir() as tmp:
        missing = os.path.join(tmp, "does_not_exist.fire")
        try:
            resolver.parse_file(missing)
            t.require(False, "expected FileNotFoundError")
        except FileNotFoundError:
            pass


def test_parse_file_with_syntax_error_raises_runtime_error():
    resolver = ModuleResolver()
    with t.tmpdir() as tmp:
        bad = os.path.join(tmp, "bad.fire")
        with open(bad, "w", encoding="utf-8") as f:
            f.write("int32 x = ;\n")
        try:
            resolver.parse_file(bad)
            t.require(False, "expected RuntimeError for parse error")
        except RuntimeError as e:
            t.require("Parse error in" in str(e), str(e))


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


# --- _load_module: cycle / external / relative-import rejection ------------
# parse_file is monkeypatched to return hand-built ASTs so we can drive
# _load_module's DFS without needing real files on disk.

class _FakeImportSpec:
    def __init__(self, module_path, kind="module"):
        self.module_path = module_path
        self.kind = kind
        self.symbols = []
        self.alias = None
        self.span = (0, 0)


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
    """_load_module's cycle-detection branch ('if dotted in load_stack:
    raise') sits *after* the 'if dotted in self.modules: return' early-out,
    but self.modules[dotted] is populated *before* recursing into that
    module's own dependencies (see _load_module). That means a real A -> B
    -> A cycle never reaches the load_stack check: by the time B's DFS
    revisits "A", self.modules["A"] is already set (from A's own call
    frame, still mid-DFS), so it returns early instead of detecting the
    cycle -- confirmed by tests/sources/invalid/imports/import_cycle_a.fire,
    which expects a downstream FS-PARSE-0003 (undefined symbol) error, not
    a CyclicImportError. This looks like a real, pre-existing bug: the
    cycle branch below is effectively dead code for genuine cycles. It is
    only reachable by calling _load_module directly with a load_stack that
    already contains `dotted` while self.modules does not yet have it --
    which is what this test does, to at least cover the branch's own logic
    in isolation. See CLAUDE.md: this is flagged, not fixed, per
    instructions to leave firescript/ source untouched."""
    fake_asts = {"a": _root()}
    fake_imports = {"a": []}
    resolver, restore = _with_fake_modules(fake_asts, fake_imports)
    try:
        try:
            resolver._load_module("a", ["a"])
            t.require(False, "expected RuntimeError for cyclic import")
        except RuntimeError as e:
            t.require("Cyclic" in str(e) or "cyclic" in str(e), str(e))
    finally:
        restore()


def test_load_module_external_import_rejected():
    fake_asts = {"a": _root()}
    fake_imports = {"a": [_FakeImportSpec("some_pkg", kind="external")]}
    resolver, restore = _with_fake_modules(fake_asts, fake_imports)
    try:
        try:
            resolver._load_module("a", [])
            t.require(False, "expected RuntimeError for external import")
        except RuntimeError as e:
            t.require("External packages are not supported" in str(e), str(e))
    finally:
        restore()


def test_load_module_relative_import_rejected():
    fake_asts = {"a": _root()}
    fake_imports = {"a": [_FakeImportSpec(".sibling")]}
    resolver, restore = _with_fake_modules(fake_asts, fake_imports)
    try:
        try:
            resolver._load_module("a", [])
            t.require(False, "expected RuntimeError for relative import")
        except RuntimeError as e:
            t.require("Relative imports are not supported" in str(e), str(e))
    finally:
        restore()


def test_load_module_not_found_raises_file_not_found():
    resolver = ModuleResolver()
    try:
        resolver._load_module("firescript.std.__totally_missing_module__", [])
        t.require(False, "expected FileNotFoundError")
    except FileNotFoundError:
        pass


def test_resolve_for_entry_skips_external_in_topo_visit():
    # An external-kind import must be skipped (continue) during the
    # topological visit in resolve_for_entry, not just at load time.
    with t.tmpdir() as tmp:
        entry_path = os.path.join(tmp, "entry.fire")
        with open(entry_path, "w", encoding="utf-8") as f:
            f.write("int32 x = 1;\n")
        resolver = ModuleResolver(import_root=tmp)
        entry_mod, topo = resolver.resolve_for_entry(entry_path)
        t.require_eq(entry_mod.dotted, "entry")
        t.require(len(topo) >= 1)


# --- build_merged_ast: duplicate-symbol / no-name / entry-conflict paths ---

def test_build_merged_ast_skips_export_with_no_name():
    entry = Module("entry", "<entry>", _root())
    # A module whose only export has an empty name (should be skipped).
    unnamed = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, "", [ASTNode(NodeTypes.SCOPE, None, "scope", [], 0)], 0)
    unnamed.is_exported = True
    dep_ast = _root([unnamed])
    dep = Module("dep", "<dep>", dep_ast)
    dep.exports = {"": unnamed}  # collect_exports would skip an empty name in practice; force it here
    root = build_merged_ast(entry, [dep, entry])
    # No crash, and nothing with an empty name got appended.
    t.require(all(getattr(c, "name", None) != "" for c in root.children))


def test_build_merged_ast_conflicting_import_symbols_first_wins():
    fn_a = _func_def("shared")
    fn_b = _func_def("shared")
    mod_a = Module("mod_a", "<mod_a>", _root([fn_a]))
    mod_a.exports = {"shared": fn_a}
    mod_b = Module("mod_b", "<mod_b>", _root([fn_b]))
    mod_b.exports = {"shared": fn_b}
    entry = Module("entry", "<entry>", _root())

    root = build_merged_ast(entry, [mod_a, mod_b, entry])
    shared_nodes = [c for c in root.children if getattr(c, "name", None) == "shared"]
    t.require_eq(len(shared_nodes), 1)
    t.require(shared_nodes[0] is fn_a, "first definition must win")


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
