"""
Finance Tool para o Hejmai Agent.

Fornece capacidades de análise financeira e orçamentos.
"""

from agno.tools import tool

from hejmai import crud
from hejmai.database import SessionLocal


@tool
def verificar_gastos(categoria: str = None) -> str:
    """Check recent expenses, optionally filtered by category."""
    db = SessionLocal()
    try:
        compras = crud.get_compras_recentes(db, limite=3)
        if not compras:
            return "📭 Nenhuma compra recente registrada."

        linhas = ["🛒 *Últimas Compras:*\n"]
        total = 0
        for c in compras:
            linhas.append(f"• {c.local_compra}: R$ {c.valor_total_nota:.2f}")
            total += c.valor_total_nota

        linhas.append(f"\n💰 *Total Recente:* R$ {total:.2f}")
        return "\n".join(linhas)
    finally:
        db.close()


@tool
def consultar_historico_precos(produto_nome: str, dias: int = 90) -> str:
    """View a product's price history."""
    db = SessionLocal()
    try:
        resultado = crud.get_historico_precos(db, produto_nome, days_back=dias)

        if "mensagem" in resultado:
            return f"📊 *Histórico de Preços:*\n{resultado['mensagem']}"

        linhas = [f"💵 *Histórico de Preços: {resultado['produto']}*\n"]
        linhas.append(f"📈 Menor preço: R$ {resultado['menor_preco']:.2f}")
        linhas.append(f"📊 Preço médio: R$ {resultado['preco_medio']:.2f}")
        linhas.append(
            f"📍 Última compra: {resultado['ultima_compra']} em {resultado['local_ultima_compra']}"
        )
        linhas.append("\n*Histórico:*\n")

        for item in resultado["historico_detalhado"][:10]:
            linhas.append(f"• {item['data']}: R$ {item['preco']:.2f} ({item['local']})")

        return "\n".join(linhas)
    finally:
        db.close()


# Agrupando as funções para serem exportadas como uma Tool
FinanceTool = [verificar_gastos, consultar_historico_precos]
