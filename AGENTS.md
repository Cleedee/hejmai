# AGENTS.md

## Project Overview

**Hejmai** is a Portuguese pantry management and meal planning system using:
- **Framework**: FastAPI (API) + Streamlit (UI)
- **Database**: SQLite with SQLAlchemy ORM
- **AI**: Ollama for natural language processing (product parsing, recipe suggestions)
- **Package Manager**: uv
- **Python**: 3.14+

---

## Build & Run Commands

### Development Server
```bash
# Start the API server (runs on port 8081)
uv run dev

# Or directly via uvicorn
uv run uvicorn hejmai.main:app --reload --port 8081
```

### Dependency Management
```bash
# Install dependencies
uv sync

# Add a new dependency
uv add <package>

# Add dev dependency
uv add --dev <package>
```

### Testing (no framework configured yet)
```bash
# Run a single test file (once tests are added)
uv run pytest tests/test_file.py -v

# Run a specific test
uv run pytest tests/test_file.py::test_function_name -v

# Run with coverage
uv run pytest --cov=hejmai --cov-report=term-missing
```

---

## Code Style Guidelines

### Import Organization (in this order)
1. Standard library imports
2. Third-party imports
3. Local application imports

```python
# Example from main.py
import datetime
from typing import List
import os

from fastapi import Body, FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from hejmai import models, schemas, database, nlp, crud
```

### Naming Conventions
| Element | Convention | Example |
|---------|-----------|---------|
| Classes | PascalCase | `class Produto`, `class ProcessadorCompras` |
| Functions/variables | snake_case | `traga_todas_categorias()`, `estoque_atual` |
| Constants | SCREAMING_SNAKE | `SQLALCHEMY_DATABASE_URL` |
| Database columns | snake_case | `estoque_atual`, `local_compra` |

### Type Annotations
- Use `typing` module for complex types: `List`, `Optional`, `Dict`
- Annotate function parameters and return types when not obvious
- Pydantic models use `BaseModel` with typed fields

```python
from typing import List, Optional

def traga_todas_categorias(db: Session) -> List[Categoria]:
    ...
```

### Docstrings
- Add docstrings to all public classes
- Use simple descriptions (no complex formatting)

```python
class Produto(Base):
    """O Catálogo: Representa a identidade do que você consome."""
    ...
```

### Error Handling
- Use FastAPI's `HTTPException` for API errors with status codes
- Always rollback database transactions on failure

```python
@app.patch("/produtos/consumir/{produto_id}")
async def consumir_produto(produto_id: int, quantidade: float, db: Session = Depends(get_db)):
    produto = db.query(models.Produto).filter(...).first()
    
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    
    try:
        # operation
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")
```

### Database Patterns
- Use `db.commit()` after batch operations
- Use `db.flush()` when you need generated IDs before commit
- Always close sessions with `db.close()` (or use dependency injection)

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### API Response Patterns
- Return dictionaries for complex responses
- Use Pydantic schemas for request/response validation
- Document endpoints with appropriate HTTP status codes

### Async/Await
- Mark FastAPI route handlers as `async` when using async libraries
- Use `await` for I/O operations (Ollama calls, database queries via async sessions)

---

## Project Structure

```
hejmai/
├── src/
│   └── hejmai/
│       ├── __init__.py
│       ├── main.py          # FastAPI app + routes
│       ├── models.py        # SQLAlchemy models
│       ├── schemas.py       # Pydantic schemas
│       ├── database.py      # DB connection
│       ├── crud.py          # Database operations
│       ├── nlp.py           # Ollama integration
│       ├── validator.py     # Data validation
│       └── services.py
├── main.py                  # Entry point
├── pyproject.toml
├── uv.lock
└── estoque.db               # SQLite database
```

---

## Key Dependencies

| Package | Purpose |
|---------|---------|
| fastapi | REST API framework |
| sqlalchemy | ORM |
| streamlit | Web UI |
| ollama | AI/LLM integration |
| uvicorn | ASGI server |
| pydantic | Data validation |
| python-dotenv | Environment variables |

---

## Environment Variables

Create a `.env` file with:
```
MODEL=llama3                    # Ollama model
OLLAMA_BASE_URL=http://localhost:11434
```

---

## Running the Application

1. Ensure Ollama is running locally
2. Install dependencies: `uv sync`
3. Start server: `uv run dev`
4. Access API docs at `http://localhost:8081/docs`
