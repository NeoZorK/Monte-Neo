"""AST utilities for genetic programming.

Handles parsing, manipulation, and unparsing of indicator code strings.
"""

from __future__ import annotations

import ast
import random
from typing import Any

from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


class ExpressionCollector(ast.NodeVisitor):
    """Collects all expression nodes from an AST."""

    def __init__(self) -> None:
        self.nodes: list[ast.AST] = []

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        self.nodes.append(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        self.nodes.append(node)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        # data['close'].rolling(...) -> 'rolling' attribute is part of Call usually
        # but let's collect it too if it's top level
        self.nodes.append(node)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        # data['close']
        self.nodes.append(node)
        self.generic_visit(node)


class CrossoverTransformer(ast.NodeTransformer):
    """Replaces a specific node in the AST with another."""

    def __init__(self, target_node: ast.AST, replacement_node: ast.AST) -> None:
        self.target_node = target_node
        self.replacement_node = replacement_node

    def visit(self, node: ast.AST) -> ast.AST:
        if node is self.target_node:
            return self.replacement_node
        return super().visit(node)


def crossover_trees(code1: str, code2: str) -> str:
    """Perform crossover between two code strings using AST subtree swapping.

    Returns:
        New code string derived from code1 with a subtree from code2.
    """
    try:
        tree1 = ast.parse(code1)
        tree2 = ast.parse(code2)

        collector1 = ExpressionCollector()
        collector1.visit(tree1)

        collector2 = ExpressionCollector()
        collector2.visit(tree2)

        if not collector1.nodes or not collector2.nodes:
            logger.warning(
                "Crossover failed: No valid nodes found in one or both trees."
            )
            return code1

        # Pick random crossover points
        target_node = random.choice(collector1.nodes)
        replacement_node = random.choice(collector2.nodes)

        # Transform tree1 by replacing target_node with replacement_node
        transformer = CrossoverTransformer(target_node, replacement_node)
        new_tree = transformer.visit(tree1)

        # Fix missing line numbers etc.
        ast.fix_missing_locations(new_tree)

        # Generate code back
        return ast.unparse(new_tree).strip()

    except Exception as e:
        logger.error(f"Error during AST crossover: {e}")
        return code1
