"""
Testes para o endpoint /produtos/unificar.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient

from hejmai import models
from hejmai.database import Base, engine
from hejmai.main import app

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


class TestUnificarProdutos:
    def test_unificar_produtos_sucesso(self, client, setup_produtos):
        """Deve unificar produtos secundários no principal."""
        produtos = setup_produtos
        principal_id = produtos[0]["id"]
        secundarios = [p["id"] for p in produtos[1:]]

        response = client.post(
            "/produtos/unificar",
            json={
                "produto_principal_id": principal_id,
                "produtos_para_unificar": secundarios,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sucesso"
        assert data["produtos_removidos"] == 2

    def test_unificar_lista_vazia(self, client, setup_produtos):
        """Deve recusar lista vazia."""
        principal_id = setup_produtos[0]["id"]

        response = client.post(
            "/produtos/unificar",
            json={
                "produto_principal_id": principal_id,
                "produtos_para_unificar": [],
            },
        )

        assert response.status_code == 400
        assert "Nenhum produto" in response.json()["detail"]

    def test_unificar_principal_na_lista(self, client, setup_produtos):
        """Deve recusar se o principal está na lista."""
        principal_id = setup_produtos[0]["id"]
        secundarios = [p["id"] for p in setup_produtos[1:]]

        response = client.post(
            "/produtos/unificar",
            json={
                "produto_principal_id": principal_id,
                "produtos_para_unificar": secundarios + [principal_id],
            },
        )

        assert response.status_code == 400
        assert "principal não pode estar" in response.json()["detail"]

    def test_unificar_produto_inexistente(self, client, setup_produtos):
        """Deve recusar produto principal inexistente."""
        secundarios = [p["id"] for p in setup_produtos[1:]]

        response = client.post(
            "/produtos/unificar",
            json={
                "produto_principal_id": 99999,
                "produtos_para_unificar": secundarios,
            },
        )

        assert response.status_code == 404

    def test_unificar_produto_nao_encontrado(self, client, setup_produtos):
        """Deve recusar se algum secundário não existe."""
        principal_id = setup_produtos[0]["id"]

        response = client.post(
            "/produtos/unificar",
            json={
                "produto_principal_id": principal_id,
                "produtos_para_unificar": [99999],
            },
        )

        assert response.status_code == 404
        assert "não foram encontrados" in response.json()["detail"]
