r"""
Integration tests for Camp 2: Interactor-complete state.

Camp 2 = 10 entities coordinating through O.

These tests verify that all interactors work together:
- Message flow: say → listen → incoming (returns true/false)
- Wake conditions: wake → eval → condition triggers → messages bundled
- Entity lifecycle: spawn → execute → wake
- Multi-entity coordination

Architecture notes:
- \incoming returns "true"/"false" (presence of new messages)
- \wake bundles actual messages when waking (from listened spaces)
- Named spaces (#general) must exist before sending; entity spaces auto-create

This is the integration layer - individual interactor tests
are in interactors/tests/. These tests verify the system
as a whole.
"""

import pytest
import json
import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from mind import Mind
from body import Body, Space
from state.state import SystemState
from grammar.parser import parse

# Import all Camp 2 interactors
from interactors.echo import EchoInteractor
from interactors.name import NameInteractor
from interactors.say import SayInteractor
from interactors.listen import ListenInteractor
from interactors.incoming import IncomingInteractor
from interactors.spawn import SpawnInteractor
from interactors.up import UpInteractor
from interactors.wake import WakeInteractor
from interactors.eval import EvalInteractor


@pytest.fixture
def camp2_env(tmp_path):
    """
    Complete Camp 2 environment with all interactors wired together.

    This is the canonical setup for O with 10 entities.
    """
    # Directories
    spaces_dir = tmp_path / "spaces"
    listen_dir = tmp_path / "listen"
    wake_dir = tmp_path / "wake"
    logs_dir = tmp_path / "logs"
    incoming_dir = tmp_path / "incoming"

    spaces_dir.mkdir()
    listen_dir.mkdir()
    wake_dir.mkdir()
    logs_dir.mkdir()
    incoming_dir.mkdir()

    # Core components
    state = SystemState(tick=0, executions=[])

    # Interactors (some need body reference, added after body creation)
    up = UpInteractor()
    echo = EchoInteractor()
    name = NameInteractor()
    listen = ListenInteractor(memory_root=str(listen_dir))

    # Partial mind for interactors that need it
    interactors = {
        "up": up,
        "echo": echo,
        "name": name,
        "listen": listen,
    }
    mind = Mind(interactors)

    # Body (no transformer for now - we use execute_now)
    body = Body(mind, state, transformer=None, tick_interval=0.1)

    # Add body reference to listen (created before body)
    listen.body = body

    # Add body-dependent interactors
    say = SayInteractor(body=body, spaces_root=str(spaces_dir))
    incoming = IncomingInteractor(
        body=body,
        spaces_root=str(spaces_dir),
        state_root=str(incoming_dir)
    )
    spawn = SpawnInteractor(body=body)
    wake = WakeInteractor(
        body=body,
        mind=mind,
        memory_root=str(wake_dir),
        listen=listen,
        spaces_root=str(spaces_dir)
    )
    eval_interactor = EvalInteractor(body=body, mind=mind)

    # Add to mind
    mind.interactors["say"] = say
    mind.interactors["incoming"] = incoming
    mind.interactors["spawn"] = spawn
    mind.interactors["wake"] = wake
    mind.interactors["eval"] = eval_interactor

    return {
        "mind": mind,
        "body": body,
        "state": state,
        "tmp_path": tmp_path,
        "spaces_dir": spaces_dir,
        "listen_dir": listen_dir,
        "wake_dir": wake_dir,
        "incoming_dir": incoming_dir,
    }


