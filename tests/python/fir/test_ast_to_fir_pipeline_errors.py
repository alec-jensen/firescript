"""Unit tests for internal FIRConversionError branches in
firescript/ast_to_fir.py that are only reachable by feeding
ASTToFIRConverter a real (lexed/parsed/preprocessed/semantically-analyzed)
AST built from small, deliberately-malformed-at-the-FIR-level source
snippets -- these are constructs the parser and semantic_analyzer both
accept, but that ast_to_fir.py itself rejects while lowering to FIR.
No sidecar files: everything is driven directly through CompilerPipeline
(see firescript/compiler_pipeline.py) exactly the way firescript/main.py
drives it, up to (but not including) the AST->FIR conversion step, which
each test performs itself so it can assert on the resulting
FIRConversionError.

Note: `--check` (used by the tests/sources/invalid/ compile-fail harness)
never reaches ast_to_fir.py at all (firescript/main.py returns before the
AST->FIR conversion step when --check is passed), so these branches are
not reachable through the compile-fail test kind and must be exercised at
the Python level instead."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from compiler_pipeline import CompilerPipeline  # noqa: E402
from ast_to_fir import ASTToFIRConverter, FIRConversionError  # noqa: E402
from errors import IRVerificationError  # noqa: E402
from fir import FIRBuilder, FIRFunction, FIRModule, make_simple  # noqa: E402
from fir.textual import dump_module  # noqa: E402


def _convert(source: str, module_name: str = "test", is_runtime_module: bool = False):
    """Run the full parse -> import-resolve -> preprocess -> semantic-analyze
    pipeline on `source`, then hand the resulting AST to ASTToFIRConverter.
    Raises whatever ASTToFIRConverter.convert() raises; fails the test via
    t.require if an earlier pipeline stage reports parser/semantic errors,
    since that would mean the snippet doesn't reach ast_to_fir.py at all."""
    pipeline = CompilerPipeline(source, "test.fire", "test.fire")
    ast = pipeline.parse()
    t.require(not pipeline.parser_errors, f"unexpected parser errors: {pipeline.parser_errors}")
    if pipeline.has_imports():
        ast = pipeline.resolve_imports()
        t.require(not pipeline.parser_errors, f"unexpected parser errors after import resolution: {pipeline.parser_errors}")
    ast = pipeline.preprocess()
    analyzer = pipeline.analyze_semantics()
    t.require(not analyzer.errors, f"unexpected semantic errors: {analyzer.errors}")
    converter = ASTToFIRConverter(ast, module_name=module_name, is_runtime_module=is_runtime_module)
    return converter.convert()


def _expect_conversion_error(source: str, needle: str, **kwargs) -> None:
    try:
        _convert(source, **kwargs)
        t.require(False, f"no FIRConversionError raised (expected message containing {needle!r})")
    except FIRConversionError as e:
        t.require(needle in str(e), f"{needle!r} not in: {e}")


def test_const_initializer_must_be_a_literal():
    """_render_const_initializer only supports LITERAL (and unary-minus-of-
    LITERAL) initializer nodes; nothing in the parser or semantic_analyzer
    restricts a `const` declaration's RHS to a literal expression, so a
    non-literal const initializer reaches this rejection at FIR-conversion
    time instead of being caught earlier."""
    _expect_conversion_error(
        "const X: int32 = 1 + 2;",
        "Unsupported const initializer node",
    )


def test_match_expression_form_rejects_block_bodied_arm():
    """A `match` used in expression form (its value assigned/returned)
    requires every arm body to be a plain expression, not a `{ }` block --
    nothing in semantic_analyzer.py enforces this, so it's ast_to_fir.py's
    _convert_match() that rejects it while lowering."""
    _expect_conversion_error(
        """
        enum Shape { Circle, Square }
        fn area(s: Shape) -> float64 {
            return match s {
                Shape.Circle -> { return 1.0; },
                Shape.Square -> 2.0
            };
        }
        """,
        "requires every arm body to be a plain expression",
    )


