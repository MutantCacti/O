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
class SchedulerQuery:
    r"""Scheduler command: $(\command---)"""
    command: List['Node']  # Parsed command inside $(\...---)

    def __repr__(self):
        return f'$({self.command})'


# Boolean expression nodes for conditions
@dataclass
class BoolOr:
    """Boolean OR: left or right"""
    left: 'ConditionExpr'
    right: 'ConditionExpr'

    def __repr__(self):
        return f'({self.left} or {self.right})'


@dataclass
class BoolAnd:
    """Boolean AND: left and right"""
    left: 'ConditionExpr'
    right: 'ConditionExpr'

    def __repr__(self):
        return f'({self.left} and {self.right})'


@dataclass
class BoolNot:
    """Boolean NOT: not operand"""
    operand: 'ConditionExpr'

    def __repr__(self):
        return f'(not {self.operand})'


# Comparison nodes
@dataclass
class Compare:
    """Comparison: left op right where op is <, >, or ="""
    left: 'ConditionExpr'
    op: str  # '<', '>', or '='
    right: 'ConditionExpr'

    def __repr__(self):
        return f'({self.left} {self.op} {self.right})'


# A condition expression leaf can be a query, text literal, or any node
# Internal nodes are BoolOr, BoolAnd, BoolNot, Compare
ConditionExpr = Union['BoolOr', 'BoolAnd', 'BoolNot', 'Compare', SchedulerQuery, 'Text', 'Entity', 'Space']


@dataclass
class Condition:
    """Condition class: ?(expression)

    Contains a boolean expression tree where:
    - Leaves are SchedulerQuery, Text, Entity, Space nodes
    - Internal nodes are BoolOr, BoolAnd, BoolNot
    """
    expression: ConditionExpr

    def __repr__(self):
        return f'?({self.expression})'


# Union type for all node types (excluding internal boolean nodes)
Node = Union[Text, Entity, Space, Condition, SchedulerQuery]


@dataclass
class Command:
    r"""Parsed command: \name args ---"""
    name: str  # Command name (first word after backslash)
    content: List[Node]  # Arguments (everything after the name)

    def __repr__(self):
        return f'Command({self.name}, {self.content})'


# === Condition Parser ===

