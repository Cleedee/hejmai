"""
Handlers do Telegram Bot para o Hejmai.

Comandos disponíveis:
- /start: Boas-vindas
- /estoque: Ver inventário completo
- /status: Ver alertas (vencimento/estoque)
- /vigia: Relatório do Vigia do Estoque
- /vigia_config: Configurações do vigia
- /ultimas_compras: Ver últimas compras
- /precos: Histórico de preços (ex: /precos arroz)
- /produto: Gerenciar produtos (buscar/ver/editar)
- /usar: Registrar consumo (ex: /usar 2 leite)
- /desperdicio: Registrar perda (ex: /desperdicio 1 leite)
- /sugerir_jantar: Sugere receita baseada no estoque
- /receitas: Lista todas as receitas
- /receita: Ver detalhes (ex: /receita Marmota)
- /add_receita: Criar receita (ex: /add_receita Nome | Desc | Ing:qtd)
- /lista_compras: Gera lista de compras
- /agente: Pergunta ao Agente IA
- /backup: Baixar banco + configurações
"""

import datetime
import os

import httpx
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    JobQueue,
    MessageHandler,
    filters,
)

from hejmai import crud
from hejmai.database import SessionLocal
from hejmai.vigia_estoque.analise_consumo import (
    analisar_estoque,
    gerar_relatorio_texto,
    tem_alertas_urgentes,
)
from hejmai.vigia_estoque.vigia import executar_vigia
from hejmai.config import config

# =============================================================================
# Configuração
# =============================================================================

TOKEN = config.TELEGRAM_TOKEN()
CHAT_ID_PESSOAL = config.TELEGRAM_CHAT_ID()

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


