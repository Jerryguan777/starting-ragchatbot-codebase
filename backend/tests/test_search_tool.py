"""Unit tests for CourseSearchTool"""
import pytest
from search_tools import CourseSearchTool
from vector_store import SearchResults


class TestCourseSearchTool:
    """Test suite for CourseSearchTool"""

    def test_get_tool_definition(self, course_search_tool):
        """Test that tool definition is correctly formatted"""
        definition = course_search_tool.get_tool_definition()

        assert definition['name'] == 'search_course_content'
        assert 'description' in definition
        assert 'input_schema' in definition
        assert definition['input_schema']['type'] == 'object'
        assert 'query' in definition['input_schema']['properties']
        assert 'query' in definition['input_schema']['required']

    def test_basic_search(self, course_search_tool, mock_vector_store):
        """Test basic search without filters"""
        result = course_search_tool.execute(query="Python programming")

        # Verify vector store was called correctly
        mock_vector_store.search.assert_called_once_with(
            query="Python programming",
            course_name=None,
            lesson_number=None
        )

        # Verify result format
        assert isinstance(result, str)
        assert "Introduction to Python" in result
        assert "This is lesson content" in result

    def test_search_with_course_name(self, course_search_tool, mock_vector_store):
        """Test search with course_name filter"""
        result = course_search_tool.execute(
            query="Python basics",
            course_name="Python"
        )

        mock_vector_store.search.assert_called_once_with(
            query="Python basics",
            course_name="Python",
            lesson_number=None
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_search_with_lesson_number(self, course_search_tool, mock_vector_store):
        """Test search with lesson_number filter"""
        result = course_search_tool.execute(
            query="Python basics",
            lesson_number=1
        )

        mock_vector_store.search.assert_called_once_with(
            query="Python basics",
            course_name=None,
            lesson_number=1
        )

        assert isinstance(result, str)

    def test_search_with_all_filters(self, course_search_tool, mock_vector_store):
        """Test search with both filters"""
        result = course_search_tool.execute(
            query="Python basics",
            course_name="Python",
            lesson_number=1
        )

        mock_vector_store.search.assert_called_once_with(
            query="Python basics",
            course_name="Python",
            lesson_number=1
        )

        assert isinstance(result, str)

    def test_search_no_results(self, mock_empty_vector_store):
        """Test search when no results are found"""
        tool = CourseSearchTool(mock_empty_vector_store)
        result = tool.execute(query="nonexistent topic")

        assert "No relevant content found" in result

    def test_search_error_handling(self, mock_error_vector_store):
        """Test search when vector store returns error"""
        tool = CourseSearchTool(mock_error_vector_store)
        result = tool.execute(query="test query")

        assert "Database connection failed" in result

    def test_sources_tracking(self, course_search_tool, mock_vector_store):
        """Test that sources are properly tracked"""
        # Execute search
        course_search_tool.execute(query="Python programming")

        # Check that sources were populated
        assert len(course_search_tool.last_sources) > 0

        # Verify source structure
        source = course_search_tool.last_sources[0]
        assert 'title' in source
        assert 'url' in source
        assert 'Introduction to Python' in source['title']

    def test_format_results(self, course_search_tool, mock_vector_store):
        """Test result formatting"""
        result = course_search_tool.execute(query="Python")

        # Check format includes course title and lesson info
        assert "[Introduction to Python - Lesson 1]" in result
        assert "This is lesson content" in result

    def test_empty_query(self, course_search_tool, mock_vector_store):
        """Test behavior with empty query"""
        # This should still call the vector store
        result = course_search_tool.execute(query="")

        mock_vector_store.search.assert_called_once()
        assert isinstance(result, str)


class TestCourseOutlineTool:
    """Test suite for CourseOutlineTool"""

    def test_get_tool_definition(self, course_outline_tool):
        """Test that tool definition is correctly formatted"""
        definition = course_outline_tool.get_tool_definition()

        assert definition['name'] == 'get_course_outline'
        assert 'description' in definition
        assert 'input_schema' in definition
        assert definition['input_schema']['type'] == 'object'
        assert 'course_name' in definition['input_schema']['properties']
        # course_name should be optional
        assert definition['input_schema']['required'] == []

    def test_get_outline_no_filter(self, course_outline_tool, mock_vector_store):
        """Test getting all course outlines"""
        result = course_outline_tool.execute()

        # Verify vector store was called
        mock_vector_store.get_all_courses_metadata.assert_called_once()

        # Verify result contains course info
        assert "Introduction to Python" in result
        assert "John Doe" in result
        assert "Lessons (2 total)" in result
        assert "Getting Started" in result
        assert "Python Basics" in result

    def test_get_outline_with_course_name(self, course_outline_tool, mock_vector_store):
        """Test getting outline for specific course"""
        result = course_outline_tool.execute(course_name="Python")

        # Verify fuzzy matching was used
        mock_vector_store._resolve_course_name.assert_called_once_with("Python")

        # Verify result
        assert "Introduction to Python" in result
        assert isinstance(result, str)

    def test_get_outline_no_courses(self, mock_empty_vector_store):
        """Test when no courses exist"""
        tool = CourseOutlineTool(mock_empty_vector_store)
        result = tool.execute()

        assert "No courses found in the system" in result

    def test_get_outline_course_not_found(self, course_outline_tool, mock_vector_store):
        """Test when requested course doesn't exist"""
        # Make _resolve_course_name return None
        mock_vector_store._resolve_course_name.return_value = None

        result = course_outline_tool.execute(course_name="Nonexistent Course")

        assert "No course found matching" in result
        assert "Nonexistent Course" in result

    def test_outline_sources_tracking(self, course_outline_tool, mock_vector_store):
        """Test that sources are properly tracked for outlines"""
        course_outline_tool.execute()

        # Check that sources were populated
        assert len(course_outline_tool.last_sources) > 0

        # Verify source structure includes lesson links
        for source in course_outline_tool.last_sources:
            assert 'title' in source
            assert 'url' in source


class TestToolManager:
    """Test suite for ToolManager"""

    def test_register_tool(self, course_search_tool):
        """Test tool registration"""
        from search_tools import ToolManager
        manager = ToolManager()

        manager.register_tool(course_search_tool)

        assert 'search_course_content' in manager.tools

    def test_get_tool_definitions(self, tool_manager):
        """Test getting all tool definitions"""
        definitions = tool_manager.get_tool_definitions()

        assert len(definitions) == 2
        tool_names = [d['name'] for d in definitions]
        assert 'search_course_content' in tool_names
        assert 'get_course_outline' in tool_names

    def test_execute_tool(self, tool_manager, mock_vector_store):
        """Test executing a registered tool"""
        result = tool_manager.execute_tool(
            'search_course_content',
            query="Python programming"
        )

        assert isinstance(result, str)
        mock_vector_store.search.assert_called_once()

    def test_execute_nonexistent_tool(self, tool_manager):
        """Test executing a tool that doesn't exist"""
        result = tool_manager.execute_tool('nonexistent_tool', query="test")

        assert "Tool 'nonexistent_tool' not found" in result

    def test_get_last_sources(self, tool_manager):
        """Test retrieving sources from tools"""
        # Execute a search to generate sources
        tool_manager.execute_tool('search_course_content', query="Python")

        sources = tool_manager.get_last_sources()

        assert isinstance(sources, list)
        # At least one tool should have sources
        assert len(sources) > 0

    def test_reset_sources(self, tool_manager):
        """Test resetting sources"""
        # Execute a search to generate sources
        tool_manager.execute_tool('search_course_content', query="Python")

        # Reset sources
        tool_manager.reset_sources()

        # Check that all tools have empty sources
        for tool in tool_manager.tools.values():
            if hasattr(tool, 'last_sources'):
                assert tool.last_sources == []
