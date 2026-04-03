# 🚀 Guia de Migração para Outro Computador

## Visão Geral

Este guia explica como migrar o Hejmai para um computador mais potente para rodar o LLM localmente.

---

## 📦 O Que Precisa Ser Migrado

| Arquivo/Diretório | Por Que | Tamanho Típico |
|-------------------|---------|----------------|
| `data/estoque.db` | Banco de dados com todo o estoque | ~50KB - 1MB |
| `.env` | Configurações (tokens, URLs) | ~1KB |
| `docker-compose.yml` | Configuração dos containers | ~2KB |
| `Dockerfile.*` | Definição das imagens | ~3KB cada |
| `src/` | Código fonte | ~500KB |
| `pyproject.toml` + `uv.lock` | Dependências | ~200KB |

---

## 🛠️ Método 1: Script de Backup (Recomendado)

### No Computador Atual

```bash
# 1. Criar backup completo
./scripts/backup_migracao.sh

# Saída:
# [OK] Backup criado: ./backups/hejmai_backup_20260403_123456.tar.gz (1.2MB)
```

### No Novo Computador

```bash
# 1. Instalar pré-requisitos
# Docker: https://docs.docker.com/get-docker/
# Ollama: https://ollama.ai

# 2. Instalar Ollama e baixar modelo
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3

# 3. Copiar o backup para o novo computador
scp hejmai_backup_*.tar.gz usuario@novo-pc:~/

# 4. No novo computador, extrair e iniciar
tar -xzf hejmai_backup_*.tar.gz
cd hejmai_backup_*

# 5. Iniciar tudo
docker-compose up -d

# 6. Verificar status
docker-compose ps
```

---

## 🛠️ Método 2: Manual (Passo a Passo)

### No Computador Atual

```bash
# 1. Criar diretório de migração
mkdir -p hejmai_migracao
cd hejmai_migracao

# 2. Copiar arquivos essenciais
cp ../data/estoque.db ./
cp ../.env ./
cp ../docker-compose.yml ./
cp ../Dockerfile.* ./
cp ../pyproject.toml ./
cp ../uv.lock ./
cp -r ../src ./

# 3. Compactar
cd ..
tar -czf hejmai_migracao.tar.gz hejmai_migracao/
```

### No Novo Computador

```bash
# 1. Instalar Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 2. Instalar Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3

# 3. Extrair backup
tar -xzf hejmai_migracao.tar.gz
cd hejmai_migracao

# 4. Ajustar .env se necessário
nano .env
# Verifique:
# - OLLAMA_BASE_URL=http://host.docker.internal:11434
# - TELEGRAM_TOKEN=seu_token

# 5. Iniciar
docker-compose up -d

# 6. Verificar
docker-compose ps
curl http://localhost:8081
```

---

## 🔧 Configurações Importantes no Novo PC

### Arquivo `.env`

```bash
# ===========================================
# API FastAPI
# ===========================================
DATABASE_URL=sqlite:////app/data/estoque.db
DATABASE_PATH=/app/data/estoque.db

# URL do Ollama (ajuste se necessário)
# Linux: use IP da máquina host
# Mac/Windows: use host.docker.internal
OLLAMA_BASE_URL=http://host.docker.internal:11434

# Modelo do Ollama
MODEL=llama3

# ===========================================
# Telegram Bot
# ===========================================
TELEGRAM_TOKEN=8605596954:AAG30vmp0PQVvJkfLcF1qsLvGUclgh9NTKo
TELEGRAM_CHAT_ID=103694315

# ===========================================
# Interface
# ===========================================
API_URL=http://api:8081
```

### ⚠️ Atenção: OLLAMA_BASE_URL

| Sistema | Valor |
|---------|-------|
| **Linux** | `http://172.17.0.1:11434` ou `http://host.docker.internal:11434` |
| **Mac** | `http://host.docker.internal:11434` |
| **Windows** | `http://host.docker.internal:11434` |

Para descobrir o IP no Linux:
```bash
ip addr show docker0 | grep "inet\b" | awk '{print $2}' | cut -d/ -f1
```

---

## ✅ Verificação Pós-Migração

```bash
# 1. Verificar containers
docker-compose ps
# Todos devem estar "Up"

# 2. Testar API
curl http://localhost:8081
# {"status": "Agente Online", "ano": 2026}

# 3. Testar banco
docker exec hejmai_api uv run python -c "
from hejmai.database import SessionLocal
db = SessionLocal()
from hejmai import models
print(f'Produtos: {db.query(models.Produto).count()}')
print(f'Categorias: {db.query(models.Categoria).count()}')
"

# 4. Testar Ollama
curl http://localhost:11434/api/tags
# Deve listar os modelos disponíveis

# 5. Testar Bot Telegram
# Envie /start no Telegram
```

---

## 🚨 Problemas Comuns

### "Ollama não conecta"

```bash
# Verifique se Ollama está rodando
ollama list

# Teste conexão
curl http://localhost:11434/api/tags

# No Linux, pode precisar de:
OLLAMA_BASE_URL=http://172.17.0.1:11434
```

### "Banco de dados vazio"

```bash
# Verifique se o banco foi copiado
ls -la data/estoque.db

# Verifique tabelas
docker exec hejmai_api sqlite3 /app/data/estoque.db ".tables"
```

### "Bot não responde"

```bash
# Verifique logs
docker-compose logs bot

# Verifique TOKEN
docker exec hejmai_bot env | grep TELEGRAM
```

---

## 📊 Checklist de Migração

- [ ] Backup criado no computador atual
- [ ] Docker instalado no novo computador
- [ ] Ollama instalado e modelo baixado
- [ ] Arquivos copiados para novo computador
- [ ] `.env` configurado corretamente
- [ ] `OLLAMA_BASE_URL` ajustado para o novo sistema
- [ ] `docker-compose up -d` executado
- [ ] API respondendo em http://localhost:8081
- [ ] Interface acessível em http://localhost:8501
- [ ] Bot Telegram funcionando
- [ ] Dados do banco preservados

---

## 💡 Dicas

1. **Teste antes de desligar o PC antigo**: Verifique tudo no novo computador antes de remover do antigo.

2. **Mantenha backup**: Guarde o arquivo `.tar.gz` em um local seguro (nuvem, HD externo).

3. **Ollama no novo PC**: Baixe o modelo antes de iniciar os containers:
   ```bash
   ollama pull llama3
   ```

4. **Performance**: No PC mais potente, considere aumentar recursos no `docker-compose.yml`:
   ```yaml
   api:
     deploy:
       resources:
         limits:
           cpus: '4'
           memory: 4G
   ```
