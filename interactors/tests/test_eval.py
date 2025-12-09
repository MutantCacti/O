r"""Tests for \eval interactor."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from grammar.parser import parse, Condition
from interactors.eval import EvalInteractor, evaluate_condition


@pytest.fixture
def mock_mind():
    """Mock Mind that returns configurable results."""
    mind = MagicMock()
    mind.execute = AsyncMock(return_value="true")
    return mind


@pytest.fixture
def eval_interactor(mock_mind):
    """Eval interactor with mock mind."""
    return EvalInteractor(mind=mock_mind)


class TestEvalBasics:
    """Test basic eval functionality."""

    def test_eval_sync_returns_error(self, eval_interactor):
        """Sync execute returns error directing to async."""
        cmd = parse(r"\eval ?(true) ---")
        result = eval_interactor.execute(cmd, executor="@alice")
        assert "ERROR" in result
        assert "async" in result.lower()

    @pytest.mark.asyncio
    async def test_eval_requires_condition(self, eval_interactor):
        """Eval needs a ?() condition block."""
        cmd = parse(r"\eval no condition here ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert "ERROR" in result
        assert "No condition" in result

    @pytest.mark.asyncio
    async def test_eval_requires_mind(self):
        """Eval needs mind for query execution."""
        evaluator = EvalInteractor(mind=None)
        cmd = parse(r"\eval ?($(\up---)) ---")
        result = await evaluator.execute_async(cmd, executor="@alice")
        assert "ERROR" in result
        assert "mind" in result.lower()


class TestLiteralEvaluation:
    """Test evaluation of literal values."""

    @pytest.mark.asyncio
    async def test_true_literal(self, eval_interactor):
        """?(true) returns 'true'."""
        cmd = parse(r"\eval ?(true) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "true"

    @pytest.mark.asyncio
    async def test_false_literal(self, eval_interactor):
        """?(false) returns 'false'."""
        cmd = parse(r"\eval ?(false) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "false"

    @pytest.mark.asyncio
    async def test_TRUE_case_insensitive(self, eval_interactor):
        """?(TRUE) returns 'true' (case insensitive)."""
        cmd = parse(r"\eval ?(TRUE) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "true"

    @pytest.mark.asyncio
    async def test_other_text_is_false(self, eval_interactor):
        """?(hello) returns 'false'."""
        cmd = parse(r"\eval ?(hello) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "false"

    @pytest.mark.asyncio
    async def test_entity_is_false(self, eval_interactor):
        """?(@alice) returns 'false'."""
        cmd = parse(r"\eval ?(@alice) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "false"

    @pytest.mark.asyncio
    async def test_space_is_false(self, eval_interactor):
        """?(#general) returns 'false'."""
        cmd = parse(r"\eval ?(#general) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "false"


class TestSchedulerQueryEvaluation:
    """Test evaluation of scheduler queries."""

    @pytest.mark.asyncio
    async def test_query_returns_true(self, eval_interactor, mock_mind):
        """Query returning 'true' evaluates to 'true'."""
        mock_mind.execute = AsyncMock(return_value="true")
        cmd = parse(r"\eval ?($(\up---)) ---")

        result = await eval_interactor.execute_async(cmd, executor="@alice")

        assert result == "true"
        mock_mind.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_returns_false(self, eval_interactor, mock_mind):
        """Query returning 'false' evaluates to 'false'."""
        mock_mind.execute = AsyncMock(return_value="false")
        cmd = parse(r"\eval ?($(\busy---)) ---")

        result = await eval_interactor.execute_async(cmd, executor="@alice")

        assert result == "false"

    @pytest.mark.asyncio
    async def test_query_exception_is_false(self, eval_interactor, mock_mind):
        """Query that throws evaluates to 'false'."""
        mock_mind.execute = AsyncMock(side_effect=Exception("error"))
        cmd = parse(r"\eval ?($(\broken---)) ---")

        result = await eval_interactor.execute_async(cmd, executor="@alice")

        assert result == "false"


class TestBooleanOperators:
    """Test boolean operator evaluation."""

    @pytest.mark.asyncio
    async def test_or_true_false(self, eval_interactor):
        """true or false = true"""
        cmd = parse(r"\eval ?(true or false) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "true"

    @pytest.mark.asyncio
    async def test_or_false_false(self, eval_interactor):
        """false or false = false"""
        cmd = parse(r"\eval ?(false or false) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "false"

    @pytest.mark.asyncio
    async def test_and_true_true(self, eval_interactor):
        """true and true = true"""
        cmd = parse(r"\eval ?(true and true) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "true"

    @pytest.mark.asyncio
    async def test_and_true_false(self, eval_interactor):
        """true and false = false"""
        cmd = parse(r"\eval ?(true and false) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "false"

    @pytest.mark.asyncio
    async def test_not_true(self, eval_interactor):
        """not true = false"""
        cmd = parse(r"\eval ?(not true) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "false"

    @pytest.mark.asyncio
    async def test_not_false(self, eval_interactor):
        """not false = true"""
        cmd = parse(r"\eval ?(not false) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "true"


class TestPrecedence:
    """Test operator precedence."""

    @pytest.mark.asyncio
    async def test_and_before_or(self, eval_interactor):
        """a or b and c = a or (b and c)"""
        # true or false and false = true or (false and false) = true or false = true
        cmd = parse(r"\eval ?(true or false and false) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "true"

    @pytest.mark.asyncio
    async def test_parens_override_precedence(self, eval_interactor):
        """(a or b) and c groups correctly"""
        # (true or false) and false = true and false = false
        cmd = parse(r"\eval ?((true or false) and false) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "false"


class TestShortCircuit:
    """Test short-circuit evaluation."""

    @pytest.mark.asyncio
    async def test_or_short_circuits(self, eval_interactor, mock_mind):
        """OR short-circuits when left is true."""
        mock_mind.execute = AsyncMock(return_value="true")
        # true or $(\query---) should not call the query
        cmd = parse(r"\eval ?(true or $(\should-not-call---)) ---")

        result = await eval_interactor.execute_async(cmd, executor="@alice")

        assert result == "true"
        mock_mind.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_and_short_circuits(self, eval_interactor, mock_mind):
        """AND short-circuits when left is false."""
        mock_mind.execute = AsyncMock(return_value="true")
        # false and $(\query---) should not call the query
        cmd = parse(r"\eval ?(false and $(\should-not-call---)) ---")

        result = await eval_interactor.execute_async(cmd, executor="@alice")

        assert result == "false"
        mock_mind.execute.assert_not_called()


class TestComplexExpressions:
    """Test complex nested expressions."""

    @pytest.mark.asyncio
    async def test_mixed_queries_and_literals(self, eval_interactor, mock_mind):
        r"""$(\query---) and true"""
        mock_mind.execute = AsyncMock(return_value="true")
        cmd = parse(r"\eval ?($(\incoming---) and true) ---")

        result = await eval_interactor.execute_async(cmd, executor="@alice")

        assert result == "true"

    @pytest.mark.asyncio
    async def test_multiple_queries(self, eval_interactor, mock_mind):
        """$(\a---) or $(\b---)"""
        mock_mind.execute = AsyncMock(side_effect=["false", "true"])
        cmd = parse(r"\eval ?($(\a---) or $(\b---)) ---")

        result = await eval_interactor.execute_async(cmd, executor="@alice")

        assert result == "true"
        assert mock_mind.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_deeply_nested(self, eval_interactor):
        """((a or b) and (c or d))"""
        cmd = parse(r"\eval ?(((true or false) and (false or true))) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "true"


class TestComparison:
    """Test comparison operators."""

    @pytest.mark.asyncio
    async def test_greater_than_true(self, eval_interactor):
        """10 > 5 = true"""
        cmd = parse(r"\eval ?(10 > 5) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "true"

    @pytest.mark.asyncio
    async def test_greater_than_false(self, eval_interactor):
        """5 > 10 = false"""
        cmd = parse(r"\eval ?(5 > 10) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "false"

    @pytest.mark.asyncio
    async def test_less_than_true(self, eval_interactor):
        """5 < 10 = true"""
        cmd = parse(r"\eval ?(5 < 10) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "true"

    @pytest.mark.asyncio
    async def test_less_than_false(self, eval_interactor):
        """10 < 5 = false"""
        cmd = parse(r"\eval ?(10 < 5) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "false"

    @pytest.mark.asyncio
    async def test_equals_true(self, eval_interactor):
        """10 = 10 = true"""
        cmd = parse(r"\eval ?(10 = 10) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "true"

    @pytest.mark.asyncio
    async def test_equals_false(self, eval_interactor):
        """10 = 5 = false"""
        cmd = parse(r"\eval ?(10 = 5) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "false"

    @pytest.mark.asyncio
    async def test_query_comparison(self, eval_interactor, mock_mind):
        r"""$(\count---) > 5 with query returning 10"""
        mock_mind.execute = AsyncMock(return_value="10")
        cmd = parse(r"\eval ?($(\count---) > 5) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "true"

    @pytest.mark.asyncio
    async def test_query_comparison_false(self, eval_interactor, mock_mind):
        r"""$(\count---) > 5 with query returning 3"""
        mock_mind.execute = AsyncMock(return_value="3")
        cmd = parse(r"\eval ?($(\count---) > 5) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "false"

    @pytest.mark.asyncio
    async def test_string_equals(self, eval_interactor):
        """hello = hello = true"""
        cmd = parse(r"\eval ?(hello = hello) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "true"

    @pytest.mark.asyncio
    async def test_comparison_with_boolean(self, eval_interactor):
        """Comparison combined with boolean: (a > b) and true"""
        cmd = parse(r"\eval ?((10 > 5) and true) ---")
        result = await eval_interactor.execute_async(cmd, executor="@alice")
        assert result == "true"


class TestConvenienceFunction:
    """Test the evaluate_condition convenience function."""

    @pytest.mark.asyncio
    async def test_evaluate_condition_true(self, mock_mind):
        """evaluate_condition returns True for true condition."""
        parsed = parse(r"\wake ?(true) ---")
        condition = [n for n in parsed.content if isinstance(n, Condition)][0]

        result = await evaluate_condition(condition, mock_mind, "@alice")

        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_condition_with_query(self, mock_mind):
        """evaluate_condition works with queries."""
        mock_mind.execute = AsyncMock(return_value="true")
        parsed = parse(r"\wake ?($(\up---)) ---")
        condition = [n for n in parsed.content if isinstance(n, Condition)][0]

        result = await evaluate_condition(condition, mock_mind, "@alice")

        assert result is True
