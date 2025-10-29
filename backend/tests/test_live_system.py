"""Live system diagnostic tests - tests against actual running system"""
import pytest
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from config import Config
from vector_store import VectorStore
from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from ai_generator import AIGenerator


class TestLiveVectorStore:
    """Test the actual vector store with real data"""

    @pytest.fixture
    def live_vector_store(self):
        """Create connection to actual vector store"""
        config = Config()
        return VectorStore(
            chroma_path=config.CHROMA_PATH,
            embedding_model=config.EMBEDDING_MODEL,
            max_results=config.MAX_RESULTS
        )

    def test_vector_store_has_data(self, live_vector_store):
        """Test that vector store contains course data"""
        course_count = live_vector_store.get_course_count()
        print(f"\n📊 Total courses in database: {course_count}")

        assert course_count > 0, "Vector store is empty! No courses found."

        # Get course titles
        titles = live_vector_store.get_existing_course_titles()
        print(f"📚 Courses: {titles}")

        assert len(titles) > 0, "No course titles found"

    def test_vector_store_catalog_collection(self, live_vector_store):
        """Test that catalog collection exists and has data"""
        metadata = live_vector_store.get_all_courses_metadata()
        print(f"\n📖 Courses metadata count: {len(metadata)}")

        assert len(metadata) > 0, "Catalog collection is empty!"

        # Check structure of first course
        if metadata:
            first_course = metadata[0]
            print(f"✅ Sample course: {first_course.get('title')}")
            print(f"   Instructor: {first_course.get('instructor')}")
            print(f"   Lessons: {len(first_course.get('lessons', []))}")

            assert 'title' in first_course
            assert 'lessons' in first_course

    def test_vector_store_search(self, live_vector_store):
        """Test that search actually returns results"""
        # Try a basic search
        results = live_vector_store.search(query="Python programming")

        print(f"\n🔍 Search results for 'Python programming':")
        print(f"   Documents found: {len(results.documents)}")
        print(f"   Has error: {results.error}")

        if results.documents:
            print(f"   First result snippet: {results.documents[0][:100]}...")

        # This should return results if there's any Python-related content
        # If it fails, the vector store search is broken
        assert results.error is None, f"Search returned error: {results.error}"

        if results.documents:
            assert len(results.documents) > 0, "Search returned no documents"


class TestLiveSearchTool:
    """Test CourseSearchTool against real vector store"""

    @pytest.fixture
    def live_search_tool(self):
        """Create search tool with real vector store"""
        config = Config()
        vector_store = VectorStore(
            chroma_path=config.CHROMA_PATH,
            embedding_model=config.EMBEDDING_MODEL,
            max_results=config.MAX_RESULTS
        )
        return CourseSearchTool(vector_store)

    def test_search_tool_execute(self, live_search_tool):
        """Test executing search tool with real data"""
        result = live_search_tool.execute(query="What is Python?")

        print(f"\n🔧 Search tool result:")
        print(f"   Type: {type(result)}")
        print(f"   Length: {len(result)}")
        print(f"   Content preview: {result[:200]}...")

        assert isinstance(result, str), "Search tool should return a string"
        assert len(result) > 0, "Search tool returned empty string"

        # Check if it's an actual error message (not just content mentioning errors)
        if "No relevant content found" in result:
            print(f"⚠️  Search tool returned no results")
            pytest.fail(f"Search tool returned no results: {result[:200]}")

    def test_search_tool_sources(self, live_search_tool):
        """Test that search tool populates sources"""
        result = live_search_tool.execute(query="course content")

        print(f"\n📌 Sources tracked: {len(live_search_tool.last_sources)}")
        if live_search_tool.last_sources:
            print(f"   Sample source: {live_search_tool.last_sources[0]}")

        # Sources should be populated if results were found
        if "No relevant content found" not in result:
            assert len(live_search_tool.last_sources) > 0, "Sources not tracked"