class TestMessageFlow:
    """Test complete message flow: say → listen → incoming."""

    @pytest.mark.asyncio
    async def test_say_creates_space_and_message(self, camp2_env):
        """Say to named space writes message (space must exist first)."""
        body = camp2_env["body"]
        spaces_dir = camp2_env["spaces_dir"]

        # Spawn Alice
        output = await body.execute_now("@system", r"\spawn @alice ---")
        assert "Spawned" in output

        # Create #general space with Alice as member
        body.spaces["#general"] = Space(name="#general", members={"@alice"})

        # Alice says to #general
        output = await body.execute_now("@alice", r"\say #general Hello world ---")
        assert "Sent to #general" in output

        # Verify Alice is still in the space
        assert "#general" in body.spaces
        assert "@alice" in body.spaces["#general"].members

        # Verify message file exists
        space_file = spaces_dir / "#general.jsonl"
        assert space_file.exists()

        with open(space_file) as f:
            line = f.readline()
            msg = json.loads(line)
            assert msg["sender"] == "@alice"
            assert msg["content"] == "Hello world"

    @pytest.mark.asyncio
    async def test_listen_subscribes_to_entity(self, camp2_env):
        """Listen creates subscription."""
        body = camp2_env["body"]
        listen_dir = camp2_env["listen_dir"]

        # Spawn Alice and Bob
        await body.execute_now("@system", r"\spawn @alice ---")
        await body.execute_now("@system", r"\spawn @bob ---")

        # Alice listens to Bob
        output = await body.execute_now("@alice", r"\listen @bob ---")
        assert "@bob" in output

        # Verify subscription file
        sub_file = listen_dir / "alice.json"
        assert sub_file.exists()

        with open(sub_file) as f:
            data = json.load(f)
            assert "@bob" in data["spaces"]

    @pytest.mark.asyncio
    async def test_full_message_flow_entity_to_entity(self, camp2_env):
        """Complete flow: Bob says → Alice listens → incoming returns true."""
        body = camp2_env["body"]

        # Spawn entities
        await body.execute_now("@system", r"\spawn @alice ---")
        await body.execute_now("@system", r"\spawn @bob ---")

        # Alice listens to Bob
        await body.execute_now("@alice", r"\listen @bob ---")

        # Bob says something to Alice (creates @alice-@bob space)
        await body.execute_now("@bob", r"\say @alice Hey Alice! ---")

        # Alice checks incoming - returns "true"/"false" (presence check)
        output = await body.execute_now("@alice", r"\incoming ---")
        assert output == "true"

    @pytest.mark.asyncio
    async def test_full_message_flow_through_space(self, camp2_env):
        """Complete flow: Multiple entities communicate through #channel."""
        body = camp2_env["body"]

        # Spawn entities
        await body.execute_now("@system", r"\spawn @alice ---")
        await body.execute_now("@system", r"\spawn @bob ---")
        await body.execute_now("@system", r"\spawn @charlie ---")

        # Create #general space with all members
        body.spaces["#general"] = Space(name="#general", members={"@alice", "@bob", "@charlie"})

        # All listen to #general
        await body.execute_now("@alice", r"\listen #general ---")
        await body.execute_now("@bob", r"\listen #general ---")
        await body.execute_now("@charlie", r"\listen #general ---")

        # Bob posts to #general
        await body.execute_now("@bob", r"\say #general Hello everyone! ---")

        # Alice checks incoming - returns "true" (presence check)
        output = await body.execute_now("@alice", r"\incoming ---")
        assert output == "true"

        # Charlie checks incoming
        output = await body.execute_now("@charlie", r"\incoming ---")
        assert output == "true"


