import logging

from lexer import Token, Lexer
from utils.file_utils import get_line_and_coumn_from_index, get_line


class ASTNode:
    tokens: list[Token]
    children: list["ASTNode"]
    parent: "ASTNode"

    def __init__(self, tokens: list[Token], parent: "ASTNode" = None):
        self.tokens = tokens
        self.children = []
        self.parent = parent

        if parent:
            parent.add_child(self)

    # voodoo magic
    def __str__(self, last: bool = False, header: str = ''):
        elbow = "└──"
        pipe = "│  "
        tee = "├──"
        blank = "   "
        tree_str = f"{header}ASTNode\n"

        for i, node in enumerate(self.children):
            if type(node) == Token:
                tree_str += f"{header}{elbow if (i ==
                                                 len(self.children) - 1) else tee}{node}\n"
            else:
                tree_str += node.__str__(header=header + (blank if last else pipe),
                                         last=i == len(self.children) - 1)

        return tree_str

    def add_child(self, node: "ASTNode" or Token) -> "ASTNode" or Token:
        """
        :param node: The node to add as a child
        :return: The node that was added"""

        if node in self.children:
            return node

        node.parent = self
        self.children.append(node)
        return node

    def find_root(self) -> "ASTNode":
        if self.parent:
            return self.parent.find_root()
        else:
            return self


class Parser:
    builtin_functions: list[str] = [
        "print",
        "input",
    ]

    def __init__(self, tokens: list[Token], file: str = None, filename: str = None):
        self.tokens: list[Token] = tokens

        self.ast = ASTNode([Token("ROOT", "ROOT", 0)])

        self.file: str = file
        self.filename: str = filename

    def error(self, text: str, token: Token = None):
        if self.file is None or token is None:
            logging.error(text)
            return

        line_num, column_num = get_line_and_coumn_from_index(
            self.file, token.index)
        line_text = get_line(self.file, line_num)
        logging.error(text + f"\n> {line_text.strip()}\n" + " " * (
            column_num + 2) + "^" + f"\n({self.filename}:{line_num}:{column_num})")

    def parse(self):
        logging.debug("Parsing tokens...")

        index = 0

        self.working_node: ASTNode = self.ast
        current_scope = self.ast
        scope_stack: list[ASTNode] = []  # Stack to keep track of scopes

        while index < len(self.tokens):
            token = self.tokens[index]

            if token.type == "OPEN_BRACE":
                # Create a new scope
                new_scope = ASTNode([], parent=current_scope)
                current_scope = current_scope.add_child(new_scope)
                # Push the new scope to the stack
                scope_stack.append(current_scope)
                index += 1
            elif token.type == "CLOSE_BRACE":
                # Close the current scope
                # Pop the previous scope from the stack
                current_scope = scope_stack.pop().parent
                index += 1
            else:
                # Add token to the current scope
                current_scope.add_child(token)
                index += 1

        return self.ast
