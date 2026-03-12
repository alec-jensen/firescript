from .base import CCodeGeneratorBase
from .generics import GenericsMixin
from .classes import ClassesMixin
from .declarations import DeclarationsMixin
from .statements import StatementsMixin
from .generator import GeneratorMixin


class CCodeGenerator(GeneratorMixin):
    pass
