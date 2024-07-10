import logging

from lexer import Token, Lexer
from utils.file_utils import get_line_and_coumn_from_index, get_line

from typing import Union


class ASTNode:
    children: list[Union["ASTNode", Token]]
    parent: "ASTNode"

    def __init__(self, parent: "ASTNode" = None):
        self.children = []
        self.parent = parent

    # voodoo magic to get tree visualization
    def __str__(self, last: bool = False, header: str = ''):
        elbow = "└──"
        pipe = "│  "
        tee = "├──"
        blank = "   "
        tree_str = f"{header}" + type(self).__name__ + "\n"

        for i, node in enumerate(self.children):
            if type(node) == Token:
                tree_str += f"{header}{elbow if (i ==
                                                 len(self.children) - 1) else tee}{node}\n"
            else:
                tree_str += node.__str__(header=header + pipe,
                                         last=i == len(self.children) - 1)

        return tree_str

    def add_child(self, node: Union["ASTNode", Token]) -> Union["ASTNode", Token]:
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

class MethodNode(ASTNode):
    def __init__(self, parent: ASTNode, name: str, args: list[tuple[str, str, str]], return_type: str, nullable: bool = False, children: list[Union["ASTNode", Token]] = []):
        super().__init__(parent)
        self.name = name
        self.args = args
        self.return_type = return_type
        self.nullable = nullable
        self.children = children

    def __str__(self, last: bool = False, header: str = ''):
        elbow = "└──"
        pipe = "│  "
        tee = "├──"
        blank = "   "
        tree_str = f"{header}" + type(self).__name__ + "\n"
        tree_str += f"{header}{pipe}name: {self.name}\n"
        tree_str += f"{header}{pipe}nullable: {self.nullable}\n"
        tree_str += f"{header}{pipe}return_type: {self.return_type}\n"
        tree_str += f"{header}{pipe}args: {self.args}\n"

        for i, node in enumerate(self.children):
            next = tee

            if type(node) == Token:
                if i == len(self.children) - 1:
                    for i in range(0, len(header), 3):
                        header = header[0:i] + elbow + header[i+3:]

                    next = elbow

                tree_str += f"{header}{next}{node}\n"
            else:
                tree_str += node.__str__(header=header + pipe,
                                         last=i == len(self.children) - 1)

        return tree_str


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

        # Make sure all braces, brackets, parentheses and comments are closed

        open_braces: list[Token] = []
        open_brackets: list[Token] = []
        open_parentheses: list[Token] = []
        open_comments: list[Token] = []

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
            elif token.type == "MULTI_LINE_COMMENT_START":
                open_comments.append(token)
            elif token.type == "MULTI_LINE_COMMENT_END":
                if len(open_comments) == 0:
                    self.error("Unexpected multiline comment terminator", token)
                else:
                    open_comments.pop()

        if len(open_braces) > 0:
            self.error("Unclosed brace", open_braces[0])
        if len(open_brackets) > 0:
            self.error("Unclosed bracket", open_brackets[0])
        if len(open_parentheses) > 0:
            self.error("Unclosed parenthesis", open_parentheses[0])
        if len(open_comments) > 0:
            self.error("Unclosed multiline comment", open_comments[0])

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

        # Parse method declarations

        def parse_method_declaration(scope: ASTNode):
            method_start = -1

            for i, child in enumerate(scope.children):
                if isinstance(child, ASTNode):
                    parse_method_declaration(child)
                elif isinstance(child, Token):
                    if len(scope.children) > 3:
                        if scope.children[i].type in list(Lexer.types.keys()):
                            if scope.children[i+1].type == "IDENTIFIER":
                                if scope.children[i+2].type == "OPEN_PAREN":
                                    if i > 0 and type(scope.children[i-1]) == ASTNode:
                                        if scope.children[i-1].type == "NULLABLE":
                                            method_start = i-1
                                        else:
                                            method_start = i
                                    else:
                                        method_start = i

                                    logging.debug(f"Found method start at index {method_start}")

                    # Parse method end
                    if scope.children[i].type == "CLOSE_PAREN":
                        if method_start != -1:
                            method_end = i
                            
                            nullable = False
                            return_type = ""
                            method_name = ""
                            
                            if scope.children[method_start].type == "NULLABLE":
                                nullable = True
                                method_start += 1

                            return_type = scope.children[method_start].type

                            method_name = scope.children[method_start+1].value

                            # Parse arguments

                            # type, name
                            args: list[tuple[str, str]] = []

                            arg_start = method_start + 3

                            while arg_start < method_end:
                                arg_nullable = False
                                if scope.children[arg_start].type == "NULLABLE":
                                    arg_nullable = True
                                    arg_start += 1

                                arg_type = scope.children[arg_start].type
                                arg_name = scope.children[arg_start+1].value

                                args.append((arg_nullable, arg_type, arg_name))

                                arg_start += 3

                            logging.debug(nullable)
                            method_signature = f"{"NULLABLE" if nullable else ""} {return_type} {method_name}"
                            method_signature += f"({', '.join([f'{"NULLABLE" if arg_nullable else ""} {arg_type} {arg_name}' for arg_nullable, arg_type, arg_name in args])})"

                            logging.debug(f"Found method declaration: {method_signature}")

                            method_node = MethodNode(scope, method_name, args, return_type, nullable, scope.children[method_end + 1].children)

                            scope.children[method_end + 1] = method_node

                            method_start = -1

        parse_method_declaration(self.ast)

        if self.error_count > 0:
            logging.error(f"Found {self.error_count} errors while parsing {self.filename}")
            return None

        return self.ast