class TestLiveOutlineTool:
    """Test CourseOutlineTool against real vector store"""

    @pytest.fixture
    def live_outline_tool(self):
        """Create outline tool with real vector store"""
        config = Config()
        vector_store = VectorStore(
            chroma_path=config.CHROMA_PATH,
            embedding_model=config.EMBEDDING_MODEL,
            max_results=config.MAX_RESULTS
        )
        return CourseOutlineTool(vector_store)

    def test_outline_tool_execute(self, live_outline_tool):
        """Test executing outline tool with real data"""
        result = live_outline_tool.execute()

        print(f"\n📚 Outline tool result:")
        print(f"   Type: {type(result)}")
        print(f"   Length: {len(result)}")
        print(f"   Content preview: {result[:300]}...")

        assert isinstance(result, str), "Outline tool should return a string"
        assert len(result) > 0, "Outline tool returned empty string"

        # Should not be an error
        assert "No courses found" not in result, "Outline tool found no courses"


class TestLiveToolManager:
    """Test ToolManager with real tools"""

    @pytest.fixture
    def live_tool_manager(self):
        """Create tool manager with real tools"""
        config = Config()
        vector_store = VectorStore(
            chroma_path=config.CHROMA_PATH,
            embedding_model=config.EMBEDDING_MODEL,
            max_results=config.MAX_RESULTS
        )

        manager = ToolManager()
        manager.register_tool(CourseSearchTool(vector_store))
        manager.register_tool(CourseOutlineTool(vector_store))

        return manager

    def test_tool_manager_definitions(self, live_tool_manager):
        """Test that tool definitions are correct"""
        definitions = live_tool_manager.get_tool_definitions()

        print(f"\n🛠️  Tool definitions:")
        for tool_def in definitions:
            print(f"   - {tool_def['name']}: {tool_def.get('description', 'No description')[:80]}...")

        assert len(definitions) == 2, "Should have 2 tools registered"

        tool_names = [d['name'] for d in definitions]
        assert 'search_course_content' in tool_names
        assert 'get_course_outline' in tool_names

        # Verify structure
        for tool_def in definitions:
            assert 'name' in tool_def
            assert 'description' in tool_def
            assert 'input_schema' in tool_def
            assert tool_def['input_schema']['type'] == 'object'

    def test_tool_manager_execute_search(self, live_tool_manager):
        """Test executing search through tool manager"""
        result = live_tool_manager.execute_tool(
            'search_course_content',
            query="programming concepts"
        )

        print(f"\n✅ Tool execution result length: {len(result)}")
        print(f"   Preview: {result[:150]}...")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_tool_manager_execute_outline(self, live_tool_manager):
        """Test executing outline through tool manager"""
        result = live_tool_manager.execute_tool('get_course_outline')

        print(f"\n✅ Outline execution result length: {len(result)}")

        assert isinstance(result, str)
        assert len(result) > 0


class TestAIGeneratorToolDefinitions:
    """Test that AI generator receives correct tool definitions"""

    def test_tool_definitions_format(self):
        """Test that tool definitions match Anthropic's expected format"""
        config = Config()
        vector_store = VectorStore(
            chroma_path=config.CHROMA_PATH,
            embedding_model=config.EMBEDDING_MODEL,
            max_results=config.MAX_RESULTS
        )

        manager = ToolManager()
        manager.register_tool(CourseSearchTool(vector_store))
        manager.register_tool(CourseOutlineTool(vector_store))

        definitions = manager.get_tool_definitions()

        print(f"\n🔍 Checking tool definitions format:")
        for tool_def in definitions:
            print(f"\n   Tool: {tool_def['name']}")
            print(f"   - Has 'name': {('name' in tool_def)}")
            print(f"   - Has 'description': {('description' in tool_def)}")
            print(f"   - Has 'input_schema': {('input_schema' in tool_def)}")

            # Check input schema structure
            schema = tool_def['input_schema']
            print(f"   - Schema type: {schema.get('type')}")
            print(f"   - Schema properties: {list(schema.get('properties', {}).keys())}")
            print(f"   - Schema required: {schema.get('required', [])}")

            # Verify required fields
            assert 'name' in tool_def
            assert 'description' in tool_def
            assert 'input_schema' in tool_def
            assert schema['type'] == 'object'
            assert 'properties' in schema


