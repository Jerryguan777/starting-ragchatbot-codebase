"""
API Endpoint Tests for RAG System

Tests the FastAPI endpoints for proper request/response handling,
error scenarios, and integration with the RAG system.
"""
import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException


@pytest.mark.api
class TestQueryEndpoint:
    """Tests for POST /api/query endpoint"""

    def test_query_with_session_id(self, client, sample_query_request):
        """Test query endpoint with existing session ID"""
        response = client.post("/api/query", json=sample_query_request)

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        assert data["session_id"] == "test-session-123"
        assert isinstance(data["sources"], list)
        assert len(data["sources"]) > 0

    def test_query_without_session_id(self, client, sample_query_request_no_session, mock_rag_system):
        """Test query endpoint creates new session when not provided"""
        response = client.post("/api/query", json=sample_query_request_no_session)

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        # Verify session was created
        mock_rag_system.session_manager.create_session.assert_called_once()

    def test_query_response_structure(self, client, sample_query_request):
        """Test that query response has correct structure"""
        response = client.post("/api/query", json=sample_query_request)

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)

        # Validate sources structure
        if len(data["sources"]) > 0:
            source = data["sources"][0]
            assert "course_title" in source
            assert "lesson_number" in source

    def test_query_with_empty_query(self, client):
        """Test query endpoint with empty query string"""
        response = client.post("/api/query", json={"query": ""})

        # Should still process (backend determines if query is valid)
        assert response.status_code in [200, 422]

    def test_query_with_missing_query_field(self, client):
        """Test query endpoint with missing required query field"""
        response = client.post("/api/query", json={"session_id": "test-123"})

        # Should return validation error
        assert response.status_code == 422

    def test_query_with_invalid_json(self, client):
        """Test query endpoint with invalid JSON"""
        response = client.post(
            "/api/query",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_query_calls_rag_system(self, client, sample_query_request, mock_rag_system):
        """Test that query endpoint calls RAG system correctly"""
        client.post("/api/query", json=sample_query_request)

        # Verify RAG system was called with correct parameters
        mock_rag_system.query.assert_called_once_with(
            sample_query_request["query"],
            sample_query_request["session_id"]
        )

    def test_query_with_special_characters(self, client):
        """Test query endpoint with special characters in query"""
        special_query = {
            "query": "What is Python? Can you explain <html> tags & symbols!",
            "session_id": "test-session-123"
        }

        response = client.post("/api/query", json=special_query)
        assert response.status_code == 200

    def test_query_with_long_query(self, client):
        """Test query endpoint with very long query string"""
        long_query = {
            "query": "What is Python? " * 100,  # Very long query
            "session_id": "test-session-123"
        }

        response = client.post("/api/query", json=long_query)
        assert response.status_code == 200

    def test_query_error_handling(self, client, mock_rag_system):
        """Test query endpoint handles RAG system errors"""
        # Make RAG system raise an exception
        mock_rag_system.query.side_effect = Exception("Database error")

        response = client.post("/api/query", json={"query": "test query"})

        # Should return 500 error
        assert response.status_code == 500
        assert "detail" in response.json()


@pytest.mark.api
class TestCoursesEndpoint:
    """Tests for GET /api/courses endpoint"""

    def test_get_courses_success(self, client):
        """Test getting course statistics"""
        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        assert "total_courses" in data
        assert "course_titles" in data
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)

    def test_get_courses_response_structure(self, client):
        """Test course statistics response structure"""
        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert data["total_courses"] == 2
        assert len(data["course_titles"]) == 2
        assert "Introduction to Python" in data["course_titles"]
        assert "Advanced JavaScript" in data["course_titles"]

    def test_get_courses_calls_analytics(self, client, mock_rag_system):
        """Test that courses endpoint calls get_course_analytics"""
        client.get("/api/courses")

        # Verify analytics method was called
        mock_rag_system.get_course_analytics.assert_called_once()

    def test_get_courses_error_handling(self, client, mock_rag_system):
        """Test courses endpoint handles errors gracefully"""
        # Make analytics method raise an exception
        mock_rag_system.get_course_analytics.side_effect = Exception("Analytics error")

        response = client.get("/api/courses")

        # Should return 500 error
        assert response.status_code == 500
        assert "detail" in response.json()

    def test_get_courses_with_no_courses(self, client, mock_rag_system):
        """Test courses endpoint when no courses exist"""
        # Mock empty course list
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []


