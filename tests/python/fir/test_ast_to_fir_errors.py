"""Coverage-focused unit tests for firescript/ast_to_fir.py's internal
defensive branches: malformed/edge-case AST shapes that semantic analysis
normally rejects before ast_to_fir ever sees them, or that no current
parser rule can produce. Built with hand-constructed ASTNode trees driving
ASTToFIRConverter directly (there is no builder for the AST layer),
following tests/python/flir/test_verifier_heap.py's "build IR objects by
hand" pattern one layer up the pipeline.

Several of the FIRConversionError sites exercised here (_check_directive,
_convert_array_method's array_length fallback, the ARRAY_LITERAL type_args
fallback in _convert_construction) are plausibly reachable through real
firescript source too; they are exercised directly here for speed and
determinism, but a full .fire-source regression test may still be worth
adding later (noted in the coverage report).
"""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from enums import NodeTypes  # noqa: E402
from lexer import Token  # noqa: E402
from parser import ASTNode  # noqa: E402

from ast_to_fir import ASTToFIRConverter, FIRConversionError  # noqa: E402
from fir.ir_builder import FIRBuilder  # noqa: E402
from fir.ir_module import FIRFunction  # noqa: E402


def _tok(ttype: str, value: str = "", index: int = 0) -> Token:
    return Token(ttype, value, index)


def _node(node_type: NodeTypes, name: str = "", children=None, token=None, **kwargs) -> ASTNode:
    n = ASTNode(node_type, token, name, children or [], token.index if token else 0)
    for k, v in kwargs.items():
        setattr(n, k, v)
    return n


def _root(children) -> ASTNode:
    return _node(NodeTypes.ROOT, "root", children, token=_tok("EOF"))


def _new_converter(children=None, is_runtime_module: bool = False) -> ASTToFIRConverter:
    return ASTToFIRConverter(_root(children or []), is_runtime_module=is_runtime_module)


def _with_builder(converter: ASTToFIRConverter) -> ASTToFIRConverter:
    """Give a fresh converter a minimal function/builder/scope so private
    per-statement/per-expression helpers (which assume self.builder is
    live) can be called directly."""
    func = FIRFunction("f", return_type=None)
    converter.current_function = func
    converter.builder = FIRBuilder(func)
    converter._push_scope()
    return converter


def _expect_conversion_error(fn) -> None:
    try:
        fn()
        t.require(False, "expected FIRConversionError")
    except FIRConversionError:
        pass


# -- FIRConversionError message formatting (location suffix) ----------------

def test_conversion_error_with_node_and_token():
    tok = _tok("IDENTIFIER", "x", 42)
    node = _node(NodeTypes.IDENTIFIER, "x", token=tok)
    err = FIRConversionError("boom", node)
    t.require("source index 42" in str(err), str(err))
    t.require(err.node is node)


def test_conversion_error_without_node():
    err = FIRConversionError("boom")
    t.require(str(err) == "boom", str(err))


def test_conversion_error_node_without_token():
    node = _node(NodeTypes.IDENTIFIER, "x")
    node.token = None
    err = FIRConversionError("boom", node)
    t.require(str(err) == "boom", str(err))


# -- convert(): runtime modules must not contain top-level statements ------

def test_runtime_module_rejects_top_level_statements():
    stray = _node(NodeTypes.BREAK_STATEMENT, "break", token=_tok("BREAK"))
    converter = _new_converter([stray], is_runtime_module=True)
    _expect_conversion_error(converter.convert)


# -- _fir_type: None defaults to int32 ---------------------------------------

def test_fir_type_none_defaults_to_int32():
    converter = _new_converter()
    ty = converter._fir_type(None)
    t.require(ty.render() == "int32", ty.render())


# -- _expr_type: literal-token defaults when return_type isn't annotated ---

def test_expr_type_literal_token_defaults():
    converter = _new_converter()
    for ttype, expected in [
        ("INTEGER_LITERAL", "int32"),
        ("FLOAT_LITERAL", "float32"),
        ("DOUBLE_LITERAL", "float64"),
        ("BOOLEAN_LITERAL", "bool"),
        ("STRING_LITERAL", "string"),
        ("CHAR_LITERAL", "char"),
        ("NULL_LITERAL", "null"),
    ]:
        node = _node(NodeTypes.LITERAL, "", token=_tok(ttype, "0"))
        t.require_eq(converter._expr_type(node), expected, ttype)