async def check_authorization(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
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
async def comando_vigia_config(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Mostra configuração atual do vigia.
    Uso: /vigia_config
    """
    from hejmai.vigia_estoque.analise_consumo import (
        DIAS_ANALISE_CONSUMO,
        DIAS_PARA_ACABAR_ALERTA,
        DIAS_PARA_VENCER_ALERTA,
    )

    config_texto = f"""
⚙️ *Configuração do Vigia*

📊 *Parâmetros de Análise*
• Alerta estoque: <{DIAS_PARA_ACABAR_ALERTA} dias
• Alerta validade: <{DIAS_PARA_VENCER_ALERTA} dias
• Período análise: {DIAS_ANALISE_CONSUMO} dias

🤖 *Telegram*
• Token: {"✅ Configurado" if TOKEN else "❌ Não configurado"}
• Chat ID: `{CHAT_ID_PESSOAL or "Não configurado"}`

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
            response = await client.get(f"{config.API_URL()}/estoque/resumo-geral")
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
                await update.message.reply_text(
                    mensagem[i : i + 4000], parse_mode="Markdown"
                )
        else:
            await update.message.reply_text(mensagem, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao ler estoque: {e}")


@authorized_handler
async def verificar_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica alertas de estoque (vencimento e estoque baixo)."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{config.API_URL()}/produtos/alertas")
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
                f"{config.API_URL()}/produtos/buscar",
                params={"termo": busca_nome, "com_estoque": True},
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
                    if item.get("ultima_validade"):
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
                f"{config.API_URL()}/produtos/consumir/{produto['id']}", params=payload
            )

            if res.status_code == 200:
                dados = res.json()
                texto = f"✅ **Baixa Registrada!**\n"
                texto += f"Item: {produto['nome']}\n"
                texto += f"Quantidade: {qtd} {produto['unidade_medida']}\n"
                texto += (
                    f"Restante: {dados['estoque_restante']} {produto['unidade_medida']}"
                )
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
            "💡 Use: /desperdicio [quantidade] [nome do item]\nEx: /desperdicio 2 leite"
        )
        return

    try:
        qtd = float(context.args[0])
        busca_nome = " ".join(context.args[1:])

        async with httpx.AsyncClient() as client:
            # Busca produto por similaridade
            r = await client.get(
                f"{config.API_URL()}/produtos/buscar",
                params={"termo": busca_nome, "com_estoque": True},
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
                f"{config.API_URL()}/produtos/perda/{produto['id']}", params=payload
            )

            if res.status_code == 200:
                dados = res.json()
                texto = f"🗑️ **Perda Registrada!**\n"
                texto += f"Item: {produto['nome']}\n"
                texto += f"Quantidade perdida: {qtd} {produto['unidade_medida']}\n"
                texto += (
                    f"Restante: {dados['estoque_restante']} {produto['unidade_medida']}"
                )
                await update.message.reply_text(texto, parse_mode="Markdown")
            else:
                erro = res.json().get("detail", "Erro desconhecido")
                await update.message.reply_text(f"❌ {erro}")

    except ValueError:
        await update.message.reply_text(
            "❌ Quantidade deve ser um número (ex: /desperdicio 0.5 leite)."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao registrar perda: {e}")


@authorized_handler
async def sugerir_jantar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sugere receita com base no estoque."""
    await update.message.reply_text("👨‍🍳 Consultando o Chef Hejmai...")
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.get(f"{config.API_URL()}/sugerir-receita")
            resposta = r.json()

        texto = "🍽️ **Sugestões do Chef Hejmai**\n\n"

        # Receitas completas primeiro
        completas = resposta.get("receitas_completas", [])
        if completas:
            texto += "✅ **Prontas para fazer:**\n"
            for rec in completas[:3]:
                texto += f"• {rec['nome']}\n"
                texto += f"  _{rec['descricao']}_\n\n"

        # Quase prontas
        quase = resposta.get("quase_prontas", [])
        if quase:
            texto += "🔶 **Quase completas:**\n"
            for rec in quase:
                texto += f"• {rec['nome']}\n"
                texto += f"  Faltam: {', '.join(rec['itens_faltantes'][:2])}\n\n"

        # Sugestão da IA
        sugestao_ia = resposta.get("sugestao_ia")
        if sugestao_ia:
            texto += "💡 **Dica do Chef:**\n"
            texto += f"_{sugestao_ia}_"

        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")


@authorized_handler
async def gerar_lista_orcada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gera lista de compras agrupada por estabelecimento mais barato."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{config.API_URL()}/produtos/lista-compras-detalhada")
            dados = response.json()

        if not dados.get("por_estabelecimento"):
            await update.message.reply_text(
                "✅ O estoque está em dia! Nada para comprar."
            )
            return

        hoje = datetime.date.today().strftime("%d/%m")
        texto = f"📝 **Orçamento de Compras ({hoje})**\n"
        texto += "--- Agrupado por melhor preço ---\n\n"

        total_geral = 0

        for estabelecimento, info in dados["por_estabelecimento"].items():
            texto += f"🏪 *{estabelecimento}*\n"
            for produto in info["produtos"]:
                texto += (
                    f"  ☐ {produto['nome']} - R$ {produto['preco_referencia']:.2f}\n"
                )
            texto += f"  💰 Subtotal: R$ {info['total_estimado']:.2f}\n\n"
            total_geral += info["total_estimado"]

        texto += f"💵 **Estimativa Total: R$ {dados['total_estimado']:.2f}**"
        texto += f"\n📦 {dados['quantidade_produtos']} produtos"
        texto += "\n\n*Dica: Cole no Keep e ative as Checkboxes!*"

        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao gerar lista: {e}")


@authorized_handler
async def comando_precos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Mostra histórico de preços de um produto.
    
    Uso: /precos arroz
    """
    if not context.args:
        await update.message.reply_text(
            "💡 Use: /precos [nome do produto]\nEx: /precos arroz"
        )
        return

    busca_nome = " ".join(context.args)

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{config.API_URL()}/produtos/buscar",
                params={"termo": busca_nome, "com_estoque": False},
            )
            r.raise_for_status()
            itens = r.json()

            if not itens:
                await update.message.reply_text(
                    f"❓ Não encontrei '{busca_nome}' no sistema."
                )
                return

            produto = itens[0]
            produto_id = produto["id"]

            r = await client.get(
                f"{config.API_URL()}/relatorios/historico-precos/{produto_id}"
            )

            if r.status_code != 200 or not r.json():
                await update.message.reply_text(
                    f"📊 *Histórico de Preços: {produto['nome']}*\n\n"
                    f"Nenhum registro de compra encontrado."
                )
                return

            historico = r.json()
            
            if not historico:
                await update.message.reply_text(
                    f"📊 *Histórico de Preços: {produto['nome']}*\n\n"
                    f"Nenhum registro encontrado."
                )
                return

            precos = [h["preco"] for h in historico]
            menor = min(precos)
            maior = max(precos)
            medio = sum(precos) / len(precos)

            texto = f"💵 *Histórico de Preços: {produto['nome']}*\n\n"
            texto += f"📊 Estatísticas:\n"
            texto += f"• Menor: R$ {menor:.2f}\n"
            texto += f"• Médio: R$ {medio:.2f}\n"
            texto += f"• Maior: R$ {maior:.2f}\n\n"
            texto += f"📋 Registros:\n"

            for item in historico[-10:]:  # Últimos 10
                texto += f"• {item['data'][:10]}: R$ {item['preco']:.2f} ({item['local']})\n"

            await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")


