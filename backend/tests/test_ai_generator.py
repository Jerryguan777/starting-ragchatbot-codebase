"""Integration tests for AIGenerator"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from ai_generator import AIGenerator


class MockContentBlock:
    """Mock for Anthropic API content block"""
    def __init__(self, type, text=None, id=None, name=None, input=None):
        self.type = type
        self.text = text
        self.id = id
        self.name = name
        self.input = input or {}


class MockAPIResponse:
    """Mock for Anthropic API response"""
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client"""
    mock_client = Mock()
    mock_client.messages = Mock()
    return mock_client


@pytest.fixture
def ai_generator(mock_anthropic_client):
    """Create AIGenerator with mocked client"""
    with patch('ai_generator.anthropic.Anthropic', return_value=mock_anthropic_client):
        generator = AIGenerator(api_key="test_key", model="claude-sonnet-4")
        generator.client = mock_anthropic_client
        return generator


class TestAIGeneratorBasic:
    """Test basic AIGenerator functionality"""

    def test_init(self):
        """Test AIGenerator initialization"""
        with patch('ai_generator.anthropic.Anthropic') as mock_anthropic:
            generator = AIGenerator(api_key="test_key", model="claude-sonnet-4")

            assert generator.model == "claude-sonnet-4"
            assert generator.base_params['model'] == "claude-sonnet-4"
            assert generator.base_params['temperature'] == 0
            assert generator.base_params['max_tokens'] == 800
            mock_anthropic.assert_called_once_with(api_key="test_key")

    def test_system_prompt_exists(self):
        """Test that system prompt is defined"""
        assert hasattr(AIGenerator, 'SYSTEM_PROMPT')
        assert len(AIGenerator.SYSTEM_PROMPT) > 0
        assert "course materials" in AIGenerator.SYSTEM_PROMPT.lower()


class TestAIGeneratorWithoutTools:
    """Test AIGenerator without tool usage"""

    def test_generate_response_without_tools(self, ai_generator, mock_anthropic_client):
        """Test generating response without tools"""
        # Mock API response
        mock_response = MockAPIResponse(
            content=[MockContentBlock(type="text", text="This is a response")],
            stop_reason="end_turn"
        )
        mock_anthropic_client.messages.create.return_value = mock_response

        # Generate response
        result = ai_generator.generate_response(query="What is Python?")

        # Verify
        assert result == "This is a response"
        mock_anthropic_client.messages.create.assert_called_once()

        # Check call parameters
        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert call_args['model'] == "claude-sonnet-4"
        assert len(call_args['messages']) == 1
        assert call_args['messages'][0]['content'] == "What is Python?"

    def test_generate_response_with_history(self, ai_generator, mock_anthropic_client):
        """Test generating response with conversation history"""
        mock_response = MockAPIResponse(
            content=[MockContentBlock(type="text", text="Response with context")],
            stop_reason="end_turn"
        )
        mock_anthropic_client.messages.create.return_value = mock_response

        history = "User: Previous question\nAssistant: Previous answer"
        result = ai_generator.generate_response(
            query="Follow-up question",
            conversation_history=history
        )

        assert result == "Response with context"

        # Verify history was included in system prompt
        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert history in call_args['system']


