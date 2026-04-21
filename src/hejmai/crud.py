"""
Operações de banco de dados centralizadas.

Este módulo deve ser a única fonte de consultas ao banco de dados.
Todos os outros módulos (handlers, vigia, services) devem usar estas funções.
"""

import datetime
from difflib import get_close_matches
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

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
    return db.query(models.Produto).filter(models.Produto.estoque_atual > 0).all()


def get_produto_por_id(db: Session, produto_id: int) -> Optional[models.Produto]:
    """Busca um produto pelo ID."""
    return db.query(models.Produto).filter(models.Produto.id == produto_id).first()


def get_produto_por_nome(db: Session, nome: str) -> Optional[models.Produto]:
    """Busca um produto por nome (case insensitive, match parcial)."""
    return (
        db.query(models.Produto).filter(models.Produto.nome.ilike(f"%{nome}%")).first()
    )


def buscar_produtos_similares(
    db: Session, termo: str, com_estoque: bool = True
) -> List[models.Produto]:
    """
    Busca produtos por similaridade de nome.

    Usa abordagem híbrida:
    1. Busca match exato por substring (ilike)
    2. Busca por similaridade fuzzy (difflib)
    3. Combina resultados, removendo duplicatas

    Isso resolve casos como "pão" → "Pães" E "Pão Francês".

    Args:
        termo: Termo de busca (case insensitive)
        com_estoque: Se True, retorna apenas produtos com estoque > 0

    Returns:
        Lista de produtos similares, priorizando matches exatos
    """
    # 1. Match exato por substring (prioridade)
    query = db.query(models.Produto).filter(models.Produto.nome.ilike(f"%{termo}%"))

    if com_estoque:
        query = query.filter(models.Produto.estoque_atual > 0)

    resultados_ilike = query.all()
    ids_encontrados = {p.id for p in resultados_ilike}

    # 2. Fuzzy matching para encontrar variações (ex: "pão" → "Pães")
    if com_estoque:
        todos_produtos = get_produtos_com_estoque(db)
    else:
        todos_produtos = get_todos_produtos(db)

    if not todos_produtos:
        return resultados_ilike

    # Filtra produtos já encontrados pelo ilike
    produtos_para_fuzzy = [p for p in todos_produtos if p.id not in ids_encontrados]

    if produtos_para_fuzzy:
        # Usa a primeira palavra do nome para fuzzy matching
        # Isso ajuda com "arros" → "Arroz Integral" (compara "arros" com "Arroz")
        nomes_para_busca = [p.nome.split()[0].lower() for p in produtos_para_fuzzy]
        termo_normalizado = termo.lower().split()[0]

        matches = get_close_matches(
            termo_normalizado,
            nomes_para_busca,
            n=10,
            cutoff=0.75,
        )

        # Mapeia de volta para produtos (pode ter duplicatas na primeira palavra)
        seen_ids = set()
        resultados_fuzzy = []
        for i, nome_lower in enumerate(nomes_para_busca):
            if nome_lower in matches and produtos_para_fuzzy[i].id not in seen_ids:
                resultados_fuzzy.append(produtos_para_fuzzy[i])
                seen_ids.add(produtos_para_fuzzy[i].id)
    else:
        resultados_fuzzy = []

    # 3. Combina resultados (exatos primeiro, depois fuzzy)
    return resultados_ilike + resultados_fuzzy


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


def get_consumo_periodo(db: Session, produto_id: int, dias: int = 30) -> float:
    """
    Calcula o total consumido de um produto em um período.

    Args:
        produto_id: ID do produto
        dias: Número de dias para analisar

    Returns:
        Quantidade total consumida no período (sempre positiva)
    """
    data_limite = datetime.date.today() - datetime.timedelta(days=dias)

    resultado = (
        db.query(func.sum(func.abs(models.Movimentacao.quantidade)))
        .filter(
            models.Movimentacao.produto_id == produto_id,
            models.Movimentacao.tipo == "CONSUMO",
            models.Movimentacao.data_movimento >= data_limite,
        )
        .scalar()
    )

    return float(resultado) if resultado else 0.0