@pytest.fixture(scope="module")
def system_health_check():
    """Run before all tests to check system health"""
    print("\n" + "="*70)
    print("🏥 SYSTEM HEALTH CHECK")
    print("="*70)

    config = Config()

    # Check if chroma_db exists
    from pathlib import Path
    chroma_path = Path(config.CHROMA_PATH)

    if not chroma_path.exists():
        print(f"❌ ChromaDB path does not exist: {chroma_path}")
        pytest.fail("ChromaDB database not found")

    print(f"✅ ChromaDB path exists: {chroma_path}")

    # Try to connect
    try:
        vector_store = VectorStore(
            chroma_path=config.CHROMA_PATH,
            embedding_model=config.EMBEDDING_MODEL,
            max_results=config.MAX_RESULTS
        )
        course_count = vector_store.get_course_count()
        print(f"✅ Connected to vector store: {course_count} courses found")
    except Exception as e:
        print(f"❌ Failed to connect to vector store: {e}")
        pytest.fail(f"Vector store connection failed: {e}")

    print("="*70 + "\n")


def test_system_health(system_health_check):
    """Dummy test to ensure health check runs"""
    pass


class TestEndToEndUserQuery:
    """Test complete user query flow to reproduce 'query failed' issue"""

    @pytest.fixture
    def full_rag_system(self):
        """Create full RAG system"""
        from rag_system import RAGSystem
        from config import Config
        config = Config()
        return RAGSystem(config)

    def test_content_query_flow(self, full_rag_system):
        """Test a content-related query end-to-end"""
        print("\n" + "="*70)
        print("🔍 Testing content query: 'What is MCP?'")
        print("="*70)

        try:
            response, sources = full_rag_system.query(
                query="What is MCP?",
                session_id="test_session_001"
            )

            print(f"\n✅ Response received:")
            print(f"   Type: {type(response)}")
            print(f"   Length: {len(response)}")
            print(f"   Preview: {response[:200]}...")
            print(f"\n📎 Sources count: {len(sources)}")

            if sources:
                print(f"   Sample source: {sources[0]}")

            # Assertions
            assert isinstance(response, str), "Response should be a string"
            assert len(response) > 0, "Response should not be empty"

            # Check if it's a failure message
            if response.lower() == "query failed":
                print("\n❌ REPRODUCED THE BUG: Response is 'query failed'")
                pytest.fail("Bug reproduced: System returned 'query failed'")

        except Exception as e:
            print(f"\n❌ Exception occurred: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            pytest.fail(f"Query raised exception: {e}")

    def test_outline_query_flow(self, full_rag_system):
        """Test an outline-related query end-to-end"""
        print("\n" + "="*70)
        print("📚 Testing outline query: 'What lessons are in the MCP course?'")
        print("="*70)

        try:
            response, sources = full_rag_system.query(
                query="What lessons are in the MCP course?",
                session_id="test_session_002"
            )

            print(f"\n✅ Response received:")
            print(f"   Type: {type(response)}")
            print(f"   Length: {len(response)}")
            print(f"   Preview: {response[:200]}...")
            print(f"\n📎 Sources count: {len(sources)}")

            assert isinstance(response, str)
            assert len(response) > 0

            if response.lower() == "query failed":
                print("\n❌ REPRODUCED THE BUG: Response is 'query failed'")
                pytest.fail("Bug reproduced: System returned 'query failed'")

        except Exception as e:
            print(f"\n❌ Exception occurred: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            pytest.fail(f"Query raised exception: {e}")