def test_expr_type_empty_array_literal_defaults_int32():
    converter = _new_converter()
    node = _node(NodeTypes.ARRAY_LITERAL, "[]", [])
    t.require_eq(converter._expr_type(node), "int32[]")


# -- _collect_program_info: array-typed class field --------------------------

def test_class_array_field_type_string():
    field = _node(NodeTypes.CLASS_FIELD, "items", var_type="int32", is_array=True)
    cls = _node(NodeTypes.CLASS_DEFINITION, "C", [field])
    converter = _new_converter([cls])
    converter._collect_program_info()
    t.require_eq(converter.class_fields["C"], [("items", "int32[]")])


# -- break/continue outside a loop -------------------------------------------

def test_break_outside_loop_raises():
    converter = _with_builder(_new_converter())
    stmt = _node(NodeTypes.BREAK_STATEMENT, "break", token=_tok("BREAK"))
    _expect_conversion_error(lambda: converter._convert_statement(stmt))


def test_continue_outside_loop_raises():
    converter = _with_builder(_new_converter())
    stmt = _node(NodeTypes.CONTINUE_STATEMENT, "continue", token=_tok("CONTINUE"))
    _expect_conversion_error(lambda: converter._convert_statement(stmt))


# -- return with a post-return-drop name not currently in scope -------------

def test_return_post_drop_name_not_in_scope_is_skipped():
    converter = _with_builder(_new_converter())
    lit = _node(NodeTypes.LITERAL, "", token=_tok("INTEGER_LITERAL", "1"))
    ret = _node(
        NodeTypes.RETURN_STATEMENT, "return", [lit],
        token=_tok("RETURN"), post_return_drop_names=["unknown_local"],
    )
    converter.current_function.return_type = None
    converter._convert_statement(ret)  # must not raise


# -- unsupported statement / expression / literal-token fallbacks -----------

def test_unsupported_statement_raises():
    converter = _with_builder(_new_converter())
    bogus = _node(NodeTypes.ENUM_VARIANT, "bogus", token=_tok("EOF"))
    _expect_conversion_error(lambda: converter._convert_statement(bogus))


def test_unsupported_expression_raises():
    converter = _with_builder(_new_converter())
    bogus = _node(NodeTypes.ENUM_VARIANT, "bogus", token=_tok("EOF"))
    _expect_conversion_error(lambda: converter._convert_expression(bogus))


def test_unsupported_literal_token_raises():
    converter = _with_builder(_new_converter())
    node = _node(NodeTypes.LITERAL, "", token=_tok("UNKNOWN_LITERAL", "?"))
    _expect_conversion_error(lambda: converter._convert_literal(node))


# -- assignment without a value, unsupported assignment target --------------

def test_assignment_without_value_raises():
    converter = _with_builder(_new_converter())
    node = _node(NodeTypes.VARIABLE_ASSIGNMENT, "x", [])
    _expect_conversion_error(lambda: converter._convert_variable_assignment(node))


def test_unsupported_assignment_target_raises():
    converter = _with_builder(_new_converter())
    lit = _node(NodeTypes.LITERAL, "", token=_tok("INTEGER_LITERAL", "1"))
    bogus_target = _node(NodeTypes.ENUM_VARIANT, "bogus", token=_tok("EOF"))
    node = _node(NodeTypes.ASSIGNMENT, "=", [bogus_target, lit])
    _expect_conversion_error(lambda: converter._convert_assignment(node))


# -- increment/decrement used as a sub-expression (statement-only in the
# real grammar, but _convert_expression still handles it defensively) ------

def test_increment_as_expression_returns_none_and_require_value_raises():
    converter = _with_builder(_new_converter())
    converter._declare("i", "int32", False, None)
    int_type = converter._fir_type("int32")
    from fir.ir_node import Value  # noqa: F401
    zero = converter.builder.int_literal("0", int_type)
    converter.builder.declare_local(converter._local_name("i"), int_type, zero)
    incr = _node(NodeTypes.UNARY_EXPRESSION, "++", token=_tok("IDENTIFIER", "i"))
    result = converter._convert_expression(incr)
    t.require(result is None, result)
    _expect_conversion_error(lambda: converter._require_value(incr))


# -- enum variant construction: unknown variant / wrong argument count ------

