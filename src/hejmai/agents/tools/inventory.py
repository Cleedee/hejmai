"""
Inventory Tool para o Hejmai Agent.

Fornece capacidades de consulta e modificação do estoque.
"""

import datetime

from agno.tools import tool

from hejmai import crud
from hejmai.database import SessionLocal
from hejmai.vigia_estoque.analise_consumo import analisar_estoque, gerar_relatorio_texto


@tool
def consultar_ultimas_compras() -> str:
    """Check the last purchases."""
    db = SessionLocal()
    try:
        compras = crud.get_compras_recentes(db)
        if not compras:
            return "Nenhuma compra recente encontrada."

        texto = "*Últimas Compras Realizadas*\n\n"
        for i, compra in enumerate(compras, 1):
            data_formatada = compra.data_compra.strftime("%d/%m/%Y")

            quantidade_itens = len(compra.itens) if compra.itens else 0

            texto += f"*{i}. {compra.local_compra}*\n"
            texto += f"   📅 {data_formatada}\n"
            texto += f"   💰 R$ {compra.valor_total_nota:.2f}\n"
            texto += f"   📦 {quantidade_itens} itens\n\n"

        total_geral = sum(c.valor_total_nota for c in compras)
        texto += f"💵 *Total (últimas {len(compras)} compras): R$ {total_geral:.2f}*"

        return texto
    finally:
        db.close()


@tool
def consultar_estoque(termo_busca: str = None) -> str:
    """Check the current stock."""
    db = SessionLocal()
    try:
        if termo_busca:
            itens = crud.buscar_produtos_similares(db, termo_busca)
            titulo = f"Resultados para '{termo_busca}'"
        else:
            itens = crud.get_produtos_com_estoque(db)
            titulo = "Estoque Completo"

        if not itens:
            return "Nenhum item encontrado no estoque."

        linhas = [f"📦 *{titulo}*\n"]
        for p in itens[:15]:
            linhas.append(f"• {p.nome}: {p.estoque_atual} {p.unidade_medida}")

        if len(itens) > 15:
            linhas.append(f"\n_...e mais {len(itens) - 15} itens._")

        return "\n".join(linhas)
    finally:
        db.close()


@tool
def verificar_alertas_estoque() -> str:
    """Check if any products are running out or expiring soon."""
    db = SessionLocal()
    try:
        analise = analisar_estoque(db)
        return gerar_relatorio_texto(analise)
    finally:
        db.close()


@tool
def registrar_consumo(produto_nome: str, quantidade: float) -> str:
    """Registra o consumo de um produto no estoque. USE SOMENTE quando o usuário EXPLICITAMENTE pedir para registrar/dar baixa em um produto."""
    db = SessionLocal()
    try:
        produto = crud.get_produto_por_nome(db, produto_nome)
        if not produto:
            return f"❌ Produto '{produto_nome}' não encontrado no estoque."

        if produto.estoque_atual < quantidade:
            return f"⚠️ Estoque insuficiente para {produto.nome}. Disponível: {produto.estoque_atual}."

        produto.estoque_atual -= quantidade
        db.commit()

        return f"✅ Consumo registrado: {quantidade} {produto.unidade_medida} de {produto.nome}. Restante: {produto.estoque_atual}."
    except Exception as e:
        db.rollback()
        return f"❌ Erro ao registrar consumo: {e}"
    finally:
        db.close()


@tool
def analisar_frequencia_consumo(produto_nome: str) -> str:
    """Analyzes the frequency and history of consumption of a specific product."""
    db = SessionLocal()
    try:
        produto = crud.get_produto_por_nome(db, produto_nome)
        if not produto:
            return f"❌ Produto '{produto_nome}' não encontrado no estoque."

        from datetime import datetime, timedelta

        from hejmai import models

        movimentacoes = (
            db.query(models.Movimentacao)
            .filter(models.Movimentacao.produto_id == produto.id)
            .filter(models.Movimentacao.tipo == "consumo")
            .order_by(models.Movimentacao.data.desc())
            .limit(10)
            .all()
        )

        if not movimentacoes:
            return f"📊 Histórico de consumo de '{produto.nome}':\nNenhum registro de consumo encontrado no histórico."

        linhas = [f"📊 *Histórico de Consumo: {produto.nome}*\n"]
        linhas.append(
            f"Quantidade atual em estoque: {produto.estoque_atual} {produto.unidade_medida}\n"
        )
        linhas.append("_Últimos registros:_\n")

        for m in movimentacoes:
            data_str = (
                m.data.strftime("%d/%m/%Y")
                if hasattr(m.data, "strftime")
                else str(m.data)
            )
            linhas.append(f"• {data_str}: -{m.quantidade} {produto.unidade_medida}")

        return "\n".join(linhas)
    finally:
        db.close()


InventoryTool = [
    consultar_ultimas_compras,
    consultar_estoque,
    verificar_alertas_estoque,
    analisar_frequencia_consumo,
]
