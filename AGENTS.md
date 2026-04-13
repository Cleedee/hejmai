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

```bash
# Start the API server (port 8081)
uv run dev

# Install dependencies
uv sync

# Add dependency
uv add <package>
```

---

## Code Style Guidelines

### Import Organization
1. Standard library imports
2. Third-party imports
3. Local application imports

### Naming Conventions
| Element | Convention | Example |
|---------|-----------|---------|
| Classes | PascalCase | `class Produto` |
| Functions/variables | snake_case | `traga_todas_categorias()` |
| Database columns | snake_case | `estoque_atual` |

### Error Handling
- Use `HTTPException` for API errors
- Always `db.rollback()` on failure

---

## Project Structure

```
src/hejmai/
├── main.py          # FastAPI app + routes
├── models.py        # SQLAlchemy models
├── schemas.py       # Pydantic schemas
├── database.py      # DB connection
├── crud.py          # Database operations
├── nlp.py           # Ollama integration
├── config.py        # Centralized configuration
├── telegram_bot/
│   └── handlers.py  # Bot commands
├── agents/tools/    # Agent tools
├── interface/       # Streamlit UI
└── vigia_estoque/   # Stock monitoring

scripts/
└── atualizar_tags.py  # Auto-tag products script

data/
└── estoque.db       # SQLite database
```

---

## Key Features

### Products (`/produtos`)
- CRUD operations with categories
- Price history tracking
- Tag-based organization (auto-extracted from name + category)
- Consumption frequency analysis

### Recipes (`/receitas`)
- Predefined recipes with linked ingredients
- Tag-based fallback matching (finds similar products when exact match fails)
- Suggestions based on expiring items
- Ingredient matching with stock

### Budget (`/budgets`)
- Category-based budget limits
- Spending tracking per category
- Performance reports

### AI Integration
- Ollama for natural language processing
- Product parsing from shopping receipts
- Recipe suggestions using expiring items
- Small models (qwen2.5:0.5b) work due to local hardware constraints

### Telegram Bot Commands
```
/start              - Boas-vindas
/estoque            - Ver inventário
/status             - Alertas (vencimento/estoque)
/vigia              - Relatório do Vigia
/precos <produto>   - Histórico de preços
/produto            - Gerenciar produtos
/budget             - Orçamentos por categoria
/usar <qtd> <prod>  - Registrar consumo
/desperdicio        - Registrar perda
/sugerir_jantar     - Sugere receita
/receitas           - Lista receitas
/receita <nome>     - Detalhes da receita
/add_receita        - Criar receita
/tm_*               - TheMealDB (branch feature/themealdb-import)
/lista_compras      - Lista de compras
/agente             - Pergunta à IA
/backup             - Baixar banco
```

---

## Tags System

Products and recipes use tags for organization:

**Product tags** (auto-extracted via `scripts/atualizar_tags.py`):
- From category: "laticinios", "carnes", "bebidas", etc.
- From name: extracted keywords

**Recipe tags**: "rapida", "fit", "barata", cuisine types

**Tag-based matching**: When a recipe ingredient doesn't have an exact product match, the system searches for products with matching tags.

---

## Database Schema

### Tables
- `produtos` - Product catalog
- `compras` - Purchase records
- `itens_compra` - Items per purchase
- `categorias` - Categories
- `receitas` - Recipes
- `itens_receita` - Recipe ingredients
- `budgets` - Budget limits
- `historico_precos` - Price history

---

## Environment Variables

```env
MODEL=qwen2.5:0.5b
OLLAMA_BASE_URL=http://localhost:11434
```

---

## Running the Application

1. Ensure Ollama is running locally
2. Install dependencies: `uv sync`
3. Start server: `uv run dev`
4. Access API docs at `http://localhost:8081/docs`