def test_enum_variant_construct_unknown_variant_raises():
    converter = _with_builder(_new_converter())
    converter.enum_variants["MyEnum"] = [("Known", [])]
    node = _node(NodeTypes.ENUM_VARIANT_CONSTRUCT, "Missing", [], class_name="MyEnum")
    _expect_conversion_error(lambda: converter._convert_enum_variant_construct(node))


def test_enum_variant_construct_wrong_arg_count_raises():
    converter = _with_builder(_new_converter())
    int_ty = converter._fir_type("int32")
    converter.enum_variants["MyEnum"] = [("Circle", [("radius", int_ty)])]
    node = _node(NodeTypes.ENUM_VARIANT_CONSTRUCT, "Circle", [], class_name="MyEnum")
    _expect_conversion_error(lambda: converter._convert_enum_variant_construct(node))


# -- match used as an expression with a block-bodied arm --------------------

def test_match_expression_with_block_arm_raises():
    converter = _with_builder(_new_converter())
    scrutinee = _node(NodeTypes.LITERAL, "", token=_tok("INTEGER_LITERAL", "1"))
    block_body = _node(NodeTypes.SCOPE, "scope", [])
    arm = _node(NodeTypes.MATCH_ARM, "_", [block_body], is_wildcard=True, enum_name=None)
    match_node = _node(NodeTypes.MATCH_EXPRESSION, "match", [scrutinee, arm])
    _expect_conversion_error(lambda: converter._convert_match(match_node, as_statement=False))


# -- match arm binding referencing an unknown payload field is skipped
# (semantic analysis is expected to have already reported it) --------------

def test_match_arm_unknown_binding_field_is_skipped():
    converter = _with_builder(_new_converter())
    int_ty = converter._fir_type("int32")
    string_ty = converter._fir_type("string")
    scrut_type = converter._fir_type("string")  # arbitrary placeholder type
    scrut = converter.builder.string_literal("x", string_ty)
    converter.builder.declare_local("__scrut", scrut_type, scrut)
    arm = _node(
        NodeTypes.MATCH_ARM, "Circle", [],
        variant_name="Circle", bindings=[("unknown_field", "r")],
    )
    variant_fields = {"Circle": [("radius", int_ty)]}
    converter._convert_match_arm_body(arm, variant_fields, "__scrut", scrut_type, None)


# -- _array_size_of: neither an array literal nor a known identifier -------

def test_array_size_of_unknown_expression_is_none():
    converter = _new_converter()
    call = _node(NodeTypes.FUNCTION_CALL, "make_array", [])
    t.require(converter._array_size_of(call) is None)


def test_array_size_of_unbound_identifier_is_none():
    converter = _new_converter()
    ident = _node(NodeTypes.IDENTIFIER, "nope")
    t.require(converter._array_size_of(ident) is None)


# -- _norm_source: exception path (non-string input) -------------------------

def test_norm_source_exception_path_returns_input():
    result = ASTToFIRConverter._norm_source(12345)  # not a path-like string
    t.require_eq(result, 12345)


def test_norm_source_falsy_is_none():
    t.require(ASTToFIRConverter._norm_source("") is None)


# -- _check_directive: gated intrinsic called without the enabling directive

def test_check_directive_missing_raises():
    converter = _with_builder(_new_converter())
    node = _node(NodeTypes.FUNCTION_CALL, "syscall_open", [])
    _expect_conversion_error(lambda: converter._check_directive(node))


def test_check_directive_present_does_not_raise():
    converter = _with_builder(_new_converter())
    converter.file_directives[None] = {"enable_syscalls"}
    node = _node(NodeTypes.FUNCTION_CALL, "syscall_open", [])
    converter._check_directive(node)  # must not raise


def test_check_directive_ungated_name_is_noop():
    converter = _with_builder(_new_converter())
    node = _node(NodeTypes.FUNCTION_CALL, "some_user_function", [])
    converter._check_directive(node)  # must not raise


# -- _convert_construction: type_args inferred from the node's own
# annotation (not from an explicit "Name<...>" spelling) -------------------

