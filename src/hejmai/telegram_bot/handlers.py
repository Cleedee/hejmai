"""
Handlers do Telegram Bot para o Hejmai.

Comandos:
- /start: Boas-vindas
- /estoque: Ver estoque completo
- /status: Ver alertas de estoque
- /vigia: Executa o vigia do estoque (novo)
- /vigia_config: Configurações do vigia (novo)
- /usar: Registrar consumo de produto
- /sugerir_jantar: Sugere receita com itens vencendo
- /lista_compras: Gera lista de compras
- /pergunta: Pergunta em linguagem natural
- Mensagens de texto: Processa compras via NLP
"""

import os
import datetime
import httpx
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    JobQueue,
)

from hejmai.database import SessionLocal
from hejmai import crud
from hejmai.vigia_estoque.vigia import executar_vigia
from hejmai.vigia_estoque.analise_consumo import (
    gerar_relatorio_texto,
    analisar_estoque,
    tem_alertas_urgentes,
)


# =============================================================================
# Configuração
# =============================================================================

API_URL = os.getenv("API_URL", "http://api:8081")
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID_PESSOAL = os.getenv("TELEGRAM_CHAT_ID")

# Usuários permitidos (separados por vírgula)
ALLOWED_USER_IDS = os.getenv("TELEGRAM_ALLOWED_USERS", CHAT_ID_PESSOAL or "")
ALLOWED_GROUP_IDS = os.getenv("TELEGRAM_ALLOWED_GROUPS", "")


def is_authorized(update: Update) -> bool:
    """
    Verifica se o usuário ou grupo está autorizado a usar o bot.

    Regras:
    1. Se ALLOWED_USER_IDS estiver vazio, permite apenas CHAT_ID_PESSOAL
    2. Verifica se o usuário está na lista de permitidos
    3. Verifica se o chat é um grupo permitido
    """
    if not update.effective_user:
        return False

    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id) if update.effective_chat else ""

    # Lista de usuários permitidos
    users_allowed = {u.strip() for u in ALLOWED_USER_IDS.split(",") if u.strip()}
    # Lista de grupos permitidos
    groups_allowed = {g.strip() for g in ALLOWED_GROUP_IDS.split(",") if g.strip()}

    # Se não há configuração, permite apenas o dono
    if not users_allowed and not groups_allowed:
        return user_id == str(CHAT_ID_PESSOAL)

    # Verifica se usuário está autorizado
    if user_id in users_allowed:
        return True

    # Verifica se é um grupo autorizado (chat_id negativo para grupos/supergrupos)
    if chat_id.startswith("-") and chat_id in groups_allowed:
        return True

    return False


