"""
Comprehensive pytest suite for O grammar parser

Tests all grammar classes and parser methods with full coverage
including edge cases, error conditions, and boundary conditions.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path (grammar/)
grammar_dir = Path(__file__).parent.parent
sys.path.insert(0, str(grammar_dir))

from parser import (
    parse, Parser, Command, Text, Entity, Space,
    Condition, SchedulerQuery, ParserError,
    MAX_COMMAND_LENGTH, MAX_NESTING_DEPTH
)


# ============================================================
# Grammar Class Tests
# ============================================================

class TestGrammarClasses:
    """Test the grammar class data structures"""

    def test_text_creation(self):
        """Test Text node creation and repr"""
        text = Text("hello world")
        assert text.text == "hello world"
        assert repr(text) == 'Text("hello world")'

    def test_entity_creation(self):
        """Test Entity node creation and repr"""
        entity = Entity("alice")
        assert entity.name == "alice"
        assert repr(entity) == '@alice'

    def test_space_creation(self):
        """Test Space node creation and repr"""
        space = Space("general")
        assert space.name == "general"
        assert repr(space) == '#general'

    def test_condition_creation(self):
        """Test Condition node creation"""
        cond = Condition([Text("x > 5")])
        assert len(cond.expression) == 1
        assert isinstance(cond.expression[0], Text)

    def test_scheduler_query_creation(self):
        """Test SchedulerQuery node creation"""
        query = SchedulerQuery([Text("N")])
        assert len(query.command) == 1
        assert isinstance(query.command[0], Text)

    def test_command_creation(self):
        """Test Command node creation"""
        cmd = Command([Text("say"), Entity("alice")])
        assert len(cmd.content) == 2
        assert isinstance(cmd.content[0], Text)
        assert isinstance(cmd.content[1], Entity)


# ============================================================
# Parser Utility Method Tests
# ============================================================

class TestParserUtilities:
    """Test Parser helper methods"""

    def test_peek(self):
        """Test peek method"""
        parser = Parser("hello")
        assert parser.peek() == 'h'
        assert parser.peek(3) == 'hel'
        assert parser.pos == 0  # peek doesn't advance

    def test_consume(self):
        """Test consume method"""
        parser = Parser("hello")
        assert parser.consume() == 'h'
        assert parser.pos == 1
        assert parser.consume(2) == 'el'
        assert parser.pos == 3

    def test_skip_whitespace(self):
        """Test whitespace skipping"""
        parser = Parser("   hello")
        parser.skip_whitespace()
        assert parser.pos == 3
        assert parser.peek() == 'h'


# ============================================================
# Single Entity/Space Parsing Tests
# ============================================================

class TestSingleEntitySpace:
    """Test parsing single @entity and #space"""

    @pytest.mark.parametrize("input_str,expected_name", [
        (r"\say @alice ---", "alice"),
        (r"\say @bob ---", "bob"),
        (r"\say @user-name ---", "user-name"),
        (r"\say @user_name ---", "user_name"),
        (r"\say @user123 ---", "user123"),
    ])
    def test_single_entity_names(self, input_str, expected_name):
        """Test various entity name formats"""
        result = parse(input_str)
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(entities) == 1
        assert entities[0].name == expected_name

    @pytest.mark.parametrize("input_str,expected_name", [
        (r"\say #general ---", "general"),
        (r"\say #my-space ---", "my-space"),
        (r"\say #space_name ---", "space_name"),
        (r"\say #room123 ---", "room123"),
    ])
    def test_single_space_names(self, input_str, expected_name):
        """Test various space name formats"""
        result = parse(input_str)
        spaces = [n for n in result.content if isinstance(n, Space)]
        assert len(spaces) == 1
        assert spaces[0].name == expected_name


# ============================================================
# Multi-Entity/Space Parsing Tests
# ============================================================

