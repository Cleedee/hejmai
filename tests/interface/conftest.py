"""
Configurações e fixtures compartilhados para os testes.

Este arquivo é carregado automaticamente pelo pytest antes de executar os testes.
"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_api_response():
    """
    Fixture para criar respostas mockadas da API.
    
    Uso:
        def test_algo(mock_api_response):
            mock_api_response.status_code = 200
            mock_api_response.json.return_value = {"chave": "valor"}
    """
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {}
    return mock


@pytest.fixture
def sample_categoria():
    """Fixture com dados de categoria de exemplo."""
    return {"id": 1, "nome": "Mercearia"}


@pytest.fixture
def sample_categorias():
    """Fixture com lista de categorias de exemplo."""
    return [
        {"id": 1, "nome": "Açougue"},
        {"id": 2, "nome": "Laticínios"},
        {"id": 3, "nome": "Hortifruti"},
        {"id": 4, "nome": "Mercearia"},
    ]


@pytest.fixture
def sample_produto():
    """Fixture com dados de produto de exemplo."""
    return {
        "id": 1,
        "nome": "Arroz Integral",
        "categoria": "Mercearia",
        "estoque_atual": 5.0,
        "unidade_medida": "kg",
    }


@pytest.fixture
def sample_alertas():
    """Fixture com alertas de exemplo."""
    return {
        "estoque_baixo": [
            {"id": 1, "nome": "Arroz", "estoque_atual": 0.5},
        ],
        "vencendo_em_breve": [
            {"id": 2, "nome": "Leite", "ultima_validade": "2026-04-10"},
        ],
    }


@pytest.fixture
def sample_historico_precos():
    """Fixture com histórico de preços de exemplo."""
    return [
        {"data": "2026-04-01", "preco": 10.50, "local": "Mercado A"},
        {"data": "2026-03-01", "preco": 9.90, "local": "Mercado B"},
        {"data": "2026-02-01", "preco": 11.00, "local": "Mercado A"},
    ]


@pytest.fixture
def sample_compra_lote():
    """Fixture com dados de compra em lote."""
    return {
        "local_compra": "Mercado Teste",
        "itens": [
            {
                "nome": "Arroz",
                "categoria": "Mercearia",
                "quantidade": 2.0,
                "unidade": "kg",
                "preco_pago": 15.00,
                "data_validade": "2026-12-31",
            },
            {
                "nome": "Feijão",
                "categoria": "Mercearia",
                "quantidade": 1.0,
                "unidade": "kg",
                "preco_pago": 8.00,
                "data_validade": "2026-12-31",
            },
        ],
    }


@pytest.fixture
def sample_df_carga_valid():
    """Fixture com DataFrame válido para carga manual."""
    import pandas as pd
    return pd.DataFrame([
        {
            "nome": "Arroz Integral",
            "categoria": "Mercearia",
            "quantidade": 2.0,
            "unidade": "kg",
            "preco_pago": 15.00,
            "data_validade": "2026-12-31",
        },
        {
            "nome": "Feijão Preto",
            "categoria": "Mercearia",
            "quantidade": 1.0,
            "unidade": "kg",
            "preco_pago": 8.00,
            "data_validade": "2026-12-31",
        },
    ])


@pytest.fixture
def sample_df_carga_invalid():
    """Fixture com DataFrame inválido para carga manual."""
    import pandas as pd
    return pd.DataFrame([
        {
            "nome": "",  # Nome vazio
            "categoria": "Mercearia",
            "quantidade": -1.0,  # Quantidade negativa
            "unidade": "kg",
            "preco_pago": -10.00,  # Preço negativo
            "data_validade": "2026-12-31",
        },
    ])


@pytest.fixture
def api_client():
    """Fixture com instância do APIClient."""
    from hejmai.interface.api_client import APIClient
    return APIClient()


@pytest.fixture
def mock_httpx_request():
    """
    Fixture para mockar httpx.request.
    
    Uso:
        def test_algo(mock_httpx_request):
            mock_httpx_request.return_value.status_code = 200
    """
    with patch('src.interface.api_client.httpx.request') as mock:
        yield mock
