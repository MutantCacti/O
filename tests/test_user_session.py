"""
Actual user test session - running the commands the test user tried.
This validates our UX predictions.
"""

import pytest
from pathlib import Path
import shutil
from mind import Mind
from body import Body
from state.state import SystemState
from interactors.stdout import StdoutInteractor


@pytest.fixture
def test_memory_dir(tmp_path):
    """Create temporary memory directory"""
    memory_dir = tmp_path / "memory" / "stdout"
    memory_dir.mkdir(parents=True)
    yield memory_dir
    if memory_dir.parent.exists():
        shutil.rmtree(memory_dir.parent)


@pytest.fixture
def system(test_memory_dir):
    """Create integrated system"""
    state = SystemState(tick=0, executions=[])
    stdout = StdoutInteractor(memory_root=str(test_memory_dir))
    mind = Mind(interactors={"stdout": stdout})
    body = Body(mind, state)
    stdout.body = body
    return body


class TestQuickStart:
    """Test the Quick Start commands"""

    @pytest.mark.asyncio
    async def test_step_1_write_first_entry(self, system):
        result = await system.execute_now("@testuser", r"\stdout write: I just woke up for the first time ---")
        assert "Written to stdout" in result
        assert "tick 0" in result

    @pytest.mark.asyncio
    async def test_step_2_read_it_back(self, system):
        await system.execute_now("@testuser", r"\stdout write: I just woke up for the first time ---")
        result = await system.execute_now("@testuser", r"\stdout read: ---")
        assert "Last 1 stdout entries" in result
        assert "I just woke up for the first time" in result

    @pytest.mark.asyncio
    async def test_step_3_implicit_writes(self, system):
        result1 = await system.execute_now("@testuser", r"\stdout Exploring the system ---")
        result2 = await system.execute_now("@testuser", r"\stdout Found some interesting entities: @alice @bob ---")
        result3 = await system.execute_now("@testuser", r"\stdout Learning about spaces like #general ---")

        assert "Written to stdout" in result1
        assert "Written to stdout" in result2
        assert "Written to stdout" in result3

    @pytest.mark.asyncio
    async def test_step_4_read_last_3(self, system):
        await system.execute_now("@testuser", r"\stdout Exploring the system ---")
        await system.execute_now("@testuser", r"\stdout Found some interesting entities: @alice @bob ---")
        await system.execute_now("@testuser", r"\stdout Learning about spaces like #general ---")

        result = await system.execute_now("@testuser", r"\stdout read: last 3 ---")
        assert "Last 3 stdout entries" in result
        assert "Exploring the system" in result
        assert "Found some interesting entities" in result
        assert "Learning about spaces" in result


class TestQuestionA_StateReconstruction:
    """Test A: State Reconstruction"""

    @pytest.mark.asyncio
    async def test_read_last_2(self, system):
        await system.execute_now("@testuser", r"\stdout Started task: analyze system architecture ---")
        await system.execute_now("@testuser", r"\stdout Task progress: 50% complete ---")

        result = await system.execute_now("@testuser", r"\stdout read: last 2 ---")
        assert "Started task: analyze system architecture" in result
        assert "Task progress: 50% complete" in result

    @pytest.mark.asyncio
    async def test_read_default(self, system):
        await system.execute_now("@testuser", r"\stdout Started task: analyze system architecture ---")
        await system.execute_now("@testuser", r"\stdout Task progress: 50% complete ---")

        result = await system.execute_now("@testuser", r"\stdout read: ---")
        # Default is last 1
        assert "Task progress: 50% complete" in result


class TestQuestionB_FindingSpecificInfo:
    """Test B: Finding @bob mentions"""

    @pytest.mark.asyncio
    async def test_query_works(self, system):
        """The command that SHOULD work: query:"""
        await system.execute_now("@testuser", r"\stdout Met @alice in #general today ---")
        await system.execute_now("@testuser", r"\stdout @bob suggested I look at the parser code ---")
        await system.execute_now("@testuser", r"\stdout Discussing with @charlie about wake conditions ---")
        await system.execute_now("@testuser", r"\stdout @bob mentioned the scheduler might be busy ---")

        result = await system.execute_now("@testuser", r"\stdout query: @bob ---")
        assert "Entries matching '@bob'" in result
        assert "@bob suggested" in result
        assert "@bob mentioned" in result
        assert "@alice" not in result  # Should not appear

    @pytest.mark.asyncio
    async def test_read_bob_fails(self, system):
        """User tried: read: @bob - should fail"""
        await system.execute_now("@testuser", r"\stdout @bob is mentioned here ---")

        result = await system.execute_now("@testuser", r"\stdout read: @bob ---")
        # This interprets "@bob" as text, tries to parse as "last @bob"
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_find_fails(self, system):
        """User tried: find: @bob - should fail"""
        result = await system.execute_now("@testuser", r"\stdout find: @bob ---")
        assert "ERROR" in result
        assert "Unknown operation" in result


