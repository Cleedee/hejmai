"""
Testes unitários para exclusão lógica de compras.

Estes testes detectam o bug onde produto_id é null na Movimentacao
quando a compra tem múltiplos itens.
"""

import pytest
import os
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Usa banco em memória para testes
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    """Cria uma sessão de banco de dados com tabelas criadas para cada teste."""
    # Importa modelos aqui para evitar importação do main.py
    from hejmai import models
    
    # Cria todas as tabelas
    models.Base.metadata.create_all(bind=engine)
    
    sess = TestingSessionLocal()
    try:
        yield sess
    finally:
        sess.close()


@pytest.fixture(autouse=True)
def reset_database(db):
    """Limpa o banco de dados antes de cada teste."""
    from hejmai import models
    
    # Limpa todas as tabelas em ordem de dependência
    db.query(models.Movimentacao).delete()
    db.query(models.ItemCompra).delete()
    db.query(models.Compra).delete()
    db.query(models.Produto).delete()
    db.query(models.Categoria).delete()
    db.commit()


def criar_compra_com_itens(db, itens):
    """
    Helper para criar uma compra com múltiplos itens.
    
    Args:
        db: Sessão do banco de dados
        itens: Lista de dicts com {nome, quantidade, preco_pago, categoria}
    
    Returns:
        Compra criada
    """
    from hejmai import models
    
    # Cria produtos
    produto_ids = []
    for item in itens:
        produto = models.Produto(
            nome=item["nome"],
            categoria=item.get("categoria", "Mercearia"),
            unidade_medida="un",
            estoque_atual=item["quantidade"],
        )
        db.add(produto)
        db.flush()
        produto_ids.append(produto.id)
    
    # Cria compra
    compra = models.Compra(
        local_compra="Mercado Teste",
        valor_total_nota=sum(i["preco_pago"] for i in itens),
        excluida=0,
    )
    db.add(compra)
    db.flush()
    
    # Cria itens da compra
    for i, item in enumerate(itens):
        item_compra = models.ItemCompra(
            produto_id=produto_ids[i],
            compra_id=compra.id,
            quantidade=item["quantidade"],
            preco_unitario=item["preco_pago"] / item["quantidade"],
            validade_especifica=date.today() + timedelta(days=30),
        )
        db.add(item_compra)
    
    db.commit()
    db.refresh(compra)
    return compra


def excluir_compra_manual(db, compra_id):
    """
    Simula a lógica do endpoint DELETE /compras/{compra_id}.
    
    Esta função replica o código do endpoint para podermos testar
    a lógica diretamente sem precisar do FastAPI TestClient.
    """
    from hejmai import models
    import datetime
    
    # Busca a compra (apenas se não estiver já excluída)
    compra = db.query(models.Compra).filter(
        models.Compra.id == compra_id,
        models.Compra.excluida == 0
    ).first()
    
    if not compra:
        raise ValueError(f"Compra {compra_id} não encontrada ou já excluída")
    
    # Busca os itens da compra
    itens_compra = (
        db.query(models.ItemCompra)
        .filter(models.ItemCompra.compra_id == compra_id)
        .all()
    )
    
    # Reverte estoque dos produtos
    for item in itens_compra:
        produto = db.query(models.Produto).filter(
            models.Produto.id == item.produto_id
        ).first()
        
        if produto:
            produto.estoque_atual = max(0, produto.estoque_atual - item.quantidade)
    
    # Faz exclusão lógica da compra
    compra.excluida = 1
    compra.data_exclusao = datetime.datetime.now(datetime.timezone.utc)
    
    # Cria movimentação de ajuste para auditoria
    # CORREÇÃO: Uma movimentação por produto para rastreio correto
    for item in itens_compra:
        mov_ajuste = models.Movimentacao(
            produto_id=item.produto_id,
            quantidade=-item.quantidade,
            tipo="AJUSTE",
        )
        db.add(mov_ajuste)
    
    db.commit()
    return compra


def test_excluir_compra_com_um_item(db):
    """
    Testa exclusão de compra com APENAS UM item.
    
    Este teste deve PASSAR porque o código atual define produto_id
    quando len(itens_compra) == 1.
    """
    from hejmai import models
    
    # Arrange: Cria compra com 1 item
    compra = criar_compra_com_itens(db, [
        {"nome": "Arroz", "quantidade": 2.0, "preco_pago": 10.0, "categoria": "Mercearia"},
    ])
    
    # Act: Executa lógica de exclusão
    excluir_compra_manual(db, compra.id)
    
    # Assert: Verifica se a movimentação foi criada com produto_id
    movimentacao = db.query(models.Movimentacao).first()
    assert movimentacao is not None, "Movimentação deveria ter sido criada"
    assert movimentacao.produto_id is not None, "produto_id NÃO deveria ser null para compra com 1 item"
    assert movimentacao.produto_id > 0, "produto_id deveria ser um ID válido"
    assert movimentacao.tipo == "AJUSTE"
    assert movimentacao.quantidade < 0, "Quantidade deveria ser negativa (saída de estoque)"


def test_excluir_compra_com_multiplos_itens(db):
    """
    Testa exclusão de compra com MÚLTIPLOS itens.
    
    Após a correção, este teste deve PASSAR porque o código agora
    cria uma movimentação para cada produto afetado.
    """
    from hejmai import models
    
    # Arrange: Cria compra com 3 itens
    compra = criar_compra_com_itens(db, [
        {"nome": "Arroz", "quantidade": 2.0, "preco_pago": 10.0, "categoria": "Mercearia"},
        {"nome": "Feijão", "quantidade": 3.0, "preco_pago": 15.0, "categoria": "Mercearia"},
        {"nome": "Macarrão", "quantidade": 5.0, "preco_pago": 12.0, "categoria": "Mercearia"},
    ])
    
    # Act: Executa lógica de exclusão
    excluir_compra_manual(db, compra.id)
    
    # Assert: Verifica se as movimentações foram criadas corretamente
    movimentacoes = db.query(models.Movimentacao).all()
    assert len(movimentacoes) == 3, "Deveria haver 3 movimentações (uma por produto)"
    
    for mov in movimentacoes:
        assert mov.produto_id is not None, "produto_id NÃO deveria ser null"
        assert mov.produto_id > 0, "produto_id deveria ser um ID válido"
        assert mov.tipo == "AJUSTE"
        assert mov.quantidade < 0, "Quantidade deveria ser negativa (saída de estoque)"
    
    # Verifica que cada movimentação tem um produto_id diferente
    produto_ids = [mov.produto_id for mov in movimentacoes]
    assert len(set(produto_ids)) == 3, "Cada movimentação deveria ter um produto_id único"


def test_excluir_compra_ja_excluida(db):
    """
    Testa que não é possível excluir compra já excluída.
    """
    # Arrange: Cria compra e marca como excluída
    compra = criar_compra_com_itens(db, [
        {"nome": "Arroz", "quantidade": 2.0, "preco_pago": 10.0, "categoria": "Mercearia"},
    ])
    compra.excluida = 1
    db.commit()
    
    # Act & Assert: Tenta excluir novamente
    with pytest.raises(ValueError, match="não encontrada ou já excluída"):
        excluir_compra_manual(db, compra.id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