def get_historico_movimentacoes(
    db: Session, produto_id: int, limite: int = 50
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


def get_compras_recentes(db: Session, limite: int = 5) -> List[models.Compra]:
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
    return db.query(models.Compra).filter(models.Compra.id == compra_id).first()


# =============================================================================
# Itens de Compra
# =============================================================================


def get_historico_precos(db: Session, product_name: str, days_back: int = 90):
    """
    Busca o histórico de preços pagos por um produto específico nos últimos meses.
    Útil para comparar se um preço atual vale a pena ou identificar inflação doméstica.

    Args:
        product_name: Nome parcial ou completo do produto (ex: 'Leite', 'Café').
        days_back: Quantidade de dias de histórico (padrão 90 dias).
    """
    date_limit = datetime.datetime.now() - datetime.timedelta(days=days_back)

    # Query que cruza itens de compra com a data da compra
    results = (
        db.query(
            models.Produto.nome,
            models.ItemCompra.preco_unitario,
            models.Compra.data_compra,
            models.Compra.local_compra,
        )
        .join(models.ItemCompra, models.Produto.id == models.ItemCompra.produto_id)
        .join(models.Compra, models.Compra.id == models.ItemCompra.compra_id)
        .filter(models.Produto.nome.contains(product_name))
        .filter(models.Compra.data_compra >= date_limit)
        .order_by(models.Compra.data_compra.desc())
        .all()
    )

    if not results:
        return {
            "mensagem": f"Não encontrei compras de '{product_name}' nos últimos {days_back} dias."
        }

    precos = [r.preco_unitario for r in results]
    min_price = min(precos)
    avg_price = sum(precos) / len(precos)

    return {
        "produto": results[0].nome,
        "menor_preco": min_price,
        "preco_medio": round(avg_price, 2),
        "ultima_compra": results[0].data_compra.strftime("%d/%m/%Y"),
        "local_ultima_compra": results[0].local_compra,
        "historico_detalhado": [
            {
                "data": r.data_compra.strftime("%d/%m"),
                "preco": r.preco_unitario,
                "local": r.local_compra,
            }
            for r in results
        ],
    }


# =============================================================================
# Utilitários
# =============================================================================


def get_estatisticas_gerais(db: Session) -> Dict[str, Any]:
    """Retorna estatísticas gerais do estoque."""
    total_produtos = db.query(models.Produto).count()
    com_estoque = (
        db.query(models.Produto).filter(models.Produto.estoque_atual > 0).count()
    )
    sem_estoque = total_produtos - com_estoque

    return {
        "total_produtos": total_produtos,
        "com_estoque": com_estoque,
        "sem_estoque": sem_estoque,
    }


# =============================================================================
# Receitas
# =============================================================================


def get_todas_receitas(db: Session, ativas: bool = True) -> List[models.Receita]:
    """Lista todas as receitas, opcionalmente só as ativas."""
    query = db.query(models.Receita)
    if ativas:
        query = query.filter(models.Receita.ativa == 1)
    return query.order_by(models.Receita.nome).all()


def get_receita_por_id(db: Session, receita_id: int) -> Optional[models.Receita]:
    """Busca uma receita pelo ID."""
    return db.query(models.Receita).filter(models.Receita.id == receita_id).first()


def get_receita_por_nome(db: Session, nome: str) -> Optional[models.Receita]:
    """Busca uma receita pelo nome."""
    return db.query(models.Receita).filter(models.Receita.nome == nome).first()


def get_receitas_por_nome(db: Session, nome: str) -> List[models.Receita]:
    """Busca receitas pelo nome."""
    return db.query(models.Receita).filter(models.Receita.nome.ilike(f"%{nome}%")).all()


def get_receitas_por_ingrediente(db: Session, ingrediente: str) -> List[models.Receita]:
    """Busca receitas que contêm um ingrediente específico."""
    produto = get_produto_por_nome(db, ingrediente)
    if not produto:
        return []
    return (
        db.query(models.Receita)
        .filter(models.Receita.itens.any(models.ItemReceita.produto_id == produto.id))
        .all()
    )


def criar_receita(
    db: Session, receita_data: dict, itens_data: List[dict]
) -> tuple[models.Receita, List[dict]]:
    """
    Cria uma nova receita com seus itens.

    Args:
        receita_data: Dados da receita (nome, descricao, etc.)
        itens_data: Lista de dicts com produto_id, quantidade_porcao, observacao

    Returns:
        Tupla (receita, lista de ingredientes pendentes)
    """
    receita = models.Receita(**receita_data)
    db.add(receita)
    db.flush()

    pendentes = []
    for item_data in itens_data:
        produto_id = item_data.get("produto_id")
        observacao = item_data.get("observacao", "")

        if produto_id is None or produto_id == 0:
            pendentes.append(
                {
                    "observacao": observacao,
                    "quantidade": item_data.get("quantidade_porcao"),
                }
            )
            item_data["produto_id"] = 0

        item = models.ItemReceita(receita_id=receita.id, **item_data)
        db.add(item)

    db.commit()
    db.refresh(receita)
    return receita, pendentes


def receita_ingredientes_pendentes(db: Session, receita_id: int) -> List[dict]:
    """Retorna lista de ingredientes sem produto vinculado."""
    receita = get_receita_por_id(db, receita_id)
    if not receita:
        return []

    pendentes = []
    for item in receita.itens:
        if item.produto_id == 0 or item.produto_id is None:
            pendentes.append(
                {
                    "item_id": item.id,
                    "observacao": item.observacao,
                    "quantidade_porcao": item.quantidade_porcao,
                }
            )
    return pendentes


def atualizar_receita(
    db: Session, receita_id: int, receita_data: dict
) -> Optional[models.Receita]:
    """Atualiza dados de uma receita."""
    receita = get_receita_por_id(db, receita_id)
    if not receita:
        return None

    for campo, valor in receita_data.items():
        if valor is not None:
            setattr(receita, campo, valor)

    db.commit()
    db.refresh(receita)
    return receita


def deletar_receita(db: Session, receita_id: int) -> bool:
    """Soft delete - desativa a receita."""
    receita = get_receita_por_id(db, receita_id)
    if not receita:
        return False

    receita.ativa = 0
    db.commit()
    return True


def atualizar_item_receita(
    db: Session,
    item_id: int,
    produto_id: int = None,
    quantidade_porcao: float = None,
    observacao: str = None,
) -> Optional[models.ItemReceita]:
    """Atualiza um item de receita (ingrediente)."""
    item = db.query(models.ItemReceita).filter(models.ItemReceita.id == item_id).first()

    if not item:
        return None

    if produto_id is not None:
        produto = (
            db.query(models.Produto).filter(models.Produto.id == produto_id).first()
        )
        if not produto:
            raise ValueError(f"Produto {produto_id} não encontrado")
        item.produto_id = produto_id

    if quantidade_porcao is not None:
        item.quantidade_porcao = quantidade_porcao

    if observacao is not None:
        item.observacao = observacao

    db.commit()
    db.refresh(item)
    return item


def remover_item_receita(db: Session, item_id: int) -> bool:
    """Remove um item de receita."""
    item = db.query(models.ItemReceita).filter(models.ItemReceita.id == item_id).first()

    if not item:
        return False

    db.delete(item)
    db.commit()
    return True


def receita_pode_ser_feita(
    db: Session, receita: models.Receita
) -> tuple[bool, List[str]]:
    """
    Verifica se uma receita pode ser feita com o estoque atual.

    Returns:
        (pode_fazer, lista de itens faltantes)
    """
    itens_faltantes = []

    for item in receita.itens:
        produto = (
            db.query(models.Produto)
            .filter(models.Produto.id == item.produto_id)
            .first()
        )

        if not produto:
            itens_faltantes.append(f"{item.produto_id} (produto não existe)")
            continue

        if produto.estoque_atual < item.quantidade_porcao:
            itens_faltantes.append(
                f"{produto.nome} (tem {produto.estoque_atual}, precisa {item.quantidade_porcao})"
            )

    pode_fazer = len(itens_faltantes) == 0
    return pode_fazer, itens_faltantes


def sugerir_receitas(db: Session, max_resultados: int = 5) -> List[dict]:
    """
    Sugere receitas que podem ser feitas com o estoque atual.

    Returns:
        Lista de receitas com info de viabilidade.
    """
    receitas = get_todas_receitas(db, ativas=True)
    sugestoes = []

    for receita in receitas:
        pode_fazer, faltantes = receita_pode_ser_feita(db, receita)

        if pode_fazer:
            status = "completa"
        elif len(faltantes) <= len(receita.itens) / 2:
            status = "quase"
        else:
            status = "inviável"

        sugestoes.append(
            {
                "id": receita.id,
                "nome": receita.nome,
                "descricao": receita.descricao,
                "tags": receita.tags,
                "porcoes": receita.porcoes,
                "itens_faltantes": faltantes,
                "status": status,
                "pode_fazer": pode_fazer,
            }
        )

    return sorted(
        sugestoes,
        key=lambda x: (
            0 if x["pode_fazer"] else 1,
            len(x["itens_faltantes"]),
        ),
    )[:max_resultados]
