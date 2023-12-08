import logging

from lexer import Token, Lexer
from utils.file_utils import get_line_and_coumn_from_index, get_line


class ASTNode:
    tokens: list[Token]
    children: list["ASTNode" or Token]
    parent: "ASTNode"

    def __init__(self, parent: "ASTNode" = None):
        self.children = []
        self.parent = parent

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
        
    def self_destruct(self):
        self.parent.children.remove(self)
        self.parent = None
        self.children = None


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

        self.error_count = 0

    def error(self, text: str, token: Token = None):
        if self.file is None or token is None:
            logging.error(text)
            return

        line_num, column_num = get_line_and_coumn_from_index(
            self.file, token.index)
        line_text = get_line(self.file, line_num)
        logging.error(text + f"\n> {line_text.strip()}\n" + " " * (
            column_num + 2) + "^" + f"\n({self.filename}:{line_num}:{column_num})")
        self.error_count += 1

    def parse(self):
        logging.debug("Parsing tokens...")

        index = 0

        # Make sure all braces, brackets and parentheses are closed

        open_braces = []
        open_brackets = []
        open_parentheses = []

        for token in self.tokens:
            if token.type == "OPEN_BRACE":
                open_braces.append(token)
            elif token.type == "CLOSE_BRACE":
                if len(open_braces) == 0:
                    self.error("Unexpected closing brace", token)
                else:
                    open_braces.pop()
            elif token.type == "OPEN_BRACKET":
                open_brackets.append(token)
            elif token.type == "CLOSE_BRACKET":
                if len(open_brackets) == 0:
                    self.error("Unexpected closing bracket", token)
                else:
                    open_brackets.pop()
            elif token.type == "OPEN_PAREN":
                open_parentheses.append(token)
            elif token.type == "CLOSE_PAREN":
                if len(open_parentheses) == 0:
                    self.error("Unexpected closing parenthesis", token)
                else:
                    open_parentheses.pop()

        if len(open_braces) > 0:
            self.error("Unclosed braces", open_braces[0])
        if len(open_brackets) > 0:
            self.error("Unclosed brackets", open_brackets[0])
        if len(open_parentheses) > 0:
            self.error("Unclosed parentheses", open_parentheses[0])

        self.working_node: ASTNode = self.ast
        current_scope = self.ast
        scope_stack: list[ASTNode] = []  # Stack to keep track of scopes

        while index < len(self.tokens):
            token = self.tokens[index]

            if token.type == "OPEN_BRACE":
                # Create a new scope
                new_scope = ASTNode(parent=current_scope)
                new_scope.add_child(token)
                current_scope = current_scope.add_child(new_scope)
                # Push the new scope to the stack
                scope_stack.append(current_scope)
                index += 1
            elif token.type == "CLOSE_BRACE":
                # Close the current scope
                # Pop the previous scope from the stack
                scope_stack[-1].children.pop(0)
                current_scope = scope_stack.pop().parent
                index += 1
            else:
                # Add token to the current scope
                current_scope.add_child(token)
                index += 1

        # Remove empty scopes
        def remove_empty_scopes(scope: ASTNode):
            for child in list(scope.children):  # Create a copy of children list for iteration
                if isinstance(child, ASTNode):
                    remove_empty_scopes(child)
                    if len(child.children) == 0:
                        child.self_destruct()

        remove_empty_scopes(self.ast)

        if self.error_count > 0:
            logging.error(f"Found {self.error_count} errors while parsing {self.filename}")
            return None

        return self.ast
