r"""Tests for \spawn interactor."""

import pytest
from grammar.parser import parse
from interactors.spawn import SpawnInteractor
from body import Body
from mind import Mind
from state.state import SystemState


class MockTransformer:
    """Mock transformer that tracks ensure_entity_fifos calls."""

    def __init__(self):
        self.created_entities = []

    def ensure_entity_fifos(self, entity: str):
        self.created_entities.append(entity)

    async def read_command(self, entity: str):
        return None

    async def write_output(self, entity: str, output: dict):
        pass


@pytest.fixture
def body_with_transformer():
    """Create Body with mock transformer."""
    mind = Mind({})
    state = SystemState(tick=0, executions=[])
    transformer = MockTransformer()
    body = Body(mind, state, transformer=transformer)
    return body


class TestSpawnBasics:
    """Test basic spawn functionality."""

    def test_spawn_requires_body(self):
        """Spawn without body returns error."""
        spawn = SpawnInteractor(body=None)
        cmd = parse(r"\spawn @alice ---")
        result = spawn.execute(cmd)
        assert "ERROR" in result
        assert "body" in result.lower()

    def test_spawn_requires_entity(self, body_with_transformer):
        """Spawn without entity target returns error."""
        spawn = SpawnInteractor(body=body_with_transformer)
        cmd = parse(r"\spawn ---")
        result = spawn.execute(cmd)
        assert "ERROR" in result
        assert "No entity" in result

    def test_spawn_creates_entity(self, body_with_transformer):
        """Spawn registers entity in body.entity_spaces."""
        body = body_with_transformer
        spawn = SpawnInteractor(body=body)

        cmd = parse(r"\spawn @alice ---")
        result = spawn.execute(cmd)

        assert "@alice" in body.entity_spaces
        assert "Spawned" in result
        assert "@alice" in result

    def test_spawn_creates_fifos(self, body_with_transformer):
        """Spawn calls transformer.ensure_entity_fifos()."""
        body = body_with_transformer
        spawn = SpawnInteractor(body=body)

        cmd = parse(r"\spawn @alice ---")
        spawn.execute(cmd)

        assert "@alice" in body.transformer.created_entities

    def test_spawn_multiple_entities(self, body_with_transformer):
        """Spawn can create multiple entities at once."""
        body = body_with_transformer
        spawn = SpawnInteractor(body=body)

        cmd = parse(r"\spawn @alice @bob ---")
        result = spawn.execute(cmd)

        assert "@alice" in body.entity_spaces
        assert "@bob" in body.entity_spaces
        assert "@alice" in result
        assert "@bob" in result

    def test_spawn_rejects_duplicate(self, body_with_transformer):
        """Spawn rejects already-existing entities."""
        body = body_with_transformer
        body.entity_spaces["@alice"] = set()

        spawn = SpawnInteractor(body=body)
        cmd = parse(r"\spawn @alice ---")
        result = spawn.execute(cmd)

        assert "already exists" in result

    def test_spawn_partial_success(self, body_with_transformer):
        """Spawn reports both successes and failures."""
        body = body_with_transformer
        body.entity_spaces["@alice"] = set()  # Pre-existing

        spawn = SpawnInteractor(body=body)
        cmd = parse(r"\spawn @alice @bob ---")
        result = spawn.execute(cmd)

        assert "@bob" in body.entity_spaces
        assert "Spawned" in result
        assert "@bob" in result
        assert "already exists" in result


class TestSpawnWithoutTransformer:
    """Test spawn when body has no transformer."""

    def test_spawn_works_without_transformer(self):
        """Spawn registers entity even without transformer."""
        mind = Mind({})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state, transformer=None)

        spawn = SpawnInteractor(body=body)
        cmd = parse(r"\spawn @alice ---")
        result = spawn.execute(cmd)

        assert "@alice" in body.entity_spaces
        assert "Spawned" in result
