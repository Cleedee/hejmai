# Hejmai - Guia Docker

## Visão Geral

O Hejmai é executado em 3 containers Docker:

| Serviço | Container | Porta | Descrição |
|---------|-----------|-------|-----------|
| **API** | `hejmai_api` | 8081 | FastAPI + Ollama + SQLite |
| **Bot** | `hejmai_bot` | - | Bot do Telegram |
| **Interface** | `hejmai_streamlit` | 8501 | Interface web Streamlit |

## Pré-requisitos

1. **Docker** e **Docker Compose** instalados
2. **Ollama** rodando localmente (para a API usar o LLM)
3. **Token do Telegram** (para o bot)

## Configuração Rápida

### 1. Clone o repositório

```bash
cd /path/to/hejmai
```

### 2. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o arquivo `.env` e preencha:

```bash
TELEGRAM_TOKEN=seu_token_aqui
```

### 3. Inicie os containers

**Produção:**
```bash
docker-compose up -d
```

**Desenvolvimento (com hot reload):**
```bash
docker-compose -f docker-compose.dev.yml up -d
```

### 4. Verifique o status

```bash
docker-compose ps
```

## Acessando os Serviços

| Serviço | URL | Descrição |
|---------|-----|-----------|
| API | http://localhost:8081 | API REST + docs em /docs |
| Interface | http://localhost:8501 | Interface web Streamlit |
| Bot | No Telegram | Converse com @seu_bot |

## Comandos Úteis

### Logs

```bash
# Todos os serviços
docker-compose logs -f

# Serviço específico
docker-compose logs -f api
docker-compose logs -f bot
docker-compose logs -f interface
```

### Parar os serviços

```bash
# Parar tudo
docker-compose down

# Parar e remover volumes (⚠️ apaga o banco!)
docker-compose down -v
```

### Reiniciar um serviço

```bash
docker-compose restart api
```

### Acessar o container

```bash
# API
docker exec -it hejmai_api bash

# Bot
docker exec -it hejmai_bot bash

# Interface
docker exec -it hejmai_streamlit bash
```

### Executar comandos dentro do container

```bash
# Rodar testes na API
docker exec hejmai_api uv run pytest

# Ver banco de dados
docker exec hejmai_api ls -la /app/data/
```

## Estrutura de Volumes

| Volume | Caminho no Container | Descrição |
|--------|---------------------|-----------|
| `hejmai_data` | `/app/data` | Banco de dados SQLite |

## Rede

Todos os containers estão na rede `hejmai_network`:

- API se comunica com Ollama via `host.docker.internal:11434`
- Bot e Interface se comunicam com API via `http://api:8081`

## Troubleshooting

### API não inicia

Verifique se o Ollama está rodando:

```bash
curl http://localhost:11434/api/tags
```

### Bot não conecta

Verifique o token do Telegram:

```bash
curl https://api.telegram.org/bot<SEU_TOKEN>/getMe
```

### Interface não carrega

Verifique se a API está saudável:

```bash
curl http://localhost:8081
```

### Banco de dados corrompido

Remova o volume e reinicie (⚠️ perde todos os dados):

```bash
docker-compose down -v
docker-compose up -d
```

## Build Manual

Se precisar rebuildar as imagens:

```bash
# Rebuildar tudo
docker-compose build --no-cache

# Rebuildar serviço específico
docker-compose build api
```

## Variáveis de Ambiente

| Variável | Serviço | Descrição |
|----------|---------|-----------|
| `TELEGRAM_TOKEN` | Bot | Token do bot no Telegram |
| `DATABASE_URL` | API | URL de conexão com SQLite |
| `DATABASE_PATH` | API, Bot | Caminho do arquivo SQLite |
| `OLLAMA_BASE_URL` | API | URL do servidor Ollama |
| `MODEL` | API | Modelo do Ollama (llama3, llama2, etc.) |
| `API_URL` | Bot, Interface | URL da API interna |

## Segurança

- **Não commitar** o arquivo `.env` (já está no `.gitignore`)
- Use tokens fortes para o Telegram
- Em produção, use HTTPS para a API e Interface
- Considere usar um proxy reverso (nginx, traefik) para SSL