def test_increment_as_subexpression_produces_no_value():
    """`++`/`--` is only supported as a standalone statement -- when used
    as a sub-expression (e.g. as an array-literal element) it converts to
    None, and any call site that requires an actual value
    (_require_value()) rejects it."""
    _expect_conversion_error(
        """
        x: int32 = 1;
        arr: int32[] = [x++];
        """,
        "produces no value but one is required",
    )


def test_const_non_numeric_literal_initializers_reach_fir():
    """Regression (B08a/b/c): `const bool`/`const char` become literal
    GlobalConstants (rendered as 1/0 and the character code so the backend
    can emit them as integers), and `const string` -- whose value is a
    pointer that can't be a static initializer -- becomes a module-level
    variable initialized in the entry prologue (and is never dropped)."""
    mod = _convert(
        """
        import @firescript/std.io.println;
        const S: string = "hi";
        const B: bool = true;
        const C: char = 'Z';
        """
    )
    consts = {c.name: c.literal_text for c in mod.constants}
    t.require(consts == {"B": "1", "C": "90"}, f"unexpected constants: {consts}")
    globals_ = {g.name for g in mod.global_vars}
    t.require(globals_ == {"S"}, f"unexpected module-level variables: {globals_}")


def test_synthesize_zero_for_char_return_type():
    """_synthesize_zero()'s `char` branch (a zero-valued char literal used
    to keep an implicit fallthrough Return well-typed) is unreachable
    through any normal .fire source: `char` can never be used as a
    function or method *return type* in the current grammar -- both
    _parse_function_definition (free functions) and the class-body
    field/method parser use _is_type_token() directly for the return-type
    token, which doesn't recognize `char` (char is only ever accepted as a
    type via the import-deferred-identifier path used for plain variable
    declarations -- see test_ast_to_fir_errors.py's other tests and
    tests/sources/control_flow/for_in_and_match_temporaries.fire's
    comment about the analogous for-in-header gap). Exercised directly
    against the helper instead, mirroring how ASTToFIRConverter sets up
    `self.builder` internally in _convert_function/_convert_method."""
    from parser import ASTNode as _ASTNode  # noqa: E402 (local import: only needed here)
    from enums import NodeTypes as _NodeTypes  # noqa: E402

    empty_module = _ASTNode(_NodeTypes.SCOPE, None, "scope", [], 0)
    converter = ASTToFIRConverter(empty_module, module_name="test")
    char_type = make_simple("char")
    function = FIRFunction("f", return_type=char_type)
    fir_module = FIRModule("test")
    fir_module.add_function(function)
    converter.builder = FIRBuilder(function)
    value = converter._synthesize_zero(char_type)
    t.require(value is not None, "expected a zero char literal, got None")
    t.require(value.result_type.render() == "char", f"unexpected type: {value.result_type.render()}")


def test_bare_array_access_statement_converts():
    """Regression (B15): `arr[0];` as a standalone statement parses (an
    ARRAY_ACCESS expression statement) and used to crash AST->FIR with
    "Unsupported statement node"; a bare in-place read is now evaluated and
    its value discarded."""
    module = _convert(
        """
        a: int32[3] = [1, 2, 3];
        a[0];
        """
    )
    t.require(any(f.name == "main" for f in module.functions), "main was not converted")


def test_directive_statement_inside_function_is_rejected_cleanly():
    """Regression (B15): `directive x;` inside a function body parses, then
    used to crash AST->FIR with a generic "Unsupported statement node"
    message; it is now rejected with a message saying where directives are
    allowed."""
    _expect_conversion_error(
        """
        fn f() -> void {
            directive enable_syscalls;
        }
        """,
        "only allowed at the top level",
    )