async def check_authorization(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Middleware de autorização. Retorna False e envia mensagem se não autorizado."""
    if not is_authorized(update):
        await update.message.reply_text(
            "🔒 Acesso negado. Você não tem permissão para usar este bot."
        )
        return False
    return True


def authorized_handler(func):
    """Decorator para adicionar verificação de autorização automaticamente."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_authorization(update, context):
            return
        return await func(update, context)
    return wrapper


# =============================================================================
# Comandos do Vigia do Estoque (Novo)
# =============================================================================

@authorized_handler
async def comando_vigia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Executa o vigia do estoque manualmente.
    Uso: /vigia
    """
    await update.message.reply_text(
        "🔍 Executando Vigia do Estoque...\n_Isso pode levar alguns segundos._",
        parse_mode="Markdown",
    )

    db = SessionLocal()

    try:
        analise = analisar_estoque(db)
        relatorio = gerar_relatorio_texto(analise)
        await update.message.reply_text(relatorio, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")
    finally:
        db.close()


@authorized_handler
async def comando_vigia_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
• Token: {'✅ Configurado' if TOKEN else '❌ Não configurado'}
• Chat ID: `{CHAT_ID_PESSOAL or 'Não configurado'}`

💡 *Dica:* Para executar manualmente, use /vigia
"""
    await update.message.reply_text(config_texto, parse_mode="Markdown")


# =============================================================================
# Comandos do Bot Original
# =============================================================================

@authorized_handler
async def comando_estoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista todo o estoque por categoria."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/estoque/resumo-geral")
            estoque = response.json()

        if not estoque:
            await update.message.reply_text(
                "📭 O estoque está vazio. Hora de usar o Streamlit para a carga inicial!"
            )
            return

        mensagem = "🏠 **Inventário Hejmai**\n\n"
        categoria_atual = ""

        icones = {
            "Açougue": "🥩",
            "Laticínios": "🥛",
            "Hortifruti": "🍎",
            "Mercearia": "🌾",
            "Higiene": "🧼",
            "Limpeza": "🧹",
            "Padaria": "🥖",
            "Bebidas": "🍶",
        }

        for p in estoque:
            if p["categoria"] != categoria_atual:
                categoria_atual = p["categoria"]
                icone = icones.get(categoria_atual, "📦")
                mensagem += f"\n{icone} **{categoria_atual.upper()}**\n"

            validade_str = datetime.datetime.strptime(
                p["ultima_validade"], "%Y-%m-%d"
            ).strftime("%d/%m")

            hoje = datetime.date.today()
            vencimento = datetime.datetime.strptime(
                p["ultima_validade"], "%Y-%m-%d"
            ).date()
            alerta = "⚠️" if (vencimento - hoje).days <= 3 else "🔹"

            mensagem += f"{alerta} {p['nome']}: {p['estoque_atual']} {p['unidade_medida']} (Vence: {validade_str})\n"

        if len(mensagem) > 4000:
            for i in range(0, len(mensagem), 4000):
                await update.message.reply_text(mensagem[i : i + 4000], parse_mode="Markdown")
        else:
            await update.message.reply_text(mensagem, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao ler estoque: {e}")


@authorized_handler
async def verificar_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica alertas de estoque (vencimento e estoque baixo)."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/produtos/alertas")
            data = response.json()

        mensagem = "📊 **Relatório de Inventário**\n\n"

        if data["vencendo_em_breve"]:
            mensagem += "⚠️ **VENCENDO EM BREVE:**\n"
            for p in data["vencendo_em_breve"]:
                mensagem += f"• {p['nome']} (Vence: {p['ultima_validade']})\n"
            mensagem += "\n"

        if data["estoque_baixo"]:
            mensagem += "🛒 **PRECISA COMPRAR (Estoque Baixo):**\n"
            for p in data["estoque_baixo"]:
                mensagem += f"• {p['nome']} ({p['estoque_atual']} {p['unidade_medida']} restante)\n"

        if not data["vencendo_em_breve"] and not data["estoque_baixo"]:
            mensagem += "✅ Tudo em ordem! O estoque está saudável."

        await update.message.reply_text(mensagem, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao buscar status: {e}")


@authorized_handler
async def usar_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Registra consumo de um produto.

    Uso com quantidade: /usar 2 leite
    Uso sem quantidade: /usar leite (mostra itens similares via API)
    """
    if len(context.args) < 1:
        await update.message.reply_text(
            "💡 Use:\n"
            "• /usar [quantidade] [nome] → Ex: /usar 2 leite\n"
            "• /usar [nome] → Busca itens similares"
        )
        return

    try:
        # Tenta converter primeiro argumento para número
        primeiro_arg = context.args[0]

        try:
            qtd = float(primeiro_arg)
            # Tem quantidade
            busca_nome = " ".join(context.args[1:])
            tem_quantidade = True
        except ValueError:
            # Não tem quantidade, primeiro arg é parte do nome
            busca_nome = " ".join(context.args)
            qtd = None
            tem_quantidade = False

        async with httpx.AsyncClient() as client:
            # Usa o novo endpoint de busca híbrida (ilike + fuzzy)
            r = await client.get(
                f"{API_URL}/produtos/buscar",
                params={"termo": busca_nome, "com_estoque": True}
            )
            r.raise_for_status()
            itens_similares = r.json()

            if not itens_similares:
                await update.message.reply_text(
                    f"❓ Não encontrei '{busca_nome}' no estoque.\n\n"
                    f"💡 Verifique o nome ou adicione ao estoque primeiro."
                )
                return

            # Se não tem quantidade, mostra itens similares
            if not tem_quantidade:
                texto = f"📦 *Itens encontrados para '{busca_nome}':*\n\n"

                for i, item in enumerate(itens_similares, 1):
                    texto += f"*{i}.* {item['nome']}\n"
                    texto += f"   Estoque: {item['estoque_atual']} {item['unidade_medida']}\n"
                    if item.get('ultima_validade'):
                        texto += f"   Validade: {item['ultima_validade']}\n"
                    texto += "\n"

                texto += (
                    f"💡 Para consumir, use:\n"
                    f"`/usar <quantidade> <nome exato>`\n"
                    f"Ex: `/usar 1 {itens_similares[0]['nome']}`"
                )

                await update.message.reply_text(texto, parse_mode="Markdown")
                return

            # Tem quantidade - usa o primeiro resultado (mais relevante)
            produto = itens_similares[0]

            payload = {"quantidade": qtd}
            res = await client.patch(
                f"{API_URL}/produtos/consumir/{produto['id']}", params=payload
            )

            if res.status_code == 200:
                dados = res.json()
                texto = f"✅ **Baixa Registrada!**\n"
                texto += f"Item: {produto['nome']}\n"
                texto += f"Quantidade: {qtd} {produto['unidade_medida']}\n"
                texto += f"Restante: {dados['estoque_restante']} {produto['unidade_medida']}"
                await update.message.reply_text(texto, parse_mode="Markdown")
            else:
                erro = res.json().get("detail", "Erro desconhecido")
                await update.message.reply_text(f"❌ {erro}")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao registrar consumo: {e}")


@authorized_handler
async def registrar_desperdicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Registra perda/desperdício de um produto.
    
    Uso: /desperdicio 2 leite (perdeu 2 unidades de leite)
    """
    if len(context.args) < 2:
        await update.message.reply_text(
            "💡 Use: /desperdicio [quantidade] [nome do item]\n"
            "Ex: /desperdicio 2 leite"
        )
        return

    try:
        qtd = float(context.args[0])
        busca_nome = " ".join(context.args[1:])

        async with httpx.AsyncClient() as client:
            # Busca produto por similaridade
            r = await client.get(
                f"{API_URL}/produtos/buscar",
                params={"termo": busca_nome, "com_estoque": True}
            )
            r.raise_for_status()
            itens_similares = r.json()

            if not itens_similares:
                await update.message.reply_text(
                    f"❓ Não encontrei '{busca_nome}' no estoque.\n\n"
                    f"💡 Verifique o nome ou adicione ao estoque primeiro."
                )
                return

            # Usa o primeiro resultado (mais relevante)
            produto = itens_similares[0]

            # Registra perda
            payload = {"quantidade": qtd}
            res = await client.patch(
                f"{API_URL}/produtos/perda/{produto['id']}", params=payload
            )

            if res.status_code == 200:
                dados = res.json()
                texto = f"🗑️ **Perda Registrada!**\n"
                texto += f"Item: {produto['nome']}\n"
                texto += f"Quantidade perdida: {qtd} {produto['unidade_medida']}\n"
                texto += f"Restante: {dados['estoque_restante']} {produto['unidade_medida']}"
                await update.message.reply_text(texto, parse_mode="Markdown")
            else:
                erro = res.json().get("detail", "Erro desconhecido")
                await update.message.reply_text(f"❌ {erro}")

    except ValueError:
        await update.message.reply_text("❌ Quantidade deve ser um número (ex: /desperdicio 0.5 leite).")
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao registrar perda: {e}")


@authorized_handler
async def sugerir_jantar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sugere receita com base em itens vencendo."""
    await update.message.reply_text("👨‍🍳 Deixe-me ver o que temos na despensa...")
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_URL}/produtos/alertas")
            vencendo = r.json().get("vencendo_em_breve", [])

        if not vencendo:
            await update.message.reply_text(
                "🌟 Parabéns! Nada está perto de vencer. Pode cozinhar o que quiser!"
            )
            return

        r = await client.get(f"{API_URL}/sugerir-receita")
        resposta = r.json()

        await update.message.reply_text(
            f"💡 **Sugestão do Chef Hejmai:**\n\n{resposta['receita']}",
            parse_mode="Markdown",
        )

    except Exception as e:
        await update.message.reply_text(f"❌ O Chef teve um problema na cozinha: {e}")


@authorized_handler
async def gerar_lista_orcada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gera lista de compras agrupada por estabelecimento mais barato."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/produtos/lista-compras-detalhada")
            dados = response.json()

        if not dados.get("por_estabelecimento"):
            await update.message.reply_text("✅ O estoque está em dia! Nada para comprar.")
            return

        hoje = datetime.date.today().strftime("%d/%m")
        texto = f"📝 **Orçamento de Compras ({hoje})**\n"
        texto += "--- Agrupado por melhor preço ---\n\n"

        total_geral = 0

        for estabelecimento, info in dados["por_estabelecimento"].items():
            texto += f"🏪 *{estabelecimento}*\n"
            for produto in info["produtos"]:
                texto += f"  ☐ {produto['nome']} - R$ {produto['preco_referencia']:.2f}\n"
            texto += f"  💰 Subtotal: R$ {info['total_estimado']:.2f}\n\n"
            total_geral += info["total_estimado"]

        texto += f"💵 **Estimativa Total: R$ {dados['total_estimado']:.2f}**"
        texto += f"\n📦 {dados['quantidade_produtos']} produtos"
        texto += "\n\n*Dica: Cole no Keep e ative as Checkboxes!*"

        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao gerar lista: {e}")


@authorized_handler
async def comando_ultimas_compras(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista as últimas compras realizadas."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/compras/recentes?limite=5")
            response.raise_for_status()
            compras = response.json()

        if not compras:
            await update.message.reply_text("📭 Nenhuma compra registrada ainda.")
            return

        texto = "🛒 *Últimas Compras Realizadas*\n\n"

        for i, compra in enumerate(compras, 1):
            data_formatada = datetime.datetime.strptime(
                compra["data_compra"], "%Y-%m-%d"
            ).strftime("%d/%m/%Y")

            texto += f"*{i}. {compra['local_compra']}*\n"
            texto += f"   📅 {data_formatada}\n"
            texto += f"   💰 R$ {compra['valor_total_nota']:.2f}\n"
            texto += f"   📦 {compra['quantidade_itens']} itens\n\n"

        total_geral = sum(c["valor_total_nota"] for c in compras)
        texto += f"💵 *Total (últimas {len(compras)} compras): R$ {total_geral:.2f}*"

        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao buscar compras: {e}")


@authorized_handler
async def comando_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gera e envia backup do banco de dados e configurações.
    
    Uso: /backup
    """
    user_id = update.effective_chat.id
    
    # Verificar se é o dono do bot
    if CHAT_ID_PESSOAL and str(user_id) != str(CHAT_ID_PESSOAL):
        await update.message.reply_text("🔒 Este comando é restrito ao administrador.")
        return
    
    await update.message.reply_text(
        "📦 Gerando backup...\n_Isso pode levar alguns segundos._",
        parse_mode="Markdown",
    )
    
    try:
        import tarfile
        import tempfile
        import os
        
        # Caminhos dos arquivos
        db_path = os.getenv("DATABASE_PATH", "/app/data/estoque.db")
        env_path = "/app/.env"
        
        # Criar arquivo temporário
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            backup_path = tmp.name
        
        # Criar tar.gz
        with tarfile.open(backup_path, "w:gz") as tar:
            if os.path.exists(db_path):
                tar.add(db_path, arcname="estoque.db")
            if os.path.exists(env_path):
                tar.add(env_path, arcname=".env")
        
        # Verificar se há arquivos no backup
        backup_size = os.path.getsize(backup_path)
        if backup_size < 100:  # Menor que 100 bytes = vazio
            await update.message.reply_text("❌ Nenhum arquivo encontrado para backup.")
            os.unlink(backup_path)
            return
        
        # Enviar arquivo
        with open(backup_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"hejmai_backup_{datetime.date.today().strftime('%Y%m%d')}.tar.gz",
                caption=(
                    "📦 *Backup do Hejmai*\n\n"
                    "Contém:\n"
                    "• `estoque.db` - Banco de dados\n"
                    "• `.env` - Configurações\n\n"
                    "Para restaurar:\n"
                    "1. Extraia os arquivos\n"
                    "2. Coloque no diretório do projeto\n"
                    "3. Execute: `docker-compose up -d`"
                ),
                parse_mode="Markdown",
            )
        
        # Limpar arquivo temporário
        os.unlink(backup_path)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao gerar backup: {e}")


@authorized_handler
async def comando_pergunta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Faz pergunta em linguagem natural para a IA."""
    pergunta = " ".join(context.args)
    if not pergunta:
        await update.message.reply_text(
            "🤔 O que você quer saber? Ex: /pergunta quanto gastei com carne este mês?"
        )
        return

    await update.message.reply_text("🔍 Consultando o cérebro do Hejmai...")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_URL}/ia/perguntar",
            json={"pergunta": pergunta},
            timeout=160.0,
        )

        if response.status_code == 200:
            dados = response.json()
            resposta_texto = dados["resposta"]
            sql_debug = f"\n\n`SQL: {dados['query']}`" if context.args and context.args[0] == "debug" else ""
            await update.message.reply_text(f"🤖 {resposta_texto}{sql_debug}", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Erro ao processar a pergunta pela IA.")


@authorized_handler
async def registrar_compra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa texto livre para registrar compra via NLP."""
    texto = update.message.text
    await update.message.reply_text("🧠 Analisando sua entrada...")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/processar-entrada-livre",
                json={"texto": texto},
                timeout=160.0,
            )

            if response.status_code == 200:
                msg = response.json()["mensagem_bot"]
                await update.message.reply_text(f"✅ {msg}")
            else:
                await update.message.reply_text("❌ Erro ao processar no servidor.")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Falha no processamento da IA: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando de boas-vindas."""
    texto = """
