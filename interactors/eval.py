r"""
Eval interactor - evaluate boolean condition expressions.

\eval ?(condition) ---
→ "true" or "false"

Evaluates ?() condition blocks containing:
- $(\command---) scheduler queries (executed via Mind)
- Boolean operators: or, and, not
- Comparison operators: <, >, =
- Literals: true, false, numbers
- Grouping with parentheses

Examples:
    \eval ?(true) ---                           → "true"
    \eval ?($(\up---)) ---                      → "true" (if \up returns "true")
    \eval ?($(\incoming---) or $(\up---)) ---   → "true" if either is true
    \eval ?(not $(\busy---)) ---                → "true" if \busy returns "false"
    \eval ?($(\N---) > 10) ---                  → "true" if entity count > 10

Used by \wake to evaluate wake conditions, but available to any
interactor or entity that needs boolean condition evaluation.
"""

from grammar.parser import (
    Command, Condition, ConditionExpr,
    BoolOr, BoolAnd, BoolNot, Compare,
    SchedulerQuery, Text, Entity, Space
)
from interactors.base import Interactor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mind import Mind


class EvalInteractor(Interactor):
    r"""
    Evaluate boolean condition expressions.

    Takes a ?() condition block and returns "true" or "false".
    """

    def __init__(self, body=None, mind=None):
        """
        Create eval interactor.

        Args:
            body: Body instance
            mind: Mind instance for executing $() queries
        """
        self.body = body
        self.mind = mind

    def execute(self, cmd: Command, executor: str = None) -> str:
        """
        Synchronous entry point - returns error directing to async.

        Use execute_async for actual evaluation.
        """
        return "ERROR: eval requires async execution. Use execute_async."

    async def execute_async(self, cmd: Command, executor: str = None) -> str:
        """
        Evaluate condition and return "true" or "false".

        Args:
            cmd: Parsed command containing ?() condition
            executor: Entity context for query execution

        Returns:
            "true" if condition is satisfied, "false" otherwise
        """
        # Find the condition block
        condition = None
        for node in cmd.content:
            if isinstance(node, Condition):
                condition = node
                break

        if not condition:
            return "ERROR: No condition found. Usage: \\eval ?(condition) ---"

        if not self.mind:
            return "ERROR: eval requires mind for query execution"

        try:
            result = await self._evaluate(condition.expression, executor)
            return "true" if result else "false"
        except Exception as e:
            return f"ERROR: Evaluation failed: {e}"

    async def _evaluate(self, expr: ConditionExpr, executor: str) -> bool:
        """
        Recursively evaluate a condition expression.

        Args:
            expr: The condition expression tree
            executor: Entity context for execution

        Returns:
            True if condition is satisfied, False otherwise
        """
        if isinstance(expr, BoolOr):
            # Short-circuit OR: if left is true, skip right
            if await self._evaluate(expr.left, executor):
                return True
            return await self._evaluate(expr.right, executor)

        elif isinstance(expr, BoolAnd):
            # Short-circuit AND: if left is false, skip right
            if not await self._evaluate(expr.left, executor):
                return False
            return await self._evaluate(expr.right, executor)

        elif isinstance(expr, BoolNot):
            return not await self._evaluate(expr.operand, executor)

        elif isinstance(expr, Compare):
            return await self._evaluate_compare(expr, executor)

        elif isinstance(expr, SchedulerQuery):
            return await self._evaluate_query(expr, executor)

        elif isinstance(expr, Text):
            # Literal text: "true" is true, anything else is false
            return expr.text.strip().lower() == "true"

        elif isinstance(expr, (Entity, Space)):
            # Entity/Space references are not boolean values
            return False

        else:
            # Unknown node type
            return False

    async def _evaluate_compare(self, expr: Compare, executor: str) -> bool:
        """
        Evaluate a comparison expression.

        Args:
            expr: Compare node with left, op, right
            executor: Entity context

        Returns:
            True if comparison is satisfied, False otherwise
        """
        left_val = await self._get_value(expr.left, executor)
        right_val = await self._get_value(expr.right, executor)

        # Try numeric comparison first
        try:
            left_num = float(left_val)
            right_num = float(right_val)

            if expr.op == '<':
                return left_num < right_num
            elif expr.op == '>':
                return left_num > right_num
            elif expr.op == '=':
                return left_num == right_num
        except (ValueError, TypeError):
            pass

        # Fall back to string comparison
        if expr.op == '=':
            return str(left_val) == str(right_val)
        elif expr.op == '<':
            return str(left_val) < str(right_val)
        elif expr.op == '>':
            return str(left_val) > str(right_val)

        return False

    async def _get_value(self, expr: ConditionExpr, executor: str) -> str:
        """
        Get the value of an expression for comparison.

        For queries, executes and returns result.
        For literals, returns the text.
        """
        if isinstance(expr, SchedulerQuery):
            command_str = self._query_to_string(expr)
            try:
                return await self.mind.execute(command_str, executor=executor)
            except Exception:
                return ""

        elif isinstance(expr, Text):
            return expr.text.strip()

        elif isinstance(expr, Entity):
            return f"@{expr.name}"

        elif isinstance(expr, Space):
            return f"#{expr.name}"

        else:
            return ""

    async def _evaluate_query(self, query: SchedulerQuery, executor: str) -> bool:
        """
        Execute a scheduler query and check if result is "true".

        Args:
            query: The scheduler query node
            executor: Entity context

        Returns:
            True if query returns "true", False otherwise
        """
        command_str = self._query_to_string(query)

        try:
            result = await self.mind.execute(command_str, executor=executor)
            return result.strip().lower() == "true"
        except Exception:
            return False

    def _query_to_string(self, query: SchedulerQuery) -> str:
        """Convert SchedulerQuery back to command string."""
        parts = []
        for node in query.command:
            if isinstance(node, Text):
                parts.append(node.text)
            elif isinstance(node, Entity):
                parts.append(f"@{node.name}")
            elif isinstance(node, Space):
                parts.append(f"#{node.name}")
            else:
                parts.append(str(node))
        return "\\" + "".join(parts).strip() + " ---"


# Convenience function for other interactors to use
async def evaluate_condition(
    condition: Condition,
    mind: 'Mind',
    executor: str
) -> bool:
    """
    Evaluate a parsed Condition.

    Convenience function for interactors like wake that need
    to evaluate conditions without going through execute_async.

    Args:
        condition: Parsed Condition node
        mind: Mind instance for query execution
        executor: Entity context

    Returns:
        True if condition is satisfied, False otherwise
    """
    evaluator = EvalInteractor(mind=mind)
    return await evaluator._evaluate(condition.expression, executor)
