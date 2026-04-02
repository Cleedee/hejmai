"""
Script do Vigia do Estoque.

Pode ser executado:
1. Manualmente via comando /vigia no Telegram
2. Automaticamente via job agendado (diário às 08:00)
3. Via CLI: uv run python -m hejmai.vigia_estoque.vigia
"""

import os
import sys
from pathlib import Path

# Adiciona src ao PYTHONPATH
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from sqlalchemy.orm import Session

from hejmai.database import SessionLocal
from hejmai.vigia_estoque.analise_consumo import (
    analisar_estoque,
    gerar_relatorio_texto,
    tem_alertas_urgentes,
)


def enviar_relatorio_telegram(relatorio: str, token: str, chat_id: str) -> bool:
    """
    Envia relatório via Telegram.
    
    Args:
        relatorio: Texto do relatório
        token: Token do bot
        chat_id: ID do chat/usuario
    
    Returns:
        True se enviado com sucesso
    """
    try:
        import requests
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": relatorio,
            "parse_mode": "Markdown",
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        print(f"✅ Relatório enviado para Telegram (chat_id: {chat_id})")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao enviar Telegram: {e}")
        return False


def executar_vigia(
    db: Session,
    token_telegram: str = None,
    chat_id: str = None,
    enviar_sempre: bool = False,
) -> dict:
    """
    Executa o vigia do estoque.
    
    Args:
        db: Sessão do banco
        token_telegram: Token do bot (opcional)
        chat_id: ID do chat (opcional)
        enviar_sempre: Se True, envia mesmo sem alertas urgentes
    
    Returns:
        Dict com resultados da análise
    """
    print("🔍 Iniciando Vigia do Estoque...")
    
    # Analisa estoque
    analise = analisar_estoque(db)
    
    print(f"📦 Produtos monitorados: {analise['total_monitorados']}")
    print(f"🔴 Produtos acabando: {len(analise['produtos_acabando'])}")
    print(f"⏰ Produtos vencendo: {len(analise['produtos_vencendo'])}")
    
    # Gera relatório
    relatorio = gerar_relatorio_texto(analise)
    
    # Verifica se deve enviar
    deve_enviar = enviar_sempre or tem_alertas_urgentes(analise)
    
    if deve_enviar and token_telegram and chat_id:
        enviar_relatorio_telegram(relatorio, token_telegram, chat_id)
    elif deve_enviar:
        print("\n📋 RELATÓRIO (não enviado - falta token/chat_id):")
        print(relatorio)
    else:
        print("\n✅ Sem alertas urgentes. Relatório não enviado.")
        print("\n📋 Relatório completo:")
        print(relatorio)
    
    return analise


def main():
    """Função principal para execução via CLI."""
    # Carrega variáveis de ambiente
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    enviar_sempre = os.getenv("VIGIA_ENVIAR_SEMPRE", "false").lower() == "true"
    
    # Conecta ao banco
    db = SessionLocal()
    
    try:
        executar_vigia(
            db=db,
            token_telegram=token,
            chat_id=chat_id,
            enviar_sempre=enviar_sempre,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