👋 Olá! Sou o *Hejmabot*.

Posso te ajudar a gerenciar seu estoque doméstico.

📋 *Comandos:*
• /estoque - Ver inventário completo
• /status - Ver alertas (vencimento/estoque)
• /vigia - Relatório do Vigia do Estoque
• /ultimas_compras - Ver últimas compras
• /backup - 📦 Baixar banco + configurações
• /usar - Registrar consumo (ex: /usar 2 leite)
• /desperdicio - Registrar perda (ex: /desperdicio 1 leite)
• /sugerir_jantar - Sugere receita
• /lista_compras - Gera lista de compras
• /pergunta - Pergunte à IA

📝 *Registro automático:*
Envie texto descrevendo compras que eu processo automaticamente!
"""
    await update.message.reply_text(texto, parse_mode="Markdown")


# =============================================================================
# Job Agendado (Relatório Vigia)
# =============================================================================

def get_authorized_chats():
    """Retorna lista de IDs de chats autorizados (usuários e grupos)."""
    chats = set()
    if ALLOWED_USER_IDS:
        chats.update([u.strip() for u in ALLOWED_USER_IDS.split(",") if u.strip()])
    else:
        if CHAT_ID_PESSOAL:
            chats.add(str(CHAT_ID_PESSOAL))
            
    if ALLOWED_GROUP_IDS:
        chats.update([g.strip() for g in ALLOWED_GROUP_IDS.split(",") if g.strip()])
    return chats


async def job_vigia(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job agendado para enviar relatório do Vigia do Estoque."""
    print("🔔 Executando job do Vigia do Estoque...")
    db = SessionLocal()
    try:
        analise = analisar_estoque(db)
        relatorio = gerar_relatorio_texto(analise)
        
        # Envia para todos os chats autorizados
        chats = get_authorized_chats()
        if not chats:
            print("❌ Nenhum chat autorizado configurado para envio automático.")
            return

        for chat_id in chats:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=relatorio,
                    parse_mode="Markdown",
                )
                print(f"✅ Relatório enviado para {chat_id}")
            except Exception as e:
                print(f"❌ Erro ao enviar para {chat_id}: {e}")
    finally:
        db.close()


