# 📦 Guia de Migração via Bot Telegram

## Visão Geral

A forma mais **prática e profissional** de migrar o Hejmai para outro computador é usando o comando `/backup` do bot Telegram.

---

## 🚀 Passo a Passo

### 1. No Computador Atual

```bash
# Abra o Telegram e envie:
/backup
```

O bot responderá com um arquivo `hejmai_backup_YYYYMMDD.tar.gz` contendo:
- `estoque.db` - Seu banco de dados completo
- `.env` - Todas as configurações (tokens, URLs)

**Baixe o arquivo** no seu computador ou celular.

---

### 2. No Novo Computador

#### Instalar Pré-requisitos

```bash
# 1. Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 2. Ollama (para IA local)
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3
```

#### Clonar Repositório

```bash
# Clone o repositório do GitHub
git clone https://github.com/seu-usuario/hejmai.git
cd hejmai
```

#### Restaurar Backup

```bash
# 1. Extrair o backup
tar -xzf hejmai_backup_*.tar.gz

# 2. Mover arquivos para os locais corretos
mv estoque.db ./data/
mv .env ./

# 3. Iniciar o sistema
docker-compose up -d
```

#### Verificar

```bash
# Verificar containers
docker-compose ps

# Testar API
curl http://localhost:8081

# Verificar banco
docker exec hejmai_api uv run python -c "
from hejmai.database import SessionLocal
db = SessionLocal()
from hejmai import models
print(f'Produtos: {db.query(models.Produto).count()}')
"
```

---

## 🔒 Segurança

O comando `/backup` é **restrito ao administrador**:
- Apenas o `CHAT_ID_PESSOAL` configurado no `.env` pode usar
- Outros usuários recebem: "🔒 Este comando é restrito ao administrador."

---

## 📋 Comandos do Bot

| Comando | Descrição |
|---------|-----------|
| `/backup` | 📦 Baixar banco + configurações |
| `/estoque` | Ver inventário completo |
| `/vigia` | Relatório do Vigia do Estoque |
| `/ultimas_compras` | Ver últimas compras |
| `/status` | Ver alertas |
| `/usar` | Registrar consumo |
| `/sugerir_jantar` | Sugere receita |
| `/lista_compras` | Gera lista de compras |
| `/pergunta` | Pergunte à IA |

---

## ⚠️ Atenção

### OLLAMA_BASE_URL

No novo computador, ajuste o `.env`:

| Sistema | Valor |
|---------|-------|
| **Linux** | `http://172.17.0.1:11434` |
| **Mac** | `http://host.docker.internal:11434` |
| **Windows** | `http://host.docker.internal:11434` |

### Modelo do Ollama

Certifique-se de que o modelo está disponível:

```bash
ollama list
# Se não tiver llama3:
ollama pull llama3
```

---

## 🎯 Vantagens Desta Abordagem

| Vantagem | Descrição |
|----------|-----------|
| **Prático** | Tudo pelo Telegram, sem scripts |
| **Seguro** | Restrito ao administrador |
| **Completo** | Banco + configurações em um arquivo |
| **Rápido** | 3 comandos no novo PC |
| **Versionado** | Código pelo GitHub, dados pelo bot |

---

## 📊 Exemplo de Uso

```
Você: /backup

Bot: 📦 Gerando backup...
     Isso pode levar alguns segundos.

[Bot envia arquivo: hejmai_backup_20260403.tar.gz]

Bot: 📦 Backup do Hejmai

     Contém:
     • estoque.db - Banco de dados
     • .env - Configurações

     Para restaurar:
     1. Extraia os arquivos
     2. Coloque no diretório do projeto
     3. Execute: docker-compose up -d
```

---

## 🛠️ Troubleshooting

### "Banco de dados vazio"

Verifique se o `estoque.db` está no lugar certo:

```bash
ls -la ./data/estoque.db
```

### "Bot não conecta"

Verifique o `TELEGRAM_TOKEN` no `.env`:

```bash
docker exec hejmai_bot env | grep TELEGRAM
```

### "Ollama não responde"

Teste a conexão:

```bash
curl http://localhost:11434/api/tags
```

Ajuste `OLLAMA_BASE_URL` no `.env` se necessário.