class TestWakeConditions:
    """Test wake condition registration and evaluation."""

    @pytest.mark.asyncio
    async def test_wake_with_up_condition(self, camp2_env):
        """Wake with \\up condition triggers immediately."""
        body = camp2_env["body"]
        mind = camp2_env["mind"]
        wake = mind.interactors["wake"]

        # Spawn Alice
        await body.execute_now("@system", r"\spawn @alice ---")

        # Alice registers wake with always-true condition
        output = await body.execute_now("@alice", r"\wake ?($(\up---)) Time to check messages ---")
        assert "Wake registered" in output

        # Check should_wake
        should, prompt = await wake.should_wake("@alice")
        assert should is True
        assert "Time to check messages" in prompt

        # Record consumed - second check should be False
        should, _ = await wake.should_wake("@alice")
        assert should is False

    @pytest.mark.asyncio
    async def test_wake_with_complex_condition(self, camp2_env):
        """Wake with boolean condition."""
        body = camp2_env["body"]
        mind = camp2_env["mind"]
        wake = mind.interactors["wake"]

        # Spawn Alice
        await body.execute_now("@system", r"\spawn @alice ---")

        # Alice registers wake with (true or false) condition
        output = await body.execute_now("@alice", r"\wake ?(true or false) Complex wake ---")
        assert "Wake registered" in output

        # Should trigger (true or false = true)
        should, prompt = await wake.should_wake("@alice")
        assert should is True
        assert "Complex wake" in prompt

    @pytest.mark.asyncio
    async def test_wake_bundles_messages(self, camp2_env):
        """Wake includes messages from listened spaces."""
        body = camp2_env["body"]
        mind = camp2_env["mind"]
        wake = mind.interactors["wake"]

        # Spawn entities
        await body.execute_now("@system", r"\spawn @alice ---")
        await body.execute_now("@system", r"\spawn @bob ---")

        # Alice listens to Bob
        await body.execute_now("@alice", r"\listen @bob ---")

        # Bob sends message
        await body.execute_now("@bob", r"\say @alice Hello from Bob ---")

        # Alice registers wake
        await body.execute_now("@alice", r"\wake ?($(\up---)) Check messages ---")

        # Should wake includes message
        should, prompt = await wake.should_wake("@alice")
        assert should is True
        assert "Check messages" in prompt
        assert "--- Messages ---" in prompt
        assert "@bob" in prompt
        assert "Hello from Bob" in prompt


class TestConditionEvaluation:
    """Test \\eval interactor standalone."""

    @pytest.mark.asyncio
    async def test_eval_true_literal(self, camp2_env):
        """Eval with true literal returns 'true'."""
        body = camp2_env["body"]

        output = await body.execute_now("@test", r"\eval ?(true) ---")
        assert output == "true"

    @pytest.mark.asyncio
    async def test_eval_false_literal(self, camp2_env):
        """Eval with false literal returns 'false'."""
        body = camp2_env["body"]

        output = await body.execute_now("@test", r"\eval ?(false) ---")
        assert output == "false"

    @pytest.mark.asyncio
    async def test_eval_boolean_or(self, camp2_env):
        """Eval with OR returns correct result."""
        body = camp2_env["body"]

        output = await body.execute_now("@test", r"\eval ?(true or false) ---")
        assert output == "true"

        output = await body.execute_now("@test", r"\eval ?(false or false) ---")
        assert output == "false"

    @pytest.mark.asyncio
    async def test_eval_boolean_and(self, camp2_env):
        """Eval with AND returns correct result."""
        body = camp2_env["body"]

        output = await body.execute_now("@test", r"\eval ?(true and true) ---")
        assert output == "true"

        output = await body.execute_now("@test", r"\eval ?(true and false) ---")
        assert output == "false"

    @pytest.mark.asyncio
    async def test_eval_comparison(self, camp2_env):
        """Eval with comparison operators."""
        body = camp2_env["body"]

        output = await body.execute_now("@test", r"\eval ?(10 > 5) ---")
        assert output == "true"

        output = await body.execute_now("@test", r"\eval ?(10 < 5) ---")
        assert output == "false"

        output = await body.execute_now("@test", r"\eval ?(5 = 5) ---")
        assert output == "true"

    @pytest.mark.asyncio
    async def test_eval_scheduler_query(self, camp2_env):
        """Eval with scheduler query."""
        body = camp2_env["body"]

        # \up always returns "true"
        output = await body.execute_now("@test", r"\eval ?($(\up---)) ---")
        assert output == "true"


