"""Pytest fixtures for RAG chatbot tests"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Optional

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from vector_store import VectorStore, SearchResults
from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from models import Course, Lesson, CourseChunk
from fastapi.testclient import TestClient


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


# API Testing Fixtures

@pytest.fixture
def mock_rag_system():
    """Create a mock RAGSystem for API testing"""
    mock_rag = Mock()

    # Mock query method - note: all dict values must be strings or None per the QueryResponse model
    mock_rag.query.return_value = (
        "Python is a versatile programming language used for web development, data science, and automation.",
        [
            {
                "course_title": "Introduction to Python",
                "lesson_number": "1",
                "lesson_link": "https://example.com/python/lesson1"
            }
        ]
    )

    # Mock get_course_analytics method
    mock_rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Introduction to Python", "Advanced JavaScript"]
    }

    # Mock session_manager
    mock_session_manager = Mock()
    mock_session_manager.create_session.return_value = "test-session-123"
    mock_rag.session_manager = mock_session_manager

    return mock_rag


@pytest.fixture
def test_app(mock_rag_system):
    """Create a test FastAPI application with mocked dependencies"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import List, Optional, Dict

    # Create test app without static file mounting
    app = FastAPI(title="Course Materials RAG System (Test)")

    # Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Pydantic models for request/response
    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Dict[str, Optional[str]]]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    # API Endpoints (inline definitions for testing)
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        from fastapi import HTTPException
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()

            answer, sources = mock_rag_system.query(request.query, session_id)

            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        from fastapi import HTTPException
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/")
    async def root():
        return {"message": "RAG System API"}

    return app


@pytest.fixture
def client(test_app):
    """Create a test client for the FastAPI app"""
    return TestClient(test_app)


@pytest.fixture
def sample_query_request():
    """Sample query request data"""
    return {
        "query": "What is Python?",
        "session_id": "test-session-123"
    }


@pytest.fixture
def sample_query_request_no_session():
    """Sample query request without session ID"""
    return {
        "query": "What is Python?"
    }
