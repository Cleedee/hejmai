"""
Operações de banco de dados centralizadas.

Este módulo deve ser a única fonte de consultas ao banco de dados.
Todos os outros módulos (handlers, vigia, services) devem usar estas funções.
"""

import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any

from hejmai import models


# =============================================================================
# Categorias
# =============================================================================

def traga_todas_categorias(db: Session) -> List[models.Categoria]:
    """Lista todas as categorias cadastradas."""
    return db.query(models.Categoria).all()


# =============================================================================
# Produtos
# =============================================================================

def atualizar_produto(
    db: Session, produto_id: int, dados: dict
) -> Optional[models.Produto]:
    """Atualiza campos específicos de um produto."""
    produto = db.query(models.Produto).filter(models.Produto.id == produto_id).first()
    if not produto:
        return None

    for campo, valor in dados.items():
        if valor is not None:
            setattr(produto, campo, valor)

    db.commit()
    db.refresh(produto)
    return produto


def get_todos_produtos(db: Session) -> List[models.Produto]:
    """Lista todos os produtos cadastrados."""
    return db.query(models.Produto).all()


def get_produtos_com_estoque(db: Session) -> List[models.Produto]:
    """Lista produtos com estoque positivo."""
    return (
        db.query(models.Produto)
        .filter(models.Produto.estoque_atual > 0)
        .all()
    )


def get_produto_por_id(db: Session, produto_id: int) -> Optional[models.Produto]:
    """Busca um produto pelo ID."""
    return (
        db.query(models.Produto)
        .filter(models.Produto.id == produto_id)
        .first()
    )


def get_produto_por_nome(db: Session, nome: str) -> Optional[models.Produto]:
    """Busca um produto por nome (case insensitive, match parcial)."""
    return (
        db.query(models.Produto)
        .filter(models.Produto.nome.ilike(f"%{nome}%"))
        .first()
    )


def buscar_produtos_similares(
    db: Session, termo: str, com_estoque: bool = True
) -> List[models.Produto]:
    """
    Busca produtos por similaridade de nome.
    
    Args:
        termo: Termo de busca (case insensitive)
        com_estoque: Se True, retorna apenas produtos com estoque > 0
    
    Returns:
        Lista de produtos que contêm o termo no nome
    """
    query = db.query(models.Produto).filter(
        models.Produto.nome.ilike(f"%{termo}%")
    )
    
    if com_estoque:
        query = query.filter(models.Produto.estoque_atual > 0)
    
    return query.all()


def get_produtos_alertas(db: Session) -> Dict[str, List[models.Produto]]:
    """
    Busca produtos com alertas de estoque baixo ou vencimento próximo.
    
    Returns:
        Dict com 'estoque_baixo' e 'vencendo_em_breve'
    """
    hoje = datetime.date.today()
    proxima_semana = hoje + datetime.timedelta(days=7)
    
    estoque_baixo = (
        db.query(models.Produto)
        .filter(
            models.Produto.estoque_atual < 1.0,
            models.Produto.estoque_atual > 0,
        )
        .all()
    )
    
    vencendo = (
        db.query(models.Produto)
        .filter(
            models.Produto.ultima_validade <= proxima_semana,
            models.Produto.ultima_validade >= hoje,
            models.Produto.estoque_atual > 0,
        )
        .all()
    )
    
    return {
        "estoque_baixo": estoque_baixo,
        "vencendo_em_breve": vencendo,
    }


# =============================================================================
# Movimentações (Consumo)
# =============================================================================

def get_consumo_periodo(
    db: Session, 
    produto_id: int, 
    dias: int = 30
) -> float:
    """
    Calcula o total consumido de um produto em um período.
    
    Args:
        produto_id: ID do produto
        dias: Número de dias para analisar
    
    Returns:
        Quantidade total consumida no período (sempre positiva)
    """
    data_limite = datetime.date.today() - datetime.timedelta(days=dias)
    
    resultado = db.query(
        func.sum(func.abs(models.Movimentacao.quantidade))
    ).filter(
        models.Movimentacao.produto_id == produto_id,
        models.Movimentacao.tipo == "CONSUMO",
        models.Movimentacao.data_movimento >= data_limite,
    ).scalar()
    
    return float(resultado) if resultado else 0.0


def get_historico_movimentacoes(
    db: Session, 
    produto_id: int, 
    limite: int = 50
) -> List[models.Movimentacao]:
    """Busca as últimas movimentações de um produto."""
    return (
        db.query(models.Movimentacao)
        .filter(models.Movimentacao.produto_id == produto_id)
        .order_by(models.Movimentacao.data_movimento.desc())
        .limit(limite)
        .all()
    )


# =============================================================================
# Compras
# =============================================================================

def get_compras_recentes(
    db: Session, 
    limite: int = 5
) -> List[models.Compra]:
    """Lista as últimas compras realizadas (não excluídas)."""
    return (
        db.query(models.Compra)
        .filter(models.Compra.excluida == 0)
        .order_by(models.Compra.data_compra.desc(), models.Compra.id.desc())
        .limit(limite)
        .all()
    )


def get_compra_por_id(db: Session, compra_id: int) -> Optional[models.Compra]:
    """Busca uma compra pelo ID."""
    return (
        db.query(models.Compra)
        .filter(models.Compra.id == compra_id)
        .first()
    )


# =============================================================================
# Utilitários
# =============================================================================

def get_estatisticas_gerais(db: Session) -> Dict[str, Any]:
    """Retorna estatísticas gerais do estoque."""
    total_produtos = db.query(models.Produto).count()
    com_estoque = db.query(models.Produto).filter(
        models.Produto.estoque_atual > 0
    ).count()
    sem_estoque = total_produtos - com_estoque
    
    return {
        "total_produtos": total_produtos,
        "com_estoque": com_estoque,
        "sem_estoque": sem_estoque,
    }

