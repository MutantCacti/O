"""
Comprehensive tests for Mind (the execution engine).

Mind is the CPU - it should:
- Parse commands correctly
- Dispatch to the right interactor
- Handle errors gracefully
- Pass context to interactors
- Be stateless (no side effects)
"""

import pytest
from mind import Mind
from grammar.parser import Command, parse
from interactors.base import Interactor
from interactors.echo import EchoInteractor


class MockInteractor(Interactor):
    """Mock interactor for testing"""

    def __init__(self):
        self.last_cmd = None
        self.last_executor = None
        self.call_count = 0

    def execute(self, cmd: Command, executor: str = None) -> str:
        self.last_cmd = cmd
        self.last_executor = executor
        self.call_count += 1
        return f"Mock executed by {executor}"


class ErrorInteractor(Interactor):
    """Interactor that raises errors"""

    def execute(self, cmd: Command, executor: str = None) -> str:
        raise ValueError("Intentional error for testing")


class TestMindExecution:
    """Test basic execution flow"""

    def test_mind_executes_command(self):
        """Mind executes a simple command"""
        mock = MockInteractor()
        mind = Mind(interactors={"test": mock})

        output = mind.execute(r"\test hello ---")

        assert "Mock executed" in output
        assert mock.call_count == 1

    def test_mind_passes_executor_context(self):
        """Mind passes executor to interactor"""
        mock = MockInteractor()
        mind = Mind(interactors={"test": mock})

        output = mind.execute(r"\test hello ---", executor="@alice")

        assert mock.last_executor == "@alice"
        assert "@alice" in output

    def test_mind_works_without_executor(self):
        """Mind handles missing executor gracefully"""
        mock = MockInteractor()
        mind = Mind(interactors={"test": mock})

        output = mind.execute(r"\test hello ---")

        assert mock.last_executor is None
        assert mock.call_count == 1

    def test_mind_is_stateless(self):
        """Mind doesn't retain state between calls"""
        mock = MockInteractor()
        mind = Mind(interactors={"test": mock})

        mind.execute(r"\test first ---", executor="@alice")
        mind.execute(r"\test second ---", executor="@bob")

        # Last call should be bob, not alice
        assert mock.last_executor == "@bob"
        assert mock.call_count == 2


class TestCommandDispatch:
    """Test command name extraction and dispatching"""

    def test_dispatch_simple_command(self):
        """Dispatch command with simple name"""
        mock = MockInteractor()
        mind = Mind(interactors={"test": mock})

        mind.execute(r"\test arg1 arg2 ---")

        assert mock.call_count == 1

    def test_dispatch_command_with_entities(self):
        """Dispatch command with entities before text"""
        mock = MockInteractor()
        mind = Mind(interactors={"test": mock})

        # Command name is first Text node, not Entity
        mind.execute(r"\test @alice @bob hello ---")

        assert mock.call_count == 1

    def test_dispatch_extracts_first_word(self):
        """Command name is first word of first text node"""
        mock = MockInteractor()
        mind = Mind(interactors={"say": mock})

        mind.execute(r"\say hello world ---")

        assert mock.call_count == 1

    def test_dispatch_multiple_interactors(self):
        """Mind dispatches to correct interactor"""
        mock1 = MockInteractor()
        mock2 = MockInteractor()
        mind = Mind(interactors={"test1": mock1, "test2": mock2})

        mind.execute(r"\test1 hello ---")
        mind.execute(r"\test2 world ---")

        assert mock1.call_count == 1
        assert mock2.call_count == 1


class TestErrorHandling:
    """Test error handling in Mind"""

    def test_unknown_command_returns_error(self):
        """Unknown command returns helpful error"""
        mind = Mind(interactors={})

        output = mind.execute(r"\unknown test ---")

        assert "ERROR" in output
        assert "Unknown command" in output
        assert "unknown" in output.lower()

    def test_interactor_exception_caught(self):
        """Mind catches exceptions from interactors"""
        mind = Mind(interactors={"error": ErrorInteractor()})

        output = mind.execute(r"\error test ---")

        assert "ERROR" in output
        assert "Intentional error" in output

    def test_parse_error_caught(self):
        """Mind catches parser errors"""
        mind = Mind(interactors={"test": MockInteractor()})

        # Invalid command (no terminator)
        output = mind.execute(r"\test hello")

        assert "ERROR" in output

    def test_empty_command_name(self):
        """Command with no text returns error"""
        mind = Mind(interactors={"test": MockInteractor()})

        # Command with only entities (no text to extract name from)
        output = mind.execute(r"\@alice ---")

        assert "ERROR" in output


class TestRealInteractors:
    """Test Mind with real interactors"""

    def test_echo_interactor(self):
        """Mind works with EchoInteractor"""
        mind = Mind(interactors={"echo": EchoInteractor()})

        output = mind.execute(r"\echo Hello World ---")

        assert output == "Echo: Hello World"

    def test_multiple_interactors(self):
        """Mind handles multiple real interactors"""
        mind = Mind(interactors={
            "echo": EchoInteractor(),
            "test": MockInteractor()
        })

        output1 = mind.execute(r"\echo test ---")
        output2 = mind.execute(r"\test hello ---")

        assert output1 == "Echo: test"
        assert "Mock executed" in output2


class TestEdgeCases:
    """Test edge cases and corner scenarios"""

    def test_empty_interactor_dict(self):
        """Mind works with no interactors"""
        mind = Mind(interactors={})

        output = mind.execute(r"\anything ---")

        assert "ERROR" in output
        assert "Unknown command" in output

    def test_command_with_special_chars(self):
        """Commands with special characters in text"""
        mock = MockInteractor()
        mind = Mind(interactors={"test": mock})

        mind.execute(r"\test Hello! How are you? ---")

        assert mock.call_count == 1

    def test_very_long_command(self):
        """Mind handles long commands"""
        mock = MockInteractor()
        mind = Mind(interactors={"test": mock})

        long_text = "word " * 100
        mind.execute(rf"\test {long_text}---")

        assert mock.call_count == 1

    def test_command_with_backslash_in_text(self):
        """Backslash in text content should error"""
        mock = MockInteractor()
        mind = Mind(interactors={"test": mock})

        # Backslash inside text is not allowed (reserved for commands)
        output = mind.execute(r"\test Line 1\nLine 2 ---")

        assert "ERROR" in output
        assert "Backslash" in output


class TestCommandParsing:
    """Test that Mind properly parses commands before dispatch"""

    def test_parsed_command_passed_to_interactor(self):
        """Interactor receives parsed Command object"""
        mock = MockInteractor()
        mind = Mind(interactors={"test": mock})

        mind.execute(r"\test hello ---")

        assert mock.last_cmd is not None
        assert isinstance(mock.last_cmd, Command)

    def test_parsed_command_has_content(self):
        """Parsed command contains nodes"""
        mock = MockInteractor()
        mind = Mind(interactors={"test": mock})

        mind.execute(r"\test @alice hello ---")

        assert len(mock.last_cmd.content) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