class TestAIGeneratorWithTools:
    """Test AIGenerator with tool usage"""

    def test_generate_response_with_tools_defined(self, ai_generator, mock_anthropic_client, tool_manager):
        """Test that tools are passed to API correctly"""
        mock_response = MockAPIResponse(
            content=[MockContentBlock(type="text", text="Response without tool use")],
            stop_reason="end_turn"
        )
        mock_anthropic_client.messages.create.return_value = mock_response

        # Generate response with tools
        result = ai_generator.generate_response(
            query="What is Python?",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )

        # Verify tools were passed to API
        call_args = mock_anthropic_client.messages.create.call_args[1]
        assert 'tools' in call_args
        assert len(call_args['tools']) == 2
        assert call_args['tool_choice'] == {"type": "auto"}

    def test_tool_execution_flow(self, ai_generator, mock_anthropic_client, tool_manager):
        """Test complete tool execution flow"""
        # Mock initial response with tool use
        tool_use_response = MockAPIResponse(
            content=[
                MockContentBlock(
                    type="tool_use",
                    id="tool_1",
                    name="search_course_content",
                    input={"query": "Python programming"}
                )
            ],
            stop_reason="tool_use"
        )

        # Mock final response after tool execution
        final_response = MockAPIResponse(
            content=[MockContentBlock(type="text", text="Here's what I found about Python...")],
            stop_reason="end_turn"
        )

        # Set up mock to return different responses
        mock_anthropic_client.messages.create.side_effect = [
            tool_use_response,
            final_response
        ]

        # Generate response
        result = ai_generator.generate_response(
            query="Tell me about Python",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )

        # Verify result
        assert result == "Here's what I found about Python..."

        # Verify API was called twice
        assert mock_anthropic_client.messages.create.call_count == 2

        # Verify second call includes tool results
        second_call_args = mock_anthropic_client.messages.create.call_args_list[1][1]
        assert len(second_call_args['messages']) == 2  # Original query + tool results
        assert second_call_args['messages'][1]['role'] == 'user'
        assert second_call_args['messages'][1]['content'][0]['type'] == 'tool_result'

    def test_handle_tool_execution(self, ai_generator, mock_anthropic_client, tool_manager):
        """Test _handle_tool_execution method directly"""
        # Create mock tool use response
        initial_response = MockAPIResponse(
            content=[
                MockContentBlock(
                    type="tool_use",
                    id="tool_123",
                    name="search_course_content",
                    input={"query": "test query"}
                )
            ],
            stop_reason="tool_use"
        )

        base_params = {
            "messages": [{"role": "user", "content": "Test question"}],
            "system": AIGenerator.SYSTEM_PROMPT
        }

        # Mock final response
        final_response = MockAPIResponse(
            content=[MockContentBlock(type="text", text="Final answer")],
            stop_reason="end_turn"
        )
        mock_anthropic_client.messages.create.return_value = final_response

        # Execute
        result = ai_generator._handle_tool_execution(
            initial_response,
            base_params,
            tool_manager
        )

        # Verify
        assert result == "Final answer"
        mock_anthropic_client.messages.create.assert_called_once()

    def test_multiple_tool_calls(self, ai_generator, mock_anthropic_client, tool_manager):
        """Test handling multiple tool calls in one response"""
        # Mock response with multiple tool uses
        tool_use_response = MockAPIResponse(
            content=[
                MockContentBlock(
                    type="tool_use",
                    id="tool_1",
                    name="search_course_content",
                    input={"query": "Python"}
                ),
                MockContentBlock(
                    type="tool_use",
                    id="tool_2",
                    name="get_course_outline",
                    input={"course_name": "Python"}
                )
            ],
            stop_reason="tool_use"
        )

        final_response = MockAPIResponse(
            content=[MockContentBlock(type="text", text="Combined results")],
            stop_reason="end_turn"
        )

        mock_anthropic_client.messages.create.side_effect = [
            tool_use_response,
            final_response
        ]

        result = ai_generator.generate_response(
            query="Tell me about Python courses",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )

        assert result == "Combined results"

        # Verify second call has both tool results
        second_call_args = mock_anthropic_client.messages.create.call_args_list[1][1]
        tool_results = second_call_args['messages'][1]['content']
        assert len(tool_results) == 2
        assert all(tr['type'] == 'tool_result' for tr in tool_results)


class TestAIGeneratorErrorHandling:
    """Test error handling in AIGenerator"""

    def test_api_error_handling(self, ai_generator, mock_anthropic_client):
        """Test handling of API errors"""
        mock_anthropic_client.messages.create.side_effect = Exception("API Error")

        with pytest.raises(Exception) as exc_info:
            ai_generator.generate_response(query="Test question")

        assert "API Error" in str(exc_info.value)

    def test_tool_execution_with_nonexistent_tool(self, ai_generator, mock_anthropic_client, tool_manager):
        """Test tool execution when tool doesn't exist"""
        # Mock response requesting nonexistent tool
        tool_use_response = MockAPIResponse(
            content=[
                MockContentBlock(
                    type="tool_use",
                    id="tool_1",
                    name="nonexistent_tool",
                    input={"query": "test"}
                )
            ],
            stop_reason="tool_use"
        )

        final_response = MockAPIResponse(
            content=[MockContentBlock(type="text", text="Handled gracefully")],
            stop_reason="end_turn"
        )

        mock_anthropic_client.messages.create.side_effect = [
            tool_use_response,
            final_response
        ]

        result = ai_generator.generate_response(
            query="Test",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )

        # Should still get a response
        assert result == "Handled gracefully"

        # Verify tool error was passed back to API
        second_call_args = mock_anthropic_client.messages.create.call_args_list[1][1]
        tool_result = second_call_args['messages'][1]['content'][0]
        assert "not found" in tool_result['content']
