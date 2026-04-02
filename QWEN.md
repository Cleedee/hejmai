# Hejmai - Contexto do Projeto

## Visão Geral

**Hejmai** é um sistema de gestão de despensa e planejamento de refeições com foco em economia doméstica. O projeto combina uma API REST em FastAPI com uma interface web em Streamlit, utilizando IA (Ollama) para processamento de linguagem natural.

### Funcionalidades Principais

- **Gestão de Estoque**: Cadastro de produtos, controle de validade e movimentações
- **Entrada de Compras via NLP**: Extração automática de itens de notas fiscais usando Ollama (LLM local)
- **Alertas Inteligentes**: Produtos com estoque baixo e vencimento próximo
- **Histórico de Preços**: Rastreamento de preços por produto e local de compra
- **Previsão de Gastos**: Estimativa de custos para reposição de estoque
- **Budget por Categoria**: Definição de limites de gastos mensais
- **Sugestão de Receitas**: IA sugere receitas com base em itens próximos do vencimento
- **Vigia do Estoque**: Monitora burn rate e envia alertas via Telegram
- **Bot Telegram**: Comandos para consultar estoque, registrar consumo, gerar listas
- **Interface Streamlit**: Dashboard interativo para gestão completa

## Stack Tecnológico

| Componente | Tecnologia |
|------------|-----------|
| Framework API | FastAPI |
| Interface Web | Streamlit |
| ORM | SQLAlchemy |
| Banco de Dados | SQLite |
| IA/LLM | Ollama (llama3, llama2) |
| Package Manager | uv |
| Python | 3.14+ |

## Estrutura do Projeto

```
hejmai/
├── src/
│   ├── hejmai/                  # Código principal da API
│   │   ├── __init__.py
│   │   ├── main.py              # App FastAPI + rotas
│   │   ├── models.py            # Modelos SQLAlchemy
│   │   ├── schemas.py           # Schemas Pydantic
│   │   ├── database.py          # Configuração do banco
│   │   ├── crud.py              # Operações de banco
│   │   ├── nlp.py               # Integração com Ollama
│   │   ├── validator.py         # Validação de dados (Sanity Check)
│   │   ├── analista_ia.py       # Analista de estoque com IA
│   │   ├── services.py          # Serviços de negócio
│   │   ├── telegram_bot/        # Bot do Telegram
│   │   │   ├── __init__.py
│   │   │   ├── __main__.py      # Entry point do bot
│   │   │   └── handlers.py      # Handlers de comandos
│   │   ├── interface/           # Interface Streamlit
│   │   │   ├── __init__.py
│   │   │   ├── app.py           # App principal
│   │   │   ├── config.py        # Configurações
│   │   │   ├── api_client.py    # Cliente HTTP
│   │   │   ├── components/      # Componentes reutilizáveis
│   │   │   └── utils/           # Utilitários
│   │   ├── vigia_estoque/       # Vigia do Estoque
│   │   │   ├── __init__.py
│   │   │   ├── analise_consumo.py  # Análise de burn rate
│   │   │   └── vigia.py         # Script principal
│   │   └── scripts/             # Scripts de migração
│   └── telegram_bot/            # (Legado - será removido)
├── main.py                      # Entry point (placeholder)
├── pyproject.toml               # Dependências e config do projeto
├── web.sh                       # Script para rodar Streamlit
└── data/
    └── estoque.db               # Banco de dados SQLite
```

## Comandos de Build e Execução

### Instalação de Dependências

```bash
uv sync
```

### Iniciar Servidor de Desenvolvimento (API)

```bash
# Via script definido no pyproject.toml
uv run dev

# Ou diretamente com uvicorn
uv run uvicorn hejmai.main:app --reload --port 8081 --app-dir src
```

A API estará disponível em `http://localhost:8081` com docs em `http://localhost:8081/docs`.

### Iniciar Interface Web (Streamlit)

```bash
uv run streamlit run src/hejmai/interface/app.py --server.headless true
```

Ou usar o script:
```bash
./web.sh
```

### Iniciar Bot do Telegram

