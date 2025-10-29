"""End-to-end tests for RAGSystem"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from rag_system import RAGSystem
from config import Config


class MockConfig:
    """Mock configuration"""
    CHUNK_SIZE = 800
    CHUNK_OVERLAP = 100
    CHROMA_PATH = "./test_chroma_db"
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    MAX_RESULTS = 5
    MAX_HISTORY = 2
    ANTHROPIC_API_KEY = "test_api_key"
    ANTHROPIC_MODEL = "claude-sonnet-4"


@pytest.fixture
def mock_config():
    """Create mock configuration"""
    return MockConfig()


@pytest.fixture
def mock_components():
    """Create mocks for all RAG system components"""
    mocks = {
        'document_processor': Mock(),
        'vector_store': Mock(),
        'ai_generator': Mock(),
        'session_manager': Mock(),
        'tool_manager': Mock(),
        'search_tool': Mock(),
        'outline_tool': Mock()
    }

    # Set up vector store mock
    mocks['vector_store'].search.return_value = Mock(
        documents=["Sample content"],
        metadata=[{'course_title': 'Test Course', 'lesson_number': 1}],
        distances=[0.5],
        error=None,
        is_empty=Mock(return_value=False)
    )

    mocks['vector_store'].get_all_courses_metadata.return_value = [{
        'title': 'Test Course',
        'instructor': 'Test Instructor',
        'course_link': 'https://test.com',
        'lessons': []
    }]

    # Set up AI generator mock
    mocks['ai_generator'].generate_response.return_value = "This is the answer"

    # Set up session manager mock
    mocks['session_manager'].get_conversation_history.return_value = None

    # Set up tool manager mock
    mocks['tool_manager'].get_tool_definitions.return_value = [
        {'name': 'search_course_content'},
        {'name': 'get_course_outline'}
    ]
    mocks['tool_manager'].get_last_sources.return_value = [
        {'title': 'Test Course - Lesson 1', 'url': 'https://test.com/lesson1'}
    ]

    return mocks


@pytest.fixture
def rag_system(mock_config, mock_components):
    """Create RAGSystem with mocked components"""
    with patch('rag_system.DocumentProcessor', return_value=mock_components['document_processor']), \
         patch('rag_system.VectorStore', return_value=mock_components['vector_store']), \
         patch('rag_system.AIGenerator', return_value=mock_components['ai_generator']), \
         patch('rag_system.SessionManager', return_value=mock_components['session_manager']), \
         patch('rag_system.ToolManager', return_value=mock_components['tool_manager']), \
         patch('rag_system.CourseSearchTool', return_value=mock_components['search_tool']), \
         patch('rag_system.CourseOutlineTool', return_value=mock_components['outline_tool']):

        system = RAGSystem(mock_config)
        system.mock_components = mock_components  # Store for test access
        return system


class TestRAGSystemInit:
    """Test RAGSystem initialization"""

    def test_init_components(self, rag_system):
        """Test that all components are initialized"""
        assert rag_system.document_processor is not None
        assert rag_system.vector_store is not None
        assert rag_system.ai_generator is not None
        assert rag_system.session_manager is not None
        assert rag_system.tool_manager is not None

    def test_init_tools_registered(self, rag_system):
        """Test that tools are registered"""
        # Verify both tools were registered
        assert rag_system.mock_components['tool_manager'].register_tool.call_count == 2


class TestRAGSystemQuery:
    """Test RAGSystem query processing"""

    def test_query_basic(self, rag_system):
        """Test basic query without session"""
        response, sources = rag_system.query(
            query="What is Python?",
            session_id=None
        )

        # Verify response
        assert response == "This is the answer"
        assert isinstance(sources, list)

        # Verify AI generator was called with correct parameters
        ai_gen = rag_system.mock_components['ai_generator']
        ai_gen.generate_response.assert_called_once()

        call_kwargs = ai_gen.generate_response.call_args[1]
        assert "What is Python?" in call_kwargs['query']
        assert call_kwargs['tools'] is not None
        assert call_kwargs['tool_manager'] is not None

    def test_query_with_session(self, rag_system):
        """Test query with session ID for conversation history"""
        session_id = "test_session_123"

        response, sources = rag_system.query(
            query="Follow-up question",
            session_id=session_id
        )

        # Verify session manager was used
        session_mgr = rag_system.mock_components['session_manager']
        session_mgr.get_conversation_history.assert_called_once_with(session_id)
        session_mgr.add_exchange.assert_called_once_with(
            session_id,
            "Follow-up question",
            "This is the answer"
        )

    def test_query_sources_returned(self, rag_system):
        """Test that sources are properly returned"""
        response, sources = rag_system.query(query="Test query")

        # Verify sources were retrieved from tool manager
        tool_mgr = rag_system.mock_components['tool_manager']
        tool_mgr.get_last_sources.assert_called_once()

        # Verify sources structure
        assert isinstance(sources, list)
        assert len(sources) > 0
        assert 'title' in sources[0]
        assert 'url' in sources[0]

    def test_query_sources_reset(self, rag_system):
        """Test that sources are reset after retrieval"""
        response, sources = rag_system.query(query="Test query")

        # Verify sources were reset
        tool_mgr = rag_system.mock_components['tool_manager']
        tool_mgr.reset_sources.assert_called_once()

    def test_query_empty_response(self, rag_system):
        """Test handling of empty AI response"""
        # Mock empty response
        rag_system.mock_components['ai_generator'].generate_response.return_value = ""

        response, sources = rag_system.query(query="Test")

        assert response == ""
        assert isinstance(sources, list)

    def test_query_content_question(self, rag_system):
        """Test that content questions go through correct flow"""
        query = "What is covered in lesson 1 of Python course?"

        response, sources = rag_system.query(query=query)

        # Verify AI generator received tools
        ai_gen = rag_system.mock_components['ai_generator']
        call_kwargs = ai_gen.generate_response.call_args[1]

        assert 'tools' in call_kwargs
        tool_defs = call_kwargs['tools']
        tool_names = [t['name'] for t in tool_defs]
        assert 'search_course_content' in tool_names

    def test_query_outline_question(self, rag_system):
        """Test that outline questions have access to outline tool"""
        query = "What lessons are in the Python course?"

        response, sources = rag_system.query(query=query)

        # Verify AI generator received both tools
        ai_gen = rag_system.mock_components['ai_generator']
        call_kwargs = ai_gen.generate_response.call_args[1]

        tool_defs = call_kwargs['tools']
        tool_names = [t['name'] for t in tool_defs]
        assert 'get_course_outline' in tool_names
        assert 'search_course_content' in tool_names


class TestRAGSystemAnalytics:
    """Test RAGSystem analytics methods"""

    def test_get_course_analytics(self, rag_system):
        """Test getting course analytics"""
        # Mock vector store methods
        vector_store = rag_system.mock_components['vector_store']
        vector_store.get_course_count.return_value = 5
        vector_store.get_existing_course_titles.return_value = [
            "Course 1", "Course 2", "Course 3"
        ]

        analytics = rag_system.get_course_analytics()

        assert analytics['total_courses'] == 5
        assert len(analytics['course_titles']) == 3
        assert "Course 1" in analytics['course_titles']


class TestRAGSystemErrorHandling:
    """Test error handling in RAGSystem"""

    def test_query_ai_generator_error(self, rag_system):
        """Test handling of AI generator errors"""
        # Mock AI generator to raise error
        rag_system.mock_components['ai_generator'].generate_response.side_effect = \
            Exception("API connection failed")

        with pytest.raises(Exception) as exc_info:
            rag_system.query(query="Test query")

        assert "API connection failed" in str(exc_info.value)

    def test_query_tool_manager_error(self, rag_system):
        """Test handling of tool manager errors"""
        # Mock tool manager to raise error
        rag_system.mock_components['tool_manager'].get_last_sources.side_effect = \
            Exception("Tool error")

        with pytest.raises(Exception) as exc_info:
            rag_system.query(query="Test query")

        assert "Tool error" in str(exc_info.value)


class TestRAGSystemIntegrationScenarios:
    """Test realistic usage scenarios"""

    def test_scenario_first_question(self, rag_system):
        """Test first question in new conversation"""
        response, sources = rag_system.query(
            query="What topics are covered in the Python course?",
            session_id="session_001"
        )

        # Should get response
        assert len(response) > 0
        # Should have sources
        assert isinstance(sources, list)
        # Session should be created
        session_mgr = rag_system.mock_components['session_manager']
        session_mgr.add_exchange.assert_called_once()

    def test_scenario_follow_up_question(self, rag_system):
        """Test follow-up question with context"""
        # Set up conversation history
        history = "User: What is Python?\nAssistant: Python is a programming language."
        rag_system.mock_components['session_manager'].get_conversation_history.return_value = history

        response, sources = rag_system.query(
            query="Tell me more about it",
            session_id="session_001"
        )

        # Verify history was passed to AI
        ai_gen = rag_system.mock_components['ai_generator']
        call_kwargs = ai_gen.generate_response.call_args[1]
        assert call_kwargs['conversation_history'] == history

    def test_scenario_multiple_queries_same_session(self, rag_system):
        """Test multiple queries in same session"""
        session_id = "session_multi"

        # First query
        rag_system.query(query="Question 1", session_id=session_id)

        # Second query
        rag_system.query(query="Question 2", session_id=session_id)

        # Third query
        rag_system.query(query="Question 3", session_id=session_id)

        # Verify session manager was called 3 times
        session_mgr = rag_system.mock_components['session_manager']
        assert session_mgr.add_exchange.call_count == 3
        assert session_mgr.get_conversation_history.call_count == 3