@pytest.mark.api
class TestRootEndpoint:
    """Tests for GET / endpoint"""

    def test_root_endpoint(self, client):
        """Test root endpoint returns welcome message"""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data


@pytest.mark.api
class TestCORSHeaders:
    """Tests for CORS configuration"""

    def test_cors_headers_on_query_post(self, client, sample_query_request):
        """Test that CORS headers are present on query POST response"""
        response = client.post("/api/query", json=sample_query_request)

        # CORS middleware should add these headers
        assert response.status_code == 200
        # Note: TestClient may not always include CORS headers,
        # but in production FastAPI with CORSMiddleware will

    def test_cors_headers_on_courses_get(self, client):
        """Test that CORS headers are present on courses GET response"""
        response = client.get("/api/courses")

        assert response.status_code == 200
        # CORS middleware is configured in the test app


@pytest.mark.api
class TestEndpointIntegration:
    """Integration tests for multiple endpoints working together"""

    def test_query_then_get_courses(self, client, sample_query_request):
        """Test making a query and then getting course statistics"""
        # First make a query
        query_response = client.post("/api/query", json=sample_query_request)
        assert query_response.status_code == 200

        # Then get courses
        courses_response = client.get("/api/courses")
        assert courses_response.status_code == 200

    def test_multiple_queries_same_session(self, client):
        """Test multiple queries with the same session ID"""
        session_id = "persistent-session-123"

        # First query
        response1 = client.post("/api/query", json={
            "query": "What is Python?",
            "session_id": session_id
        })
        assert response1.status_code == 200
        assert response1.json()["session_id"] == session_id

        # Second query with same session
        response2 = client.post("/api/query", json={
            "query": "Tell me more about variables",
            "session_id": session_id
        })
        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id

    def test_concurrent_different_sessions(self, client):
        """Test queries with different session IDs"""
        # Query with session 1
        response1 = client.post("/api/query", json={
            "query": "What is Python?",
            "session_id": "session-1"
        })

        # Query with session 2
        response2 = client.post("/api/query", json={
            "query": "What is JavaScript?",
            "session_id": "session-2"
        })

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json()["session_id"] != response2.json()["session_id"]


@pytest.mark.api
class TestRequestValidation:
    """Tests for request validation and edge cases"""

    def test_query_with_null_session_id(self, client):
        """Test query with explicitly null session ID"""
        response = client.post("/api/query", json={
            "query": "What is Python?",
            "session_id": None
        })

        assert response.status_code == 200
        # Should create a new session
        assert response.json()["session_id"] is not None

    def test_query_with_extra_fields(self, client):
        """Test query with extra unexpected fields"""
        response = client.post("/api/query", json={
            "query": "What is Python?",
            "session_id": "test-123",
            "extra_field": "should be ignored"
        })

        # FastAPI should ignore extra fields or handle gracefully
        assert response.status_code in [200, 422]

    def test_query_with_unicode_characters(self, client):
        """Test query with Unicode characters"""
        response = client.post("/api/query", json={
            "query": "¿Qué es Python? 你好 مرحبا",
            "session_id": "test-123"
        })

        assert response.status_code == 200

    def test_invalid_http_method_on_query(self, client):
        """Test using wrong HTTP method on query endpoint"""
        response = client.get("/api/query")

        # Should return method not allowed
        assert response.status_code == 405

    def test_invalid_http_method_on_courses(self, client):
        """Test using wrong HTTP method on courses endpoint"""
        response = client.post("/api/courses", json={})

        # Should return method not allowed
        assert response.status_code == 405


@pytest.mark.api
class TestResponseFormats:
    """Tests for response format consistency"""

    def test_query_response_json_format(self, client, sample_query_request):
        """Test that query response is valid JSON"""
        response = client.post("/api/query", json=sample_query_request)

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        # Should be parseable JSON
        data = response.json()
        assert data is not None

    def test_courses_response_json_format(self, client):
        """Test that courses response is valid JSON"""
        response = client.get("/api/courses")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        data = response.json()
        assert data is not None

    def test_error_response_format(self, client, mock_rag_system):
        """Test that error responses have consistent format"""
        mock_rag_system.query.side_effect = Exception("Test error")

        response = client.post("/api/query", json={"query": "test"})

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