@authorized_handler
async def comando_produto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gerencia produtos no estoque.

    Uso:
    /produto buscar [nome] - Busca produtos
    /produto ver [nome] - Mostra detalhes completos
    /produto editar [nome] | campo:valor - Edita produto
    """
    if not context.args:
        await update.message.reply_text(
            "💡 *Comandos de produto:*\n\n"
            "`/produto buscar [nome]` - Buscar produtos\n"
            "`/produto ver [nome]` - Ver detalhes\n"
            "`/produto editar [nome] | campo:valor` - Editar\n\n"
            "*Campos editáveis:* nome, categoria, estoque, validade, tags\n\n"
            "*Exemplo:*\n"
            "`/produto editar Iogurte | tags:iogurte,natural`"
        )
        return

    texto_completo = " ".join(context.args)
    partes = texto_completo.split("|")
    acao = partes[0].strip().split()[0].lower() if partes else ""
    nome = " ".join(partes[0].strip().split()[1:]) if len(partes[0].strip().split()) > 1 else ""

    if acao == "editar" and "|" in texto_completo:
        await editar_produto_telegram(update, nome, partes[1])
    elif acao == "buscar" and nome:
        await buscar_produto_telegram(update, nome)
    elif acao == "ver" and nome:
        await ver_produto_telegram(update, nome)
    else:
        await buscar_produto_telegram(update, nome)


async def buscar_produto_telegram(update: Update, nome: str):
    """Busca e lista produtos."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{config.API_URL()}/produtos/buscar",
                params={"termo": nome, "com_estoque": False},
            )
            r.raise_for_status()
            itens = r.json()

        if not itens:
            await update.message.reply_text(f"❓ Não encontrei '{nome}' no sistema.")
            return

        texto = f"🔍 *Resultados para '{nome}':*\n\n"
        for i, item in enumerate(itens[:10], 1):
            texto += f"{i}. *{item['nome']}*\n"
            texto += f"   📦 {item['estoque_atual']} {item['unidade_medida']}\n"
            if item.get("ultima_validade"):
                texto += f"   📅 Vence: {item['ultima_validade']}\n"
            texto += "\n"

        texto += "💡 Use `/produto ver [nome]` para ver detalhes."
        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")