# =============================================================================
# Inicialização
# =============================================================================

def criar_bot(app: Application) -> None:
    """
    Configura o bot do Telegram com handlers e jobs.

    Args:
        app: Aplicação do Telegram
    """
    if not app:
        print("⚠️ Aplicação não fornecida. Bot não será configurado.")
        return
    
    # Adiciona handlers de comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("estoque", comando_estoque))
    app.add_handler(CommandHandler("status", verificar_status))
    app.add_handler(CommandHandler("vigia", comando_vigia))
    app.add_handler(CommandHandler("vigia_config", comando_vigia_config))
    app.add_handler(CommandHandler("usar", usar_item))
    app.add_handler(CommandHandler("desperdicio", registrar_desperdicio))
    app.add_handler(CommandHandler("sugerir_jantar", sugerir_jantar))
    app.add_handler(CommandHandler("lista_compras", gerar_lista_orcada))
    app.add_handler(CommandHandler("ultimas_compras", comando_ultimas_compras))
    app.add_handler(CommandHandler("backup", comando_backup))
    app.add_handler(CommandHandler("pergunta", comando_pergunta))

    # Handler de mensagens de texto (NLP)
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), registrar_compra))

    # Jobs agendados do Vigia (08:00, 13:00, 18:00)
    if app.job_queue:
        import datetime
        times = [
            datetime.time(hour=8, minute=0),
            datetime.time(hour=15, minute=0),
            datetime.time(hour=18, minute=0),
        ]
        for t in times:
            app.job_queue.run_daily(
                job_vigia,
                time=t,
                name=f"vigia_{t.hour}h",
            )
        print("📅 Jobs do Vigia agendados para 08:00, 13:00 e 18:00")

    print("✅ Bot do Telegram configurado")