class ConditionParser:
    r"""
    Parser for boolean expressions inside ?().

    Grammar (precedence low to high):
        or_expr  := and_expr ('or' and_expr)*
        and_expr := not_expr ('and' not_expr)*
        not_expr := 'not' not_expr | atom
        atom     := '$(' query ')' | '(' or_expr ')' | literal

    Examples:
        $(\incoming---)
        $(\incoming---) or $(\sleep 60---)
        not $(\busy---)
        ($(\a---) or $(\b---)) and $(\c---)
    """

    def __init__(self, text: str, nesting_depth: int = 0):
        self.text = text
        self.pos = 0
        self.length = len(text)
        self.nesting_depth = nesting_depth

        if nesting_depth > MAX_NESTING_DEPTH:
            raise ParserError(
                f"Condition nesting too deep (depth {nesting_depth}). Maximum is {MAX_NESTING_DEPTH}.",
                position=0
            )

    def skip_whitespace(self):
        """Skip whitespace characters."""
        while self.pos < self.length and self.text[self.pos] in ' \t\n\r':
            self.pos += 1

    def peek(self, n: int = 1) -> str:
        """Peek at next n characters."""
        return self.text[self.pos:self.pos + n]

    def consume(self, n: int = 1) -> str:
        """Consume and return next n characters."""
        result = self.text[self.pos:self.pos + n]
        self.pos += n
        return result

    def match_keyword(self, keyword: str) -> bool:
        """Check if next chars match keyword (case insensitive) at word boundary."""
        self.skip_whitespace()
        kw_len = len(keyword)
        if self.pos + kw_len > self.length:
            return False
        if self.text[self.pos:self.pos + kw_len].lower() != keyword.lower():
            return False
        # Must not be preceded by alphanumeric (word boundary check)
        if self.pos > 0:
            prev_char = self.text[self.pos - 1]
            if prev_char.isalnum() or prev_char == '_':
                return False
        # Must be followed by non-alphanumeric or end
        if self.pos + kw_len < self.length:
            next_char = self.text[self.pos + kw_len]
            if next_char.isalnum() or next_char == '_':
                return False
        return True

    def consume_keyword(self, keyword: str):
        """Consume a keyword."""
        self.skip_whitespace()
        self.pos += len(keyword)

    def parse_or_expr(self) -> ConditionExpr:
        """Parse: and_expr ('or' and_expr)*"""
        left = self.parse_and_expr()

        while self.match_keyword('or'):
            self.consume_keyword('or')
            right = self.parse_and_expr()
            left = BoolOr(left, right)

        return left

    def parse_and_expr(self) -> ConditionExpr:
        """Parse: not_expr ('and' not_expr)*"""
        left = self.parse_not_expr()

        while self.match_keyword('and'):
            self.consume_keyword('and')
            right = self.parse_not_expr()
            left = BoolAnd(left, right)

        return left

    def parse_not_expr(self) -> ConditionExpr:
        """Parse: 'not' not_expr | compare_expr"""
        if self.match_keyword('not'):
            self.consume_keyword('not')
            operand = self.parse_not_expr()
            return BoolNot(operand)

        return self.parse_compare_expr()

    def parse_compare_expr(self) -> ConditionExpr:
        """Parse: atom (('<' | '>' | '=') atom)?"""
        left = self.parse_atom()

        self.skip_whitespace()
        if self.pos < self.length and self.peek() in '<>=':
            op = self.consume()
            right = self.parse_atom()
            return Compare(left, op, right)

        return left

    def parse_atom(self) -> ConditionExpr:
        """Parse: '$(' query ')' | '?(' nested ')' | func(args) | '(' or_expr ')' | literal"""
        self.skip_whitespace()

        if self.pos >= self.length:
            raise ParserError(
                "Unexpected end of condition expression",
                position=self.pos
            )

        # Check for $(\...) scheduler query
        if self.peek(2) == '$(':
            return self.parse_scheduler_query()

        # Check for ?(...) nested condition - parse recursively
        if self.peek(2) == '?(':
            return self.parse_nested_condition()

        # Check for ( grouped expression )
        if self.peek() == '(':
            self.consume()  # Skip (
            expr = self.parse_or_expr()
            self.skip_whitespace()
            if self.peek() != ')':
                raise ParserError(
                    "Expected ')' to close grouped expression",
                    position=self.pos,
                    command_snippet=self.text[max(0, self.pos - 10):self.pos + 10]
                )
            self.consume()  # Skip )
            return expr

        # Check for function call syntax: identifier(args)
        # This is sugar for $(\identifier args---)
        func_call = self.try_parse_function_call()
        if func_call is not None:
            return func_call

        # Otherwise it's a literal (text until operator or end)
        return self.parse_literal()

    def try_parse_function_call(self) -> ConditionExpr | None:
        r"""
        Try to parse function call syntax: identifier(args).

        This is syntactic sugar for $(\identifier args---).
        Examples:
            response(@bob) → $(\response @bob---)
            sleep(60) → $(\sleep 60---)
            incoming() → $(\incoming---)

        Returns SchedulerQuery if successful, None if not a function call.
        """
        # Save position for backtracking
        saved_pos = self.pos

        # Try to read an identifier (alphanumeric + underscore)
        identifier = ''
        while self.pos < self.length and (self.text[self.pos].isalnum() or self.text[self.pos] == '_'):
            identifier += self.consume()

        if not identifier:
            self.pos = saved_pos
            return None

        # Must be followed by (
        if self.pos >= self.length or self.peek() != '(':
            self.pos = saved_pos
            return None

        self.consume()  # Skip (

        # Find matching ) - handle nested parens
        depth = 1
        args_start = self.pos
        while depth > 0 and self.pos < self.length:
            if self.peek() == '(':
                depth += 1
            elif self.peek() == ')':
                depth -= 1
            if depth > 0:
                self.pos += 1

        if depth > 0:
            # Unclosed paren - backtrack
            self.pos = saved_pos
            return None

        args = self.text[args_start:self.pos].strip()
        self.consume()  # Skip )

        # Build nodes directly: [Text(identifier), ...args...]
        # This is equivalent to what $(\identifier args---) would produce
        nodes = [Text(identifier)]

        if args:
            # Parse the args to extract entities, spaces, etc.
            args_parser = Parser(args + " ---", nesting_depth=self.nesting_depth + 1)
            arg_nodes = args_parser.parse_until('---')
            nodes.extend(arg_nodes)

        return SchedulerQuery(nodes)

    def parse_nested_condition(self) -> ConditionExpr:
        """Parse nested ?(...) condition."""
        self.consume(2)  # Skip ?(

        # Find matching )
        depth = 1
        start_pos = self.pos
        while depth > 0 and self.pos < self.length:
            if self.peek() == '(':
                depth += 1
            elif self.peek() == ')':
                depth -= 1
            if depth > 0:
                self.pos += 1

        if depth > 0:
            raise ParserError(
                "Unclosed nested condition ?(...)",
                position=start_pos
            )

        content = self.text[start_pos:self.pos]
        self.consume()  # Skip )

        # Recursively parse with increased nesting depth
        nested_parser = ConditionParser(content, nesting_depth=self.nesting_depth + 1)
        return nested_parser.parse_or_expr()

    def parse_scheduler_query(self) -> SchedulerQuery:
        r"""Parse $(\command---)"""
        self.consume(2)  # Skip $(

        if self.peek() != '\\':
            raise ParserError(
                "Scheduler queries must start with $(\\",
                position=self.pos
            )
        self.consume()  # Skip \

        # Find the closing ) - need to track depth for nested parens
        start_pos = self.pos
        depth = 1
        while self.pos < self.length and depth > 0:
            if self.peek() == '(':
                depth += 1
            elif self.peek() == ')':
                depth -= 1
            if depth > 0:
                self.pos += 1

        if depth > 0:
            raise ParserError(
                "Unclosed scheduler query $(...)",
                position=start_pos
            )

        # Extract command text (everything between $( and ))
        command_text = self.text[start_pos:self.pos]
        self.consume()  # Skip )

        # Parse the command content to extract nodes
        # The command_text should end with ---
        sub_parser = Parser(command_text, nesting_depth=self.nesting_depth + 1)
        nodes = sub_parser.parse_until('---')

        return SchedulerQuery(nodes)

    def parse_literal(self) -> ConditionExpr:
        """Parse a literal value (text, @entity, #space)."""
        self.skip_whitespace()

        # Check for @entity
        if self.peek() == '@':
            self.consume()
            name = ''
            while self.pos < self.length and (self.text[self.pos].isalnum() or self.text[self.pos] in '-_'):
                name += self.consume()
            if name:
                return Entity(name)
            raise ParserError("Empty entity name after @", position=self.pos)

        # Check for #space - only if followed by alphanumeric, _, or (
        if self.peek() == '#':
            # Look ahead to see if this is a space reference
            next_pos = self.pos + 1
            if next_pos < self.length:
                next_char = self.text[next_pos]
                if next_char.isalnum() or next_char == '_' or next_char == '(':
                    self.consume()  # consume #
                    name = ''
                    while self.pos < self.length and (self.text[self.pos].isalnum() or self.text[self.pos] in '-_'):
                        name += self.consume()
                    if name:
                        return Space(name)
                    raise ParserError("Empty space name after #", position=self.pos)
            # Otherwise treat # as text (e.g., markdown headers ##)

        # Otherwise collect text until we hit an operator, paren, or special char
        text = ''
        while self.pos < self.length:
            # Stop at boolean operators
            if self.match_keyword('or') or self.match_keyword('and') or self.match_keyword('not'):
                break
            # Stop at comparison operators and special chars
            if self.peek() in '()$@#<>=':
                break
            text += self.consume()

        text = text.strip()
        if not text:
            raise ParserError(
                "Expected expression in condition",
                position=self.pos,
                command_snippet=self.text[max(0, self.pos - 10):self.pos + 10]
            )

        return Text(text)


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
        r"""Parse a command: \name args ---"""
        # Expect leading \
        if self.peek() != '\\':
            raise self.error("Commands must start with backslash (\\)")
        self.consume()  # Skip \

        # Extract command name (first word, letters/numbers/underscores only)
        self.skip_whitespace()
        name_start = self.pos
        while self.pos < self.length:
            char = self.peek()
            if char.isalnum() or char == '_':
                self.consume()
            else:
                break

        name = self.text[name_start:self.pos]
        if not name:
            raise self.error("Command must have a name after backslash (\\name)")

        # Parse arguments until ---
        content = self.parse_until('---')

        # Consume ---
        if self.peek(3) != '---':
            raise self.error("Commands must end with --- terminator")
        self.consume(3)

        return Command(name=name, content=content)

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
                # Only parse as space if followed by alphanumeric, _, or (
                # Otherwise parse_text will handle it as regular text
                next_pos = self.pos + 1
                if next_pos < self.length:
                    next_char = self.text[next_pos]
                    if next_char.isalnum() or next_char == '_' or next_char == '(':
                        nodes.extend(self.parse_space())
                    else:
                        # Let parse_text handle non-space # (e.g., markdown ##)
                        nodes.append(self.parse_text())
                else:
                    nodes.append(self.parse_text())
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
        """Parse ?(expression) with boolean operators.

        Grammar (precedence low to high):
            or_expr  := and_expr ('or' and_expr)*
            and_expr := not_expr ('and' not_expr)*
            not_expr := 'not' not_expr | atom
            atom     := '$(' query ')' | '(' or_expr ')' | literal
        """
        self.consume()  # Skip ?

        if self.peek() != '(':
            raise self.error("Conditions must start with ?( - missing opening parenthesis after ?")
        self.consume()  # Skip (

        # Find matching ) to get content bounds
        depth = 1
        content_start = self.pos
        while depth > 0 and self.pos < self.length:
            if self.peek() == '(':
                depth += 1
            elif self.peek() == ')':
                depth -= 1
            if depth > 0:
                self.consume()

        if depth > 0 or self.pos >= self.length:
            raise ParserError(
                "Unclosed condition ?(... - missing closing parenthesis",
                position=content_start,
                command_snippet=self.text[content_start:min(content_start + 40, self.length)] + "..."
            )

        content = self.text[content_start:self.pos]
        self.consume()  # Skip closing )

        # Parse the boolean expression
        cond_parser = ConditionParser(content, nesting_depth=self.nesting_depth + 1)
        expression = cond_parser.parse_or_expr()

        # Validate all input was consumed
        cond_parser.skip_whitespace()
        if cond_parser.pos < cond_parser.length:
            remaining = content[cond_parser.pos:].strip()
            if remaining:
                raise ParserError(
                    f"Unexpected content in condition after valid expression: '{remaining[:20]}{'...' if len(remaining) > 20 else ''}'",
                    position=content_start + cond_parser.pos,
                    command_snippet=content
                )

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

            # Stop at @ and \ always
            if char in '@\\':
                break

            # Stop at # only if it's a valid space marker (followed by alnum, _, or ()
            if char == '#':
                next_pos = self.pos + 1
                if next_pos < self.length:
                    next_char = self.text[next_pos]
                    if next_char.isalnum() or next_char == '_' or next_char == '(':
                        break
                    # Otherwise consume # as regular text (e.g., markdown ##)
                else:
                    # # at end of input - consume as text
                    pass

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
