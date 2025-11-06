import os
import logging
from typing import Dict, List, Optional, Tuple, Iterable

from lexer import Lexer
from parser import Parser, ASTNode
from enums import NodeTypes


class ImportSpec:
    def __init__(self, module_path: str, kind: str, symbols: List[dict], alias: Optional[str], span: Tuple[int, int]):
        self.module_path = module_path
        self.kind = kind  # "module" | "symbols" | "wildcard" | "external"
        self.symbols = symbols
        self.alias = alias
        self.span = span


def iter_imports(ast: ASTNode) -> Iterable[ImportSpec]:
    for c in ast.children:
        if c.node_type == NodeTypes.IMPORT_STATEMENT:
            module_path = getattr(c, "module_path", "")
            kind = getattr(c, "kind", "module")
            alias = getattr(c, "alias", None)
            symbols = getattr(c, "symbols", []) or []
            span = getattr(c, "span", (c.index, c.index))
            yield ImportSpec(module_path, kind, symbols, alias, span)


class Module:
    def __init__(self, dotted: str, path: str, ast: ASTNode):
        self.dotted = dotted
        self.path = path
        self.ast = ast
        self.imports: List[ImportSpec] = list(iter_imports(ast))
        self.exports: Dict[str, ASTNode] = {}


class ModuleResolver:
    def __init__(self, import_root: Optional[str] = None) -> None:
        # Default import root to project root (parent of firescript package)
        if import_root is None:
            import_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.import_root = os.path.abspath(import_root)
        self.modules: Dict[str, Module] = {}

    def dotted_to_path(self, dotted: str) -> str:
        rel = dotted.replace(".", os.sep) + ".fire"
        return os.path.join(self.import_root, rel)

    def path_to_dotted(self, path: str) -> str:
        abs_path = os.path.abspath(path)
        if not abs_path.startswith(self.import_root + os.sep) and abs_path != self.import_root:
            # If file is outside import root, derive best-effort dotted from basename
            base = os.path.splitext(os.path.basename(abs_path))[0]
            return base
        rel = os.path.relpath(abs_path, self.import_root)
        no_ext = os.path.splitext(rel)[0]
        return no_ext.replace(os.sep, ".")

    def parse_file(self, file_path: str) -> ASTNode:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(file_path)
        lexer = Lexer(file_content)
        tokens = lexer.tokenize()
        parser = Parser(tokens, file_content, os.path.relpath(file_path))
        ast = parser.parse()
        if parser.errors:
            # Surface the first parser error to the caller
            msg, line, col = parser.errors[0]
            raise RuntimeError(f"Parse error in {file_path}: {msg} at {line}:{col}")
        return ast

    def collect_exports(self, mod: Module) -> Dict[str, ASTNode]:
        exports: Dict[str, ASTNode] = {}
        for c in mod.ast.children:
            if c.node_type in (NodeTypes.FUNCTION_DEFINITION, NodeTypes.CLASS_DEFINITION):
                exports[c.name] = c
            # Optionally, expose top-level variable declarations as well
            if c.node_type == NodeTypes.VARIABLE_DECLARATION:
                exports[c.name] = c
        return exports

    def _load_module(self, dotted: str, load_stack: List[str]) -> Module:
        if dotted in self.modules:
            return self.modules[dotted]
        # Cycle detection
        if dotted in load_stack:
            cycle = load_stack + [dotted]
            raise RuntimeError("Cyclic import detected: " + " -> ".join(cycle))

        path = self.dotted_to_path(dotted)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Module not found: {dotted} (looked in {path})")

        ast = self.parse_file(path)
        mod = Module(dotted, path, ast)
        self.modules[dotted] = mod

        # Resolve dependencies (DFS)
        load_stack.append(dotted)
        for imp in mod.imports:
            if imp.kind == "external":
                raise RuntimeError(f"External packages are not supported: {imp.module_path}")
            base = imp.module_path
            if not base or base.startswith("."):
                raise RuntimeError(f"Relative imports are not supported: {base}")
            dep_dotted = base
            self._load_module(dep_dotted, load_stack)
        load_stack.pop()

        # Collect exports after dependencies (optional for now)
        mod.exports = self.collect_exports(mod)
        return mod

    def resolve_for_entry(self, entry_file: str) -> Tuple[Module, List[Module]]:
        # Derive entry module dotted name from file path
        entry_abs = os.path.abspath(entry_file)
        entry_dotted = self.path_to_dotted(entry_abs)
        entry_mod = self._load_module(entry_dotted, [])

        # Topologically sort modules by DFS post-order
        visited: Dict[str, bool] = {}
        order: List[str] = []

        def visit(dotted: str):
            if visited.get(dotted):
                return
            visited[dotted] = True
            m = self.modules[dotted]
            deps = []
            for imp in m.imports:
                if imp.kind == "external":
                    continue  # already error during load
                deps.append(imp.module_path)
            for dep in deps:
                if dep in self.modules:
                    visit(dep)
            order.append(dotted)

        for dotted in list(self.modules.keys()):
            visit(dotted)

        topo = [self.modules[d] for d in order]
        return entry_mod, topo


