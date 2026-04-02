"""
Testes unitários para a interface Streamlit do Hejmai.

Estes testes cobrem:
- api_client: Cliente HTTP com tratamento de erros
- validators: Validações de dados
- components: Componentes renderizáveis (testes básicos)
- config: Configurações centralizadas

Executar:
    uv run pytest tests/interface/ -v

Executar com coverage:
    uv run pytest tests/interface/ --cov=src/interface --cov-report=term-missing
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
import httpx

from src.interface.config import Config, config
from src.interface.api_client import (
    APIClient,
    APIError,
    ConnectionError,
    NotFoundError,
    ServerError,
    BadRequestError,
    UnauthorizedError,
)
from src.interface.utils.validators import (
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
        from src.interface.config import config as config2
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
        with pytest.raises(Exception):  # dataclass frozen levanta exception
            config.API_URL = "http://teste.com"
    
    def test_config_custom_values(self):
        """Testa criação de Config com valores customizados."""
        custom_config = Config(
            API_URL="http://custom:9000",
            API_TIMEOUT=60,
        )
        assert custom_config.API_URL == "http://custom:9000"
        assert custom_config.API_TIMEOUT == 60
        # Valores não especificados usam default
        assert custom_config.NLP_TIMEOUT == 60


# =============================================================================
# Testes de Exceções
# =============================================================================

class TestExceptions:
    """Testes para hierarquia de exceções."""
    
    def test_api_error_is_exception(self):
        """Testa se APIError herda de Exception."""
        assert issubclass(APIError, Exception)
    
    def test_connection_error_is_api_error(self):
        """Testa hierarquia de ConnectionError."""
        assert issubclass(ConnectionError, APIError)
    
    def test_not_found_error_is_api_error(self):
        """Testa hierarquia de NotFoundError."""
        assert issubclass(NotFoundError, APIError)
    
    def test_server_error_is_api_error(self):
        """Testa hierarquia de ServerError."""
        assert issubclass(ServerError, APIError)
    
    def test_bad_request_error_is_api_error(self):
        """Testa hierarquia de BadRequestError."""
        assert issubclass(BadRequestError, APIError)
    
    def test_unauthorized_error_is_api_error(self):
        """Testa hierarquia de UnauthorizedError."""
        assert issubclass(UnauthorizedError, APIError)
    
    def test_raise_and_catch_api_error(self):
        """Testa levantar e capturar exceções."""
        with pytest.raises(APIError):
            raise ServerError("Erro no servidor")
        
        with pytest.raises(ConnectionError):
            raise ConnectionError("Falha de conexão")


# =============================================================================
# Testes do APIClient
# =============================================================================

class TestAPIClient:
    """Testes para o cliente HTTP."""
    
    def test_api_client_init_default(self):
        """Testa inicialização padrão do APIClient."""
        api = APIClient()
        assert api.base_url == config.API_URL.rstrip('/')
        assert api.timeout == config.API_TIMEOUT
    
    def test_api_client_init_custom(self):
        """Testa inicialização com parâmetros customizados."""
        api = APIClient(base_url="http://teste:9000", timeout=120)
        assert api.base_url == "http://teste:9000"
        assert api.timeout == 120
    
    def test_api_client_init_strips_trailing_slash(self):
        """Testa que URL base remove slash final."""
        api = APIClient(base_url="http://teste:9000/")
        assert api.base_url == "http://teste:9000"
    
    @patch('src.interface.api_client.httpx.request')
    def test_health_check_success(self, mock_request):
        """Testa health check bem-sucedido."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "Agente Online"}
        mock_request.return_value = mock_response
        
        api = APIClient()
        result = api.health_check()
        
        assert result == {"status": "Agente Online"}
        mock_request.assert_called_once_with(
            method="GET",
            url=f"{api.base_url}/",
            timeout=api.timeout,
        )
    
    @patch('src.interface.api_client.httpx.request')
    def test_get_categorias_success(self, mock_request):
        """Testa busca de categorias bem-sucedida."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": 1, "nome": "Açougue"},
            {"id": 2, "nome": "Laticínios"},
        ]
        mock_request.return_value = mock_response
        
        api = APIClient()
        result = api.get_categorias()
        
        assert result == ["Açougue", "Laticínios"]
    
    @patch('src.interface.api_client.httpx.request')
    def test_get_categorias_empty(self, mock_request):
        """Testa busca de categorias quando lista está vazia."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_request.return_value = mock_response
        
        api = APIClient()
        result = api.get_categorias()
        
        assert result == []
    
    @patch('src.interface.api_client.httpx.request')
    def test_get_produtos_alertas(self, mock_request):
        """Testa busca de alertas de produtos."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "estoque_baixo": [{"id": 1, "nome": "Arroz"}],
            "vencendo_em_breve": [{"id": 2, "nome": "Leite"}],
        }
        mock_request.return_value = mock_response
        
        api = APIClient()
        result = api.get_produtos_alertas()
        
        assert "estoque_baixo" in result
        assert "vencendo_em_breve" in result
        assert len(result["estoque_baixo"]) == 1
    
    def test_post_compra_lote(self):
        """Testa registro de compra em lote."""
        api = APIClient(base_url="http://teste:9000", timeout=30)
        dados = {
            "local_compra": "Mercado Teste",
            "itens": [{"nome": "Arroz", "quantidade": 2}],
        }
        
        # Mock do método _request_with_retry para evitar problemas com timeout
        with patch.object(api, '_request_with_retry') as mock_retry:
            mock_retry.return_value = MagicMock(
                status_code=201,
                json=MagicMock(return_value={"message": "Compra registrada!", "itens": 5})
            )
            
            result = api.post_compra_lote(dados)
            
            assert result["itens"] == 5
            mock_retry.assert_called_once()
    
    def test_server_error(self):
        """Testa que ServerError é levantado para HTTP 5xx."""
        api = APIClient(base_url="http://teste:9000", timeout=30)
        
        with patch.object(api, '_request_with_retry') as mock_retry:
            mock_retry.return_value = MagicMock(
                status_code=500,
                text="Internal Server Error"
            )
            
            with pytest.raises(ServerError) as exc_info:
                api.health_check()
            
            assert "500" in str(exc_info.value)
    
    def test_bad_request_error(self):
        """Testa que BadRequestError é levantado para HTTP 400."""
        api = APIClient(base_url="http://teste:9000", timeout=30)
        dados = {"dados": "inválidos"}
        
        with patch.object(api, '_request_with_retry') as mock_retry:
            mock_retry.return_value = MagicMock(
                status_code=400,
                json=MagicMock(return_value={"error": "Bad request"})
            )
            
            with pytest.raises(BadRequestError):
                api.post_compra_lote(dados)


# =============================================================================
# Testes de Validadores
# =============================================================================

class TestValidators:
    """Testes para funções de validação."""
    
    def test_validate_carga_manual_empty_dataframe(self):
        """Testa validação de DataFrame vazio."""
        df = pd.DataFrame()
        erros = validate_carga_manual(df)
        
        assert len(erros) > 0
        assert "pelo menos um item" in erros[0].lower()
    
    def test_validate_carga_manual_nome_obrigatorio(self):
        """Testa que nome é obrigatório."""
        df = pd.DataFrame([{"nome": "", "quantidade": 1, "preco_pago": 10}])
        erros = validate_carga_manual(df)
        
        assert any("nome" in erro.lower() for erro in erros)
    
    def test_validate_carga_manual_quantidade_positiva(self):
        """Testa que quantidade deve ser positiva."""
        df = pd.DataFrame([
            {"nome": "Arroz", "quantidade": -1, "preco_pago": 10, "categoria": "Mercearia"}
        ])
        erros = validate_carga_manual(df)
        
        assert any("quantidade" in erro.lower() for erro in erros)
    
    def test_validate_carga_manual_preco_nao_negativo(self):
        """Testa que preço não pode ser negativo."""
        df = pd.DataFrame([
            {"nome": "Arroz", "quantidade": 1, "preco_pago": -10, "categoria": "Mercearia"}
        ])
        erros = validate_carga_manual(df)
        
        assert any("preço" in erro.lower() or "preco" in erro.lower() for erro in erros)
    
    def test_validate_carga_manual_valid_data(self):
        """Testa dados válidos."""
        df = pd.DataFrame([
            {
                "nome": "Arroz Integral",
                "quantidade": 2.0,
                "preco_pago": 15.00,
                "categoria": "Mercearia",
                "unidade": "kg",
            }
        ])
        erros = validate_carga_manual(df)
        
        assert len(erros) == 0
    
    def test_validate_carga_manual_quantidade_muito_alta(self):
        """Testa alerta para quantidade muito alta."""
        df = pd.DataFrame([
            {"nome": "Arroz", "quantidade": 150, "preco_pago": 10, "categoria": "Mercearia"}
        ])
        erros = validate_carga_manual(df)
        
        assert any("100" in erro for erro in erros)
    
    def test_validate_carga_manual_preco_muito_alto(self):
        """Testa alerta para preço muito alto."""
        df = pd.DataFrame([
            {"nome": "Arroz", "quantidade": 1, "preco_pago": 1500, "categoria": "Mercearia"}
        ])
        erros = validate_carga_manual(df)
        
        assert any("1000" in erro for erro in erros)
    
    def test_validate_produto_individual_valid(self):
        """Testa validação de produto individual válido."""
        erros = validate_produto_individual("Arroz", 2.0, 15.00)
        assert len(erros) == 0
    
    def test_validate_produto_individual_nome_vazio(self):
        """Testa validação com nome vazio."""
        erros = validate_produto_individual("", 2.0, 15.00)
        assert len(erros) > 0
        assert any("nome" in erro.lower() for erro in erros)
    
    def test_validate_produto_individual_quantidade_invalida(self):
        """Testa validação com quantidade inválida."""
        erros = validate_produto_individual("Arroz", 0, 15.00)
        assert len(erros) > 0
        assert any("quantidade" in erro.lower() for erro in erros)
    
    def test_validate_produto_individual_preco_negativo(self):
        """Testa validação com preço negativo."""
        erros = validate_produto_individual("Arroz", 2.0, -10.00)
        assert len(erros) > 0
        assert any("preço" in erro.lower() or "preco" in erro.lower() for erro in erros)
    
    def test_validate_carga_manual_multiple_errors(self):
        """Testa múltiplos erros de uma vez."""
        df = pd.DataFrame([
            {"nome": "", "quantidade": -5, "preco_pago": -100, "categoria": "Invalida"}
        ])
        erros = validate_carga_manual(df)
        
        # Deve ter pelo menos 3 erros
        assert len(erros) >= 3


# =============================================================================
# Testes de Integração (com API real se disponível)
# =============================================================================

class TestAPIClientIntegration:
    """Testes de integração com API real (opcionais)."""
    
    @pytest.mark.integration
    def test_api_client_health_check_real(self):
        """Testa health check com API real (se disponível)."""
        api = APIClient()
        
        try:
            result = api.health_check()
            assert "status" in result
        except ConnectionError:
            pytest.skip("API não disponível para testes de integração")
    
    @pytest.mark.integration
    def test_api_client_get_categorias_real(self):
        """Testa busca de categorias com API real."""
        api = APIClient()
        
        try:
            categorias = api.get_categorias()
            assert isinstance(categorias, list)
        except ConnectionError:
            pytest.skip("API não disponível para testes de integração")


# =============================================================================
# Configuração do pytest
# =============================================================================

def pytest_configure(config):
    """Registra markers customizados."""
    config.addinivalue_line(
        "markers", "integration: mark test as requiring real API connection"
    )
