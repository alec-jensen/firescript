"""Direct-parser unit test for a real (reachable) type_system.py branch
that is impractical to drive through a full multi-file `.fire` compile: the
deferred-import-resolution machinery only activates mid-way through
cross-module import merging. This uses the actual
`defer_undefined_identifiers` mechanism and `_type_check_node` public
surface -- not a dead/defensive guard -- just invoked directly instead of
via the full import pipeline.
"""
from __future__ import annotations

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from harness import pyunit as t
from enums import NodeTypes
from parser.ast_node import ASTNode

from _helpers import make_parser, blank_token


def test_method_call_deferred_lookup_for_composite_generic_type():
    # When defer_undefined_identifiers is active (set for any file that
    # imports other modules -- see ParserBase.__init__), a method call on a
    # composite generic type like "Option<int32>" that isn't registered in
    # self.user_methods yet (because the class backing it lives in a module
    # not yet merged) is deliberately *not* flagged as an error -- the real
    # check happens after import merge. This is type_system.py's
    # `pass  # Will be resolved after import merge` branch.
    #
    # _get_node_type()'s LITERAL fallback only honors an explicit
    # `return_type` when the node also has a real token, so `obj` needs one
    # even though its value is unused here.
    p = make_parser("1;", defer_undefined_identifiers=True)
    obj = ASTNode(
        NodeTypes.LITERAL,
        blank_token("IDENTIFIER", "opt"),
        "opt",
        [],
        0,
        return_type="Option<int32>",
    )
    call = ASTNode(NodeTypes.METHOD_CALL, None, "unwrap", [obj], 0)
    result = p._type_check_node(call, {})
    t.require(result is None)
    t.require(len(p.errors) == 0, [str(e) for e in p.errors])