def build_merged_ast(entry: Module, ordered: List[Module]) -> ASTNode:
    """
    Build a merged AST suitable for single-file codegen by concatenating exported
    definitions of all modules in topological order, followed by the entry module's
    own non-import top-level statements.

    - Import statements are dropped.
    - Exports include functions, classes, and top-level variable declarations.
    - Conflicting top-level symbol names produce an error.
    - For symbol-vs-symbol conflicts (same name), the first definition wins and
      later conflicting definitions are ignored with an error logged.
    """
    # Create a new ROOT AST node
    root = ASTNode(NodeTypes.ROOT, None, "root", [], 0)

    seen: Dict[str, ASTNode] = {}

    def append_export(node: ASTNode):
        name = getattr(node, "name", None)
        if not name:
            return
        if name in seen:
            logging.error(f"Conflicting top-level symbol '{name}' from imports; already defined.")
            return
        node.parent = root
        root.children.append(node)
        seen[name] = node

    # Add exports from all modules in topo order (dependencies first)
    for mod in ordered:
        if mod is entry:
            # We'll handle entry's own items after imports to preserve user order later
            continue
        for name, node in mod.exports.items():
            # Only include function, class, and top-level var declarations
            if node.node_type in (NodeTypes.FUNCTION_DEFINITION, NodeTypes.CLASS_DEFINITION, NodeTypes.VARIABLE_DECLARATION):
                append_export(node)

    # Finally, include entry module's non-import top-level statements in order
    for c in entry.ast.children:
        if c.node_type == NodeTypes.IMPORT_STATEMENT:
            continue
        # Prevent duplicate symbol definitions when an import pulled in a symbol with same name
        if c.node_type in (NodeTypes.FUNCTION_DEFINITION, NodeTypes.CLASS_DEFINITION, NodeTypes.VARIABLE_DECLARATION):
            if getattr(c, "name", None) in seen:
                logging.error(f"Top-level symbol '{c.name}' in entry conflicts with imported symbol.")
                # Prefer entry's definition: replace the imported one
                prev = seen[c.name]
                try:
                    idx = root.children.index(prev)
                    root.children[idx] = c
                    c.parent = root
                    seen[c.name] = c
                except ValueError:
                    # If somehow not present, just append
                    append_export(c)
                continue
        # For non-symbol statements, just append
        c.parent = root
        root.children.append(c)

    # Lightweight post-merge annotation: set return types for known function calls
    # and var types for identifiers based on merged top-level declarations.
    # Also build a symbol table for the merged scope to help with later type resolution.
    func_types: Dict[str, str] = {}
    var_types: Dict[str, str] = {}
    symbol_table: Dict[str, tuple[str, bool]] = {}
    
    for node in root.children:
        if node.node_type == NodeTypes.FUNCTION_DEFINITION:
            rt = getattr(node, "return_type", None) or "void"
            fname = getattr(node, "name", "")
            func_types[fname] = rt
            # Add function to symbol table as well (not an array)
            symbol_table[fname] = (rt, False)
        elif node.node_type == NodeTypes.VARIABLE_DECLARATION:
            vt = getattr(node, "var_type", None)
            vname = getattr(node, "name", None)
            is_arr = getattr(node, "is_array", False)
            if vname and vt:
                var_types[vname] = vt
                symbol_table[vname] = (vt, is_arr)

    def annotate(n: ASTNode):
        # annotate function calls
        if n.node_type == NodeTypes.FUNCTION_CALL:
            fname = getattr(n, "name", None)
            if fname and fname in func_types:
                setattr(n, "return_type", func_types[fname])
        elif n.node_type == NodeTypes.IDENTIFIER:
            vname = getattr(n, "name", None)
            if vname and vname in var_types:
                setattr(n, "var_type", var_types[vname])
            if vname and vname in symbol_table:
                vt, is_arr = symbol_table[vname]
                setattr(n, "var_type", vt)
                setattr(n, "is_array", is_arr)
        for ch in getattr(n, "children", []) or []:
            annotate(ch)

    for ch in root.children:
        annotate(ch)
    
    # Attach the merged symbol table to root for downstream passes
    setattr(root, "_merged_symbols", symbol_table)

    return root