class TestEntityLifecycle:
    """Test entity creation and lifecycle."""

    @pytest.mark.asyncio
    async def test_spawn_creates_entity(self, camp2_env):
        """Spawn registers entity in body."""
        body = camp2_env["body"]

        assert "@alice" not in body.entity_spaces

        output = await body.execute_now("@system", r"\spawn @alice ---")

        assert "Spawned" in output
        assert "@alice" in body.entity_spaces

    @pytest.mark.asyncio
    async def test_spawn_multiple_entities(self, camp2_env):
        """Spawn creates multiple entities."""
        body = camp2_env["body"]

        await body.execute_now("@system", r"\spawn @alice ---")
        await body.execute_now("@system", r"\spawn @bob ---")
        await body.execute_now("@system", r"\spawn @charlie ---")

        assert "@alice" in body.entity_spaces
        assert "@bob" in body.entity_spaces
        assert "@charlie" in body.entity_spaces

    @pytest.mark.asyncio
    async def test_spawn_duplicate_fails(self, camp2_env):
        """Cannot spawn duplicate entity."""
        body = camp2_env["body"]

        await body.execute_now("@system", r"\spawn @alice ---")
        output = await body.execute_now("@system", r"\spawn @alice ---")

        assert "already exists" in output


class TestMultiEntityCoordination:
    """Test multiple entities coordinating through O."""

    @pytest.mark.asyncio
    async def test_three_entity_conversation(self, camp2_env):
        """Three entities have a conversation in #general."""
        body = camp2_env["body"]

        # Spawn entities
        await body.execute_now("@system", r"\spawn @alice ---")
        await body.execute_now("@system", r"\spawn @bob ---")
        await body.execute_now("@system", r"\spawn @charlie ---")

        # Create #general with all members
        body.spaces["#general"] = Space(name="#general", members={"@alice", "@bob", "@charlie"})

        # All listen to #general
        await body.execute_now("@alice", r"\listen #general ---")
        await body.execute_now("@bob", r"\listen #general ---")
        await body.execute_now("@charlie", r"\listen #general ---")

        # Conversation
        await body.execute_now("@alice", r"\say #general Hi everyone! ---")
        await body.execute_now("@bob", r"\say #general Hey Alice! ---")
        await body.execute_now("@charlie", r"\say #general Hello team! ---")

        # Charlie checks incoming - returns "true" (has new messages)
        output = await body.execute_now("@charlie", r"\incoming ---")
        assert output == "true"

    @pytest.mark.asyncio
    async def test_private_dm_not_visible_to_others(self, camp2_env):
        """DM between two entities not visible to third."""
        body = camp2_env["body"]

        # Spawn entities
        await body.execute_now("@system", r"\spawn @alice ---")
        await body.execute_now("@system", r"\spawn @bob ---")
        await body.execute_now("@system", r"\spawn @charlie ---")

        # Alice and Bob DM each other
        await body.execute_now("@alice", r"\listen @bob ---")
        await body.execute_now("@bob", r"\listen @alice ---")

        # Bob sends private message to Alice
        await body.execute_now("@bob", r"\say @alice Secret message ---")

        # Alice has incoming messages
        output = await body.execute_now("@alice", r"\incoming ---")
        assert output == "true"

        # Charlie doesn't listen to anyone - no incoming
        output = await body.execute_now("@charlie", r"\incoming ---")
        assert output == "false"

    @pytest.mark.asyncio
    async def test_entity_in_multiple_spaces(self, camp2_env):
        """Entity participates in multiple spaces."""
        body = camp2_env["body"]

        # Spawn entities
        await body.execute_now("@system", r"\spawn @alice ---")
        await body.execute_now("@system", r"\spawn @bob ---")

        # Create spaces with both members
        body.spaces["#general"] = Space(name="#general", members={"@alice", "@bob"})
        body.spaces["#dev"] = Space(name="#dev", members={"@alice", "@bob"})

        # Alice listens to both #general and #dev
        await body.execute_now("@alice", r"\listen #general ---")
        await body.execute_now("@alice", r"\listen #dev ---")

        # Bob posts to both
        await body.execute_now("@bob", r"\say #general General message ---")
        await body.execute_now("@bob", r"\say #dev Dev message ---")

        # Alice has incoming messages from both spaces
        output = await body.execute_now("@alice", r"\incoming ---")
        assert output == "true"


