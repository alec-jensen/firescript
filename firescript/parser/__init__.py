from .ast_node import ASTNode
from .base import ParserBase
from .expressions import ExpressionsMixin
from .statements import StatementsMixin
from .type_system import TypeSystemMixin
from .declarations import DeclarationsMixin
from utils.file_utils import get_line_and_coumn_from_index, get_line


class Parser(DeclarationsMixin):
    pass
