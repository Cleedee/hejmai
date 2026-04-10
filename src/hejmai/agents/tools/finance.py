"""
Finance Tool para o Hejmai Agent.

Fornece capacidades de análise financeira e orçamentos.
"""

from agno.tools import tool
from hejmai.database import SessionLocal
from hejmai import crud


@tool
def resumo_financeiro() -> str:
    """Retorna um resumo geral das finanças e orçamentos."""
    return "📊 Resumo Financeiro:\n- Orçamento mensal definido para categorias.\n- Use 'verificar_gastos' para detalhes."


@tool
def verificar_gastos(categoria: str = None) -> str:
    """Verifica os gastos recentes, opcionalmente filtrados por categoria."""
    db = SessionLocal()
    try:
        compras = crud.get_compras_recentes(db, limite=5)
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
