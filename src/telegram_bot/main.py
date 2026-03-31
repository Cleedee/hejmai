import os
import datetime
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import httpx

from telegram_bot.api_client import EstoqueAPI

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8081")
CHAT_ID_PESSOAL = os.getenv("CHAT_ID_PESSOAL")

api = EstoqueAPI(base_url=API_URL)


async def comando_pergunta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pergunta = " ".join(context.args)
    if not pergunta:
        await update.message.reply_text(
            "🤔 O que você quer saber? Ex: /pergunta quanto gastei com carne este mês?"
        )
        return

    await update.message.reply_text("🔍 Consultando o cérebro do Hejmai...")

    async with httpx.AsyncClient() as client:
        # Enviamos a pergunta para o novo endpoint do backend
        response = await client.post(
            f"{API_URL}/ia/perguntar",
            json={"pergunta": pergunta},
            timeout=160.0,  # O Ollama pode demorar um pouco
        )

        if response.status_code == 200:
            dados = response.json()
            resposta_texto = dados["resposta"]
            # Opcional: mostrar a query SQL para você (como dev) validar
            sql_debug = (
                f"\n\n`SQL: {dados['query']}`" if context.args[0] == "debug" else ""
            )

            await update.message.reply_text(
                f"🤖 {resposta_texto}{sql_debug}", parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Erro ao processar a pergunta pela IA.")


async def gerar_lista_orcada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        itens = await api.lista_compras_detalhada()

        if not itens:
            await update.message.reply_text(
                "✅ O stock está em dia! Nada para comprar."
            )
            return

        hoje = datetime.date.today().strftime("%d/%m")
        texto = f"📝 **Orçamento de Compras ({hoje})**\n"
        texto += "--- Copie abaixo para o Keep ---\n\n"

        total_estimado = 0
        for item in itens:
            preco = item["preco_referencia"]
            total_estimado += preco

            # Formato: [ ] Item - R$ Preço (Referência)
            texto += f"☐ {item['nome']} - (Ref: R$ {preco:.2f})\n"

        texto += f"\n💰 **Estimativa Total: R$ {total_estimado:.2f}**"
        texto += "\n\n*Dica: Cole no Keep e ative as Checkboxes!*"

        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao gerar lista: {e}")


async def sugerir_jantar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Feedback imediato ao usuário
    await update.message.reply_text(
        "👨‍🍳 Deixe-me ver o que temos na despensa que precisa de atenção..."
    )
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    try:
        # 2. Busca apenas itens vencendo na API
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_URL}/produtos/alertas")
            vencendo = r.json().get("vencendo_em_breve", [])

        if not vencendo:
            await update.message.reply_text(
                "🌟 Parabéns! Nada está perto de vencer. Pode cozinhar o que quiser!"
            )
            return

        # 3. IA processa a receita
        resposta = await api.sugerir_receita()

        await update.message.reply_text(
            f"💡 **Sugestão do Chef Hejmai:**\n\n{resposta['receita']}",
            parse_mode="Markdown",
        )

    except Exception as e:
        await update.message.reply_text(f"❌ O Chef teve um problema na cozinha: {e}")


async def usar_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Uso: /usar 1 maca (quantidade + nome)
    if len(context.args) < 2:
        await update.message.reply_text("💡 Use: /usar [quantidade] [nome do item]")
        return

    try:
        qtd = float(context.args[0])
        busca_nome = " ".join(context.args[1:])

        # 1. Buscar o ID do produto via API (Fuzzy search ou busca simples)
        async with httpx.AsyncClient() as client:
            # Endpoint que lista produtos ativos
            r = await client.get(f"{API_URL}/produtos/todos")
            produtos = r.json()

            # Busca simples por contorno de string
            produto = next(
                (p for p in produtos if busca_nome.lower() in p["nome"].lower()), None
            )

            if not produto:
                await update.message.reply_text(
                    f"❓ Não encontrei '{busca_nome}' no estoque."
                )
                return

            # 2. Registrar o consumo
            payload = {"quantidade": qtd}
            res = await client.patch(
                f"{API_URL}/produtos/consumir/{produto['id']}", params=payload
            )

            if res.status_code == 200:
                dados = res.json()
                texto = f"✅ **Baixa Registrada!**\n"
                texto += f"Item: {produto['nome']}\n"
                texto += (
                    f"Restante: {dados['estoque_restante']} {produto['unidade_medida']}"
                )

                await update.message.reply_text(texto, parse_mode="Markdown")
            else:
                erro = res.json().get("detail", "Erro desconhecido")
                await update.message.reply_text(f"❌ {erro}")

    except ValueError:
        await update.message.reply_text(
            "❌ A quantidade deve ser um número (ex: /usar 0.5 leite)."
        )


async def registrar_compra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text

    await update.message.reply_text("🧠 Analisando sua entrada...")

    try:
        # Envia para o seu backend FastAPI na porta 8081
        msg = await api.processar_entrada_livre(texto)
        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Falha no processamento da IA: {e}")


async def verificar_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def comando_estoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

        # Mapeamento simples de emojis para categorias canônicas
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
            # Cabeçalho de Categoria
            if p["categoria"] != categoria_atual:
                categoria_atual = p["categoria"]
                icone = icones.get(categoria_atual, "📦")
                mensagem += f"\n{icone} **{categoria_atual.upper()}**\n"

            # Formatação do Item
            validade_str = datetime.datetime.strptime(
                p["ultima_validade"], "%Y-%m-%d"
            ).strftime("%d/%m")

            # Alerta visual se estiver vencendo em menos de 3 dias
            hoje = datetime.date.today()
            vencimento = datetime.datetime.strptime(
                p["ultima_validade"], "%Y-%m-%d"
            ).date()
            alerta = "⚠️" if (vencimento - hoje).days <= 3 else "🔹"

            mensagem += f"{alerta} {p['nome']}: {p['estoque_atual']} {p['unidade_medida']} (Vence: {validade_str})\n"

        # Dividir a mensagem se for muito longa (limite do Telegram é 4096 caracteres)
        if len(mensagem) > 4000:
            for i in range(0, len(mensagem), 4000):
                await update.message.reply_text(
                    mensagem[i : i + 4000], parse_mode="Markdown"
                )
        else:
            await update.message.reply_text(mensagem, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao ler estoque: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    print(
        f"DEBUG: O Chat ID deste usuário é: {user_id}"
    )  # Vai aparecer no seu terminal
    await update.message.reply_text(
        "Olá! Sou o Hejmabot. Posso te ajudar a gerenciar seu estoque doméstico.\n"
        "Use /estoque para ver o que temos."
    )


if __name__ == "__main__":
    if not TOKEN:
        print("Erro: TELEGRAM_TOKEN não encontrado no arquivo .env")
        exit(1)
    app = ApplicationBuilder().token(TOKEN).build()

    # 2. Configuração do Agendamento (JobQueue)
    job_queue = app.job_queue

    # Roda todo dia às 09:00 da manhã
    # job_queue.run_daily(callback_validade, time=datetime.time(hour=9, minute=0, second=0))

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("estoque", comando_estoque))
    app.add_handler(CommandHandler("status", verificar_status))
    app.add_handler(CommandHandler("usar", usar_item))
    app.add_handler(CommandHandler("sugerir_jantar", sugerir_jantar))
    app.add_handler(CommandHandler("lista_compras", gerar_lista_orcada))
    app.add_handler(CommandHandler("pergunta", comando_pergunta))

    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), registrar_compra))

    print(f"Hejmabot online (Conectado em {API_URL})...")
    app.run_polling()
