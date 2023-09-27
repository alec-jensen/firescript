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

        if parent:
            parent.add_child(self)

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
    
    def add_tokens(self, tokens: list[Token]) -> list[Token]:
        self.tokens += tokens
        return tokens

    def add_child(self, node: "ASTNode") -> "ASTNode":
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

    def __init__(self, tokens: list[Token]):
        self.tokens: list[Token] = tokens

        self.ast = ASTNode([Token("ROOT", "ROOT", 0)])

    def parse(self):
        logging.debug("Parsing tokens...")

        self.index = 0

        self.method_start = None
        self.in_method = False
        self.method_body: ASTNode = None

        self.working_node: ASTNode = self.ast

        while self.index < len(self.tokens):
            logging.debug(f"Token: {self.tokens[self.index]}")
            logging.debug(f"Index: {self.index}")
            logging.debug(f"In method: {self.in_method}")
            logging.debug(f"Method start: {self.method_start}")

            # Variable declaration

            if self.tokens[self.index].type in Lexer.keywords.keys() and self.tokens[self.index].type != 'NULLABLE':
                if self.tokens[self.index + 1].type == 'IDENTIFIER':
                    if self.tokens[self.index + 2].type == 'ASSIGN':
                        if self.tokens[self.index+4].type == 'SEMICOLON':
                            self.ast.add_child(ASTNode(self.tokens[self.index:self.index+5]))
                            self.index += 5
                            continue

            elif self.tokens[self.index].type == 'NULLABLE':
                if self.tokens[self.index + 1].type in Lexer.keywords.keys():
                    if self.tokens[self.index + 2].type == 'IDENTIFIER':
                        if self.tokens[self.index + 3].type == 'ASSIGN':
                            if self.tokens[self.index+5].type == 'SEMICOLON':
                                self.ast.add_child(ASTNode(self.tokens[self.index:self.index+6]))
                                self.index += 6
                                continue

            # Method declaration

            if self.tokens[self.index].type in Lexer.keywords.keys() and self.tokens[self.index].type != 'NULLABLE':
                if self.tokens[self.index + 1].type == 'IDENTIFIER':
                    if self.tokens[self.index + 2].type == 'OPEN_PAREN':
                        if self.in_method:
                            raise Exception("Cannot declare method inside method")
                        
                        self.working_node = ASTNode(tokens=[], parent=self.working_node)
                        self.method_body = ASTNode(tokens=[], parent=self.working_node)

                        for i in range(self.index, len(self.tokens)):
                            if self.tokens[i].type == 'CLOSE_PAREN':
                                if self.tokens[i+1].type == 'OPEN_BRACE':
                                    self.working_node.add_tokens(self.tokens[self.index:i+1])
                                    
                                    self.in_method = True
                                    self.method_start = i + 2

                                    self.index = i + 2
                                    break
                        
                        continue

            # Nullable method declaration

            if self.tokens[self.index].type == 'NULLABLE':
                if self.tokens[self.index + 1].type in Lexer.keywords.keys():
                    if self.tokens[self.index + 2].type == 'IDENTIFIER':
                        if self.tokens[self.index + 3].type == 'OPEN_PAREN':
                            if self.in_method:
                                raise Exception("Cannot declare method inside method")
                            
                            self.working_node = ASTNode(tokens=[], parent=self.working_node)
                            self.method_body = ASTNode(tokens=[], parent=self.working_node)

                            for i in range(self.index, len(self.tokens)):
                                if self.tokens[i].type == 'CLOSE_PAREN':
                                    if self.tokens[i+1].type == 'OPEN_BRACE':
                                        self.working_node.add_tokens(self.tokens[self.index:i+1])

                                        self.in_method = True
                                        self.method_start = i + 2

                                        self.index = i + 2
                                        break

                            continue

            # If statement

            if self.tokens[self.index].type == 'IF':
                if self.tokens[self.index + 1].type == 'OPEN_PAREN':
                    self.working_node = ASTNode(tokens=[], parent=self.working_node)
                    if_body = ASTNode(tokens=[], parent=self.working_node)

                    for i in range(self.index, len(self.tokens)):
                        if self.tokens[i].type == 'CLOSE_PAREN':
                            if self.tokens[i+1].type == 'OPEN_BRACE':
                                self.working_node.add_tokens(self.tokens[self.index:i+1])
                                
                                # Parse if body

                                for j in range(i+1, len(self.tokens)):
                                    if self.tokens[j].type == 'CLOSE_BRACE':
                                        if_body.add_tokens(self.tokens[i+2:j])
                                        self.index = j + 1
                                        break

                                break

                    continue
                                    
            # Method body
            if self.in_method:
                if self.tokens[self.index].type == 'CLOSE_BRACE':
                    if self.method_body is None:
                        raise Exception("Method body is None")
                    
                    self.method_body.add_tokens(self.tokens[self.method_start:self.index])
                    self.index += 1
                    self.in_method = False
                    self.method_body = None
                    self.working_node = self.working_node.parent
                    continue

            self.index += 1

        return self.ast