async def ver_produto_telegram(update: Update, nome: str):
    """Mostra detalhes de um produto."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{config.API_URL()}/produtos/buscar",
                params={"termo": nome, "com_estoque": False},
            )
            r.raise_for_status()
            itens = r.json()

        if not itens:
            await update.message.reply_text(f"❓ Não encontrei '{nome}' no sistema.")
            return

        produto = itens[0]
        produto_id = produto["id"]

        async with httpx.AsyncClient() as client:
            r = await client.get(f"{config.API_URL()}/produtos/{produto_id}")
            if r.status_code == 404:
                await update.message.reply_text(f"❌ Produto não encontrado.")
                return
            detalhes = r.json()

        texto = f"📦 *{detalhes['nome']}*\n\n"
        texto += f"🏷️ Categoria: {detalhes.get('categoria', '-')}\n"
        texto += f"📊 Estoque: {detalhes.get('estoque_atual', 0)} {detalhes.get('unidade_medida', '')}\n"
        if detalhes.get("ultima_validade"):
            texto += f"📅 Validade: {detalhes['ultima_validade']}\n"
        
        tags = detalhes.get('tags', [])
        if tags:
            texto += f"🏷️ Tags: {', '.join(tags)}\n"

        historico = detalhes.get("historico_precos", {})
        if "mensagem" not in historico and historico.get("menor_preco"):
            texto += "\n💰 *Preços:*\n"
            texto += f"• Menor: R$ {historico.get('menor_preco', 0):.2f}\n"
            texto += f"• Médio: R$ {historico.get('preco_medio', 0):.2f}\n"
            if historico.get("ultima_compra"):
                texto += f"• Última compra: {historico.get('ultima_compra')}\n"
                texto += f"• Local: {historico.get('local_ultima_compra', '-')}\n"

        texto += "\n💡 Use `/produto editar {nome} | campo:valor` para editar."
        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")


async def editar_produto_telegram(update: Update, nome: str, campos_str: str):
    """Edita um produto."""
    if not nome:
        await update.message.reply_text("❌ Informe o nome do produto.\nEx: `/produto editar Arroz | estoque:5`")
        return

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{config.API_URL()}/produtos/buscar",
                params={"termo": nome, "com_estoque": False},
            )
            r.raise_for_status()
            itens = r.json()

        if not itens:
            await update.message.reply_text(f"❓ Não encontrei '{nome}' no sistema.")
            return

        produto = itens[0]
        produto_id = produto["id"]

        campos = {}
        for campo in campos_str.split(","):
            campo = campo.strip()
            if ":" in campo:
                chave, valor = campo.split(":", 1)
                chave = chave.strip().lower()
                valor = valor.strip()

                if chave in ("nome", "categoria"):
                    campos[chave] = valor
                elif chave in ("estoque", "quantidade"):
                    try:
                        campos["estoque_atual"] = float(valor)
                    except ValueError:
                        await update.message.reply_text(f"❌ Valor inválido para estoque: {valor}")
                        return
                elif chave == "validade":
                    campos["ultima_validade"] = valor
                elif chave == "tags":
                    campos["tags"] = valor  # Tags separadas por vírgula

        if not campos:
            await update.message.reply_text(
                "❌ Nenhum campo válido informado.\n"
                "Campos: nome, categoria, estoque, validade, tags"
            )
            return

        async with httpx.AsyncClient() as client:
            r = await client.patch(
                f"{config.API_URL()}/produtos/{produto_id}",
                json=campos
            )

        if r.status_code == 200:
            campos_editados = ", ".join([f"{k}={v}" for k, v in campos.items()])
            await update.message.reply_text(
                f"✅ *{produto['nome']}* atualizado!\n"
                f"Alterações: {campos_editados}"
            )
        else:
            await update.message.reply_text(f"❌ Erro ao atualizar: {r.status_code}")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")


@authorized_handler
async def comando_receitas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista todas as receitas disponíveis."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{config.API_URL()}/receitas")
            receitas = r.json()

        if not receitas:
            await update.message.reply_text(
                "📋 Nenhuma receita cadastrada ainda.\n\n"
                "Use /add_receita para criar uma!"
            )
            return

        texto = "📖 *Receitas Cadastradas*\n\n"

        for rec in receitas:
            tags = rec.get("tags", [])
            tags_str = f" [{', '.join(tags)}]" if tags else ""
            texto += f"• *{rec['nome']}*{tags_str}\n"
            texto += f"  _{rec['descricao']}_\n\n"

        texto += f"💡 Use /receita [nome] para ver detalhes"
        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")


@authorized_handler
async def comando_receita_detalhe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Mostra detalhes de uma receita específica.
    
    Uso: /receita Marmota
    """
    if not context.args:
        await update.message.reply_text(
            "💡 Use: /receita [nome da receita]\n"
            "Ex: /receita Marmota\n\n"
            "Use /receitas para ver todas."
        )
        return

    nome_receita = " ".join(context.args)

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{config.API_URL()}/receitas")
            receitas = r.json()

        # Buscar receita pelo nome
        receita = None
        for rec in receitas:
            if rec["nome"].lower() == nome_receita.lower():
                receita = rec
                break

        if not receita:
            await update.message.reply_text(
                f"❓ Não encontrei '{nome_receita}'.\n\n"
                f"Use /receitas para ver as disponíveis."
            )
            return

        # Buscar detalhes com estoque
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{config.API_URL()}/receitas/{receita['id']}")
            detalhes = r.json()

        texto = f"🍽️ *{detalhes['nome']}*\n\n"
        texto += f"_{detalhes['descricao'] or ''}_\n\n"

        texto += "📦 *Ingredientes:*\n"
        for item in detalhes.get("itens", []):
            tem = item.get("estoque_atual", 0)
            precisa = item.get("quantidade", 0)
            status_emoji = "✅" if tem >= precisa else "⚠️"
            texto += f"{status_emoji} {item['produto_nome']}: {precisa} ({tem} em estoque)\n"

        if detalhes.get("modo_preparo"):
            texto += f"\n👨‍🍳 *Modo de preparo:*\n{detalhes['modo_preparo']}\n"

        tags = detalhes.get("tags", [])
        if tags:
            texto += f"\n🏷️ Tags: {', '.join(tags)}"

        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")


