"""
Recipe Tool para o Hejmai Agent.

Fornece capacidades de localizar receitas e sugestões de receitas.
"""

from agno.tools import tool

from hejmai import crud
from hejmai.database import SessionLocal


@tool
def consulta_receitas(nome_receita: str) -> str:
    """
    Consulta receitas pelo nome e retorna receitas encontradas.
    """
    with SessionLocal() as session:
        receitas = crud.get_receitas_por_nome(session, nome_receita)
        if receitas:
            return "\n".join([f"{r.nome}: {r.descricao}" for r in receitas])
        else:
            return "Receitas não encontradas."


@tool
def consulta_receitas_por_ingrediente(ingrediente: str) -> str:
    """
    Consulta receitas que contêm um ingrediente específico e retorna receitas encontradas.
    """
    with SessionLocal() as session:
        receitas = crud.get_receitas_por_ingrediente(session, ingrediente)
        if receitas:
            return "\n".join([f"{r.nome}: {r.descricao}" for r in receitas])
        else:
            return "Receitas não encontradas."


@tool
def sugerir_receitas() -> str:
    """
    Sugere receitas com base nos ingredientes disponíveis e retorna receitas sugeridas.
    """
    with SessionLocal() as session:
        receitas = crud.sugerir_receitas(session)
        if receitas:
            return "\n".join([f"{r['nome']}: {r['descricao']}" for r in receitas])
        else:
            return "Receitas não encontradas."


def get_receitas_por_nome(db: Session, nome: str) -> List[models.Receita]:
    """Busca receitas pelo nome."""
    return db.query(models.Receita).filter(models.Receita.nome.ilike(f"%{nome}%")).all()


def get_receitas_por_ingrediente(db: Session, ingrediente: str) -> List[models.Receita]:
    """Busca receitas que contêm um ingrediente específico."""
    produto = crud.get_produto_por_nome(db, ingrediente)
    if not produto:
        return []
    return (
        db.query(models.Receita)
        .filter(models.Receita.itens.any(models.ItemReceita.produto_id == produto.id))
        .all()
    )


@tool
def buscar_receita_especifica(nome_receita: str) -> str:
    """
    Busca uma receita específica pelo nome e retorna a receita encontrada.
    """
    with SessionLocal() as session:
        receita = crud.get_receita_por_nome(session, nome_receita)
        if receita:
            pode_fazer, faltantes = crud.receita_pode_ser_feita(session, receita)

            if pode_fazer:
                status = "completa"
            elif len(faltantes) <= len(receita.itens) / 2:
                status = "quase"
            else:
                status = "inviável"
            sugestao = {
                "id": receita.id,
                "nome": receita.nome,
                "descricao": receita.descricao,
                "tags": receita.tags,
                "porcoes": receita.porcoes,
                "itens_faltantes": faltantes,
                "status": status,
                "pode_fazer": pode_fazer,
            }
            completa = receita if pode_fazer else {}
            quase = sugestao if not pode_fazer and status == "quase" else {}

            texto = ""
            if completa:
                texto += "✅ **Prontas para fazer:**\n"
                texto += f"• {sugestao['nome']}\n"
                texto += f"  _{sugestao['descricao']}_\n\n"
            if quase:
                texto += "⚠️ **Quase prontas para fazer:**\n"
                texto += f"• {quase['nome']}\n"
                texto += f"  Faltam: {', '.join(quase['itens_faltantes'][:2])}\n\n"
            if not pode_fazer and status == "inviável":
                texto += "❌ **Inviável:**\n"
                texto += f"• {sugestao['nome']}\n"
                texto += f"  _{sugestao['descricao']}_\n\n"

            return texto
        else:
            return "Receita não encontrada."


RecipeTool = [
    consulta_receitas,
    consulta_receitas_por_ingrediente,
    sugerir_receitas,
    buscar_receita_especifica,
]
