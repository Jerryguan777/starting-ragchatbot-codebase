from typing import Dict, Any, Optional, Protocol
from abc import ABC, abstractmethod
from vector_store import VectorStore, SearchResults


class Tool(ABC):
    """Abstract base class for all tools"""
    
    @abstractmethod
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool with given parameters"""
        pass


class CourseSearchTool(Tool):
    """Tool for searching course content with semantic course name matching"""
    
    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []  # Track sources from last search
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "search_course_content",
            "description": "Search course materials with smart course name matching and lesson filtering",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string", 
                        "description": "What to search for in the course content"
                    },
                    "course_name": {
                        "type": "string",
                        "description": "Course title (partial matches work, e.g. 'MCP', 'Introduction')"
                    },
                    "lesson_number": {
                        "type": "integer",
                        "description": "Specific lesson number to search within (e.g. 1, 2, 3)"
                    }
                },
                "required": ["query"]
            }
        }
    
    def execute(self, query: str, course_name: Optional[str] = None, lesson_number: Optional[int] = None) -> str:
        """
        Execute the search tool with given parameters.
        
        Args:
            query: What to search for
            course_name: Optional course filter
            lesson_number: Optional lesson filter
            
        Returns:
            Formatted search results or error message
        """
        
        # Use the vector store's unified search interface
        results = self.store.search(
            query=query,
            course_name=course_name,
            lesson_number=lesson_number
        )
        
        # Handle errors
        if results.error:
            return results.error
        
        # Handle empty results
        if results.is_empty():
            filter_info = ""
            if course_name:
                filter_info += f" in course '{course_name}'"
            if lesson_number:
                filter_info += f" in lesson {lesson_number}"
            return f"No relevant content found{filter_info}."
        
        # Format and return results
        return self._format_results(results)
    
    def _format_results(self, results: SearchResults) -> str:
        """Format search results with course and lesson context"""
        formatted = []
        sources = []  # Track sources for the UI (with links)

        for doc, meta in zip(results.documents, results.metadata):
            course_title = meta.get('course_title', 'unknown')
            lesson_num = meta.get('lesson_number')

            # Build context header
            header = f"[{course_title}"
            if lesson_num is not None:
                header += f" - Lesson {lesson_num}"
            header += "]"

            # Build source title
            source_title = course_title
            if lesson_num is not None:
                source_title += f" - Lesson {lesson_num}"

            # Retrieve lesson link from course_catalog
            lesson_link = None
            if lesson_num is not None and course_title != 'unknown':
                lesson_link = self.store.get_lesson_link(course_title, lesson_num)

            # Track source with link for the UI
            sources.append({
                "title": source_title,
                "url": lesson_link
            })

            formatted.append(f"{header}\n{doc}")

        # Store sources for retrieval
        self.last_sources = sources

        return "\n\n".join(formatted)


class CourseOutlineTool(Tool):
    """Tool for retrieving course outlines with lesson structure"""

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []  # Track sources for UI display

    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "get_course_outline",
            "description": "Get course structure including title, instructor, and complete lesson list. Use for questions about course outlines, table of contents, or lesson structure.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "course_name": {
                        "type": "string",
                        "description": "Course title to get outline for (partial matches work, e.g. 'MCP', 'Introduction'). If omitted, returns all courses."
                    }
                },
                "required": []
            }
        }

    def execute(self, course_name: Optional[str] = None) -> str:
        """
        Execute the outline tool to get course structure.

        Args:
            course_name: Optional course filter (supports fuzzy matching)

        Returns:
            Formatted course outline(s) with lessons or error message
        """

        # Get all courses metadata
        all_courses = self.store.get_all_courses_metadata()

        if not all_courses:
            return "No courses found in the system."

        # Filter by course name if provided
        if course_name:
            # Use vector store's fuzzy matching
            resolved_title = self.store._resolve_course_name(course_name)
            if not resolved_title:
                return f"No course found matching '{course_name}'."

            # Filter courses by resolved title
            courses_to_show = [c for c in all_courses if c.get('title') == resolved_title]

            if not courses_to_show:
                return f"No course found matching '{course_name}'."
        else:
            courses_to_show = all_courses

        # Format and return results
        return self._format_outline(courses_to_show)

    def _format_outline(self, courses: list) -> str:
        """Format course outlines with lessons"""
        formatted = []
        sources = []

        for course in courses:
            title = course.get('title', 'Unknown Course')
            instructor = course.get('instructor', 'Unknown')
            course_link = course.get('course_link')
            lessons = course.get('lessons', [])

            # Build course header
            outline = f"**{title}**\n"
            outline += f"Instructor: {instructor}\n"
            if course_link:
                outline += f"Course Link: {course_link}\n"

            # Add lesson list
            outline += f"\nLessons ({len(lessons)} total):\n"
            for lesson in lessons:
                lesson_num = lesson.get('lesson_number')
                lesson_title = lesson.get('lesson_title', 'Untitled')
                lesson_link = lesson.get('lesson_link')

                outline += f"  {lesson_num}. {lesson_title}\n"

                # Track source for UI (with link if available)
                if lesson_link:
                    sources.append({
                        "title": f"{title} - Lesson {lesson_num}",
                        "url": lesson_link
                    })

            # Add course-level source if no lesson links
            if not any(lesson.get('lesson_link') for lesson in lessons) and course_link:
                sources.append({
                    "title": title,
                    "url": course_link
                })

            formatted.append(outline)

        # Store sources for UI retrieval
        self.last_sources = sources

        return "\n\n".join(formatted)


class ToolManager:
    """Manages available tools for the AI"""
    
    def __init__(self):
        self.tools = {}
    
    def register_tool(self, tool: Tool):
        """Register any tool that implements the Tool interface"""
        tool_def = tool.get_tool_definition()
        tool_name = tool_def.get("name")
        if not tool_name:
            raise ValueError("Tool must have a 'name' in its definition")
        self.tools[tool_name] = tool

    
    def get_tool_definitions(self) -> list:
        """Get all tool definitions for Anthropic tool calling"""
        return [tool.get_tool_definition() for tool in self.tools.values()]
    
    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Execute a tool by name with given parameters"""
        if tool_name not in self.tools:
            return f"Tool '{tool_name}' not found"
        
        return self.tools[tool_name].execute(**kwargs)
    
    def get_last_sources(self) -> list:
        """Get sources from the last search operation"""
        # Check all tools for last_sources attribute
        for tool in self.tools.values():
            if hasattr(tool, 'last_sources') and tool.last_sources:
                return tool.last_sources
        return []

    def reset_sources(self):
        """Reset sources from all tools that track sources"""
        for tool in self.tools.values():
            if hasattr(tool, 'last_sources'):
                tool.last_sources = []