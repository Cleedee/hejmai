"""
Testes unitários para o endpoint de edição de compras (PUT /compras/{compra_id}).

Testa a lógica do endpoint diretamente com banco em memória.

Executar:
    uv run pytest tests/test_editar_compra.py -v
"""

import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from datetime import date, timedelta
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hejmai import models, database, schemas
from hejmai.main import editar_compra

# =============================================================================
# Banco de Testes
# =============================================================================

test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

database.engine = test_engine
database.SessionLocal = TestingSessionLocal
models.Base.metadata.create_all(bind=test_engine)


@pytest.fixture
def db():
    s = TestingSessionLocal()
    try:
        yield s
    finally:
        s.close()


# =============================================================================
# Helper
# =============================================================================

def criar_compra(db, local="Mercado Teste", data=None, valor=50.0):
    import uuid
    if data is None:
        data = date.today()
    produto = models.Produto(
        nome=f"Produto_{uuid.uuid4().hex[:8]}",
        categoria="Mercearia",
        unidade_medida="un",
        estoque_atual=1.0,
    )
    db.add(produto)
    db.flush()
    compra = models.Compra(
        local_compra=local,
        data_compra=data,
        valor_total_nota=valor,
        excluida=0,
    )
    db.add(compra)
    db.flush()
    db.commit()
    db.refresh(compra)
    return compra


# =============================================================================
# Testes
# =============================================================================

class TestEditarCompra:
    """Testes da função editar_compra."""
    
    @pytest.mark.asyncio
    async def test_editar_local_compra(self, db):
        compra = criar_compra(db, local="Mercado A")
        update = schemas.CompraUpdate(local_compra="Mercado B")
        resultado = await editar_compra(compra.id, update, db)
        
        assert resultado["status"] == "sucesso"
        assert resultado["compra"]["local_compra"] == "Mercado B"
        db.refresh(compra)
        assert compra.local_compra == "Mercado B"
    
    @pytest.mark.asyncio
    async def test_editar_data_compra(self, db):
        data_antiga = date.today() - timedelta(days=5)
        compra = criar_compra(db, data=data_antiga)
        nova_data = date.today()
        update = schemas.CompraUpdate(data_compra=nova_data)
        resultado = await editar_compra(compra.id, update, db)
        
        assert resultado["compra"]["data_compra"] == nova_data
    
    @pytest.mark.asyncio
    async def test_editar_local_e_data(self, db):
        compra = criar_compra(db, local="Velho", data=date.today() - timedelta(days=10))
        update = schemas.CompraUpdate(local_compra="Novo", data_compra=date.today())
        resultado = await editar_compra(compra.id, update, db)
        
        d = resultado["compra"]
        assert d["local_compra"] == "Novo"
        assert d["data_compra"] == date.today()
    
    @pytest.mark.asyncio
    async def test_editar_compra_inexistente(self, db):
        update = schemas.CompraUpdate(local_compra="Teste")
        with pytest.raises(HTTPException) as exc_info:
            await editar_compra(9999, update, db)
        assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_editar_sem_dados(self, db):
        compra = criar_compra(db)
        update = schemas.CompraUpdate()
        with pytest.raises(HTTPException) as exc_info:
            await editar_compra(compra.id, update, db)
        assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_editar_preserva_valor_total(self, db):
        compra = criar_compra(db, valor=99.99)
        update = schemas.CompraUpdate(local_compra="Novo")
        resultado = await editar_compra(compra.id, update, db)
        assert resultado["compra"]["valor_total_nota"] == 99.99
    
    @pytest.mark.asyncio
    async def test_editar_resposta_completa(self, db):
        compra = criar_compra(db, local="Original")
        update = schemas.CompraUpdate(local_compra="Atualizado")
        resultado = await editar_compra(compra.id, update, db)
        
        assert resultado["status"] == "sucesso"
        assert "mensagem" in resultado
        assert "compra" in resultado
        assert resultado["compra"]["local_compra"] == "Atualizado"
        assert resultado["compra"]["id"] == compra.id
