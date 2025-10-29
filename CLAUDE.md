# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **custom-built RAG (Retrieval-Augmented Generation) system** for course materials. It does NOT use frameworks like LangChain or LlamaIndex - all RAG components are implemented from scratch using low-level libraries.

**Tech Stack:**
- **Backend:** FastAPI + Python 3.13 (managed with `uv`)
- **Vector DB:** ChromaDB (persistent storage)
- **Embeddings:** Sentence Transformers (all-MiniLM-L6-v2, 384-dim)
- **LLM:** Anthropic Claude (claude-sonnet-4-20250514)
- **Frontend:** Vanilla JavaScript/HTML/CSS

## Development Commands

### Running the Application

```bash
# Quick start (from project root)
./run.sh

# Manual start
cd backend
uv run uvicorn app:app --reload --port 8000

# Access points:
# - Web UI: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

### Dependency Management

```bash
# Install/sync dependencies
uv sync

# Add new dependency
uv add package-name

# List installed packages
uv pip list
```

### Environment Setup

Create `.env` in project root:
```
ANTHROPIC_API_KEY=your_api_key_here
```

## Architecture Overview

### Core RAG Pipeline (No Framework Used)

The system implements a **two-API-call pattern** for each user query:

1. **First Claude API call** → Claude decides to use `search_course_content` tool
2. **Tool execution** → Semantic search in ChromaDB (top 5 chunks)
3. **Second Claude API call** → Claude synthesizes answer from search results

**Data Flow:**
```
User Query (frontend/script.js)
  → FastAPI endpoint (backend/app.py)
  → RAGSystem orchestrator (backend/rag_system.py)
  → AIGenerator (backend/ai_generator.py)
    → Claude API Call #1 (with tools)
    → ToolManager executes search (backend/search_tools.py)
      → VectorStore searches ChromaDB (backend/vector_store.py)
      → Returns formatted chunks + sources
    → Claude API Call #2 (with tool results)
  → SessionManager saves history (backend/session_manager.py)
  → Response + sources returned to frontend
```

### Key Architectural Components

**RAGSystem (`rag_system.py`)** - Main orchestrator
- Coordinates all components (document processor, vector store, AI generator, session manager)
- Entry point: `query(query, session_id)` returns `(answer, sources)`
- Handles document ingestion via `add_course_folder(folder_path)`

**VectorStore (`vector_store.py`)** - ChromaDB wrapper with dual collections:
- `course_catalog` collection: Course metadata (titles, instructors, lessons) - used for course name resolution
- `course_content` collection: Chunked text with embeddings - used for semantic search
- Search supports optional filtering by `course_name` (fuzzy matched) and `lesson_number`

**DocumentProcessor (`document_processor.py`)** - Custom text chunking:
- Parses structured course format (Course Title/Link/Instructor → Lesson markers → content)
- Sentence-aware chunking: 800 chars with 100 char overlap
- Context injection: First chunk of each lesson prefixed with "Lesson N content:"
- Returns: `(Course, List[CourseChunk])`

**AIGenerator (`ai_generator.py`)** - Claude API client:
- Implements tool-based conversation pattern
- `_handle_tool_execution()` manages multi-turn tool use
- System prompt instructs: one search per query, no meta-commentary

**ToolManager + CourseSearchTool (`search_tools.py`)** - Tool abstraction:
- `CourseSearchTool.execute()` performs vector search and formats results
- Tracks `last_sources` for UI display (e.g., "Course Title - Lesson 3")
- Tool definition exposed to Claude API with input schema

**SessionManager (`session_manager.py`)** - Conversation state:
- In-memory storage (not persisted to DB)
- Keeps last 10 messages (5 exchanges) per session
- Returns formatted history string for Claude's system prompt

### Document Format

Course documents in `docs/` must follow this structure:
```
Course Title: [title]
Course Link: [url]
Course Instructor: [name]

Lesson 0: [title]
Lesson Link: [url]
[content...]

Lesson 1: [title]
[content...]
```

Only `.txt`, `.pdf`, `.docx` files are processed.

### ChromaDB Storage

**Location:** `backend/chroma_db/` (gitignored, persistent)
**Collections:**
- IDs use course title (catalog) or `{course_title}_{chunk_index}` (content)
- Embeddings auto-generated on `.add()` calls via `SentenceTransformerEmbeddingFunction`

### Configuration

All settings in `backend/config.py`:
- `CHUNK_SIZE = 800` / `CHUNK_OVERLAP = 100`
- `MAX_RESULTS = 5` (chunks returned per search)
- `MAX_HISTORY = 2` (conversation exchanges kept)
- `EMBEDDING_MODEL = "all-MiniLM-L6-v2"`
- `ANTHROPIC_MODEL = "claude-sonnet-4-20250514"`

### Frontend Architecture

**Vanilla JavaScript** (no framework):
- `script.js`: Handles POST to `/api/query`, displays markdown with `marked.js`
- Session ID persisted in `currentSessionId` global variable
- Sources displayed in collapsible `<details>` element
- No state management library - direct DOM manipulation

## Important Implementation Details

### When Working with Document Processing
- Chunking happens at **sentence boundaries** (regex: `(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\!|\?)\s+(?=[A-Z])`)
- Course title is used as the unique ID (not a generated UUID)
- Lesson numbers must be integers starting from 0

### When Working with Vector Search
- Search is **semantic** (embedding similarity), not keyword-based
- Course name resolution uses vector search on catalog collection (fuzzy matching)
- Metadata filters use ChromaDB's `where` parameter with `$and` logic
- Distance metric is cosine similarity (lower = more similar)

### When Working with AI Generation
- Tool choice is `"auto"` - Claude decides whether to search
- System prompt emphasizes **one search per query** to reduce latency
- Temperature is 0 for deterministic responses
- `max_tokens = 800` (Claude's responses are brief)
- Conversation history injected into system prompt, not as messages array

### When Working with API Endpoints
- `POST /api/query` → Main query endpoint (returns answer + sources + session_id)
- `GET /api/courses` → Returns course statistics (total count + titles list)
- FastAPI serves static files from `../frontend` at root path
- CORS enabled with `allow_origins=["*"]` for development

### Startup Behavior
- `@app.on_event("startup")` auto-loads docs from `../docs` folder
- Uses `clear_existing=False` to avoid re-processing existing courses
- ChromaDB client is `PersistentClient` (data survives restarts)

## Common Modifications

**Adding a new tool for Claude:**
1. Create tool class inheriting from `Tool` in `search_tools.py`
2. Implement `get_tool_definition()` and `execute(**kwargs)`
3. Register with `tool_manager.register_tool(new_tool)` in `rag_system.py`

**Changing chunk size:**
- Modify `config.CHUNK_SIZE` and `config.CHUNK_OVERLAP` in `config.py`
- Requires re-ingesting documents: `rag_system.add_course_folder(path, clear_existing=True)`

**Adding document format support:**
- Extend `document_processor.py:read_file()` to handle new format
- Update file extension filter in `rag_system.py:add_course_folder()` (line 81)

**Changing conversation history length:**
- Modify `config.MAX_HISTORY` in `config.py`
- Affects `session_manager.py:add_exchange()` truncation logic

## File References

When referencing code locations, use format: `file_path:line_number`

Example: "Course name resolution happens in `vector_store.py:102`"
- alway use uv to run the server do not use pip directly
- make sure to use uv to manage all dependencies