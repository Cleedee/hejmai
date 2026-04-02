"""
Handlers do Telegram Bot para o Hejmai.

Comandos:
- /vigia: Executa o vigia do estoque manualmente
- /vigia_config: Configura horário do relatório automático
"""

import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    JobQueue,
)

from hejmai.database import SessionLocal
from hejmai.vigia_estoque.vigia import executar_vigia
from hejmai.vigia_estoque.analise_consumo import gerar_relatorio_texto, analisar_estoque


# =============================================================================
# Comandos
# =============================================================================

async def comando_vigia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Executa o vigia do estoque manualmente.
    
    Uso: /vigia
    """
    await update.message.reply_text(
        "🔍 Executando Vigia do Estoque...\n"
        "_Isso pode levar alguns segundos._",
        parse_mode="Markdown",
    )
    
    db = SessionLocal()
    
    try:
        # Executa análise
        analise = analisar_estoque(db)
        relatorio = gerar_relatorio_texto(analise)
        
        # Envia relatório
        await update.message.reply_text(
            relatorio,
            parse_mode="Markdown",
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")
    
    finally:
        db.close()


async def comando_vigia_config(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Mostra configuração atual do vigia.
    
    Uso: /vigia_config
    """
    from hejmai.vigia_estoque.analise_consumo import (
        DIAS_PARA_ACABAR_ALERTA,
        DIAS_PARA_VENCER_ALERTA,
        DIAS_ANALISE_CONSUMO,
    )
    
    config_texto = f"""
⚙️ *Configuração do Vigia*

📊 *Parâmetros de Análise*
• Alerta estoque: <{DIAS_PARA_ACABAR_ALERTA} dias
• Alerta validade: <{DIAS_PARA_VENCER_ALERTA} dias
• Período análise: {DIAS_ANALISE_CONSUMO} dias

🤖 *Telegram*
• Token: {'✅ Configurado' if os.getenv('TELEGRAM_TOKEN') else '❌ Não configurado'}
• Chat ID: `{os.getenv('TELEGRAM_CHAT_ID', 'Não configurado')}`

💡 *Dica:* Para executar manualmente, use /vigia
"""
    
    await update.message.reply_text(config_texto, parse_mode="Markdown")


async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Comando de boas-vindas.
    
    Uso: /start
    """
    texto = """
👋 Olá! Eu sou o *Vigia do Estoque* do Hejmai!

📦 Posso te ajudar a:
• Monitorar produtos acabando
• Alertar sobre vencimentos próximos
• Enviar relatórios diários

🔧 *Comandos disponíveis:*
• /vigia - Executa análise agora
• /vigia_config - Ver configurações
• /start - Esta mensagem

💡 *Dica:* Configure as variáveis TELEGRAM_TOKEN e TELEGRAM_CHAT_ID no .env
"""
    
    await update.message.reply_text(texto, parse_mode="Markdown")


# =============================================================================
# Jobs Agendados
# =============================================================================

async def job_relatorio_diario(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Job agendado para enviar relatório diário.
    
    Executa todos os dias às 08:00 (configurável).
    """
    print("🔔 Executando job de relatório diário...")
    
    db = SessionLocal()
    
    try:
        analise = analisar_estoque(db)
        
        # Só envia se tiver alertas urgentes
        from hejmai.vigia_estoque.analise_consumo import tem_alertas_urgentes
        
        if tem_alertas_urgentes(analise):
            relatorio = gerar_relatorio_texto(analise)
            
            # Pega chat_id do contexto ou das variáveis de ambiente
            chat_id = context.chat_data.get("chat_id") or os.getenv("TELEGRAM_CHAT_ID")
            token = os.getenv("TELEGRAM_TOKEN")
            
            if chat_id and token:
                from hejmai.vigia_estoque.vigia import enviar_relatorio_telegram
                enviar_relatorio_telegram(relatorio, token, chat_id)
            else:
                print("❌ Chat ID ou Token não configurados")
        else:
            print("✅ Sem alertas urgentes. Relatório não enviado.")
    
    finally:
        db.close()


# =============================================================================
# Inicialização
# =============================================================================

def criar_bot(job_queue: JobQueue = None) -> Application:
    """
    Cria e configura o bot do Telegram.
    
    Args:
        job_queue: JobQueue para agendamentos
    
    Returns:
        Application configurada
    """
    token = os.getenv("TELEGRAM_TOKEN")
    
    if not token:
        print("⚠️ TELEGRAM_TOKEN não configurado. Bot não será iniciado.")
        return None
    
    # Cria aplicação
    app = Application.builder().token(token).build()
    
    # Adiciona handlers
    app.add_handler(CommandHandler("vigia", comando_vigia))
    app.add_handler(CommandHandler("vigia_config", comando_vigia_config))
    app.add_handler(CommandHandler("start", comando_start))
    
    # Agenda job diário (08:00)
    if job_queue:
        job_queue.run_daily(
            job_relatorio_diario,
            hour=8,
            minute=0,
            name="relatorio_diario",
        )
        print("📅 Job diário agendado para 08:00")
    
    print("✅ Bot do Telegram configurado")
    return app