def test_construction_type_args_from_annotation():
    converter = _with_builder(_new_converter())
    converter.class_categories["Box"] = "owned"
    converter.class_generic_params["Box"] = ["T"]
    converter.class_fields["Box"] = [("value", "T")]
    converter.class_method_names["Box"] = set()
    lit = _node(NodeTypes.LITERAL, "", token=_tok("INTEGER_LITERAL", "1"))
    node = _node(NodeTypes.CONSTRUCTOR_CALL, "Box", [lit], type_args=["int32"])
    value = converter._convert_construction(node, "Box", "Box")
    t.require("Box<int32>" in value.result_type.render(), value.result_type.render())


# -- _call_arg_modes: unregistered non-intrinsic function name defaults to
# "own" for every argument; a registered function's non-borrowed borrowed
# parameter (plain `&`) yields "borrow" ------------------------------------

def test_call_arg_modes_unknown_function_defaults_own():
    converter = _new_converter()
    lit = _node(NodeTypes.LITERAL, "", token=_tok("INTEGER_LITERAL", "1"))
    node = _node(NodeTypes.FUNCTION_CALL, "totally_unknown_fn", [lit])
    t.require_eq(converter._call_arg_modes("totally_unknown_fn", node), ["own"])


def test_call_arg_modes_borrow_param():
    param = _node(NodeTypes.PARAMETER, "p", var_type="int32", is_borrowed=True, is_mutable_borrow=False)
    body = _node(NodeTypes.SCOPE, "scope", [])
    func_def = _node(NodeTypes.FUNCTION_DEFINITION, "takes_borrow", [param, body])
    converter = _new_converter()
    converter.function_defs["takes_borrow"] = func_def
    lit = _node(NodeTypes.LITERAL, "", token=_tok("INTEGER_LITERAL", "1"))
    node = _node(NodeTypes.FUNCTION_CALL, "takes_borrow", [lit])
    t.require_eq(converter._call_arg_modes("takes_borrow", node), ["borrow"])


# -- _infer_type_args: no type params or missing function definition -------

def test_infer_type_args_no_type_params_returns_empty():
    converter = _new_converter()
    node = _node(NodeTypes.FUNCTION_CALL, "plain_fn", [])
    t.require_eq(converter._infer_type_args("plain_fn", node), [])


def test_infer_type_args_missing_func_def_returns_empty():
    converter = _new_converter()
    converter.generic_functions["generic_fn"] = ["T"]
    node = _node(NodeTypes.FUNCTION_CALL, "generic_fn", [])
    t.require_eq(converter._infer_type_args("generic_fn", node), [])


# -- _convert_builtin_method: length()/size() with an unknown static size,
# and an unsupported array method name (registry-driven, see
# firescript/builtin_methods.py and firescript/std/internal/builtin_arrays.fire)
# ----------------------------------------------------------------------------

def test_array_method_length_unknown_size_calls_intrinsic():
    converter = _with_builder(_new_converter())
    call_fn = _node(NodeTypes.FUNCTION_CALL, "make_array", [])
    node = _node(NodeTypes.METHOD_CALL, "length", [call_fn])
    value = converter._convert_builtin_method(node, call_fn, "array", "int32", "length")
    t.require(value.instruction.metadata.get("intrinsic") is True)


def test_array_method_unsupported_name_raises():
    converter = _with_builder(_new_converter())
    ident = _node(NodeTypes.IDENTIFIER, "arr")
    node = _node(NodeTypes.METHOD_CALL, "sort", [ident])
    _expect_conversion_error(lambda: converter._convert_builtin_method(node, ident, "array", "int32", "sort"))


# -- super() call without a resolved super class -----------------------------

def test_super_call_without_resolved_class_raises():
    converter = _with_builder(_new_converter())
    node = _node(NodeTypes.SUPER_CALL, "super", [])
    _expect_conversion_error(lambda: converter._convert_super_call(node))


# -- _fir_type: array-suffixed / generator<T> string forms ------------------

def test_fir_type_array_suffix_string():
    converter = _new_converter()
    ty = converter._fir_type("int32[]")
    t.require("[]" in ty.render() or ty.render().endswith("]"), ty.render())


def test_fir_type_generator_string():
    converter = _new_converter()
    ty = converter._fir_type("generator<int32>")
    t.require("generator" in ty.render(), ty.render())


# -- _split_type_args: nested "<...>" depth tracking -------------------------

def test_split_type_args_nested_generics():
    args = ASTToFIRConverter._split_type_args("Pair<int32, string>, bool")
    t.require_eq(args, ["Pair<int32, string>", "bool"])


