"""
Bot do Telegram do Hejmai.

Executa:
- Handlers de comandos (/vigia, /estoque, /status, etc.)
- Job agendado de relatório diário (08:00)
- Processamento NLP de compras (mensagens de texto)
"""

import os
from telegram import Update
from telegram.ext import Application, JobQueue

from hejmai.telegram_bot.handlers import criar_bot


def start():
    """Função de entrada para o script."""
    token = os.getenv("TELEGRAM_TOKEN")
    
    if not token:
        print("⚠️ TELEGRAM_TOKEN não configurado. Bot não será iniciado.")
        print("Configure a variável TELEGRAM_TOKEN no .env ou docker-compose.yml")
        return
    
    print("🤖 Iniciando Bot do Telegram...")
    print(f"📡 API_URL: {os.getenv('API_URL', 'http://api:8081')}")
    
    # Cria aplicação
    app = Application.builder().token(token).build()
    
    # Configura handlers
    criar_bot(app=app)
    
    print("📡 Bot em execução. Pressione Ctrl+C para parar.")
    print("")
    print("📋 Comandos disponíveis:")
    print("   /vigia - Relatório do Vigia do Estoque")
    print("   /estoque - Ver inventário completo")
    print("   /status - Ver alertas")
    print("   /usar - Registrar consumo")
    print("   /sugerir_jantar - Sugere receita")
    print("   /lista_compras - Gera lista de compras")
    print("   /pergunta - Pergunte à IA")
    print("")
    
    # Inicia polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    start()