```bash
# Via script definido no pyproject.toml
uv run telegram

# Ou diretamente
uv run python -m hejmai.telegram_bot
```

### Variáveis de Ambiente

Criar arquivo `.env` na raiz:

```env
MODEL=llama3
OLLAMA_BASE_URL=http://localhost:11434
DATABASE_PATH=./estoque.db
```

### Pré-requisitos

- **Ollama** deve estar rodando localmente para funcionalidades de IA
- Modelo `llama3` (ou outro configurado) deve estar disponível no Ollama

## Modelos de Dados

### Principais Entidades

| Tabela | Descrição |
|--------|-----------|
| `produtos` | Catálogo de produtos com estoque e validade |
| `compras` | Registro de compras (nota fiscal) |
| `itens_compra` | Itens de cada compra (histórico de preços) |
| `categorias` | Categorias de produtos |
| `budgets` | Orçamentos mensais por categoria |
| `movimentacoes` | Histórico de movimentações (entrada/saída) |

### Categorias Permitidas

```
Açougue, Laticínios, Hortifruti, Mercearia, Higiene, Limpeza, Padaria, Bebidas
```

## Endpoints da API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/` | Status do servidor |
| `POST` | `/ia/perguntar` | Pergunta em linguagem natural → SQL → Resposta |
| `GET` | `/estoque/resumo-geral` | Resumo do estoque positivo |
| `GET` | `/produtos/alertas` | Produtos com estoque baixo ou vencendo |
| `POST` | `/processar-entrada-livre` | Processa texto livre com NLP |
| `POST` | `/compras/registrar-lote` | Registra compra em lote |
| `GET` | `/sugerir-receita` | Sugere receita com itens vencendo |
| `GET` | `/relatorios/historico-precos/{id}` | Histórico de preços do produto |
| `GET` | `/relatorios/previsao-gastos` | Previsão de gastos para reposição |
| `GET` | `/relatorios/performance-budget` | Performance vs orçamento |
| `PATCH` | `/produtos/consumir/{id}` | Registra consumo de produto |
| `PATCH` | `/produtos/{id}` | Atualiza produto |
| `GET` | `/categorias` | Lista categorias |
| `POST` | `/categoria` | Cria categoria |

## Convenções de Desenvolvimento

### Imports (nesta ordem)

1. Standard library
2. Third-party
3. Local imports

```python
import datetime
from typing import List

from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from hejmai import models, schemas, database
```

### Nomenclatura

- **Classes**: PascalCase (`Produto`, `ProcessadorCompras`)
- **Funções/variáveis**: snake_case (`estoque_atual`, `traga_todas_categorias`)
- **Constantes**: SCREAMING_SNAKE (`SQLALCHEMY_DATABASE_URL`)
- **Colunas DB**: snake_case

### Error Handling

- Usar `HTTPException` do FastAPI com códigos HTTP apropriados
- Sempre fazer `db.rollback()` em caso de erro
- Transações devem ser commitadas apenas após validação completa

```python
try:
    # operações
    db.commit()
except Exception as e:
    db.rollback()
    raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")
```

### Padrões de API

- Handlers assíncronos (`async def`) para operações I/O
- Retornar dicionários para respostas complexas
- Usar schemas Pydantic para validação de request/response
- Documentar endpoints com status codes apropriados

## Fluxo de Processamento NLP

1. **Entrada de Texto Livre**: Usuário descreve compra em linguagem natural
2. **Extração com Ollama**: IA extrai estrutura JSON (itens, quantidades, preços)
3. **Sanity Check**: Validação de preços e quantidades (alertas se anormal)
4. **Refinamento de Categoria**: Fuzzy matching com categorias do banco
5. **Persistência**: Cria/Atualiza produtos, registra compra e atualiza estoque

## Observações Importantes

- O banco `estoque.db` é criado automaticamente ao iniciar a API
- A tabela `movimentacoes` requer migração manual via `scripts/create_movimentacoes.py`
- O Streamlit espera a API rodando em `http://localhost:8081`
- O Ollama deve estar acessível em `http://localhost:11434` (configurável via env)