def test_directive_gated_intrinsic_without_directive_enabled():
    """stdout() is gated behind `directive enable_lowlevel_stdout;`; the
    parser accepts the call unconditionally (see parser/base.py's
    builtin_functions comment: "the code generator enforces the directive
    requirement at emit time"), so ast_to_fir.py's _check_directive() is
    the actual enforcement point."""
    _expect_conversion_error(
        'stdout("hi");',
        "is not available",
    )


def test_for_in_over_array_returning_function_call_converts():
    """Regression (B07): a function declared with an unsized array return
    type (`-> int32[]`) that returns a fixed-size array literal used to
    produce a FIR Return typed 'int32[3]' against the declared 'int32[]',
    tripping FIRV-T4 as an internal compiler error. The verifier now treats
    a sized array as assignable to an unsized one on return, as it already
    did for call arguments. The for-in over the call is also the only way to
    reach _array_size_of()'s final `return None` fallthrough (the collection
    is neither an ARRAY_LITERAL nor an IDENTIFIER) -- array class fields and
    array-returning class methods are unsupported by the parser, so a free
    function call is the only reachable non-identifier array-typed for-in
    collection."""
    module = _convert(
        """
        fn makeArr() -> int32[] {
            return [1, 2, 3];
        }
        for (v: int32 in makeArr()) {
        }
        """
    )
    t.require(any(f.name == "makeArr" for f in module.functions), "makeArr was not converted")


def test_runtime_module_rejects_top_level_statements():
    """is_runtime_module=True (used only for the fixed std/internal
    runtime source files compiled by firescript/main.py's
    _compile_runtime_file helper) disallows top-level statements outside
    function/class/enum/const definitions -- exercised here directly since
    no normal .fire test file is ever compiled with this flag."""
    _expect_conversion_error(
        "x: int32 = 1;",
        "Runtime modules must not contain top-level statements",
        is_runtime_module=True,
    )


def test_sized_array_without_initializer_is_zero_initialized():
    """`arr: int32[4];` (no initializer) lowers to a zero-initialized
    array literal of the declared size."""
    dump = dump_module(_convert("arr: int32[4];\n"))
    t.require("%0 = arrayconst.int32[4] []" in dump, dump)
    t.require("local arr: int32[4] = %0" in dump, dump)


def test_bare_return_in_non_void_function_is_rejected_by_the_parser():
    """`return;` in an `int32` function is a compile-time error. (It used to
    be accepted and lowered to a synthesized zero return; the FIR fallback is
    now only a defensive branch that source can no longer reach.)"""
    pipeline = CompilerPipeline("fn f() -> int32 { return; }\nx: int32 = f();\n", "test.fire", "test.fire")
    pipeline.parse()
    t.require(
        any("'return' without a value" in e.message for e in pipeline.parser_errors),
        f"expected a missing-return-value diagnostic, got: {[e.message for e in pipeline.parser_errors]}",
    )


def test_function_referenced_top_level_variable_becomes_module_variable():
    """B04: a top-level variable that a function body refers to is promoted
    to a FIR global variable (static storage); one that no function refers
    to stays a local of the synthetic main."""
    mod = _convert(
        """
        g: int32 = 10;
        local_only: int32 = 3;
        fn f() -> int32 { return g + 1; }
        """
    )
    names = {gv.name for gv in mod.global_vars}
    t.require(names == {"g"}, f"unexpected module-level variables: {names}")


def test_user_main_promotes_every_top_level_declaration():
    """With a user main(), top-level declarations still run (they become
    module-level variables initialized in main's prologue)."""
    mod = _convert(
        """
        a: int32 = 1;
        b: string = "x";
        fn main() -> void { }
        """
    )
    names = [gv.name for gv in mod.global_vars]
    t.require(names == ["a", "b"], f"unexpected module-level variables: {names}")


def test_moving_an_owned_module_variable_is_rejected():
    _expect_conversion_error(
        """
        name: string = "abc";
        fn show() -> string { return "x" + name; }
        other: string = name;
        """,
        "owned module-level variable 'name'",
    )
