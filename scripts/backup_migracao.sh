#!/bin/bash
# =============================================================================
# Hejmai - Script de Backup para Migração
# =============================================================================
# Cria um pacote completo para migrar o sistema para outro computador.
#
# Uso:
#   ./scripts/backup_migracao.sh              # Cria backup
#   ./scripts/backup_migracao.sh --restore    # Restaura backup
# =============================================================================

set -e

# Configurações
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="hejmai_backup_${TIMESTAMP}"
BACKUP_FILE="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Funções
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[AVISO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERRO]${NC} $1"
}

criar_backup() {
    log_info "Criando backup do Hejmai..."
    
    # Criar diretório de backups
    mkdir -p "$BACKUP_DIR"
    
    # Criar diretório temporário
    TEMP_DIR=$(mktemp -d)
    BACKUP_TEMP="${TEMP_DIR}/${BACKUP_NAME}"
    mkdir -p "$BACKUP_TEMP"
    
    # 1. Copiar banco de dados
    log_info "Copiando banco de dados..."
    if [ -f "./data/estoque.db" ]; then
        cp ./data/estoque.db "$BACKUP_TEMP/"
        log_success "Banco de dados copiado ($(du -h ./data/estoque.db | cut -f1))"
    else
        log_warn "Banco de dados não encontrado em ./data/estoque.db"
    fi
    
    # 2. Copiar .env (se existir)
    log_info "Copiando configurações..."
    if [ -f "./.env" ]; then
        cp ./.env "$BACKUP_TEMP/"
        log_success ".env copiado"
    else
        log_warn ".env não encontrado. Crie um antes de migrar."
    fi
    
    # 3. Copiar docker-compose.yml
    if [ -f "./docker-compose.yml" ]; then
        cp ./docker-compose.yml "$BACKUP_TEMP/"
    fi
    
    # 4. Copiar Dockerfiles
    if [ -d "./Dockerfile.api" ]; then
        cp ./Dockerfile.* "$BACKUP_TEMP/" 2>/dev/null || true
    fi
    
    # 5. Copiar pyproject.toml e uv.lock
    if [ -f "./pyproject.toml" ]; then
        cp ./pyproject.toml "$BACKUP_TEMP/"
        cp ./uv.lock "$BACKUP_TEMP/" 2>/dev/null || true
    fi
    
    # 6. Copiar código fonte
    log_info "Copiando código fonte..."
    if [ -d "./src" ]; then
        cp -r ./src "$BACKUP_TEMP/"
        log_success "Código fonte copiado"
    fi
    
    # 7. Criar arquivo de instruções
    cat > "$BACKUP_TEMP/RESTAURE_AQUI.txt" << 'EOF'
# =============================================================================
# Hejmai - Instruções de Restauração
# =============================================================================

## Pré-requisitos
1. Instalar Docker e Docker Compose
2. Instalar Ollama (https://ollama.ai)
3. Baixar modelo: ollama pull llama3

## Restauração
1. Extraia este arquivo:
   tar -xzf hejmai_backup_*.tar.gz

2. Entre no diretório:
   cd hejmai_backup_*

3. Inicie os containers:
   docker-compose up -d

4. Verifique o status:
   docker-compose ps

## Acessando
- API: http://localhost:8081
- Interface: http://localhost:8501
- Docs API: http://localhost:8081/docs

## Bot Telegram
Certifique-se de que o TELEGRAM_TOKEN está configurado no .env

## Logs
docker-compose logs -f
EOF
    
    # 8. Criar tar.gz
    log_info "Compactando backup..."
    mkdir -p "$(dirname "$BACKUP_FILE")"
    cd "$TEMP_DIR"
    tar -czf "$BACKUP_FILE" "$BACKUP_NAME"
    cd - > /dev/null
    
    # Limpar temporário
    rm -rf "$TEMP_DIR"
    
    # Resultado
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log_success "Backup criado: $BACKUP_FILE ($BACKUP_SIZE)"
    echo ""
    log_info "Para restaurar em outro computador:"
    echo "  1. Copie o arquivo: $BACKUP_FILE"
    echo "  2. No novo computador: tar -xzf $BACKUP_NAME.tar.gz"
    echo "  3. cd $BACKUP_NAME"
    echo "  4. docker-compose up -d"
}

restaurar_backup() {
    log_info "Restaurando backup do Hejmai..."
    
    # Encontrar arquivo de backup mais recente
    BACKUP_FILE=$(ls -t ./backups/hejmai_backup_*.tar.gz 2>/dev/null | head -1)
    
    if [ -z "$BACKUP_FILE" ]; then
        log_error "Nenhum backup encontrado em ./backups/"
        exit 1
    fi
    
    log_info "Restaurando: $BACKUP_FILE"
    
    # Extrair
    tar -xzf "$BACKUP_FILE"
    
    BACKUP_DIR_NAME=$(tar -tzf "$BACKUP_FILE" | head -1 | cut -d/ -f1)
    
    log_success "Backup extraído em: ./$BACKUP_DIR_NAME"
    echo ""
    log_info "Próximos passos:"
    echo "  cd $BACKUP_DIR_NAME"
    echo "  docker-compose up -d"
}

# =============================================================================
# Main
# =============================================================================

case "${1:-}" in
    --restore|-r)
        restaurar_backup
        ;;
    --help|-h)
        echo "Uso: $0 [OPÇÕES]"
        echo ""
        echo "Opções:"
        echo "  (nenhuma)    Cria backup"
        echo "  --restore    Restaura backup mais recente"
        echo "  --help       Mostra esta ajuda"
        ;;
    *)
        criar_backup
        ;;
esac
