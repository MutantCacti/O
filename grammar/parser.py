r"""
O Grammar Parser

Minimal parser for O commands: \ .. ---

Creates a tree of classes:
- Text(..)
- Entity(@name)
- Space(#name)
- Condition(?(...))
- SchedulerQuery($(\command---))

Interactors interpret the tree.
"""

from dataclasses import dataclass
from typing import List, Union
import re


# === Configuration ===

MAX_COMMAND_LENGTH = 10000  # Maximum command length in characters
MAX_NESTING_DEPTH = 10      # Maximum nesting depth for conditions/queries
VALID_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$')  # Name validation


# === Error Classes ===

class ParserError(ValueError):
    """Base class for parser errors with entity-readable messages"""
    def __init__(self, message: str, position: int = None, command_snippet: str = None):
        self.position = position
        self.command_snippet = command_snippet

        # Build entity-readable error message
        full_message = message
        if position is not None:
            full_message += f" (at position {position})"
        if command_snippet:
            full_message += f"\n  Near: {command_snippet}"

        super().__init__(full_message)


# === Grammar Classes ===

@dataclass
class Text:
    """Base text class: .."""
    text: str

    def __repr__(self):
        return f'Text("{self.text}")'


@dataclass
class Entity:
    """Entity reference: @name"""
    name: str  # Single name only - @(a,b) creates multiple Entity objects

    def __repr__(self):
        return f'@{self.name}'


@dataclass
class Space:
    """Space reference: #name"""
    name: str  # Single name only - #(a,b) creates multiple Space objects

    def __repr__(self):
        return f'#{self.name}'


@dataclass
class Condition:
    """Condition class: ?(expression)"""
    expression: List['Node']  # Parsed content inside ?()

    def __repr__(self):
        return f'?({self.expression})'


@dataclass
class SchedulerQuery:
    r"""Scheduler command: $(\command---)"""
    command: List['Node']  # Parsed command inside $(\...---)

    def __repr__(self):
        return f'$({self.command})'


# Union type for all node types
Node = Union[Text, Entity, Space, Condition, SchedulerQuery]


@dataclass
class Command:
    r"""Parsed command: \ .. ---"""
    content: List[Node]

    def __repr__(self):
        return f'Command({self.content})'


# === Parser ===