class TestStateTracking:
    """Test that state tracks executions properly."""

    @pytest.mark.asyncio
    async def test_executions_logged(self, camp2_env):
        """All executions are logged in state."""
        body = camp2_env["body"]
        state = camp2_env["state"]

        assert len(state.executions) == 0

        await body.execute_now("@alice", r"\echo Hello ---")
        await body.execute_now("@bob", r"\echo World ---")

        assert len(state.executions) == 2
        assert state.executions[0].executor == "@alice"
        assert state.executions[1].executor == "@bob"

    @pytest.mark.asyncio
    async def test_execution_output_captured(self, camp2_env):
        """Execution output is captured in state."""
        body = camp2_env["body"]
        state = camp2_env["state"]

        await body.execute_now("@test", r"\echo Test message ---")

        assert len(state.executions) == 1
        assert "Test message" in state.executions[0].output


class TestErrorHandling:
    """Test error handling across the system."""

    @pytest.mark.asyncio
    async def test_unknown_command_returns_error(self, camp2_env):
        """Unknown command returns error message."""
        body = camp2_env["body"]

        output = await body.execute_now("@test", r"\nonexistent foo ---")
        assert "ERROR" in output
        assert "Unknown command" in output

    @pytest.mark.asyncio
    async def test_incoming_without_subscriptions(self, camp2_env):
        """Incoming with no subscriptions returns false."""
        body = camp2_env["body"]

        await body.execute_now("@system", r"\spawn @lonely ---")

        output = await body.execute_now("@lonely", r"\incoming ---")
        # No subscriptions = no incoming = false
        assert output == "false"


class TestCamp2Scale:
    """Test with 10 entities (Camp 2 target scale)."""

    @pytest.mark.asyncio
    async def test_ten_entities_in_space(self, camp2_env):
        """Ten entities can join and communicate in a space."""
        body = camp2_env["body"]

        entities = [f"@entity{i}" for i in range(10)]

        # Spawn all entities
        for entity in entities:
            output = await body.execute_now("@system", f"\\spawn {entity} ---")
            assert "Spawned" in output

        # Create #camp2 with all members
        body.spaces["#camp2"] = Space(name="#camp2", members=set(entities))

        # All listen to #camp2
        for entity in entities:
            await body.execute_now(entity, r"\listen #camp2 ---")

        # Entity0 sends message
        await body.execute_now("@entity0", r"\say #camp2 Hello Camp 2! ---")

        # All others should have incoming messages
        for entity in entities[1:]:
            output = await body.execute_now(entity, r"\incoming ---")
            assert output == "true"

    @pytest.mark.asyncio
    async def test_ten_entities_all_message(self, camp2_env):
        """Ten entities all post and see each other's messages."""
        body = camp2_env["body"]

        entities = [f"@entity{i}" for i in range(10)]

        # Spawn all entities
        for entity in entities:
            await body.execute_now("@system", f"\\spawn {entity} ---")

        # Create #camp2 with all members
        body.spaces["#camp2"] = Space(name="#camp2", members=set(entities))

        # Setup listeners
        for entity in entities:
            await body.execute_now(entity, r"\listen #camp2 ---")

        # Everyone posts
        for i, entity in enumerate(entities):
            await body.execute_now(entity, f"\\say #camp2 Message from {i} ---")

        # Last entity should have incoming messages
        output = await body.execute_now("@entity9", r"\incoming ---")
        assert output == "true"