# -- _expr_type: METHOD_CALL / TYPE_METHOD_CALL / SUPER_CALL / CONSTRUCTOR_CALL
# / FIELD_ACCESS / MATCH_EXPRESSION without a pre-annotated return_type -----

def test_expr_type_method_call_constructor_method():
    ctor = _node(NodeTypes.CLASS_METHOD_DEFINITION, "C", [], is_constructor=True)
    converter = _new_converter()
    converter.class_method_defs[("C", "C")] = ctor
    receiver = _node(NodeTypes.IDENTIFIER, "obj", var_type="C")
    node = _node(NodeTypes.METHOD_CALL, "C", [receiver])
    t.require_eq(converter._expr_type(node), "C")


def test_expr_type_method_call_not_found_is_void():
    converter = _new_converter()
    receiver = _node(NodeTypes.IDENTIFIER, "obj", var_type="C")
    node = _node(NodeTypes.METHOD_CALL, "missing", [receiver])
    t.require_eq(converter._expr_type(node), "void")


def test_expr_type_type_method_call_found_and_not_found():
    method = _node(NodeTypes.CLASS_METHOD_DEFINITION, "make", [], return_type="int32")
    converter = _new_converter()
    converter.class_method_defs[("C", "make")] = method
    node_found = _node(NodeTypes.TYPE_METHOD_CALL, "make", [], class_name="C")
    t.require_eq(converter._expr_type(node_found), "int32")
    node_missing = _node(NodeTypes.TYPE_METHOD_CALL, "nope", [], class_name="C")
    t.require_eq(converter._expr_type(node_missing), "void")


def test_expr_type_super_call_defaults_void():
    converter = _new_converter()
    node = _node(NodeTypes.SUPER_CALL, "super", [])
    t.require_eq(converter._expr_type(node), "void")


def test_expr_type_constructor_call_is_class_name():
    converter = _new_converter()
    node = _node(NodeTypes.CONSTRUCTOR_CALL, "MyClass", [])
    t.require_eq(converter._expr_type(node), "MyClass")


def test_expr_type_field_access_unknown_field_defaults_int32():
    converter = _new_converter()
    converter.class_fields["C"] = []
    receiver = _node(NodeTypes.IDENTIFIER, "obj", var_type="C")
    node = _node(NodeTypes.FIELD_ACCESS, "missing_field", [receiver])
    t.require_eq(converter._expr_type(node), "int32")


def test_expr_type_match_expression_falls_back_to_first_arm():
    converter = _new_converter()
    scrutinee = _node(NodeTypes.LITERAL, "", token=_tok("INTEGER_LITERAL", "1"))
    body = _node(NodeTypes.LITERAL, "", token=_tok("INTEGER_LITERAL", "2"))
    arm = _node(NodeTypes.MATCH_ARM, "_", [body], is_wildcard=True)
    node = _node(NodeTypes.MATCH_EXPRESSION, "match", [scrutinee, arm])
    t.require_eq(converter._expr_type(node), "int32")


def test_expr_type_match_expression_all_scope_arms_is_void():
    converter = _new_converter()
    scrutinee = _node(NodeTypes.LITERAL, "", token=_tok("INTEGER_LITERAL", "1"))
    scope_body = _node(NodeTypes.SCOPE, "scope", [])
    arm = _node(NodeTypes.MATCH_ARM, "_", [scope_body], is_wildcard=True)
    node = _node(NodeTypes.MATCH_EXPRESSION, "match", [scrutinee, arm])
    t.require_eq(converter._expr_type(node), "void")


# -- _find_method_def: exhausts the base-class chain without a match -------

def test_find_method_def_exhausts_chain_returns_none():
    converter = _new_converter()
    converter.class_bases["Child"] = "Parent"
    # "Parent" has no entry in class_bases -> chain ends naturally.
    t.require(converter._find_method_def("Child", "missing_method") is None)


# -- _render_const_initializer: unsupported node type ------------------------

def test_render_const_initializer_unsupported_node_raises():
    converter = _new_converter()
    bogus = _node(NodeTypes.IDENTIFIER, "x")
    _expect_conversion_error(lambda: converter._render_const_initializer(bogus))


# -- _normalize_literal_text: non-numeric token types pass through verbatim -

