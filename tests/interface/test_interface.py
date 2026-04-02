"""
Testes unitários para a interface Streamlit do Hejmai.

Executar:
    uv run pytest tests/interface/ -v

Executar com coverage:
    uv run pytest tests/interface/ --cov=src/interface
"""

# Adiciona 'src' ao PYTHONPATH antes de qualquer import
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
import httpx

from hejmai.interface.config import Config, config
from hejmai.interface.api_client import (
    APIClient,
    APIError,
    ConnectionError,
    NotFoundError,
    ServerError,
    BadRequestError,
    UnauthorizedError,
)
from hejmai.interface.utils.validators import (
    validate_carga_manual,
    validate_produto_individual,
)


# =============================================================================
# Testes de Configuração
# =============================================================================

class TestConfig:
    """Testes para a classe Config."""
    
    def test_config_singleton(self):
        """Testa se config é uma instância singleton."""
        from hejmai.interface.config import config as config2
        assert config is config2
    
    def test_config_default_values(self):
        """Testa valores padrão da configuração."""
        assert config.API_URL is not None
        assert config.API_TIMEOUT == 30
        assert config.NLP_TIMEOUT == 60
        assert config.ORCAMENTO_LIMITE_PADRAO == 500.00
        assert config.CACHE_TTL_SEGUNDOS == 300
        assert config.MAX_RETRY_TENTATIVAS == 3
    
    def test_config_immutable(self):
        """Testa se Config é imutável (frozen)."""
        with pytest.raises(Exception):
            config.API_URL = "http://teste.com"
    
    def test_config_custom_values(self):
        """Testa criação de Config com valores customizados."""
        custom_config = Config(
            API_URL="http://custom:9000",
            API_TIMEOUT=60,
        )
        assert custom_config.API_URL == "http://custom:9000"
        assert custom_config.API_TIMEOUT == 60


# =============================================================================
# Testes de Exceções
# =============================================================================

class TestExceptions:
    """Testes para hierarquia de exceções."""
    
    def test_api_error_is_exception(self):
        assert issubclass(APIError, Exception)
    
    def test_connection_error_is_api_error(self):
        assert issubclass(ConnectionError, APIError)
    
    def test_not_found_error_is_api_error(self):
        assert issubclass(NotFoundError, APIError)
    
    def test_server_error_is_api_error(self):
        assert issubclass(ServerError, APIError)
    
    def test_bad_request_error_is_api_error(self):
        assert issubclass(BadRequestError, APIError)
    
    def test_unauthorized_error_is_api_error(self):
        assert issubclass(UnauthorizedError, APIError)
    
    def test_raise_and_catch_api_error(self):
        with pytest.raises(APIError):
            raise ServerError("Erro no servidor")


# =============================================================================
# Testes do APIClient
# =============================================================================

class TestAPIClient:
    """Testes para o cliente HTTP."""
    
    def test_api_client_init_default(self):
        api = APIClient()
        assert api.base_url == config.API_URL.rstrip('/')
        assert api.timeout == config.API_TIMEOUT
    
    def test_api_client_init_custom(self):
        api = APIClient(base_url="http://teste:9000", timeout=120)
        assert api.base_url == "http://teste:9000"
        assert api.timeout == 120
    
    def test_post_compra_lote_timeout_override(self):
        """Testa que post_compra_lote usa timeout customizado sem erro."""
        api = APIClient(base_url="http://teste:9000", timeout=30)
        dados = {"local_compra": "Teste", "itens": []}
        
        with patch.object(api, '_request_with_retry') as mock_retry:
            mock_retry.return_value = MagicMock(status_code=201)
            api.post_compra_lote(dados)
            
            # Verifica que o timeout foi sobrescrito
            call_kwargs = mock_retry.call_args.kwargs
            assert 'timeout' in call_kwargs


# =============================================================================
# Testes de Validadores
# =============================================================================

class TestValidators:
    """Testes para funções de validação."""
    
    def test_validate_carga_manual_valid_data(self):
        df = pd.DataFrame([{
            "nome": "Arroz",
            "quantidade": 2.0,
            "preco_pago": 15.00,
            "categoria": "Mercearia",
        }])
        erros = validate_carga_manual(df)
        assert len(erros) == 0
    
    def test_validate_carga_manual_empty_dataframe(self):
        df = pd.DataFrame()
        erros = validate_carga_manual(df)
        assert len(erros) > 0
    
    def test_validate_carga_manual_nome_obrigatorio(self):
        df = pd.DataFrame([{"nome": "", "quantidade": 1, "preco_pago": 10}])
        erros = validate_carga_manual(df)
        assert any("nome" in erro.lower() for erro in erros)
    
    def test_validate_carga_manual_quantidade_positiva(self):
        df = pd.DataFrame([{
            "nome": "Arroz",
            "quantidade": -1,
            "preco_pago": 10,
            "categoria": "Mercearia"
        }])
        erros = validate_carga_manual(df)
        assert any("quantidade" in erro.lower() for erro in erros)
    
    def test_validate_carga_manual_preco_nao_negativo(self):
        df = pd.DataFrame([{
            "nome": "Arroz",
            "quantidade": 1,
            "preco_pago": -10,
            "categoria": "Mercearia"
        }])
        erros = validate_carga_manual(df)
        assert any("preço" in erro.lower() or "preco" in erro.lower() for erro in erros)
