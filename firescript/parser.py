import logging

from lexer import Token, Lexer


class ASTNode:
    tokens: list[Token]
    children: list["ASTNode"]
    parent: "ASTNode"

    def __init__(self, tokens: list[Token], parent: "ASTNode" = None):
        self.tokens = tokens
        self.children = []
        self.parent = parent

    # voodoo magic
    def __str__(self, last: bool = False, header: str = ''):
        elbow = "└──"
        pipe = "│  "
        tee = "├──"
        blank = "   "
        tree_str = f"{header}ASTNode\n"

        for j, token in enumerate(self.tokens):
            tree_str += f"{header}{elbow if (j == len(self.tokens) - 1) else tee}{token}\n"

        for i, node in enumerate(self.children):
            tree_str += node.__str__(header=header + (blank if last else pipe),
                                     last=i == len(self.children) - 1)

        return tree_str

    def add_token(self, token: Token) -> Token:
        self.tokens.append(ASTNode(token))
        return token

    def add_child(self, node: "ASTNode") -> "ASTNode":
        node.parent = self
        self.children.append(node)
        return node


class Parser:
    builtin_functions: list[str] = [
        "print",
        "input",
    ]

    def __init__(self, tokens: list[Token]):
        self.tokens: list[Token] = tokens

        self.ast = ASTNode([Token("ROOT", "ROOT", 0)])

    def parse(self):
        logging.debug("Parsing tokens...")

        index = 0

        while index < len(self.tokens):
            # Variable declaration

            logging.debug(f"Current token: {self.tokens[index]} ({index})")

            if self.tokens[index].type in Lexer.keywords.keys() and self.tokens[index].type != 'NULLABLE':
                logging.debug(f"Found keyword: {self.tokens[index]}")
                if self.tokens[index + 1].type == 'IDENTIFIER':
                    logging.debug(f"Found identifier: {self.tokens[index + 1]}")
                    if self.tokens[index + 2].type == 'ASSIGN':
                        logging.debug(f"Found assignment: {self.tokens[index + 2]}")
                        if self.tokens[index+4].type == 'SEMICOLON':
                            logging.debug(f"Found semicolon: {self.tokens[index + 4]}")
                            self.ast.add_child(ASTNode(self.tokens[index:index+5]))
                            index += 5
                            continue

            elif self.tokens[index].type == 'NULLABLE':
                logging.debug(f"Found nullable: {self.tokens[index]}")
                if self.tokens[index + 1].type in Lexer.keywords.keys():
                    logging.debug(f"Found keyword: {self.tokens[index + 1]}")
                    if self.tokens[index + 2].type == 'IDENTIFIER':
                        logging.debug(f"Found identifier: {self.tokens[index + 2]}")
                        if self.tokens[index + 3].type == 'ASSIGN':
                            logging.debug(f"Found assignment: {self.tokens[index + 3]}")
                            if self.tokens[index+5].type == 'SEMICOLON':
                                logging.debug(f"Found semicolon: {self.tokens[index + 5]}")
                                self.ast.add_child(ASTNode(self.tokens[index:index+6]))
                                index += 6
                                continue

            index += 1

        return self.ast