def test_normalize_literal_text_string_literal_passthrough():
    converter = _new_converter()
    node = _node(NodeTypes.LITERAL, "", token=_tok("STRING_LITERAL", '"hi"'))
    t.require_eq(converter._normalize_literal_text(node), '"hi"')


# -- _convert_method: non-static, non-constructor method with no explicit
# "this" parameter in its signature (register_params_in_scope never saw one)

def test_convert_method_implicit_this_declared_when_missing():
    body = _node(NodeTypes.SCOPE, "scope", [])
    method = _node(NodeTypes.CLASS_METHOD_DEFINITION, "greet", [body], is_constructor=False, is_static=False)
    converter = _new_converter()
    converter.class_categories["C"] = "owned"
    converter._convert_method("C", method)
    t.require(any(f.name == "C.greet" for f in converter.module.functions))


# -- _seal_open_blocks: an unterminated block gets an Unreachable terminator;
# a function with zero blocks is a no-op --------------------------------

def test_seal_open_blocks_terminates_dangling_block():
    func = FIRFunction("f", return_type=None)
    func.new_block()  # left unterminated on purpose
    ASTToFIRConverter._seal_open_blocks(func)
    t.require(func.blocks[0].terminator is not None)


def test_seal_open_blocks_no_blocks_is_noop():
    func = FIRFunction("f", return_type=None)
    func.blocks = []
    ASTToFIRConverter._seal_open_blocks(func)  # must not raise
    t.require_eq(func.blocks, [])


# -- _synthesize_zero: non-scalar type -> None; int8/char zero values ------

def test_synthesize_zero_non_simple_type_is_none():
    converter = _with_builder(_new_converter())
    from fir.ir_types import ArrayType
    array_ty = ArrayType(converter._fir_type("int32"), 3)
    t.require(converter._synthesize_zero(array_ty) is None)


def test_synthesize_zero_int_and_char():
    converter = _with_builder(_new_converter())
    int_ty = converter._fir_type("int8")
    char_ty = converter._fir_type("char")
    t.require(converter._synthesize_zero(int_ty) is not None)
    t.require(converter._synthesize_zero(char_ty) is not None)


# -- implicit-declaration reassignment wrapper (preprocessor-inserted
# `{ drop(x); x = RHS; }`) when the name isn't already in scope -------------

def test_scope_reassignment_wrapper_implicit_declare():
    converter = _with_builder(_new_converter())
    ident = _node(NodeTypes.IDENTIFIER, "x")
    drop_call = _node(NodeTypes.FUNCTION_CALL, "drop", [ident])
    rhs = _node(NodeTypes.LITERAL, "", token=_tok("INTEGER_LITERAL", "5"))
    assign = _node(NodeTypes.VARIABLE_ASSIGNMENT, "x", [rhs])
    wrapper = _node(NodeTypes.SCOPE, "scope", [drop_call, assign])
    converter._convert_statement(wrapper)  # must not raise; x is freshly declared


# -- return with no value in a non-void, non-generator function synthesizes
# a zero return value ---------------------------------------------------

def test_return_with_no_value_synthesizes_zero():
    converter = _with_builder(_new_converter())
    converter.current_function.return_type = converter._fir_type("int32")
    ret = _node(NodeTypes.RETURN_STATEMENT, "return", [], token=_tok("RETURN"))
    converter._convert_statement(ret)  # must not raise


# -- variable declaration: array-typed local initialized from a non-literal
# expression (e.g. copying another array binding) --------------------------

def test_array_declaration_from_non_literal_expression():
    converter = _with_builder(_new_converter())
    converter._declare("src", "int32", True, 3)
    int_arr_ty = converter._fir_type("int32", True, 3)
    zero_elems = converter.builder.array_literal([], int_arr_ty)
    converter.builder.declare_local(converter._local_name("src"), int_arr_ty, zero_elems)
    ident = _node(NodeTypes.IDENTIFIER, "src", var_type="int32", is_array=True)
    decl = _node(
        NodeTypes.VARIABLE_DECLARATION, "dst", [ident],
        var_type="int32", is_array=True, array_size=3,
    )
    converter._convert_variable_declaration(decl)  # must not raise


# -- standalone generator-function call not used in a for-in loop ----------