@authorized_handler
async def comando_add_receita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Adiciona uma nova receita.
    
    Uso:
    /add_receita Nome da Receita | descrição | ingrediente1:qtd, ingrediente2:qtd | modo preparo | tags
    
    Exemplo:
    /add_receita Tapioca | Tapioca simples | Farinha de tapioca:200, Sal:1 | Aqueça a frigideira... | brasileira,rapida
    """
    if not context.args:
        await update.message.reply_text(
            "💡 *Como criar uma receita:*\n\n"
            "`/add_receita Nome | Descrição | Ing1:qtd, Ing2:qtd | Modo preparo | tags`\n\n"
            "📝 *Exemplo:*\n"
            "`/add_receita Tapioca | Tapioca simples | Farinha:200, Sal:1 | Aqueça a frigideira... | brasileira,rapida`\n\n"
            "📖 Use `/receitas` para ver as existentes.",
            parse_mode="Markdown"
        )
        return

    texto_completo = " ".join(context.args)
    
    # Parse do formato: Nome | Descrição | Ing1:qtd, Ing2:qtd | Modo | Tags
    partes = texto_completo.split("|")
    
    if len(partes) < 3:
        await update.message.reply_text(
            "❌ Formato incorreto!\n\n"
            "Use: `/add_receita Nome | Descrição | Ing1:qtd, Ing2:qtd | Modo | Tags`\n\n"
            "Mínimo: Nome | Descrição | Ingredientes"
        )
        return

    nome = partes[0].strip()
    descricao = partes[1].strip() if len(partes) > 1 else None
    ingredientes_str = partes[2].strip() if len(partes) > 2 else ""
    modo_preparo = partes[3].strip() if len(partes) > 3 else None
    tags_str = partes[4].strip() if len(partes) > 4 else None

    # Parse dos ingredientes
    ingredientes_parsed = []
    for ing in ingredientes_str.split(","):
        ing = ing.strip()
        if ":" in ing:
            nome_ing, qtd = ing.rsplit(":", 1)
            ingredientes_parsed.append({"nome": nome_ing.strip(), "quantidade": float(qtd.strip())})
        elif ing:
            ingredientes_parsed.append({"nome": ing, "quantidade": 1.0})

    if not ingredientes_parsed:
        await update.message.reply_text("❌ Nenhum ingrediente informado.")
        return

    await update.message.reply_text(f"🔍 Buscando produtos no estoque...")

    # Buscar IDs dos produtos
    async with httpx.AsyncClient() as client:
        produtos_response = await client.get(
            f"{config.API_URL()}/produtos/buscar",
            params={"termo": "", "com_estoque": False}
        )
        todos_produtos = produtos_response.json()

    itens_receita = []
    nao_encontrados = []

    for ing in ingredientes_parsed:
        # Buscar produto por nome parcial
        termo = ing["nome"]
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{config.API_URL()}/produtos/buscar",
                params={"termo": termo, "com_estoque": False}
            )
            resultados = r.json()

        if resultados:
            # Usa o primeiro resultado
            itens_receita.append({
                "produto_id": resultados[0]["id"],
                "quantidade_porcao": ing["quantidade"],
                "observacao": None
            })
        else:
            nao_encontrados.append(ing["nome"])

    if not itens_receita:
        await update.message.reply_text(
            f"❌ Nenhum dos ingredientes foi encontrado no estoque.\n"
            f"Ingredientes não encontrados: {', '.join(nao_encontrados)}"
        )
        return

    if nao_encontrados:
        await update.message.reply_text(
            f"⚠️ Ingredientes não encontrados (serão ignorados):\n"
            f"{', '.join(nao_encontrados)}\n\n"
            f"Continuando com {len(itens_receita)} ingredientes..."
        )

    # Criar a receita
    payload = {
        "nome": nome,
        "descricao": descricao,
        "modo_preparo": modo_preparo,
        "porcoes": 1,
        "tags": [t.strip() for t in tags_str.split(",")] if tags_str else [],
        "itens": itens_receita
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{config.API_URL()}/receitas",
                json=payload
            )

        if r.status_code == 201:
            await update.message.reply_text(
                f"✅ Receita *{nome}* criada com sucesso!\n\n"
                f"📦 {len(itens_receita)} ingredientes adicionados.\n"
                f"💡 Use `/receita {nome}` para ver detalhes."
            )
        elif r.status_code == 400:
            erro = r.json().get("detail", "Erro desconhecido")
            await update.message.reply_text(f"❌ {erro}")
        else:
            await update.message.reply_text(f"❌ Erro ao criar receita: {r.status_code}")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")


@authorized_handler
async def comando_ultimas_compras(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista as últimas compras realizadas."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{config.API_URL()}/compras/recentes?limite=5")
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
        import os
        import tarfile
        import tempfile

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
async def comando_agente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usa o Agente IA para responder perguntas complexas."""
    if not await check_authorization(update, context):
        return

    pergunta = " ".join(context.args)
    if not pergunta:
        await update.message.reply_text(
            "🤔 O que você quer saber? Ex: /agente quanto arroz temos?"
        )
        return

    await update.message.reply_text("🧠 Agente pensando...")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.API_URL()}/ia/agente",
                json={"pergunta": pergunta},
                timeout=120.0,
            )

            if response.status_code == 200:
                dados = response.json()
                await update.message.reply_text(
                    f"🤖 {dados.get('resposta', 'Sem resposta.')}",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text(
                    "❌ Erro ao processar a pergunta pelo Agente."
                )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Falha na comunicação com o Agente: {e}")


@authorized_handler
async def registrar_compra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa texto livre para registrar compra via NLP."""
    texto = update.message.text
    await update.message.reply_text("🧠 Analisando sua entrada...")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.API_URL()}/processar-entrada-livre",
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
• /precos - Histórico de preços (ex: /precos arroz)
• /produto - Gerenciar produtos (buscar/ver/editar)
• /backup - 📦 Baixar banco + configurações
• /usar - Registrar consumo (ex: /usar 2 leite)
• /desperdicio - Registrar perda (ex: /desperdicio 1 leite)
• /sugerir_jantar - 🍽️ Sugere receita
• /receitas - 📖 Lista todas as receitas
• /receita - Ver detalhes (ex: /receita Marmota)
• /add_receita - ➕ Criar receita
• /lista_compras - Gera lista de compras
• /agente - Pergunte ao Agente IA

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
    app.add_handler(CommandHandler("receitas", comando_receitas))
    app.add_handler(CommandHandler("receita", comando_receita_detalhe))
    app.add_handler(CommandHandler("add_receita", comando_add_receita))
    app.add_handler(CommandHandler("lista_compras", gerar_lista_orcada))
    app.add_handler(CommandHandler("ultimas_compras", comando_ultimas_compras))
    app.add_handler(CommandHandler("precos", comando_precos))
    app.add_handler(CommandHandler("produto", comando_produto))
    app.add_handler(CommandHandler("backup", comando_backup))
    app.add_handler(CommandHandler("agente", comando_agente))

    # Handler de mensagens de texto (NLP)
    # app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), registrar_compra))

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
