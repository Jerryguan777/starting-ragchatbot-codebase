"""Pytest fixtures for RAG chatbot tests"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from vector_store import VectorStore, SearchResults
from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from models import Course, Lesson, CourseChunk


@pytest.fixture
def mock_vector_store():
    """Create a mock VectorStore with sample data"""
    mock_store = Mock(spec=VectorStore)

    # Sample search results
    sample_results = SearchResults(
        documents=["This is lesson content about Python programming."],
        metadata=[{
            'course_title': 'Introduction to Python',
            'lesson_number': 1,
            'lesson_title': 'Python Basics'
        }],
        distances=[0.5],
        error=None
    )

    mock_store.search.return_value = sample_results

    # Sample course metadata
    mock_store.get_all_courses_metadata.return_value = [
        {
            'title': 'Introduction to Python',
            'instructor': 'John Doe',
            'course_link': 'https://example.com/python',
            'lessons': [
                {
                    'lesson_number': 0,
                    'lesson_title': 'Getting Started',
                    'lesson_link': 'https://example.com/python/lesson0'
                },
                {
                    'lesson_number': 1,
                    'lesson_title': 'Python Basics',
                    'lesson_link': 'https://example.com/python/lesson1'
                }
            ]
        }
    ]

    mock_store._resolve_course_name.return_value = 'Introduction to Python'
    mock_store.get_lesson_link.return_value = 'https://example.com/python/lesson1'

    return mock_store


@pytest.fixture
def mock_empty_vector_store():
    """Create a mock VectorStore with no results"""
    mock_store = Mock(spec=VectorStore)

    empty_results = SearchResults(
        documents=[],
        metadata=[],
        distances=[],
        error=None
    )

    mock_store.search.return_value = empty_results
    mock_store.get_all_courses_metadata.return_value = []
    mock_store._resolve_course_name.return_value = None

    return mock_store


@pytest.fixture
def mock_error_vector_store():
    """Create a mock VectorStore that returns errors"""
    mock_store = Mock(spec=VectorStore)

    error_results = SearchResults(
        documents=[],
        metadata=[],
        distances=[],
        error="Database connection failed"
    )

    mock_store.search.return_value = error_results

    return mock_store


@pytest.fixture
def course_search_tool(mock_vector_store):
    """Create a CourseSearchTool with mock vector store"""
    return CourseSearchTool(mock_vector_store)


@pytest.fixture
def course_outline_tool(mock_vector_store):
    """Create a CourseOutlineTool with mock vector store"""
    return CourseOutlineTool(mock_vector_store)


@pytest.fixture
def tool_manager(course_search_tool, course_outline_tool):
    """Create a ToolManager with registered tools"""
    manager = ToolManager()
    manager.register_tool(course_search_tool)
    manager.register_tool(course_outline_tool)
    return manager


@pytest.fixture
def sample_course():
    """Create a sample Course object"""
    return Course(
        title="Introduction to Python",
        instructor="John Doe",
        course_link="https://example.com/python",
        lessons=[
            Lesson(
                lesson_number=0,
                title="Getting Started",
                lesson_link="https://example.com/python/lesson0"
            ),
            Lesson(
                lesson_number=1,
                title="Python Basics",
                lesson_link="https://example.com/python/lesson1"
            )
        ]
    )


@pytest.fixture
def sample_course_chunks(sample_course):
    """Create sample course chunks"""
    return [
        CourseChunk(
            course_title=sample_course.title,
            lesson_number=0,
            text="This is the introduction to Python programming.",
            chunk_index=0
        ),
        CourseChunk(
            course_title=sample_course.title,
            lesson_number=1,
            text="Python is a high-level programming language.",
            chunk_index=1
        )
    ]