def test_generator_call_as_plain_expression():
    converter = _with_builder(_new_converter())
    gen_def = _node(NodeTypes.GENERATOR_DEFINITION, "counter", [], return_type="int32")
    converter.generator_defs["counter"] = gen_def
    node = _node(NodeTypes.FUNCTION_CALL, "counter", [])
    value = converter._convert_function_call(node, as_statement=False)
    t.require(value is not None)


# -- _call_arg_modes: a mutably-borrowed parameter yields "borrow_mut" ------

# -- _expr_type: increment/decrement expression type, annotated MATCH_EXPRESSION,
# and the final generic fallback --------------------------------------------

def test_expr_type_increment_uses_bound_variable_type():
    converter = _new_converter()
    converter._push_scope()
    converter._declare("i", "int64", False, None)
    node = _node(NodeTypes.UNARY_EXPRESSION, "++", token=_tok("IDENTIFIER", "i"))
    t.require_eq(converter._expr_type(node), "int64")


def test_expr_type_increment_unbound_defaults_int32():
    converter = _new_converter()
    node = _node(NodeTypes.UNARY_EXPRESSION, "++", token=_tok("IDENTIFIER", "nope"))
    t.require_eq(converter._expr_type(node), "int32")


def test_expr_type_match_expression_annotated():
    converter = _new_converter()
    node = _node(NodeTypes.MATCH_EXPRESSION, "match", [], return_type="bool")
    t.require_eq(converter._expr_type(node), "bool")


def test_expr_type_generic_fallback_annotated():
    converter = _new_converter()
    node = _node(NodeTypes.CLASS_FIELD, "x", return_type="float64")
    t.require_eq(converter._expr_type(node), "float64")


def test_expr_type_generic_fallback_default_int32():
    converter = _new_converter()
    node = _node(NodeTypes.CLASS_FIELD, "x")
    t.require_eq(converter._expr_type(node), "int32")


# -- _convert_method: non-constructor method whose body falls off the end
# without a return synthesizes a zero value for its declared return type ---

def test_convert_method_falls_off_end_synthesizes_zero_return():
    body = _node(NodeTypes.SCOPE, "scope", [])
    method = _node(
        NodeTypes.CLASS_METHOD_DEFINITION, "value", [body],
        is_constructor=False, is_static=True, return_type="int32",
    )
    converter = _new_converter()
    converter.class_categories["C"] = "owned"
    converter._convert_method("C", method)
    func = next(f for f in converter.module.functions if f.name == "C.value")
    t.require(func.blocks[-1].terminator is not None)


# -- variable declaration: sized array with no initializer at all (not even
# an empty array literal) zero-initializes ----------------------------------

def test_sized_array_declaration_without_initializer():
    converter = _with_builder(_new_converter())
    decl = _node(
        NodeTypes.VARIABLE_DECLARATION, "arr", [],
        var_type="int32", is_array=True, array_size=4,
    )
    converter._convert_variable_declaration(decl)  # must not raise


# -- for-in over a string driven by a non-identifier collection expression
# (a fresh temporary), with a `char` loop variable (str_char_code_at) ------

def test_for_in_string_non_identifier_collection_char_element():
    converter = _with_builder(_new_converter())
    call_node = _node(NodeTypes.FUNCTION_CALL, "get_string", [], return_type="string")
    loop_var = _node(NodeTypes.VARIABLE_DECLARATION, "c", [], var_type="char")
    body = _node(NodeTypes.SCOPE, "scope", [])
    for_in_node = _node(NodeTypes.FOR_IN_STATEMENT, "for_in", [loop_var, call_node, body])
    converter._convert_for_in_string(for_in_node, "c", "char", call_node, body)


def test_call_arg_modes_borrow_mut_param():
    param = _node(NodeTypes.PARAMETER, "p", var_type="int32", is_borrowed=True, is_mutable_borrow=True)
    body = _node(NodeTypes.SCOPE, "scope", [])
    func_def = _node(NodeTypes.FUNCTION_DEFINITION, "takes_mut_borrow", [param, body])
    converter = _new_converter()
    converter.function_defs["takes_mut_borrow"] = func_def
    lit = _node(NodeTypes.LITERAL, "", token=_tok("INTEGER_LITERAL", "1"))
    node = _node(NodeTypes.FUNCTION_CALL, "takes_mut_borrow", [lit])
    t.require_eq(converter._call_arg_modes("takes_mut_borrow", node), ["borrow_mut"])
