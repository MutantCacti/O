r"""Tests for \up interactor."""

from grammar.parser import parse
from interactors.up import UpInteractor


def test_up_returns_true():
    """\\up always returns 'true'."""
    up = UpInteractor()
    cmd = parse(r"\up ---")
    assert up.execute(cmd) == "true"


def test_up_returns_true_with_executor():
    """\\up returns 'true' regardless of executor."""
    up = UpInteractor()
    cmd = parse(r"\up ---")
    assert up.execute(cmd, executor="@alice") == "true"