class TestMultiEntitySpace:
    """Test parsing @(a,b,c) and #(x,y,z)"""

    def test_multi_entity_basic(self):
        """Test basic multi-entity parsing"""
        result = parse(r"\name @(alice, bob, charlie) ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(entities) == 3
        assert entities[0].name == "alice"
        assert entities[1].name == "bob"
        assert entities[2].name == "charlie"

    def test_multi_space_basic(self):
        """Test basic multi-space parsing"""
        result = parse(r"\broadcast #(room1, room2, room3) ---")
        spaces = [n for n in result.content if isinstance(n, Space)]
        assert len(spaces) == 3
        assert spaces[0].name == "room1"
        assert spaces[1].name == "room2"
        assert spaces[2].name == "room3"

    def test_multi_entity_whitespace_trimming(self):
        """Test that whitespace around names is trimmed"""
        result = parse(r"\test @(alice , bob  ,  charlie) ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert entities[0].name == "alice"
        assert entities[1].name == "bob"
        assert entities[2].name == "charlie"

    def test_single_entity_in_parens(self):
        """Test that @(alice) works like @alice"""
        result = parse(r"\test @(alice) ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(entities) == 1
        assert entities[0].name == "alice"

    def test_multi_entity_with_hyphens_underscores(self):
        """Test entity names with special characters in multi-entity"""
        result = parse(r"\test @(user-one, user_two, user3) ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(entities) == 3
        assert entities[0].name == "user-one"
        assert entities[1].name == "user_two"
        assert entities[2].name == "user3"


# ============================================================
# Condition Parsing Tests
# ============================================================

class TestConditionParsing:
    """Test ?(expression) parsing"""

    def test_simple_condition(self):
        """Test simple condition"""
        result = parse(r"\wake ?(t > 100) ---")
        conditions = [n for n in result.content if isinstance(n, Condition)]
        assert len(conditions) == 1

    def test_condition_with_entity(self):
        """Test condition containing entity reference"""
        result = parse(r"\wake ?(response(@alice)) ---")
        conditions = [n for n in result.content if isinstance(n, Condition)]
        assert len(conditions) == 1
        # Check entity is inside condition
        entities_in_cond = [n for n in conditions[0].expression if isinstance(n, Entity)]
        assert len(entities_in_cond) == 1
        assert entities_in_cond[0].name == "alice"

    def test_condition_with_boolean_logic(self):
        """Test condition with boolean operators"""
        result = parse(r"\wake ?(response(@alice) or sleep(30)) ---")
        conditions = [n for n in result.content if isinstance(n, Condition)]
        assert len(conditions) == 1
        # Should have entity and text nodes
        assert len(conditions[0].expression) > 1

    def test_nested_parentheses_in_condition(self):
        """Test condition with nested parentheses"""
        result = parse(r"\check ?(count(#space) > (10 + 5)) ---")
        conditions = [n for n in result.content if isinstance(n, Condition)]
        assert len(conditions) == 1

    def test_condition_with_scheduler_query(self):
        """Test scheduler query inside condition"""
        result = parse(r"\wake ?($(\N---) > 10) ---")
        conditions = [n for n in result.content if isinstance(n, Condition)]
        assert len(conditions) == 1
        # Check query is inside condition
        queries_in_cond = [n for n in conditions[0].expression if isinstance(n, SchedulerQuery)]
        assert len(queries_in_cond) == 1


# ============================================================
# Scheduler Query Parsing Tests
# ============================================================

class TestSchedulerQueryParsing:
    r"""Test $(\command---) parsing"""

    def test_single_scheduler_query(self):
        """Test single scheduler query"""
        result = parse(r"\check $(\N---) ---")
        queries = [n for n in result.content if isinstance(n, SchedulerQuery)]
        assert len(queries) == 1
        assert queries[0].command[0].text == "N"

    def test_multiple_scheduler_queries(self):
        """Test multiple commands in one $(...)"""
        result = parse(r"\monitor $(\test---\N---\O---) ---")
        queries = [n for n in result.content if isinstance(n, SchedulerQuery)]
        assert len(queries) == 3
        assert queries[0].command[0].text == "test"
        assert queries[1].command[0].text == "\\N"
        assert queries[2].command[0].text == "\\O"

    def test_scheduler_query_with_entity(self):
        """Test scheduler query with entity reference"""
        result = parse(r"\check $(\budget @alice ---) ---")
        queries = [n for n in result.content if isinstance(n, SchedulerQuery)]
        assert len(queries) == 1
        # Content should include @alice in raw text
        assert "@alice" in queries[0].command[0].text

    def test_two_separate_scheduler_queries(self):
        """Test multiple $(...)  blocks separately"""
        result = parse(r"\check $(\N---) and $(\O---) ---")
        queries = [n for n in result.content if isinstance(n, SchedulerQuery)]
        assert len(queries) == 2


# ============================================================
# Complex Combination Tests
# ============================================================

class TestComplexCombinations:
    """Test complex combinations of grammar elements"""

    def test_all_features_together(self):
        """Test multi-entity + multi-space + multi-query in one command"""
        result = parse(r"\alert @(alice, bob) #(room1, room2) Check $(\N---\O---) now ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        spaces = [n for n in result.content if isinstance(n, Space)]
        queries = [n for n in result.content if isinstance(n, SchedulerQuery)]

        assert len(entities) == 2
        assert len(spaces) == 2
        assert len(queries) == 2

    def test_multiple_entities_and_spaces_interspersed(self):
        """Test entities and spaces mixed throughout"""
        result = parse(r"\say @alice #room1 and @bob #room2 ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        spaces = [n for n in result.content if isinstance(n, Space)]

        assert len(entities) == 2
        assert len(spaces) == 2

    def test_condition_with_complex_expression(self):
        """Test condition with multiple elements"""
        result = parse(r"\wake ?(response(@alice) or (response(@bob) and sleep(30))) ---")
        conditions = [n for n in result.content if isinstance(n, Condition)]
        assert len(conditions) == 1
        # Should have multiple entities inside
        entities_in_cond = [n for n in conditions[0].expression if isinstance(n, Entity)]
        assert len(entities_in_cond) == 2


# ============================================================
# Command Structure Tests
# ============================================================

class TestCommandStructure:
    """Test overall command parsing"""

    def test_empty_command(self):
        """Test command with no arguments"""
        result = parse(r"\noop ---")
        assert isinstance(result, Command)
        assert len(result.content) >= 1  # At least the command name

    def test_command_with_only_text(self):
        """Test command with only text content"""
        result = parse(r"\say Hello world ---")
        texts = [n for n in result.content if isinstance(n, Text)]
        assert len(texts) >= 1

    def test_command_preserves_order(self):
        """Test that nodes appear in correct order"""
        result = parse(r"\say @alice then #room then text ---")
        # Should be: Text("say "), Entity("alice"), Text(" then "), Space("room"), Text(" then text ")
        assert isinstance(result.content[1], Entity)
        assert isinstance(result.content[3], Space)

    def test_whitespace_preservation_in_text(self):
        """Test that whitespace in text is preserved"""
        result = parse(r"\say    multiple    spaces ---")
        texts = [n for n in result.content if isinstance(n, Text)]
        # Should preserve multiple spaces
        combined_text = ''.join(t.text for t in texts)
        assert "    " in combined_text


# ============================================================
# Error Condition Tests
# ============================================================

class TestErrorConditions:
    """Test parser error handling"""

    def test_missing_terminator(self):
        """Test error when --- is missing"""
        with pytest.raises(ParserError, match="Commands must end with"):
            parse(r"\say @alice")

    def test_invalid_start(self):
        """Test error when command doesn't start with backslash"""
        with pytest.raises(ParserError, match="Commands must start with backslash"):
            parse(r"say @alice ---")

    def test_unclosed_entity_group(self):
        """Test error for unclosed @(...)"""
        with pytest.raises(ParserError, match="Unclosed entity group"):
            parse(r"\test @(alice, bob ---")

    def test_unclosed_space_group(self):
        """Test error for unclosed #(...)"""
        with pytest.raises(ParserError, match="Unclosed space group"):
            parse(r"\test #(room1, room2 ---")

    def test_unclosed_condition(self):
        """Test error for unclosed ?(...)"""
        with pytest.raises(ParserError, match="Unclosed"):
            parse(r"\wake ?(response(@alice) ---")

    def test_unclosed_scheduler_query(self):
        """Test error for unclosed $(...)"""
        with pytest.raises(ParserError, match="Unclosed scheduler query"):
            parse(r"\check $(\N--- ---")

    def test_invalid_scheduler_query_start(self):
        """Test error for $ not followed by (\\"""
        with pytest.raises(ParserError, match="Scheduler queries must start"):
            parse(r"\check $(N) ---")


# ============================================================
# Edge Case Tests
# ============================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_entity_name_with_numbers(self):
        """Test entity names can contain numbers"""
        result = parse(r"\say @user123 ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert entities[0].name == "user123"

    def test_empty_text_nodes(self):
        """Test handling of empty text between elements"""
        result = parse(r"\say @alice@bob ---")
        # Should have entities but minimal text between
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(entities) == 2

    def test_special_characters_in_text(self):
        """Test text can contain special characters (when not starting syntax)"""
        result = parse(r"\say Hello! How are you? ---")
        # Should parse - ? in middle of text is fine
        assert isinstance(result, Command)

    def test_consecutive_spaces_entities(self):
        """Test consecutive spaces and entities"""
        result = parse(r"\say #room1 #room2 @alice @bob ---")
        spaces = [n for n in result.content if isinstance(n, Space)]
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(spaces) == 2
        assert len(entities) == 2

    def test_long_command(self):
        """Test parsing very long command"""
        long_text = "word " * 100
        result = parse(rf"\say {long_text} ---")
        assert isinstance(result, Command)

    def test_keyword_me(self):
        """Test @me keyword works like any entity"""
        result = parse(r"\say @me Hello ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert entities[0].name == "me"


# ============================================================
# Backward Compatibility Tests
# ============================================================

class TestBackwardCompatibility:
    """Ensure changes maintain backward compatibility"""

    def test_single_entity_still_works(self):
        """Test single @entity works as before"""
        result = parse(r"\say @alice ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(entities) == 1
        assert hasattr(entities[0], 'name')  # New API
        assert entities[0].name == "alice"

    def test_single_space_still_works(self):
        """Test single #space works as before"""
        result = parse(r"\say #general ---")
        spaces = [n for n in result.content if isinstance(n, Space)]
        assert len(spaces) == 1
        assert hasattr(spaces[0], 'name')  # New API
        assert spaces[0].name == "general"

    def test_single_query_still_works(self):
        r"""Test single $(\cmd---) works as before"""
        result = parse(r"\check $(\N---) ---")
        queries = [n for n in result.content if isinstance(n, SchedulerQuery)]
        assert len(queries) == 1


# ============================================================
# Integration Tests
# ============================================================

class TestIntegration:
    """Test realistic command examples"""

    def test_dm_message(self):
        """Test DM message command"""
        result = parse(r"\say @opus Quick question about the spec ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(entities) == 1
        assert entities[0].name == "opus"

    def test_space_post_with_mention(self):
        """Test post to space with mention"""
        result = parse(r"\say #general @alice Can you review? ---")
        spaces = [n for n in result.content if isinstance(n, Space)]
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(spaces) == 1
        assert len(entities) == 1

    def test_spawn_command(self):
        """Test entity spawn"""
        result = parse(r"\spawn @new-worker ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(entities) == 1
        assert entities[0].name == "new-worker"

    def test_name_command(self):
        """Test space naming with multiple entities"""
        result = parse(r"\name #workspace @(me, worker) ---")
        spaces = [n for n in result.content if isinstance(n, Space)]
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(spaces) == 1
        assert len(entities) == 2

    def test_wake_condition(self):
        """Test wake with condition"""
        result = parse(r"\wake ?(response(@alice) or sleep(30)) ---")
        conditions = [n for n in result.content if isinstance(n, Condition)]
        assert len(conditions) == 1

    def test_budget_transfer(self):
        """Test budget transfer command"""
        result = parse(r"\givebudget @worker 5 ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(entities) == 1
        assert entities[0].name == "worker"

    def test_status_introspection(self):
        """Test status command (no args)"""
        result = parse(r"\status ---")
        assert isinstance(result, Command)
        # Should just have command name
        texts = [n for n in result.content if isinstance(n, Text)]
        assert len(texts) >= 1


# ============================================================
# Validation Tests (New)
# ============================================================

class TestValidation:
    """Test new validation features"""

    def test_empty_entity_name(self):
        """Test that @ with no name is rejected"""
        with pytest.raises(ParserError, match="Empty entity name"):
            parse(r"\test @ ---")

    def test_empty_entity_group(self):
        """Test that @() is rejected"""
        with pytest.raises(ParserError, match="Empty entity group"):
            parse(r"\test @() ---")

    def test_empty_space_name(self):
        """Test that # with no name is rejected"""
        with pytest.raises(ParserError, match="Empty space name"):
            parse(r"\test # ---")

    def test_empty_space_group(self):
        """Test that #() is rejected"""
        with pytest.raises(ParserError, match="Empty space group"):
            parse(r"\test #() ---")

    def test_invalid_entity_name_starts_with_hyphen(self):
        """Test that entity names can't start with -"""
        with pytest.raises(ParserError, match="Invalid entity name"):
            parse(r"\test @-invalid ---")

    def test_invalid_entity_name_starts_with_underscore(self):
        """Test that entity names can't start with _"""
        with pytest.raises(ParserError, match="Invalid entity name"):
            parse(r"\test @_invalid ---")

    def test_invalid_space_name_starts_with_hyphen(self):
        """Test that space names can't start with -"""
        with pytest.raises(ParserError, match="Invalid space name"):
            parse(r"\test #-invalid ---")

    def test_valid_entity_names(self):
        """Test that valid entity names work"""
        # These should all parse successfully
        test_cases = [
            r"\test @alice ---",
            r"\test @user123 ---",
            r"\test @user-name ---",
            r"\test @user_name ---",
            r"\test @123user ---",
        ]
        for cmd in test_cases:
            result = parse(cmd)
            assert isinstance(result, Command)

    def test_command_too_long(self):
        """Test that very long commands are rejected"""
        long_cmd = r"\test " + "x" * (MAX_COMMAND_LENGTH + 100) + " ---"
        with pytest.raises(ParserError, match="Command too long"):
            parse(long_cmd)

    def test_nesting_too_deep(self):
        """Test that deeply nested structures are rejected"""
        # Build deeply nested condition
        nested = r"\test ?("
        for i in range(MAX_NESTING_DEPTH + 2):
            nested += "?("
        nested += "x" + ")" * (MAX_NESTING_DEPTH + 3) + " ---"

        with pytest.raises(ParserError, match="nesting too deep"):
            parse(nested)

    def test_valid_nesting_works(self):
        """Test that reasonable nesting works"""
        nested = r"\wake ?(response(@alice) and ?($(\N---) > 10)) ---"
        result = parse(nested)
        assert isinstance(result, Command)

    def test_error_includes_position(self):
        """Test that parser errors include position info"""
        try:
            parse(r"\test @---")
        except ParserError as e:
            assert e.position is not None
            assert "position" in str(e)

    def test_error_includes_snippet(self):
        """Test that parser errors include command snippet"""
        try:
            parse(r"\test @invalid!name ---")
        except ParserError as e:
            assert e.command_snippet is not None
            assert "Near:" in str(e)


# ============================================================
# Real-World Command Tests (from DeepSeek roleplay)
# ============================================================

class TestRealWorldCommands:
    """Test commands a new instance would actually try"""

    def test_self_discovery_commands(self):
        """Commands for discovering self and environment"""
        commands = [
            r"\whoami ---",
            r"\status @me ---",
            r"\whereami ---",
        ]
        for cmd in commands:
            result = parse(cmd)
            assert isinstance(result, Command)

    def test_system_state_queries(self):
        """Querying system state with scheduler"""
        result = parse(r"\check $(\N---) ---")
        queries = [n for n in result.content if isinstance(n, SchedulerQuery)]
        assert len(queries) == 1

        # Multiple queries in one command
        result = parse(r"\stats $(\N---) entities, $(\M---) messages ---")
        queries = [n for n in result.content if isinstance(n, SchedulerQuery)]
        assert len(queries) == 2

    def test_multi_element_combinations(self):
        """Complex multi-entity, multi-space, multi-query commands"""
        result = parse(r"\multi $(\a---\b---\c---) @(x,y,z) #(1,2,3) ---")

        entities = [n for n in result.content if isinstance(n, Entity)]
        spaces = [n for n in result.content if isinstance(n, Space)]
        queries = [n for n in result.content if isinstance(n, SchedulerQuery)]

        assert len(entities) == 3
        assert len(spaces) == 3
        assert len(queries) == 3

    def test_communication_patterns(self):
        """Real communication patterns entities would use"""
        # DM to self
        result = parse(r"\say @me Hello, I exist ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(entities) == 1
        assert entities[0].name == "me"

        # Broadcast to multiple spaces
        result = parse(r"\broadcast #(general, dev) Hello from @me ---")
        spaces = [n for n in result.content if isinstance(n, Space)]
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(spaces) == 2
        assert len(entities) == 1

        # Multiple recipients
        result = parse(r"\call @(admin, mentor, guide) ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(entities) == 3

    def test_wake_condition_patterns(self):
        """Real wake conditions entities would set"""
        # Simple response trigger
        result = parse(r"\wake ?(response(@admin)) ---")
        conds = [n for n in result.content if isinstance(n, Condition)]
        assert len(conds) == 1

        # Complex boolean logic
        result = parse(r"\wake ?(response(@mentor) and not busy(@mentor)) ---")
        conds = [n for n in result.content if isinstance(n, Condition)]
        assert len(conds) == 1

        # Time-based
        result = parse(r"\wake ?(sleep(60)) ---")
        conds = [n for n in result.content if isinstance(n, Condition)]
        assert len(conds) == 1

    def test_entity_lifecycle_commands(self):
        """Commands for creating and managing entities"""
        # Spawn with hyphenated name
        result = parse(r"\spawn @worker-1 ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        assert len(entities) == 1
        assert entities[0].name == "worker-1"

        # Join space
        result = parse(r"\join @me #dev ---")
        entities = [n for n in result.content if isinstance(n, Entity)]
        spaces = [n for n in result.content if isinstance(n, Space)]
        assert len(entities) == 1
        assert len(spaces) == 1

    def test_mixed_element_commands(self):
        """Commands with all element types mixed"""
        result = parse(r"\test ?(true) $(\test---) @test-entity #test-space ---")

        entities = [n for n in result.content if isinstance(n, Entity)]
        spaces = [n for n in result.content if isinstance(n, Space)]
        queries = [n for n in result.content if isinstance(n, SchedulerQuery)]
        conds = [n for n in result.content if isinstance(n, Condition)]

        assert len(entities) == 1
        assert len(spaces) == 1
        assert len(queries) == 1
        assert len(conds) == 1


if __name__ == '__main__':
    # Try pytest if available, otherwise run manually
    try:
        import pytest
        pytest.main([__file__, '-v', '--tb=short'])
    except ImportError:
        print("pytest not installed - running tests manually")
        print("=" * 60)
        print("To use pytest:")
        print("  1. Create venv: python3 -m venv venv")
        print("  2. Activate: source venv/bin/activate")
        print("  3. Install: pip install pytest")
        print("  4. Run: pytest test_parser.py -v")
        print("=" * 60)
        print("\nRunning basic test validation...\n")

        # Run a few key tests manually
        test_classes = [
            TestGrammarClasses(),
            TestSingleEntitySpace(),
            TestMultiEntitySpace(),
            TestConditionParsing(),
            TestSchedulerQueryParsing(),
            TestComplexCombinations(),
            TestErrorConditions(),
            TestIntegration(),
        ]

        passed = 0
        failed = 0

        for test_class in test_classes:
            class_name = test_class.__class__.__name__
            print(f"\n{class_name}:")
            for method_name in dir(test_class):
                if method_name.startswith('test_'):
                    try:
                        method = getattr(test_class, method_name)
                        method()
                        print(f"  ✓ {method_name}")
                        passed += 1
                    except Exception as e:
                        print(f"  ✗ {method_name}: {e}")
                        failed += 1

        print(f"\n{'=' * 60}")
        print(f"Results: {passed} passed, {failed} failed")
        print(f"{'=' * 60}")

        if failed > 0:
            sys.exit(1)
