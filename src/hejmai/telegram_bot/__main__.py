"""
Bot do Telegram do Hejmai.

Executa:
- Handlers de comandos (/vigia, /vigia_config, /start)
- Job agendado de relatório diário
"""

import os
import asyncio
from pathlib import Path

# Adiciona src ao PYTHONPATH
src_path = Path(__file__).parent.parent.parent
os.environ["PYTHONPATH"] = str(src_path)

from telegram.ext import Application, JobQueue

from hejmai.telegram_bot.handlers import criar_bot


async def main():
    """Função principal assíncrona."""
    print("🤖 Iniciando Bot do Telegram...")
    
    # Cria aplicação com job queue
    job_queue = JobQueue()
    app = criar_bot(job_queue=job_queue)
    
    if app is None:
        print("❌ Bot não configurado. Encerrando.")
        return
    
    # Inicia job queue
    await job_queue.initialize()
    
    # Inicia bot
    print("📡 Bot em execução. Pressione Ctrl+C para parar.")
    await app.initialize()
    await app.start()
    
    # Mantém rodando
    while True:
        await asyncio.sleep(1)


def start():
    """Função de entrada para o script."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot encerrado.")


if __name__ == "__main__":
    start()