class Parser:
    r"""
    Minimal recursive parser for O grammar.

    Handles:
    - Commands: \ .. ---
    - Entities: @name or @(name1, name2)
    - Spaces: #name or #(name1, name2)
    - Conditions: ?(expression)
    - Scheduler queries: $(\command---)
    - Text: everything else
    """

    def __init__(self, text: str, nesting_depth: int = 0):
        self.text = text
        self.pos = 0
        self.length = len(text)
        self.nesting_depth = nesting_depth

        # Check command length
        if len(text) > MAX_COMMAND_LENGTH:
            raise ParserError(
                f"Command too long ({len(text)} characters). Maximum is {MAX_COMMAND_LENGTH}.",
                position=0,
                command_snippet=text[:50] + "..."
            )

        # Check nesting depth
        if nesting_depth > MAX_NESTING_DEPTH:
            raise ParserError(
                f"Command nesting too deep (depth {nesting_depth}). Maximum is {MAX_NESTING_DEPTH}.",
                position=0
            )

    def peek(self, length: int = 1) -> str:
        """Look ahead without consuming"""
        return self.text[self.pos:self.pos + length]

    def consume(self, length: int = 1) -> str:
        """Consume and return characters"""
        result = self.text[self.pos:self.pos + length]
        self.pos += length
        return result

    def skip_whitespace(self):
        """Skip whitespace characters"""
        while self.pos < self.length and self.text[self.pos].isspace():
            self.pos += 1

    def get_snippet(self, position: int = None, context: int = 20) -> str:
        """Get a snippet of text around a position for error messages"""
        if position is None:
            position = self.pos

        start = max(0, position - context)
        end = min(self.length, position + context)
        snippet = self.text[start:end]

        # Add markers to show position
        if start > 0:
            snippet = "..." + snippet
        if end < self.length:
            snippet = snippet + "..."

        return snippet

    def error(self, message: str) -> ParserError:
        """Create a ParserError with context"""
        return ParserError(message, position=self.pos, command_snippet=self.get_snippet())

    def validate_name(self, name: str, kind: str) -> None:
        """
        Validate entity or space name.

        Names must:
        - Not be empty
        - Start with alphanumeric
        - Contain only alphanumeric, hyphen, underscore
        """
        if not name:
            raise self.error(f"Empty {kind} name. {kind.capitalize()} names must have at least one character.")

        if not VALID_NAME_PATTERN.match(name):
            raise self.error(
                f"Invalid {kind} name '{name}'. Names must start with a letter or number, "
                f"and contain only letters, numbers, hyphens, and underscores."
            )

    def parse_command(self) -> Command:
        r"""Parse a command: \ .. ---"""
        # Expect leading \
        if self.peek() != '\\':
            raise self.error("Commands must start with backslash (\\)")
        self.consume()  # Skip \

        # Parse content until ---
        content = self.parse_until('---')

        # Consume ---
        if self.peek(3) != '---':
            raise self.error("Commands must end with --- terminator")
        self.consume(3)

        return Command(content)

    def parse_until(self, terminator: str) -> List[Node]:
        """Parse content until terminator is found"""
        nodes = []

        while self.pos < self.length:
            # Check for terminator (skip if empty string)
            if terminator and self.peek(len(terminator)) == terminator:
                break

            # Check for special classes
            char = self.peek()

            if char == '@':
                # parse_entity returns list - extend to unpack multiple entities
                nodes.extend(self.parse_entity())
            elif char == '#':
                # parse_space returns list - extend to unpack multiple spaces
                nodes.extend(self.parse_space())
            elif char == '\\':
                # Backslash inside command content is reserved for nested commands
                # For now, it's not allowed in text (would need escape sequences)
                raise self.error(
                    "Backslash (\\) not allowed in text content. "
                    "Use it only to start commands: \\command ---"
                )
            elif char == '?':
                # Only parse condition if next char is (
                if self.pos + 1 < self.length and self.text[self.pos + 1] == '(':
                    nodes.append(self.parse_condition())
                else:
                    # Regular ? in text
                    nodes.append(self.parse_text())
            elif char == '$':
                # Only parse scheduler query if next char is (
                if self.pos + 1 < self.length and self.text[self.pos + 1] == '(':
                    nodes.extend(self.parse_scheduler_query())
                else:
                    # Regular $ in text
                    nodes.append(self.parse_text())
            else:
                # Regular text
                nodes.append(self.parse_text())

        return nodes

    def parse_entity(self) -> List[Entity]:
        """Parse @name or @(name1, name2) - returns list of Entity objects"""
        self.consume()  # Skip @

        if self.peek() == '(':
            # Multi-entity: @(name1, name2) -> multiple Entity objects
            self.consume()  # Skip (
            names_str = ''
            while self.peek() != ')':
                if self.pos >= self.length:
                    raise self.error("Unclosed entity group @(...). Missing closing parenthesis.")
                names_str += self.consume()
            self.consume()  # Skip )

            # Split by comma and create Entity object for each
            names = [n.strip() for n in names_str.split(',') if n.strip()]

            # Validate all names
            if not names:
                raise self.error("Empty entity group @(). Must contain at least one entity name.")

            entities = []
            for name in names:
                self.validate_name(name, "entity")
                entities.append(Entity(name))
            return entities
        else:
            # Single entity: @name -> single Entity in list
            name = ''
            while self.pos < self.length and (self.text[self.pos].isalnum() or self.text[self.pos] in '-_'):
                name += self.consume()

            self.validate_name(name, "entity")
            return [Entity(name)]

    def parse_space(self) -> List[Space]:
        """Parse #name or #(name1, name2) - returns list of Space objects"""
        self.consume()  # Skip #

        if self.peek() == '(':
            # Multi-space: #(name1, name2) -> multiple Space objects
            self.consume()  # Skip (
            names_str = ''
            while self.peek() != ')':
                if self.pos >= self.length:
                    raise self.error("Unclosed space group #(...). Missing closing parenthesis.")
                names_str += self.consume()
            self.consume()  # Skip )

            # Split by comma and create Space object for each
            names = [n.strip() for n in names_str.split(',') if n.strip()]

            # Validate all names
            if not names:
                raise self.error("Empty space group #(). Must contain at least one space name.")

            spaces = []
            for name in names:
                self.validate_name(name, "space")
                spaces.append(Space(name))
            return spaces
        else:
            # Single space: #name -> single Space in list
            name = ''
            while self.pos < self.length and (self.text[self.pos].isalnum() or self.text[self.pos] in '-_'):
                name += self.consume()

            self.validate_name(name, "space")
            return [Space(name)]

    def parse_condition(self) -> Condition:
        """Parse ?(expression)"""
        self.consume()  # Skip ?

        if self.peek() != '(':
            raise self.error("Conditions must start with ?( - missing opening parenthesis after ?")
        self.consume()  # Skip (

        # Find matching )
        depth = 1
        content_start = self.pos
        while depth > 0 and self.pos < self.length:
            if self.peek() == '(':
                depth += 1
            elif self.peek() == ')':
                depth -= 1
            if depth > 0:
                self.consume()

        # Check if we found the closing paren
        if depth > 0 or self.pos >= self.length:
            raise ParserError(
                "Unclosed condition ?(... - missing closing parenthesis",
                position=content_start,
                command_snippet=self.text[content_start:min(content_start + 40, self.length)] + "..."
            )

        content = self.text[content_start:self.pos]
        self.consume()  # Skip closing )

        # Recursively parse condition content with increased nesting depth
        sub_parser = Parser(content, nesting_depth=self.nesting_depth + 1)
        expression = sub_parser.parse_until('')

        return Condition(expression)

    def parse_scheduler_query(self) -> List[SchedulerQuery]:
        r"""Parse $(\command1---\command2---...) - returns list of SchedulerQuery objects"""
        self.consume()  # Skip $

        if self.peek(2) != '(\\':
            raise self.error("Scheduler queries must start with $(\\")
        self.consume(2)  # Skip (\

        queries = []
        start_pos = self.pos

        # Loop until we hit the closing )
        while self.pos < self.length and self.peek() != ')':
            # Extract raw command text until ---
            command_text = ''
            while self.pos < self.length:
                if self.peek(3) == '---':
                    break
                command_text += self.consume()

            if self.peek(3) != '---':
                raise self.error("Scheduler query commands must end with --- terminator")
            self.consume(3)  # Skip ---

            # Create SchedulerQuery with raw command text
            # Store as single Text node for now - scheduler will parse it later
            queries.append(SchedulerQuery([Text(command_text)]))

            # Check if another command follows
            if self.peek() == ')':
                break

        if self.peek() != ')':
            raise ParserError(
                "Unclosed scheduler query $(\\... - missing closing parenthesis",
                position=start_pos,
                command_snippet=self.text[start_pos:min(start_pos + 40, self.length)] + "..."
            )
        self.consume()  # Skip )

        return queries

    def parse_text(self) -> Text:
        """Parse regular text until special character or terminator"""
        text = ''
        while self.pos < self.length:
            char = self.peek()

            # Stop at special characters (not ? or $ - those are contextual)
            if char in '@#\\':
                break

            # Stop at potential terminators
            if self.peek(3) == '---':
                break

            # Stop at ?( or $( specifically
            if char == '?' and self.pos + 1 < self.length and self.text[self.pos + 1] == '(':
                break
            if char == '$' and self.pos + 1 < self.length and self.text[self.pos + 1] == '(':
                break

            text += self.consume()

        return Text(text)


def parse(text: str) -> Command:
    r"""
    Parse an O command.

    Args:
        text: Command text starting with \ and ending with ---

    Returns:
        Command object with parsed tree

    Example:
        >>> parse(r"\say @opus Hey there ---")
        Command([Text('say '), @opus, Text(' Hey there ')])
    """
    parser = Parser(text)
    return parser.parse_command()


# === Test ===

if __name__ == '__main__':
    # Test basic parsing
    tests = [
        r"\say @opus Hey there ---",
        r"\wake ?(response(@alice) or sleep(5))---",
        r"\spawn @new-entity ---",
        r"\say #general @everyone Check $(\N---) ---",
        r"\name #space @(alice, bob, charlie) ---",
    ]

    for test in tests:
        print(f"\nInput: {test}")
        try:
            result = parse(test)
            print(f"Output: {result}")
        except Exception as e:
            print(f"Error: {e}")
