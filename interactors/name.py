"""
Name interactor - Create relational addresses.

\name #family @(me, mom, dad, sister, brother) ---

The first magic: Naming brings spaces into being.

A space is shorthand for a set of entities.
#family becomes the address for @(me, mom, dad, sister, brother).

This creates the bidirectional edges:
- Space → Entities (who #family points to)
- Entity → Spaces (which names include @me)

From Kingkiller Chronicles: "Knowing the name gives you power over the thing."
In O: Naming creates the topology of relationship.
"""

from grammar.parser import Command, Entity, Space
from interactors.base import Interactor


class NameInteractor(Interactor):
    """
    Name a space as an alias for a set of entities.

    This is the first magic - creating relational addresses.
    """

    def __init__(self, body=None):
        """
        Create name interactor.

        Args:
            body: Body instance (for spatial substrate access)
        """
        self.body = body

    def execute(self, cmd: Command, executor: str = None) -> str:
        """
        Create a named space pointing to entities.

        Args:
            cmd: Parsed command tree
            executor: Who is executing (optional for now)

        Returns:
            Status message

        Example:
            \name #family @(alice, bob, charlie) ---
            Creates #family → {@alice, @bob, @charlie}
        """
        # Extract space being named
        space_id = None
        for node in cmd.content:
            if isinstance(node, Space):
                # Add # prefix back (parser strips it)
                space_id = f"#{node.name}"
                break

        if not space_id:
            return "ERROR: No space specified. Usage: \\name #space @(entities) ---"

        # Extract all entities to include in this space
        entities = []
        for node in cmd.content:
            if isinstance(node, Entity):
                # Add @ prefix back (parser strips it)
                entities.append(f"@{node.name}")

        if not entities:
            return "ERROR: No entities specified. Usage: \\name #space @(entities) ---"

        # Guard: Need body to actually create the space
        if not self.body:
            return f"Would name {space_id} as {entities} (body not connected)"

        # Create the space (or update if exists)
        from body import Space as SpaceData

        self.body.spaces[space_id] = SpaceData(
            name=space_id,
            members=set(entities)
        )

        # Create reverse mapping: each entity knows it's in this space
        for entity in entities:
            if entity not in self.body.entity_spaces:
                self.body.entity_spaces[entity] = set()
            self.body.entity_spaces[entity].add(space_id)

        # Return success
        entity_list = ", ".join(entities)
        return f"Named {space_id} as ({entity_list})"
