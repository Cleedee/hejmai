"""
Projection Tool para o Hejmai Agent.

Fornece capacidades de previsão e análise de tendências.
"""

from agno.tools import tool
from hejmai.database import SessionLocal
from hejmai import crud


@tool
def previsao_reposicao() -> str:
    """Estima o custo para repor os itens que estão acabando."""
    db = SessionLocal()
    try:
        # Simulação simples baseada em produtos com estoque baixo
        itens = db.query(crud.models.Produto).filter(crud.models.Produto.estoque_atual < 1.0).all()
        if not itens:
            return "✅ Estoque saudável! Nenhuma reposição urgente necessária."
        
        linhas = ["📈 *Previsão de Reposição:*\n"]
        for p in itens:
            linhas.append(f"• {p.nome}: Estoque atual {p.estoque_atual}")
        
        return "\n".join(linhas)
    finally:
        db.close()