class TestQuestionC_TimeBasedQueries:
    """Test C: Time-based queries"""

    @pytest.mark.asyncio
    async def test_between_works(self, system):
        """The command that SHOULD work: between:"""
        for i in range(5):
            await system.execute_now("@testuser", f"\\stdout Tick {i} activity ---")
            await system.tick()

        result = await system.execute_now("@testuser", r"\stdout between: 1 and 3 ---")
        assert "Entries between tick 1 and 3" in result
        assert "Tick 1 activity" in result
        assert "Tick 2 activity" in result
        assert "Tick 3 activity" in result
        assert "Tick 0 activity" not in result
        assert "Tick 4 activity" not in result

    @pytest.mark.asyncio
    async def test_between_without_and_works(self, system):
        """Also works: between: 1 3"""
        for i in range(5):
            await system.execute_now("@testuser", f"\\stdout Tick {i} activity ---")
            await system.tick()

        result = await system.execute_now("@testuser", r"\stdout between: 1 3 ---")
        assert "Entries between tick 1 and 3" in result

    @pytest.mark.asyncio
    async def test_read_from_to_fails(self, system):
        """User tried: read: from 10 to 20 - should fail"""
        result = await system.execute_now("@testuser", r"\stdout read: from 10 to 20 ---")
        assert "ERROR" in result


class TestQuestionD_GettingHelp:
    """Test D: Getting help"""

    @pytest.mark.asyncio
    async def test_help_works(self, system):
        """The command that SHOULD work: help:"""
        result = await system.execute_now("@testuser", r"\stdout help: ---")
        assert "\\stdout - Memory persistence layer" in result
        assert "Operations:" in result
        assert "write:" in result
        assert "read:" in result
        assert "between:" in result
        assert "query:" in result


class TestInvalidInputs:
    """Test invalid inputs and edge cases"""

    @pytest.mark.asyncio
    async def test_empty_write(self, system):
        """User tried: write: (empty)"""
        result = await system.execute_now("@testuser", r"\stdout write: ---")
        assert "ERROR" in result
        assert "No content" in result

    @pytest.mark.asyncio
    async def test_just_stdout(self, system):
        """User tried: \stdout (nothing else) - should error"""
        result = await system.execute_now("@testuser", r"\stdout ---")
        assert "ERROR" in result
        assert "No content" in result

    @pytest.mark.asyncio
    async def test_spaces_only(self, system):
        """User tried: write: (only spaces)"""
        result = await system.execute_now("@testuser", r"\stdout write:    ---")
        assert "ERROR" in result
        assert "No content" in result

    @pytest.mark.asyncio
    async def test_special_characters_work(self, system):
        """Special chars should work in content"""
        result = await system.execute_now("@testuser", r"\stdout write: Testing @entity #space ?(condition) $(\query---) ---")
        assert "Written to stdout" in result

        # Verify it was stored
        read_result = await system.execute_now("@testuser", r"\stdout read: ---")
        assert "@entity" in read_result
        assert "#space" in read_result


class TestNaturalCommands:
    """Commands users tried naturally"""

    @pytest.mark.asyncio
    async def test_simple_implicit_writes(self, system):
        """Users naturally tried these"""
        result1 = await system.execute_now("@testuser", r"\stdout hello world ---")
        result2 = await system.execute_now("@testuser", r"\stdout Starting experiment 42 ---")
        result3 = await system.execute_now("@testuser", r"\stdout TODO - fix parser edge case ---")

        assert "Written to stdout" in result1
        assert "Written to stdout" in result2
        assert "Written to stdout" in result3

    @pytest.mark.asyncio
    async def test_colon_label_errors(self, system):
        """Using colon as label should error - colon is reserved for operations"""
        result = await system.execute_now("@testuser", r"\stdout TODO: fix parser ---")
        assert "ERROR" in result
        assert "unknown operation" in result.lower()
        assert "todo" in result.lower()

    @pytest.mark.asyncio
    async def test_read_all_not_supported(self, system):
        """User tried: read: all"""
        result = await system.execute_now("@testuser", r"\stdout read: all ---")
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_clear_not_supported(self, system):
        """User tried: clear:"""
        result = await system.execute_now("@testuser", r"\stdout clear: ---")
        assert "ERROR" in result


class TestCreativeCombinations:
    """Creative use cases users tried"""

    @pytest.mark.asyncio
    async def test_tracking_conversations(self, system):
        """User wants to track who they talked to"""
        await system.execute_now("@testuser", r"\stdout Received from @alice: Hello ---")
        await system.execute_now("@testuser", r"\stdout Replied to @alice: Hi there ---")
        await system.execute_now("@testuser", r"\stdout @bob asked about the parser ---")

        # Query for alice conversations
        result = await system.execute_now("@testuser", r"\stdout query: @alice ---")
        assert "Received from @alice" in result
        assert "Replied to @alice" in result
        assert "@bob" not in result

    @pytest.mark.asyncio
    async def test_error_logging(self, system):
        """User wants to log and query errors - use brackets instead of colon"""
        await system.execute_now("@testuser", r"\stdout [INFO] System started ---")
        await system.execute_now("@testuser", r"\stdout [ERROR] Failed to connect to #space ---")
        await system.execute_now("@testuser", r"\stdout [INFO] Retrying ---")
        await system.execute_now("@testuser", r"\stdout [ERROR] Timeout after 30s ---")

        # Query for errors only
        result = await system.execute_now("@testuser", r"\stdout query: ERROR ---")
        assert "Failed to connect" in result
        assert "Timeout" in result
        assert "INFO" not in result

    @pytest.mark.asyncio
    async def test_todo_list(self, system):
        """User wants to use stdout as todo list - use brackets instead of colon"""
        await system.execute_now("@testuser", r"\stdout [TODO] Fix the parser ---")
        await system.execute_now("@testuser", r"\stdout [TODO] Write tests ---")
        await system.execute_now("@testuser", r"\stdout [DONE] Added documentation ---")

        # Query for TODOs
        result = await system.execute_now("@testuser", r"\stdout query: TODO ---")
        assert "Fix the parser" in result
        assert "Write tests" in result
        assert "DONE" not in result
