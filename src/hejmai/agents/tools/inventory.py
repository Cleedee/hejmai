"""
Inventory Tool para o Hejmai Agent.

Fornece capacidades de consulta e modificação do estoque.
"""

from agno.tools import tool
from hejmai.database import SessionLocal
from hejmai import crud
from hejmai.vigia_estoque.analise_consumo import analisar_estoque, gerar_relatorio_texto


@tool
def consultar_estoque(termo_busca: str = None) -> str:
    """Consulta o estoque atual. Se termo_busca for informado, busca produtos específicos."""
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
    """Verifica se há produtos acabando ou vencendo em breve."""
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
    """Analisa a frequência e histórico de consumo de um produto específico. USE para perguntas como 'com que frequência', 'quando foi consumido', 'histórico de consumo'."""
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
        linhas.append(f"Quantidade atual em estoque: {produto.estoque_atual} {produto.unidade_medida}\n")
        linhas.append("_Últimos registros:_\n")
        
        for m in movimentacoes:
            data_str = m.data.strftime("%d/%m/%Y") if hasattr(m.data, 'strftime') else str(m.data)
            linhas.append(f"• {data_str}: -{m.quantidade} {produto.unidade_medida}")
        
        return "\n".join(linhas)
    finally:
        db.close()

InventoryTool = [consultar_estoque, verificar_alertas_estoque, analisar_frequencia_consumo, registrar_consumo]
