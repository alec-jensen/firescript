import logging
from typing import Optional

from enums import NodeTypes


class ASTNode:
    # Optional semantic metadata for semantic passes
    value_category: Optional[str]
    def __init__(
        self,
        node_type: NodeTypes,
        token,
        name: str,
        children: list["ASTNode"],
        index: int,
        var_type: Optional[str] = None,
        is_nullable: bool = False,
        is_const: bool = False,
        return_type: Optional[str] = None,
        is_array: bool = False,
        is_ref_counted: bool = False,
    ):
        self.node_type: NodeTypes = node_type
        self.token = token
        self.name: str = name

        # Strict check: ensure no None children are passed by callers.
        if any(child is None for child in children):
            logging.error(
                f"ASTNode constructor received None in children. Node: {node_type} {name}, Children: {children}"
            )
            raise ValueError(
                "ASTNode constructor received None in children list. This indicates a bug in a parser rule."
            )

        self.children: list[ASTNode] = children

        self.index: int = index
        self.var_type: Optional[str] = var_type
        self.is_nullable: bool = is_nullable
        self.is_const: bool = is_const
        self.return_type: Optional[str] = return_type
        self.is_array: bool = is_array
        self.is_ref_counted: bool = is_ref_counted
        self.parent: Optional[ASTNode] = None  # Parent is typically set externally
        # Optional semantic metadata; populated by analysis passes
        self.value_category = None
        # Generic function metadata
        self.type_params: list[str] = []  # Type parameter names for generic functions
        self.type_constraints: dict[str, str] = {}  # Type param -> constraint
        self.type_args: list[str] = []  # Concrete type arguments for generic calls
        # source_file is intentionally NOT initialized here; it is set dynamically
        # by annotate_source_file (imports.py) so that getattr(node, 'source_file', fallback)
        # correctly returns the fallback for nodes whose file hasn't been annotated yet.

    def tree(self, prefix: str = "", is_last: bool = True) -> str:
        # Build the display line differently for variable declarations.
        if self.node_type == NodeTypes.VARIABLE_DECLARATION:
            pre = []
            if self.is_nullable:
                pre.append("nullable")
            if self.is_const:
                pre.append("const")
            if self.var_type:
                pre.append(self.var_type)

            post = []
            # TODO: add post modifiers

            line_content = f"{self.node_type}"
            if pre:
                line_content += f" {' '.join(pre)} {self.name}"
            if post:
                line_content += f" {' '.join(post)}"
        else:
            line_content = f"{self.node_type} {self.name}"

        lines = []
        if prefix == "":
            lines.append(line_content)
        else:
            connector = "└── " if is_last else "├── "
            lines.append(prefix + connector + line_content)
        new_prefix = prefix + ("    " if is_last else "│   ")
        childs = [child for child in self.children if child is not None]
        for i, child in enumerate(childs):
            is_last_child = i == (len(childs) - 1)
            lines.append(child.tree(new_prefix, is_last_child))
        return "\n".join(lines)

    def __str__(self, level: int = 0) -> str:
        return self.tree()

    def __repr__(self):
        return self.__str__()
