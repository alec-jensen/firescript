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
        "const int32 X = 1 + 2;",
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
        float64 area(Shape s) {
            return match s {
                Shape.Circle -> { 1.0 },
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
    (_require_value()) rejects it. Note: not every value-requiring call
    site in ast_to_fir.py goes through _require_value() -- e.g. `int32 y =
    x++ + 1;` (a binary-operator operand) instead reaches
    fir/verifier.py's FIRV-D1 check as an internal compiler error (a
    latent bug: BinaryOp's operand converts to None silently instead of
    being rejected at the ast_to_fir.py level), which is a separate,
    unrelated crash from the one exercised here."""
    _expect_conversion_error(
        """
        int32 x = 1;
        int32[] arr = [x++];
        """,
        "produces no value but one is required",
    )


def test_const_non_numeric_literal_initializers_reach_fir():
    """`const string`/`const bool`/`const char` all convert to FIR
    successfully (exercising _normalize_literal_text's STRING_LITERAL/
    BOOLEAN_LITERAL/CHAR_LITERAL passthrough fallback -- only
    INTEGER_LITERAL/FLOAT_LITERAL/DOUBLE_LITERAL get suffix-stripping
    there), but each one is a *separate*, pre-existing, downstream bug
    away from actually compiling end-to-end -- deliberately not exercised
    as a tests/sources/*.fire "run"/"snapshot" case for that reason (only
    the FIR-conversion step, not the full compile, is asserted here):

    - `const string S = "hi";`: preprocessor.py inserts a drop() for the
      const string as though it were an owned local, but it backs a
      global constant (not a heap allocation) -- flir/verifier.py's
      FLIRV-A3 ("free/destroy argument is not a heap-allocation base
      pointer") then fires as an internal compiler error during FIR->FLIR
      lowering.
    - `const bool B = true;`: codegen/x86_64/flir_to_asm.py's
      _emit_globals() decides whether a global literal needs float
      parsing via `gtype.is_float() or "." in literal or "e" in
      literal` -- that "e" in literal" substring check is meant to catch
      scientific notation (e.g. "1e10") but also matches the literal text
      "true" (which contains the letter 'e'), so `_emit_globals` crashes
      with "ValueError: could not convert string to float: 'true'"
      instead of compiling (`const bool B = false;` is unaffected,
      coincidentally, since "false" contains no 'e').
    - `const char C = 'Z';`: _normalize_literal_text() has no
      CHAR_LITERAL case (only INTEGER_LITERAL/FLOAT_LITERAL/
      DOUBLE_LITERAL strip anything), so it falls through to `return
      text`, returning the *raw token text including the surrounding
      single quotes* ("'Z'") as the GlobalConstant's literal string.
      _emit_globals() then crashes with "ValueError: invalid literal for
      int() with base 10: \"'Z'\"" trying to parse it as an integer.
    """
    mod = _convert(
        """
        import @firescript/std.io.println;
        const string S = "hi";
        const bool B = true;
        const char C = 'Z';
        """
    )
    names = {c.name for c in mod.constants}
    t.require(names == {"S", "B", "C"}, f"unexpected constants: {names}")


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


def test_bare_array_access_statement_is_unsupported():
    """`arr[0];` as a standalone statement parses fine (an ARRAY_ACCESS
    expression statement) and passes semantic analysis, but
    _convert_statement() has no dispatch case for a bare ARRAY_ACCESS (only
    call-like expression nodes are permitted as expression-statements), so
    it falls through to the "Unsupported statement node" catch-all."""
    _expect_conversion_error(
        """
        int32[3] a = [1, 2, 3];
        a[0];
        """,
        "Unsupported statement node",
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


def test_for_in_over_array_returning_function_call_hits_known_verifier_bug():
    """Known bug (not fixed here, per project convention -- see
    tests/TEST_MANIFEST.md's "known issues" pattern): a function declared
    with an unsized array return type (`int32[] f() { ... }`) that returns
    a fixed-size array literal produces a FIR Return instruction typed
    'int32[N]' against the function's declared 'int32[]' return type,
    which trips FIRV-T4 ("Return value type does not match declared return
    type") as an internal compiler error (IRVerificationError) instead of
    either compiling successfully or being rejected with a clean
    diagnostic at an earlier stage. This is triggered here via a `for-in`
    over such a call (a non-identifier, non-array-literal for-in
    collection expression), which also happens to be the only way to
    reach _array_size_of()'s final `return None` fallthrough (the
    collection is neither an ARRAY_LITERAL nor an IDENTIFIER) -- array
    class fields and array-returning class methods are both unsupported
    by the parser (`class Foo { int32[] x; }` / `int32[] get(&this) {}`
    both fail to parse: "Expected identifier after type in class body"),
    so a free function call is the only reachable non-identifier
    array-typed for-in collection at all."""
    try:
        _convert(
            """
            int32[] makeArr() {
                return [1, 2, 3];
            }
            for (int32 v in makeArr()) {
            }
            """
        )
        t.require(False, "expected IRVerificationError (FIRV-T4) -- has the underlying bug been fixed?")
    except IRVerificationError as e:
        t.require("FIRV-T4" in str(e), f"expected FIRV-T4, got: {e}")


def test_runtime_module_rejects_top_level_statements():
    """is_runtime_module=True (used only for the fixed std/internal
    runtime source files compiled by firescript/main.py's
    _compile_runtime_file helper) disallows top-level statements outside
    function/class/enum/const definitions -- exercised here directly since
    no normal .fire test file is ever compiled with this flag."""
    _expect_conversion_error(
        "int32 x = 1;",
        "Runtime modules must not contain top-level statements",
        is_runtime_module=True,
    )
